"""
流式对话 API - 支持工具调用

重写流式处理逻辑，使其支持 Hermes 风格的工具调用循环。
"""
import asyncio
import nest_asyncio

# 允许嵌套的 event loop（Flask + asyncio）
nest_asyncio.apply()
import json
import queue
import threading
import logging
import time
from dataclasses import dataclass, field, asdict
from flask import Blueprint, request, jsonify, Response, stream_with_context
from service.core.runtime import runtime, tool_registry
from service.models.database import db, Session as SessionModel, Message
from service.tools.file_utils import extract_file_paths, read_file_content, build_file_context

logger = logging.getLogger(__name__)


def _friendly_llm_error(e: Exception) -> str:
    """将 LLM API 异常转换为用户友好的中文提示"""
    msg = str(e)
    # 429 / 配额耗尽
    if '429' in msg or 'throttling' in msg.lower() or 'quota' in msg.lower() or 'rate' in msg.lower():
        return 'AI 服务调用额度已用完，请稍后再试或前往 API 控制台检查配额。'
    # 401 / 认证失败
    if '401' in msg or 'unauthorized' in msg.lower() or 'invalid.*key' in msg.lower():
        return 'API 密钥无效或已过期，请在设置中检查 API Key 配置。'
    # 403 / 权限不足
    if '403' in msg or 'forbidden' in msg.lower():
        return 'API 访问被拒绝，请检查账户权限或 API Key 是否有对应模型的访问权限。'
    # 网络 / 超时
    if 'timeout' in msg.lower() or 'timed out' in msg.lower():
        return 'AI 服务请求超时，请检查网络连接后重试。'
    if 'connection' in msg.lower() or 'network' in msg.lower():
        return 'AI 服务连接失败，请检查网络连接和 API 地址配置。'
    # 模型不存在
    if 'model' in msg.lower() and ('not found' in msg.lower() or 'does not exist' in msg.lower()):
        return f'模型不存在或不可用，请在设置中检查模型名称配置。'
    # 上下文过长
    if 'context' in msg.lower() and 'length' in msg.lower() or 'too many tokens' in msg.lower():
        return '对话内容过长，请尝试新建会话或缩短输入。'
    # 兜底
    return f'请求失败：{msg}'


@dataclass
class StreamEvent:
    """统一的流式事件格式"""
    type: str  # 'chunk', 'tool_start', 'tool_end', 'thinking', 'done', 'error', 'file_start', 'file_end'
    data: dict
    timestamp: float = field(default_factory=time.time)
    
    def to_json(self):
        return json.dumps(asdict(self), ensure_ascii=False)

chat_enhanced_bp = Blueprint('chat_enhanced', __name__)  # url_prefix 在 app.py 中指定


@chat_enhanced_bp.route('/test', methods=['GET'])
def test_route():
    """测试路由"""
    return jsonify({'success': True, 'message': 'OK'})

