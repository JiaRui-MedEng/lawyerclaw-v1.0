"""
百佑 LawyerClaw 记忆管理模块
基于 SQLAlchemy + SQLite
"""
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

from service.models.database import db, Memory

logger = logging.getLogger(__name__)


class MemoryManager:
    """记忆管理器 - 百佑 LawyerClaw 集成版"""
    
    def __init__(self):
        pass
    
    def add(self, target: str, content: str, session_id: str = None) -> Dict[str, Any]:
        """添加记忆"""
        if target not in ['memory', 'user']:
            return {'success': False, 'error': 'Invalid target'}
        
        memory = Memory(
            target=target,
            content=content,
            session_id=session_id
        )
        
        db.session.add(memory)
        db.session.commit()
        
        logger.info(f"记忆已添加：{target}, id={memory.id}")
        
        return {
            'success': True,
            'action': 'add',
            'target': target,
            'id': memory.id,
            'timestamp': memory.created_at.isoformat()
        }
    
    def replace(self, memory_id: int, new_content: str) -> Dict[str, Any]:
        """替换记忆"""
        memory = Memory.query.get(memory_id)
        if not memory:
            return {'success': False, 'error': 'Memory not found'}
        
        memory.content = new_content
        memory.updated_at = datetime.now()
        db.session.commit()
        
        logger.info(f"记忆已替换：id={memory_id}")
        
        return {'success': True, 'action': 'replace', 'id': memory_id}
    
    def remove(self, memory_id: int) -> Dict[str, Any]:
        """删除记忆"""
        memory = Memory.query.get(memory_id)
        if not memory:
            return {'success': False, 'error': 'Memory not found'}
        
        db.session.delete(memory)
        db.session.commit()
        
        logger.info(f"记忆已删除：id={memory_id}")
        
        return {'success': True, 'action': 'remove', 'id': memory_id}
    
    def prefetch(self, target: str = None, limit: int = 50) -> str:
        """预取记忆 (注入到对话)"""
        query = Memory.query
        
        if target:
            query = query.filter_by(target=target)
        
        query = query.order_by(Memory.created_at.desc()).limit(limit)
        memories = query.all()
        
        if not memories:
            return ""
        
        # 构建记忆上下文
        context_parts = []
        
        # 按 target 分组
        memory_target = [m for m in memories if m.target == 'memory']
        user_target = [m for m in memories if m.target == 'user']
        
        if memory_target:
            content = "\n".join([f"- {m.content}" for m in memory_target[-20:]])
            context_parts.append(f"## Long-term Memory\n{content}")
        
        if user_target:
            content = "\n".join([f"- {m.content}" for m in user_target[-20:]])
            context_parts.append(f"## User Profile\n{content}")
        
        return "\n\n".join(context_parts)
    
    def sync(self, user_msg: str, assistant_msg: str, session_id: str = None) -> None:
        """同步对话后处理 (自动检测学习机会)"""
        # 检测用户是否要求记忆
        memory_phrases = ['记住这个', 'remember this', '下次不要', "don't do that"]
        
        if any(phrase in user_msg.lower() for phrase in memory_phrases):
            self.add(
                target="memory",
                content=f"用户要求：{user_msg[:200]}\n\n助手响应：{assistant_msg[:200]}",
                session_id=session_id
            )
    
    def get_tool_schema(self) -> Dict[str, Any]:
        """获取 memory 工具 schema"""
        return {
            "name": "memory",
            "description": "Save durable information to persistent memory",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["add", "replace", "remove"],
                        "description": "Action to perform"
                    },
                    "target": {
                        "type": "string",
                        "enum": ["memory", "user"],
                        "description": "Memory store target"
                    },
                    "content": {
                        "type": "string",
                        "description": "Entry content (for add)"
                    },
                    "memory_id": {
                        "type": "integer",
                        "description": "Memory ID (for replace/remove)"
                    }
                },
                "required": ["action", "target"]
            }
        }
    
    def handle_tool_call(self, args: Dict[str, Any]) -> str:
        """处理 memory 工具调用"""
        action = args.get('action')
        target = args.get('target')
        content = args.get('content', '')
        memory_id = args.get('memory_id')
        
        if action == 'add':
            result = self.add(target, content)
        elif action == 'replace':
            result = self.replace(memory_id, content)
        elif action == 'remove':
            result = self.remove(memory_id)
        else:
            result = {"success": False, "error": f"Unknown action: {action}"}
        
        return json.dumps(result, ensure_ascii=False)
    
    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """搜索记忆"""
        memories = Memory.query.filter(
            Memory.content.like(f'%{query}%')
        ).order_by(Memory.created_at.desc()).limit(limit).all()
        
        return [m.to_dict() for m in memories]
