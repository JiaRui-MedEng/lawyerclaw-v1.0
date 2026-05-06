"""
会话运行时核心
替代 Rust crates/runtime 的 Python 实现
"""
import uuid
import json
import threading
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from service.models.database import db
from service.models.database import Session as SessionModel, Message
from service.core.compact import Compactor
from service.providers.base import ProviderRegistry
from service.plugins.plugin_manager import manager as plugin_manager
from service.tools.legal_tools import registry as tool_registry

# ⭐ 自我进化系统导入 (Hermes 增强版：安全扫描 + FTS5)
from service.core.hermes_core import memory_manager as hermes_memory
from service.self_evolution.skills import SkillManager

# ⭐ 问题分类器导入
from service.core.question_classifier import classifier as question_classifier

logger = logging.getLogger(__name__)

# UTC+8 时区
CST = timezone(timedelta(hours=8))


def now_cst():
    """获取东八区当前时间"""
    return datetime.now(CST)


class SessionRuntime:
    """会话运行时管理器"""

    def __init__(self, registry: ProviderRegistry = None):
        self._locks = {}
        self.compactor = Compactor()
        self.registry = registry or ProviderRegistry()

        # ⭐ 自我进化系统初始化 (Hermes 增强版)
        self.memory_manager = hermes_memory
        self.skill_manager = SkillManager()

        # ⭐ RAG 触发关键词
        self.rag_keywords = [
            '法律', '法规', '法条', '条例', '规定', '办法', '司法解释',
            '民法典', '劳动法', '刑法', '行政法', '合同法', '公司法',
            '诉讼', '仲裁', '判决', '裁定', '案例'
        ]

    def _get_lock(self, session_id: str) -> threading.Lock:
        if session_id not in self._locks:
            self._locks[session_id] = threading.Lock()
        return self._locks[session_id]

    async def create_session(self, user_id: str = None, model: str = None) -> dict:
        """创建新会话"""
        session_id = str(uuid.uuid4())

        # ⭐ 使用当前活跃配置的默认模型
        if model is None:
            model = self.registry.get_default_model_for_active()

        session = SessionModel(
            id=session_id,
            user_id=user_id,
            title='新会话',
            provider='custom',
            model=model,
            status='active'
        )
        db.session.add(session)
        db.session.commit()

        return session.to_dict()

    async def send_message(self, session_id: str, content: str, user_id: str = None) -> dict:
        """发送消息并获取 AI 回复 - 增强版(支持自动模式切换)"""
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

            # ⭐ 新增:问题复杂度分类
            mode, model_config = question_classifier.classify(content)
            enable_tools = question_classifier.should_enable_tools(content)

            logger.info(f"问题分类: mode={mode}, enable_tools={enable_tools}, model={model_config.get('provider')}/{model_config.get('model')}")

            # 2. ⭐ 新增:检测并读取附件文件(仅深度模式)
            from service.tools.file_utils import extract_file_paths, read_file_content, build_file_context

            file_paths = []
            file_context = ""

            # ⭐ 无论是否深度模式,都检测并读取文件
            file_paths = extract_file_paths(content)

            if file_paths:
                logger.info(f"检测到 {len(file_paths)} 个附件")
                file_results = []

                for path in file_paths:
                    result = read_file_content(path)
                    file_results.append(result)

                    if not result.get('success'):
                        logger.error(f"文件读取失败: {path} - {result.get('error')}")

                file_context = build_file_context(file_results)

            # 3. ⭐ 自我进化系统:预取上下文 (记忆 + 技能)
            memory_context = self.memory_manager.prefetch()

            # 仅深度模式启用技能
            skills_context = []
            rag_context_str = ""

            if enable_tools:
                skills_context = self.skill_manager.get_relevant_skills(content, limit=3)

            # ⭐ 新增:RAG 法条检索(基础设施层) — 使用查询改写器判断 + 多查询检索
            rag_status = {'enabled': True, 'triggered': False, 'success': False, 'results_count': 0}
            try:
                from service.rag.query_rewriter import get_query_rewriter

                rewriter = get_query_rewriter()

                # 加载最近对话历史，帮助 query rewriter 判断上下文
                recent_msgs = Message.query.filter_by(session_id=session_id)\
                    .order_by(Message.created_at.desc())\
                    .limit(4)\
                    .all()
                chat_history = [
                    {'role': m.role, 'content': m.content}
                    for m in reversed(recent_msgs) if m.content
                ]

                rewrite_result = await rewriter.rewrite(content, chat_history=chat_history)

                if rewrite_result['should_retrieve']:
                    rag_status['triggered'] = True
                    from service.rag.rag_integration import get_rag_integration

                    rag = get_rag_integration()

                    # 使用改写后的查询进行检索（多查询合并）
                    search_queries = rewrite_result.get('search_queries', [content])
                    if not search_queries:
                        search_queries = [content]

                    all_rag_results = []
                    for sq in search_queries[:3]:  # 最多 3 个查询
                        results = rag.search_legal_articles(
                            query=sq,
                            top_k=5,
                            threshold=0.5,
                        )
                        all_rag_results.extend(results)

                    # 去重（按内容前 100 字符）
                    seen = set()
                    unique_results = []
                    for r in all_rag_results:
                        key = r['content'][:100]
                        if key not in seen:
                            seen.add(key)
                            unique_results.append(r)

                    # 取 top-5
                    unique_results = unique_results[:5]

                    if unique_results:
                        rag_context_str = rag.build_rag_context(
                            results=unique_results,
                            query=content,
                            style='detailed'
                        )
                        rag_status['success'] = True
                        rag_status['results_count'] = len(unique_results)
                        logger.info(f"RAG 检索成功（查询改写: {len(search_queries)} 个查询）")

            except Exception as e:
                logger.warning(f"RAG 检索失败(降级): {e}")
                # 降级：使用旧的关键词触发 + 原始查询
                if self._should_use_rag(content):
                    rag_status['triggered'] = True
                    try:
                        from service.rag.rag_integration import get_rag_integration
                        rag = get_rag_integration()
                        rag_context_str = rag.search_and_build_context(
                            query=content,
                            top_k=5,
                            threshold=0.5,
                            style='detailed'
                        )
                        if rag_context_str:
                            rag_status['success'] = True
                            rag_status['results_count'] = 5
                    except Exception as e2:
                        logger.warning(f"RAG 降级检索也失败: {e2}")

            # 4. 构建 prompt (使用新的分层构建器)
            messages = await self._build_prompt_v2(
                session,
                memory_context=memory_context,
                skills_context=skills_context if enable_tools else None,
                rag_context=rag_context_str,  # RAG 上下文(已构建为字符串)
                file_context=file_context,
                enable_tools=enable_tools
            )

            if file_context:
                messages[-1]['content'] = f"{file_context}\n\n{messages[-1]['content']}"

            # 5. ⭐ 使用当前活跃配置（不再需要 provider 名称）
            provider = self.registry.get_active_provider()

            # 获取工具(仅深度模式启用) — 根据 provider 类型选择格式
            tools = []
            if enable_tools:
                from service.providers.minimax_provider import MiniMaxProvider
                if isinstance(provider, MiniMaxProvider):
                    tools = tool_registry.get_claude_tools()
                else:
                    tools = tool_registry.get_openai_tools()

            # 调用 AI(带工具调用支持)
            response = await provider.chat(messages, tools=tools if enable_tools else None)

            # ⭐ 处理工具调用(仅深度模式)
            # ⭐ 新增:记录使用的技能
            used_skills = []

            if enable_tools and response.tool_calls:
                logger.info(f"工具调用: {[tc['name'] for tc in response.tool_calls]}")

                max_iterations = 10
                iteration = 0

                while response.tool_calls and iteration < max_iterations:
                    # ⭐ 性能优化：使用 asyncio.gather 并发执行多个工具调用
                    async def _execute_single_tool(tool_call):
                        tool_name = tool_call['name']
                        tool_args = json.loads(tool_call['arguments']) if isinstance(tool_call['arguments'], str) else tool_call['arguments']
                        
                        tool = tool_registry.get(tool_name)
                        if tool:
                            tool_result = await tool.execute(**tool_args)
                        else:
                            logger.warning(f"工具不存在:{tool_name}")
                            tool_result = None
                        
                        return tool_call, tool_result

                    # 并发执行所有工具调用
                    import asyncio
                    results = await asyncio.gather(
                        *[_execute_single_tool(tc) for tc in response.tool_calls],
                        return_exceptions=True
                    )
                    
                    # 收集结果并构建消息
                    for result in results:
                        if isinstance(result, Exception):
                            logger.error(f"工具执行异常: {result}")
                            continue
                        
                        tool_call, tool_result = result
                        tool_name = tool_call['name']
                        used_skills.append(tool_name)
                        
                        args_str = tool_call['arguments'] if isinstance(tool_call['arguments'], str) else json.dumps(tool_call['arguments'], ensure_ascii=False)
                        
                        messages.append({
                            'role': 'assistant',
                            'content': None,
                            'tool_calls': [{
                                'id': tool_call.get('id', 'call_1'),
                                'type': 'function',
                                'function': {
                                    'name': tool_name,
                                    'arguments': args_str
                                }
                            }]
                        })
                        
                        if tool_result:
                            messages.append({
                                'role': 'tool',
                                'tool_call_id': tool_call.get('id', 'call_1'),
                                'content': tool_result.content if tool_result.success else f"Error: {tool_result.error}"
                            })
                        else:
                            messages.append({
                                'role': 'tool',
                                'tool_call_id': tool_call.get('id', 'call_1'),
                                'content': f"Error: 工具 '{tool_name}' 不存在"
                            })

                    # 再次调用 AI(带工具结果)
                    response = await provider.chat(messages, tools=tools)
                    iteration += 1

                if iteration > 0:
                    logger.info(f"工具调用循环完成,共 {iteration} 轮")

            if not response.success:
                return {'success': False, 'message': response.error}
            
            # ⭐ 自动润色检查
            auto_polished = False
            if response.content and len(response.content) > 50:
                try:
                    auto_polish_config = await self._get_auto_polish_config(session)
                    if auto_polish_config.get('enabled'):
                        style_name = auto_polish_config['style_name']
                        intensity = auto_polish_config.get('intensity', 'medium')
                        
                        # ⭐ Profile 不存在时，从附件文件自动分析生成
                        from service.core.style_forge import profile_manager
                        profile_exists = True
                        try:
                            profile_manager.load_profile(style_name)
                        except FileNotFoundError:
                            profile_exists = False
                            # 自动分析：从当前消息的附件文件中提取文本
                            if file_results:
                                logger.info(f"自动润色：Profile '{style_name}' 不存在，从附件自动分析")
                                combined_text = []
                                for fr in file_results:
                                    if fr.get('success') and fr.get('content'):
                                        # 去除行号前缀（格式：  1234: 内容）
                                        content = fr['content']
                                        lines = content.split('\n')
                                        clean_lines = []
                                        for line in lines:
                                            # 移除行号前缀
                                            import re
                                            cleaned = re.sub(r'^\s*\d+\s*:\s*', '', line)
                                            if cleaned.strip():
                                                clean_lines.append(cleaned)
                                        combined_text.append('\n'.join(clean_lines))
                                
                                if combined_text:
                                    full_text = '\n\n'.join(combined_text)
                                    if len(full_text) >= 100:
                                        from service.core.style_forge import analyzer
                                        style_data = analyzer.analyze_style(full_text)
                                        profile_manager.create_profile(
                                            style_name, style_data, source_files=[fr['path'] for fr in file_results if fr.get('success')]
                                        )
                                        logger.info(f"✅ 自动分析完成，Profile '{style_name}' 已创建")
                                        profile_exists = True
                                    else:
                                        logger.warning(f"附件文本过短（{len(full_text)} 字符），无法自动分析")
                                else:
                                    logger.warning("附件文件内容为空，无法自动分析")
                            else:
                                logger.warning(f"自动润色：Profile '{style_name}' 不存在且无附件文件，跳过润色")
                        
                        # 只有 Profile 存在时才执行润色
                        if profile_exists:
                            polished = await self._auto_polish_text(
                                response.content,
                                style_name,
                                intensity,
                            )
                            if polished:
                                response.content = polished
                                auto_polished = True
                                logger.info("自动润色完成")
                except Exception as e:
                    logger.warning(f"自动润色失败(降级): {e}")
            
            # 4. 保存 AI 回复
            # ⭐ 新增:保存使用的技能信息
            meta_data = {}
            if used_skills:
                meta_data['skills_used'] = used_skills

            if rag_status.get('enabled') or rag_status.get('triggered'):
                meta_data['rag_status'] = rag_status
            
            if auto_polished:
                meta_data['auto_polished'] = True

            assistant_msg = Message(
                session_id=session_id,
                role='assistant',
                content=response.content,
                token_count=response.token_count,
                tool_calls=response.tool_calls,
                meta_data=meta_data if meta_data else None
            )
            db.session.add(assistant_msg)

            # 5. 更新会话统计
            session.message_count += 2
            session.token_count += response.token_count
            session.updated_at = now_cst()

            # 6. ⭐ 自我进化系统:同步记忆
            self.memory_manager.sync(
                user_msg=content,
                assistant_msg=response.content,
                session_id=session_id
            )

            # 7. 自动标题(第一条消息时)
            if session.message_count == 2:
                session.title = content[:50] + ('...' if len(content) > 50 else '')

            # 8. 检查是否需要压缩
            if session.token_count > 6000:
                await self._compact_session(session)

            db.session.commit()

            return {
                'success': True,
                'message': assistant_msg.to_dict(),
                'session': session.to_dict()
            }

    async def _build_prompt_v2(
        self,
        session: SessionModel,
        memory_context: str = "",
        skills_context: list = None,
        rag_context_str: str = "",
        file_context: str = "",
        enable_tools: bool = False
    ) -> list:
        """构建对话上下文 - 使用新的分层 System Prompt 构建器(Hermes-Agent 模式)"""
        from service.core.system_prompt_builder import build_system_prompt

        messages = Message.query.filter_by(session_id=session.id)\
            .order_by(Message.created_at)\
            .limit(50)\
            .all()

        # 使用构建器构建 system prompt
        system_prompt = build_system_prompt(
            available_tools=set(tool['function']['name'] for tool in tool_registry.get_openai_tools()) if enable_tools else None,
        )

        # ⭐ 注入额外上下文(文件、记忆、RAG)
        additional_context = []

        # 注入文件内容
        if file_context:
            additional_context.append(file_context)

        # 注入记忆上下文
        if memory_context:
            additional_context.append(f"""
## 记忆上下文
{memory_context}

[System note: 以上是持久化记忆,作为背景信息,不要直接引用]
""")

        # 注入 RAG 法条检索结果 (如果有的话)
        # 注意：即使 RAG 为空，也不影响 LLM 用自己的知识回答
        if rag_context_str and len(rag_context_str) > 0:
            additional_context.append(f"""
## 相关法条(RAG 检索)
{rag_context_str}

[System note: 以上是检索到的相关法律条文,回答时请优先参考并准确引用。]
""")

        # ⭐ 注入技能上下文(仅当 enable_tools 时)
        if skills_context and enable_tools:
            skills_text = "\n".join([
                f"- {s['name']}: {s['description']}"
                for s in skills_context
            ])
            additional_context.append(f"""
## 可用技能
{skills_text}

当用户请求与上述技能相关时,请使用相应技能处理。
""")

        # 合并 system prompt 和额外上下文
        if additional_context:
            system_prompt += "\n\n" + "\n\n".join(additional_context)

        # 构建消息列表
        message_list = [
            {'role': 'system', 'content': system_prompt},
            *[{'role': m.role, 'content': m.content} for m in messages]
        ]

        logger.info(f"System Prompt 构建完成(v2), {len(system_prompt)} 字符")

        return message_list

    async def _compact_session(self, session: SessionModel):
        """压缩会话历史"""
        messages = Message.query.filter_by(session_id=session.id)\
            .order_by(Message.created_at)\
            .all()

        if len(messages) <= 10:
            return

        compactor = Compactor()
        # 保留最近 5 条,压缩早期对话
        recent = messages[-5:]
        early = messages[:-5]

        # 标记早期消息为已压缩(实际应调用 LLM 生成摘要)
        for msg in early:
            msg.meta_data = (msg.meta_data or {})
            msg.meta_data['compacted'] = True

        db.session.commit()

    async def list_sessions(self, user_id: str = None) -> list:
        """获取会话列表(保留所有会话)"""
        query = SessionModel.query.filter_by(status='active')
        if user_id:
            query = query.filter_by(user_id=user_id)
        sessions = query.order_by(SessionModel.updated_at.desc()).all()

        # ⭐ 返回所有会话(包括空会话)
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
        """真正删除会话及其关联消息和记忆"""
        session = SessionModel.query.get(session_id)
        if not session:
            return False

        # 先清理关联的记忆记录（解除外键约束）
        from service.models.database import Memory
        Memory.query.filter_by(session_id=session_id).update({'session_id': None})
        # 删除关联的消息
        Message.query.filter_by(session_id=session_id).delete()
        # 删除会话
        db.session.delete(session)
        db.session.commit()
        return True

    async def _get_auto_polish_config(self, session) -> dict:
        """
        检查用户是否开启了自动润色
        
        Returns:
            {'enabled': bool, 'style_name': str, 'intensity': str}
        """
        from service.models.database import UserSettings
        user_id = session.user_id or 'default'
        
        enabled_setting = UserSettings.query.filter_by(
            user_id=user_id, setting_key='auto_polish'
        ).first()
        
        if not enabled_setting or enabled_setting.setting_value != 'true':
            return {'enabled': False}
        
        style_setting = UserSettings.query.filter_by(
            user_id=user_id, setting_key='auto_polish_style'
        ).first()
        
        intensity_setting = UserSettings.query.filter_by(
            user_id=user_id, setting_key='auto_polish_intensity'
        ).first()
        
        style_name = style_setting.setting_value if style_setting else None
        if not style_name:
            return {'enabled': False}  # 没有配置风格，不启用
        
        return {
            'enabled': True,
            'style_name': style_name,
            'intensity': intensity_setting.setting_value if intensity_setting else 'medium',
        }

    async def _auto_polish_text(self, text: str, style_name: str, intensity: str) -> str:
        """
        执行自动润色
        
        Args:
            text: 待润色文本
            style_name: 风格名称
            intensity: 润色强度
            
        Returns:
            润色后的文本，失败返回 None
        """
        from service.core.style_forge import profile_manager, polisher
        
        profile = profile_manager.load_profile(style_name)
        result = await polisher.polish_text(
            text=text,
            style_profile=profile,
            intensity=intensity,
            use_api=True,
        )
        
        if result.get('success'):
            return result['polished']
        return None

    def _should_use_rag(self, content: str) -> bool:
        """
        判断是否需要 RAG 检索（降级策略，仅靠关键词和长度）

        Args:
            content: 用户问题内容

        Returns:
            True/False
        """
        # 1. 检查是否包含法律关键词
        matched_keywords = [keyword for keyword in self.rag_keywords if keyword in content]
        if matched_keywords:
            return True

        if len(content) > 100:
            return True

        return False


# 全局实例
runtime = SessionRuntime()