@chat_enhanced_bp.route('/stream', methods=['POST'])
def send_message_stream_with_tools():
    """流式对话 - 支持工具调用"""
    from flask import current_app
    
    app = current_app._get_current_object()
    
    data = request.get_json(force=True) or {}
    session_id = data.get('session_id')
    content = data.get('content', '').strip()
    
    logger.info(f"[Stream] 收到请求：session_id={session_id}, content={content[:50]}...")

    if not session_id or not content:
        return jsonify({'success': False, 'message': '缺少参数'}), 400

    def generate():
        """SSE 流式生成 - 支持工具调用"""
        q = queue.Queue()

        def _stream_producer():
            """生产者：从 LLM 获取流式响应并处理工具调用"""
            with app.app_context():
                try:
                    
                    session = SessionModel.query.get(session_id)
                    if not session:
                        logger.error(f"[Stream] 会话不存在：{session_id}")
                        q.put(f"data: {json.dumps({'success': False, 'error': '会话不存在'})}\n\n")
                        return
                    
                    # ⭐ 初始化 start_time
                    start_time = time.time()

                    # 获取历史消息
                    messages = list(Message.query.filter_by(session_id=session_id)
                        .order_by(Message.created_at)
                        .limit(50)
                        .all())

                    message_list = [{'role': m.role, 'content': m.content} for m in messages]

                    # 获取 Provider 和协议类型（使用当前活跃配置）
                    provider = runtime.registry.get_active_provider()
                    protocol = runtime.registry.get_active_protocol()
                    
                    logger.info(f"[Stream] 使用协议: {protocol}, 模型: {session.model}")

                    # 获取工具 — 根据协议类型选择格式
                    tools, tool_names = runtime.registry.get_tools_for_protocol(protocol)
                    logger.info(f"[Stream] 工具 ({protocol} 格式): {tool_names}")

                    # 构建 System Prompt
                    from service.core.system_prompt_builder import build_system_prompt

                    system_prompt = build_system_prompt(
                        available_tools=set(tool_names) if tools else None,
                    )

                    logger.info(f"[Stream] System Prompt: {len(system_prompt)} 字符")
                    
                    # 将 system prompt 插入到消息列表开头
                    message_list.insert(0, {'role': 'system', 'content': system_prompt})
                    message_list.append({'role': 'user', 'content': content})
                    
                    # 检测并读取附件文件
                    file_paths = extract_file_paths(content)
                    file_context = ""
                    image_files = []
                    
                    if file_paths:
                        logger.info(f"[Stream] 检测到 {len(file_paths)} 个附件")
                        
                        # ✅ 新增：发送文件处理开始通知
                        q.put(f"data: {StreamEvent(type='file_start', data={'file_count': len(file_paths), 'files': file_paths}).to_json()}\n\n")
                        
                        file_results = []
                        
                        for path in file_paths:
                            q.put(f"data: {StreamEvent(type='file_read_start', data={'file_path': path}).to_json()}\n\n")

                            file_start = time.time()
                            result = read_file_content(path, max_chars=50000)
                            elapsed = time.time() - file_start

                            file_results.append(result)

                            if result.get('success') and result.get('file_type') == '图片':
                                image_files.append(path)

                            q.put(f"data: {StreamEvent(type='file_read_end', data={'file_path': path, 'success': result.get('success', False), 'file_type': result.get('file_type'), 'elapsed_ms': int(elapsed * 1000), 'error': result.get('error')}).to_json()}\n\n")

                            if not result.get('success'):
                                logger.warning(f"[Stream] 文件读取失败：{path} - {result.get('error')}")
                        
                        # ✅ 新增：发送文件处理完成通知
                        q.put(f"data: {StreamEvent(type='file_end', data={'file_count': len(file_paths), 'success_count': sum(1 for r in file_results if r.get('success')), 'fail_count': sum(1 for r in file_results if not r.get('success'))}).to_json()}\n\n")
                        
                        # ⭐ 将文件内容添加到 user message
                        file_context = build_file_context(file_results)

                        if file_context:
                            message_list[-1]['content'] = f"{file_context}\n\n{message_list[-1]['content']}"
                    
                    # ⭐ 新增：RAG 法条检索（基础设施层） - 移出 if file_paths 块
                    rag_status = {
                    'enabled': False,
                    'triggered': False,
                    'results_count': 0,
                    'success': False
                    }
                    
                    rag_keywords = ['法律', '法规', '法条', '条例', '规定', '办法', '司法解释',
                                   '民法典', '劳动法', '刑法', '行政法', '合同法', '公司法',
                                   '诉讼', '仲裁', '判决', '裁定', '案例', '目录']

                    matched_keywords = [kw for kw in rag_keywords if kw in content]

                    if matched_keywords:
                        rag_status['triggered'] = True
                        rag_status['enabled'] = True
                        logger.info(f"[Stream] RAG 触发，关键词: {matched_keywords}")

                        # ⭐ 性能优化：RAG 检索添加超时保护（3秒），避免阻塞首屏响应
                        rag_start = time.time()
                        rag_timeout = 3.0  # 3秒超时
                        try:
                            from service.rag.rag_simple import search_legal_articles, build_rag_context
                            import concurrent.futures
                            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as rag_executor:
                                rag_future = rag_executor.submit(
                                    search_legal_articles, query=content, top_k=10, threshold=0.3
                                )
                                try:
                                    rag_results = rag_future.result(timeout=rag_timeout)
                                except concurrent.futures.TimeoutError:
                                    logger.warning(f"[Stream] RAG 检索超时 ({rag_timeout}s)，跳过")
                                    rag_results = None
                                    rag_status['error'] = 'RAG 检索超时'

                            if rag_results:
                                rag_context_str = build_rag_context(rag_results, query=content)
                                rag_status['success'] = True
                                rag_status['results_count'] = len(rag_results)
                                rag_elapsed = time.time() - rag_start
                                logger.info(f"[Stream] RAG 检索完成，耗时 {int(rag_elapsed*1000)}ms, {len(rag_results)} 条结果")
                                # ⭐ 附加检索结果详情，供前端弹窗展示
                                rag_status['results'] = [
                                    {
                                        'title': r.get('title', '未知法条'),
                                        'content': r.get('content', '')[:800],
                                        'score': round(r.get('score', 0), 4),
                                        'category': r.get('category', ''),
                                        'collection': r.get('collection', '')
                                    }
                                    for r in rag_results
                                ]
                                system_prompt += "\n\n" + rag_context_str
                            else:
                                rag_status['success'] = False
                                rag_status['results_count'] = 0
                        except Exception as e:
                            logger.warning(f"[Stream] RAG 检索失败：{e}")
                            rag_status['success'] = False
                            rag_status['error'] = str(e)

                    # 更新 system prompt
                    message_list[0]['content'] = system_prompt

                    # 工具调用循环
                    max_iterations = 10
                    iteration = 0

                    while iteration < max_iterations:
                        iteration += 1

                        # ⭐ 使用单一事件循环，避免冲突
                        try:
                            # 检查是否有正在运行的事件循环
                            try:
                                loop = asyncio.get_running_loop()
                                # 如果有运行中的循环，创建新线程运行
                                import concurrent.futures
                                with concurrent.futures.ThreadPoolExecutor() as executor:
                                    future = executor.submit(asyncio.run, provider.chat(message_list, tools=tools))
                                    response = future.result()
                            except RuntimeError:
                                # 没有运行中的循环，直接使用 asyncio.run
                                response = asyncio.run(provider.chat(message_list, tools=tools))
                        except Exception as e:
                            error_msg = _friendly_llm_error(e)
                            logger.error(f"[Stream] LLM 调用失败：{e}")
                            q.put(f"data: {json.dumps({'success': False, 'error': error_msg}, ensure_ascii=False)}\n\n")
                            return

                        # 检查 provider 返回的错误（如 MiniMax 捕获异常后返回 success=False）
                        if hasattr(response, 'success') and not response.success:
                            error_msg = _friendly_llm_error(Exception(response.error or '未知错误'))
                            logger.error(f"[Stream] LLM 返回错误：{response.error}")
                            q.put(f"data: {json.dumps({'success': False, 'error': error_msg}, ensure_ascii=False)}\n\n")
                            return

                        tool_calls = response.tool_calls if hasattr(response, 'tool_calls') else None

                        if tool_calls:
                            # 标准化为内部格式（统一处理）
                            normalized_tool_calls = []
                            for tc in tool_calls:
                                if 'function' in tc:
                                    # 已经是 OpenAI 格式
                                    normalized_tool_calls.append(tc)
                                else:
                                    # 扁平格式 {'id', 'name', 'arguments'} → OpenAI 格式
                                    args = tc.get('arguments', '{}')
                                    if isinstance(args, dict):
                                        args = json.dumps(args, ensure_ascii=False)
                                    normalized_tool_calls.append({
                                        'id': tc.get('id', f'call_{iteration}'),
                                        'type': 'function',
                                        'function': {
                                            'name': tc.get('name', ''),
                                            'arguments': args
                                        }
                                    })

                            logger.info(f"[Stream] 工具调用: {[tc['function']['name'] for tc in normalized_tool_calls]}")

                            # ⭐ 根据协议格式添加工具调用到消息历史
                            if protocol == 'anthropic':
                                # Anthropic: tool_calls → content blocks
                                content_blocks = []
                                if response.content:
                                    content_blocks.append({'type': 'text', 'text': response.content})
                                for tc in normalized_tool_calls:
                                    func = tc.get('function', tc)
                                    args = func.get('arguments', '{}')
                                    if isinstance(args, str):
                                        try:
                                            args = json.loads(args)
                                        except json.JSONDecodeError:
                                            args = {}
                                    content_blocks.append({
                                        'type': 'tool_use',
                                        'id': tc.get('id', ''),
                                        'name': func.get('name', ''),
                                        'input': args
                                    })
                                message_list.append({'role': 'assistant', 'content': content_blocks})
                            else:
                                # OpenAI: 标准 tool_calls
                                message_list.append({
                                    'role': 'assistant',
                                    'content': response.content or '',
                                    'tool_calls': normalized_tool_calls
                                })

                            # 执行工具调用
                            for tool_call in normalized_tool_calls:
                                tool_name = tool_call['function']['name']
                                tool_args = json.loads(tool_call['function'].get('arguments', '{}'))
                                tool_id = tool_call['id']
                                
                                # ✅ 发送工具调用开始事件
                                q.put(f"data: {StreamEvent(type='tool_start', data={'tool_name': tool_name, 'arguments': tool_args, 'tool_id': tool_id}).to_json()}\n\n")
                                
                                tool_start = time.time()
                                
                                # 执行工具（同步调用）
                                try:
                                    # ⭐ 使用 asyncio.run() 包装异步调用
                                    tool_result = asyncio.run(tool_registry.execute(tool_name, **tool_args))
                                    result = {'success': tool_result.success, 'content': tool_result.content}
                                    if tool_result.error:
                                        result['error'] = tool_result.error
                                        # ⭐ 工具不存在时，提示可用工具列表
                                        if '不存在' in tool_result.error:
                                            available = [t['name'] if 'name' in t else t['function']['name'] for t in tools]
                                            result['hint'] = f"可用工具: {', '.join(available)}。请使用正确的工具名称，或直接回答用户问题。"
                                    elapsed = time.time() - tool_start
                                    
                                    # ✅ 发送工具调用完成事件
                                    q.put(f"data: {StreamEvent(type='tool_end', data={'tool_name': tool_name, 'tool_id': tool_id, 'success': tool_result.success, 'result': result, 'elapsed_ms': int(elapsed * 1000)}).to_json()}\n\n")
                                    
                                    # ⭐ 根据协议格式添加工具结果到消息历史
                                    if protocol == 'anthropic':
                                        # Anthropic: tool result 嵌入 user 消息
                                        message_list.append({
                                            'role': 'user',
                                            'content': [{
                                                'type': 'tool_result',
                                                'tool_use_id': tool_id,
                                                'content': json.dumps(result, ensure_ascii=False)
                                            }]
                                        })
                                    else:
                                        # OpenAI: 标准 tool role
                                        message_list.append({
                                            'role': 'tool',
                                            'content': json.dumps(result, ensure_ascii=False),
                                            'tool_call_id': tool_id
                                        })
                                    
                                except Exception as tool_error:
                                    elapsed = time.time() - tool_start
                                    logger.error(f"[Stream] 工具执行失败：{tool_name} - {tool_error}")
                                    
                                    # ✅ 发送工具调用失败事件
                                    q.put(f"data: {StreamEvent(type='tool_end', data={'tool_name': tool_name, 'tool_id': tool_id, 'success': False, 'error': str(tool_error), 'elapsed_ms': int(elapsed * 1000)}).to_json()}\n\n")
                                    
                                    # 添加错误结果到消息历史
                                    if protocol == 'anthropic':
                                        message_list.append({
                                            'role': 'user',
                                            'content': [{
                                                'type': 'tool_result',
                                                'tool_use_id': tool_id,
                                                'content': json.dumps({'error': str(tool_error)})
                                            }]
                                        })
                                    else:
                                        message_list.append({
                                            'role': 'tool',
                                            'content': json.dumps({'error': str(tool_error)}),
                                            'tool_call_id': tool_id
                                        })
                            
                            # 继续下一轮调用
                            continue
                        
                        # 没有工具调用，开始流式输出

                        # 先保存用户消息
                        user_msg = Message(session_id=session_id, role='user', content=content)
                        db.session.add(user_msg)
                        db.session.commit()

                        # ⭐ 优先使用 chat() 已返回的内容
                        first_call_content = response.content if hasattr(response, 'content') and response.content else ''

                        # 流式输出
                        full_content = []
                        chunk_count = 0
                        token_count = 0

                        # ⭐ 如果 chat() 已有完整回复，直接使用，跳过冗余的 chat_stream 调用
                        if first_call_content.strip():
                            logger.info(f"[Stream] chat() 已返回内容 ({len(first_call_content)} 字)，直接使用")
                            full_content.append(first_call_content)
                            chunk_count = 1
                            q.put(f"data: {StreamEvent(type='chunk', data={'content': first_call_content, 'chunk_index': 1}).to_json()}\n\n")
                        else:
                            # chat() 无内容，回退到流式调用
                            # ⭐ 修复：保留工具调用和工具结果消息，否则 LLM 看不到工具执行结果
                            # 只过滤掉可能导致 API 格式错误的消息，保留 tool 角色消息
                            stream_messages = list(message_list)
                            if not stream_messages:
                                stream_messages = message_list

                            # ⭐ 使用单一事件循环，避免冲突
                            try:
                                try:
                                    loop = asyncio.get_running_loop()
                                    import concurrent.futures

                                    async def collect_stream_in_thread():
                                        nonlocal chunk_count, token_count
                                        async for chunk in provider.chat_stream(stream_messages):
                                            if chunk:
                                                full_content.append(chunk)
                                                chunk_count += 1
                                                q.put(f"data: {StreamEvent(type='chunk', data={'content': chunk, 'chunk_index': chunk_count}).to_json()}\n\n")
                                        logger.info(f"[Stream] 流式输出完成，共 {chunk_count} 个 chunk")

                                    with concurrent.futures.ThreadPoolExecutor() as executor:
                                        future = executor.submit(asyncio.run, collect_stream_in_thread())
                                        future.result()
                                except RuntimeError:
                                    async def collect_stream():
                                        nonlocal chunk_count, token_count
                                        async for chunk in provider.chat_stream(stream_messages):
                                            if chunk:
                                                full_content.append(chunk)
                                                chunk_count += 1
                                                q.put(f"data: {StreamEvent(type='chunk', data={'content': chunk, 'chunk_index': chunk_count}).to_json()}\n\n")
                                        logger.info(f"[Stream] 流式输出完成，共 {chunk_count} 个 chunk")

                                    asyncio.run(collect_stream())
                            except Exception as stream_error:
                                logger.error(f"[Stream] 流式输出错误：{stream_error}")
                                import traceback
                                logger.error(traceback.format_exc())
                                q.put(f"data: {StreamEvent(type='error', data={'message': str(stream_error)}).to_json()}\n\n")

                        # 保存 AI 回复
                        ai_content = ''.join(full_content)

                        if ai_content:
                            # ⭐ 保存 RAG 状态到 extra_data
                            extra_data = {}
                            if rag_status.get('enabled') or rag_status.get('triggered'):
                                extra_data['rag_status'] = rag_status
                            ai_msg = Message(session_id=session_id, role='assistant', content=ai_content,
                                extra_data=extra_data if extra_data else None
                            )
                            db.session.add(ai_msg)
                            
                            session.message_count += 1
                            if session.message_count == 1:
                                session.title = content[:50] + ('...' if len(content) > 50 else '')
                            db.session.commit()
                        
                        # ✅ 优化：发送完成事件（包含 RAG 状态）- 始终返回 rag_status
                        q.put(f"data: {StreamEvent(type='done', data={'content': ai_content, 'chunk_count': chunk_count, 'token_count': token_count, 'elapsed_ms': int((time.time() - start_time) * 1000), 'rag_status': rag_status}).to_json()}\n\n")
                        
                        logger.info(f"[Stream] 请求完成，耗时 {int((time.time() - start_time) * 1000)}ms, {chunk_count} chunks")
                        return
                    
                    # 超过最大迭代次数
                    logger.warning(f"[Stream] 超过最大工具调用次数 ({max_iterations})")
                    q.put(f"data: {json.dumps({'success': False, 'error': '超过最大工具调用次数'})}\n\n")
                    
                except Exception as e:
                    import traceback
                    error_trace = traceback.format_exc()
                    logger.error(f"[Stream] 错误：{e}")
                    logger.error(error_trace)
                    error_msg = _friendly_llm_error(e)
                    q.put(f"data: {json.dumps({'success': False, 'error': error_msg}, ensure_ascii=False)}\n\n")
                finally:
                    q.put(None)
        
        # 启动生产者线程
        thread = threading.Thread(target=_stream_producer, daemon=True)
        thread.start()
        
        # 从队列读取数据并 yield
        while True:
            item = q.get()
            if item is None:
                break
            yield item
        
    # 流式响应
    return Response(generate(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no'
    })
