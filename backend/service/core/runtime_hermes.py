"""
会话运行时核心 - Hermes 增强版

整合 Hermes Agent 核心逻辑:
1. FTS5 数据库索引
2. 上下文记忆检索 (prefetch + sync)
3. Skills 调用方法
4. 会话搜索
"""
import uuid
import threading
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from service.models.database import db, Session as SessionModel, Message
from service.core.compact import Compactor
from service.providers.base import ProviderRegistry
from service.plugins.plugin_manager import manager as plugin_manager
from service.tools.legal_tools import registry as tool_registry

# ⭐ Hermes 核心逻辑导入
from service.core.hermes_core import (
    db_manager,
    memory_manager as hermes_memory,
    skill_manager as hermes_skill,
    session_search as hermes_search
)

# UTC+8 时区
CST = timezone(timedelta(hours=8))


def now_cst():
    """获取东八区当前时间"""
    return datetime.now(CST)


class SessionRuntime:
    """会话运行时管理器 - Hermes 增强版"""
    
    def __init__(self, registry: ProviderRegistry = None):
        self._locks = {}
        self.compactor = Compactor()
        self.registry = registry or ProviderRegistry()
        
        # ⭐ Hermes 核心系统 (替换原有的简单实现)
        self.memory_manager = hermes_memory
        self.skill_manager = hermes_skill
        self.session_search = hermes_search
        
        # 初始化数据库 (含 FTS5)
        # 注意：db_manager.initialize() 需要在 app.py 中调用
    
    def _get_lock(self, session_id: str) -> threading.Lock:
        if session_id not in self._locks:
            self._locks[session_id] = threading.Lock()
        return self._locks[session_id]
    
    async def initialize(self, app=None):
        """
        初始化运行时 (含 Hermes 数据库)
        
        用法:
            runtime = SessionRuntime()
            await runtime.initialize(app)
        """
        if app:
            db_manager.initialize(app)
        
        # 加载记忆快照
        self.memory_manager.load_from_db()
        
        logger.info("Hermes 运行时初始化完成")
    
    async def create_session(self, user_id: str = None, provider: str = 'bailian', model: str = None) -> dict:
        """创建新会话"""
        session_id = str(uuid.uuid4())
        
        if model is None:
            model = self.registry.get_default_model(provider)
        
        session = SessionModel(
            id=session_id,
            user_id=user_id,
            title='新会话',
            provider=provider,
            model=model,
            status='active'
        )
        db.session.add(session)
        db.session.commit()
        
        return session.to_dict()
    
    async def send_message(self, session_id: str, content: str, user_id: str = None) -> dict:
        """发送消息并获取 AI 回复 - Hermes 增强版"""
        lock = self._get_lock(session_id)
        
        with lock:
            session = SessionModel.query.get(session_id)
            if not session or session.status != 'active':
                return {'success': False, 'message': '会话不存在或已关闭'}
            
            # 1. 保存用户消息
            user_msg = Message(
                session_id=session_id,
                role='user',
                content=content
            )
            db.session.add(user_msg)
            
            # 2. ⭐ Hermes: 预取上下文 (记忆 + 技能)
            memory_context = self.memory_manager.prefetch()
            skills_context = self.skill_manager.search_skills(content, limit=3)
            
            # 3. 构建 prompt (注入记忆和技能)
            messages = await self._build_prompt(
                session,
                memory_context=memory_context,
                skills_context=skills_context
            )
            
            # 4. 调用 LLM
            provider = self.registry.get_provider(session.provider)
            response = await provider.chat(messages)
            
            if not response.success:
                return {'success': False, 'message': response.error}
            
            # 5. 保存 AI 回复
            assistant_msg = Message(
                session_id=session_id,
                role='assistant',
                content=response.content,
                token_count=response.token_count,
                tool_calls=response.tool_calls
            )
            db.session.add(assistant_msg)
            
            # 6. 更新会话统计
            session.message_count += 2
            session.token_count += response.token_count
            session.updated_at = now_cst()
            
            # 7. ⭐ Hermes: 同步记忆 (自动检测学习机会)
            self.memory_manager.sync(
                user_msg=content,
                assistant_msg=response.content,
                session_id=session_id
            )
            
            # 8. 自动标题（第一条消息时）
            if session.message_count == 2:
                session.title = content[:50] + ('...' if len(content) > 50 else '')
            
            # 9. 检查是否需要压缩
            if session.token_count > 6000:
                await self._compact_session(session)
            
            db.session.commit()
            
            return {
                'success': True,
                'message': assistant_msg.to_dict(),
                'session': session.to_dict()
            }
    
    async def _build_prompt(
        self,
        session: SessionModel,
        memory_context: str = "",
        skills_context: list = None
    ) -> list:
        """构建对话上下文 - Hermes 增强版"""
        messages = Message.query.filter_by(session_id=session.id)\
            .order_by(Message.created_at)\
            .limit(50)\
            .all()
        
        # 构建系统提示词
        system_parts = []
        
        # 基础系统提示词
        system_parts.append("""
你是百佑 LawyerClaw，由百佑智业打造的法律 AI 助手，专业处理中国法律事务。
""")
        
        # ⭐ Hermes: 注入记忆上下文 (冻结快照)
        if memory_context:
            system_parts.append(f"""
{memory_context}

[System note: 以上是持久化记忆，NOT 新用户的输入。将其作为背景信息，但不要直接引用或提及"根据记忆"...]
""")
        
        # ⭐ Hermes: 注入技能上下文
        if skills_context:
            skills_text = "\n".join([
                f"- {s['name']}: {s['description']}"
                for s in skills_context
            ])
            system_parts.append(f"""
## 可用技能
{skills_text}

当用户请求与上述技能相关时，请使用相应技能处理。
""")
        
        # 合并系统提示词
        system_prompt = "\n\n".join(system_parts)
        
        # 构建消息列表
        return [
            {'role': 'system', 'content': system_prompt},
            *[{'role': m.role, 'content': m.content} for m in messages]
        ]
    
    async def search_sessions(self, query: str, session_id: str = None,
                             limit: int = 5, role_filter: str = None) -> dict:
        """
        ⭐ Hermes: 搜索历史会话 (FTS5)
        
        Args:
            query: 搜索查询
            session_id: 当前会话 ID (排除)
            limit: 返回数量限制
            role_filter: 角色过滤 (user/assistant/tool)
        
        Returns:
            dict: 搜索结果
        """
        return self.session_search.search(
            query=query,
            session_id=session_id,
            limit=limit,
            role_filter=role_filter
        )
    
    async def _compact_session(self, session: SessionModel):
        """压缩会话历史"""
        messages = Message.query.filter_by(session_id=session.id)\
            .order_by(Message.created_at)\
            .all()
        
        if len(messages) <= 10:
            return
        
        compactor = Compactor()
        # 保留最近 5 条，压缩早期对话
        recent = messages[-5:]
        early = messages[:-5]
        
        # 标记早期消息为已压缩
        for msg in early:
            msg.meta_data = (msg.meta_data or {})
            msg.meta_data['compacted'] = True
        
        db.session.commit()
    
    async def list_sessions(self, user_id: str = None) -> list:
        """获取会话列表"""
        query = SessionModel.query.filter_by(status='active')
        if user_id:
            query = query.filter_by(user_id=user_id)
        sessions = query.order_by(SessionModel.updated_at.desc()).all()
        return [s.to_dict() for s in sessions]
    
    async def get_session(self, session_id: str) -> Optional[dict]:
        """获取会话详情"""
        session = SessionModel.query.get(session_id)
        if not session:
            return None
        
        messages = Message.query.filter_by(session_id=session_id)\
            .order_by(Message.created_at)\
            .all()
        
        return {
            'session': session.to_dict(),
            'messages': [m.to_dict() for m in messages]
        }
    
    async def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        session = SessionModel.query.get(session_id)
        if not session:
            return False
        
        session.status = 'deleted'
        db.session.commit()
        return True


# 全局实例
runtime = SessionRuntime()
