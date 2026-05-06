"""
对话 API
"""
import asyncio
import json
import os
import queue
import threading
import logging
from pathlib import Path
from flask import Blueprint, request, jsonify, Response, stream_with_context
from service.core.runtime import runtime
from service.providers.base import ProviderRegistry
from service.models.database import db, Session as SessionModel, Message

logger = logging.getLogger(__name__)

chat_bp = Blueprint('chat', __name__, url_prefix='/api/chat')


@chat_bp.route('', methods=['POST'])
def send_message():
    """发送消息（非流式）"""
    data = request.get_json(force=True) or {}
    session_id = data.get('session_id')
    content = data.get('content', '').strip()
    user_id = data.get('user_id')

    if not session_id:
        return jsonify({'success': False, 'message': '缺少 session_id'}), 400
    if not content:
        return jsonify({'success': False, 'message': '消息内容不能为空'}), 400

    result = asyncio.run(runtime.send_message(session_id, content, user_id))

    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 500


# ⚠️ 已禁用：此路由已被 chat_enhanced.py 中的增强版本替代
# @chat_bp.route('/stream', methods=['POST'])
# def send_message_stream():
#     """流式对话"""
#     from flask import current_app
#     app = current_app._get_current_object()
#     
#     data = request.get_json(force=True) or {}
#     session_id = data.get('session_id')
#     content = data.get('content', '') or ''
#     if content:
#         content = content.strip()
#
#     if not session_id or not content:
#         return jsonify({'success': False, 'message': '缺少参数'}), 400
#
#     def generate():
#         """SSE 流式生成 — 同步方式运行"""
#         q = queue.Queue()
#        
#         logger.info(f"[Stream] 收到请求：session_id={session_id}, content_length={len(content)}")
#         print(f"[Stream] 收到请求：session_id={session_id[:20]}..., content_length={len(content)}")

        def _stream_producer(msg_content):
            """生产者：从LLM获取流式响应并放入队列"""
            with app.app_context():
                try:
                    logger.info("[Stream] 开始处理请求")
                    
                    # 获取会话信息
                    session = SessionModel.query.get(session_id)
                    if not session:
                        logger.error(f"[Stream] 会话不存在：{session_id}")
                        q.put(f"data: {json.dumps({'success': False, 'error': '会话不存在'})}\n\n")
                        return
                    
                    logger.info(f"[Stream] 会话找到：{session.title}")
                    
                    # 处理附件文件
                    from service.tools.file_utils import extract_file_paths, build_file_context
                    from service.api.chat_sync_file_processor import process_files_smart
                    
                    file_paths = extract_file_paths(msg_content)
                    file_context = ""
                    image_files = []
                    
                    if file_paths:
                        logger.info(f"[Stream] 检测到 {len(file_paths)} 个附件文件：{file_paths}")
                        
                        results = process_files_smart(file_paths)
                        
                        file_results = [
                            r['result'] if r.get('success') else {'success': False, 'error': r.get('error')}
                            for r in results
                        ]
                        
                        # 检测图片文件
                        for i, result in enumerate(file_results):
                            logger.info(f"[Stream] 文件处理结果 [{i}]: success={result.get('success')}, file_type={result.get('file_type')}")
                            if result.get('success') and result.get('file_type') == '图片':
                                image_files.append(file_paths[i])
                                logger.info(f"[Stream] ✅ 检测到图片：{file_paths[i]}")
                        
                        success_count = sum(1 for r in results if r.get('success'))
                        failed_count = sum(1 for r in results if not r.get('success'))
                        avg_duration = sum(r.get('duration', 0) for r in results) / len(results) if results else 0
                        
                        logger.info(f"[Stream] 文件处理完成：成功 {success_count}/{len(file_paths)}, 失败 {failed_count}, 平均耗时 {avg_duration:.2f}s")
                        
                        file_context = build_file_context(file_results)
                        logger.info(f"[Stream] 文件上下文长度：{len(file_context)} 字符")
                    
                    # 如果有图片，自动分析并添加到上下文
                    original_msg_content = msg_content  # 保存原始消息内容
                    image_analysis_done = False
                    
                    if image_files:
                        logger.info(f"[Stream] 发现 {len(image_files)} 张图片，开始分析...")
                        
                        from openai import OpenAI
                        
                        image_analyses = []
                        for img_path in image_files:
                            try:
                                logger.info(f"[Stream] 分析图片：{img_path}")
                                
                                import base64
                                with open(img_path, 'rb') as f:
                                    image_data = base64.b64encode(f.read()).decode('utf-8')
                                
                                ext = Path(img_path).suffix.lower()
                                mime_map = {
                                    '.jpg': 'image/jpeg',
                                    '.jpeg': 'image/jpeg',
                                    '.png': 'image/png',
                                    '.gif': 'image/gif',
                                    '.bmp': 'image/bmp',
                                    '.webp': 'image/webp'
                                }
                                mime_type = mime_map.get(ext, 'image/jpeg')
                                image_url = f"data:{mime_type};base64,{image_data}"
                                
                                client = OpenAI(
                                    api_key=os.getenv('OPENAI_API_KEY'),
                                    base_url=os.getenv('OPENAI_BASE_URL')
                                )
                                
                                response = client.chat.completions.create(
                                    model=os.getenv('OPENAI_MODEL', 'qwen3.5-plus'),
                                    messages=[{
                                        "role": "user",
                                        "content": [
                                            {"type": "image_url", "image_url": {"url": image_url}},
                                            {"type": "text", "text": "请详细描述这张图片的内容"}
                                        ]
                                    }],
                                    max_tokens=1000
                                )
                                
                                analysis = response.choices[0].message.content
                                image_analyses.append(f"图片 {Path(img_path).name}:\n{analysis}")
                                logger.info(f"[Stream] 图片分析完成：{len(analysis)} 字符")
                                image_analysis_done = True
                                
                            except Exception as e:
                                logger.error(f"[Stream] 图片分析失败：{e}")
                                image_analyses.append(f"图片 {Path(img_path).name}: 分析失败 ({e})")
                        
                        if image_analyses:
                            analysis_text = "\n\n".join(image_analyses)
                            # 重要：不要修改 msg_content，保持原始用户消息
                            # 只在发送给 AI 时添加图片分析作为上下文
                            image_context = f"以下是对用户发送图片的内容分析：\n\n{analysis_text}\n\n"
                            logger.info(f"[Stream] 图片分析结果已生成，共 {len(analysis_text)} 字符")

                    # 构建消息列表
                    messages = list(Message.query.filter_by(session_id=session_id)
                        .order_by(Message.created_at)
                        .limit(50)
                        .all())
                    
                    logger.info(f"[Stream] 历史消息数：{len(messages)}")

                    message_list = [{'role': m.role, 'content': m.content} for m in messages]
                    
                    # 如果有图片分析，在用户消息前添加分析结果作为系统提示
                    if image_analysis_done and image_files:
                        # 添加系统消息说明图片分析结果
                        analysis_for_system = f"用户发送了 {len(image_files)} 张图片，以下是图片分析结果供参考：\n\n" + "\n\n".join(image_analyses)
                        message_list.append({'role': 'system', 'content': analysis_for_system})
                    
                    message_list.append({'role': 'user', 'content': original_msg_content})
                    
                    if file_context:
                        message_list.insert(0, {'role': 'system', 'content': file_context})

                    provider = runtime.registry.get_provider(session.provider)
                    if not provider:
                        logger.error(f"[Stream] LLM 提供商未配置：{session.provider}")
                        q.put(f"data: {json.dumps({'success': False, 'error': 'LLM 提供商未配置'})}\n\n")
                        return
                    
                    logger.info(f"[Stream] 使用 Provider: {session.provider}, Model: {session.model}")

                    full_content = []
                    chunk_count = 0
                    stream_success = False
                    
                    loop = asyncio.new_event_loop()
                    try:
                        asyncio.set_event_loop(loop)
                        
                        async def collect_stream():
                            nonlocal chunk_count, stream_success
                            try:
                                async for chunk in provider.chat_stream(message_list):
                                    if chunk:
                                        full_content.append(chunk)
                                        chunk_count += 1
                                        q.put(f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n")
                                stream_success = True
                                logger.info(f"[Stream] 流式完成，共收到 {chunk_count} 个 chunk")
                            except Exception as e:
                                logger.error(f"[Stream] 流式收集错误：{e}")
                                stream_success = False
                        
                        loop.run_until_complete(collect_stream())
                    finally:
                        loop.close()
                    
                    logger.info(f"[Stream] AI 回复长度：{len(''.join(full_content))}")

                    ai_content = ''.join(full_content)
                    logger.info(f"[Stream] AI 回复内容：{ai_content[:100] if ai_content else '(空)'}...")
                    
                    # 保存消息到数据库
                    # 重要：使用 original_msg_content 保存原始用户消息，不要包含图片分析前缀
                    try:
                        user_msg = Message(session_id=session_id, role='user', content=original_msg_content)
                        ai_msg = Message(session_id=session_id, role='assistant', content=ai_content)
                        db.session.add(user_msg)
                        db.session.add(ai_msg)

                        session.message_count += 2
                        if session.message_count == 2:
                            session.title = original_msg_content[:50] + ('...' if len(original_msg_content) > 50 else '')
                        db.session.commit()
                        logger.info("[Stream] 消息已保存到数据库")
                    except Exception as e:
                        logger.error(f"[Stream] 保存消息失败：{e}")
                        db.session.rollback()
                    
                    if ai_content:
                        q.put(f"data: {json.dumps({'success': True, 'message': {'content': ai_content}}, ensure_ascii=False)}\n\n")
                    else:
                        # AI 回复为空，发送错误
                        error_msg = "AI 回复为空，可能是模型调用超时或失败"
                        logger.warning(f"[Stream] {error_msg}")
                        q.put(f"data: {json.dumps({'success': False, 'error': error_msg})}\n\n")
                    
                    q.put("data: [DONE]\n\n")
                    logger.info("[Stream] 请求处理完成")

                except Exception as e:
                    import traceback
                    error_trace = traceback.format_exc()
                    logger.error(f"[Stream] 错误：{e}")
                    logger.error(error_trace)
                    q.put(f"data: {json.dumps({'success': False, 'error': str(e)}, ensure_ascii=False)}\n\n")
                finally:
                    q.put(None)

        thread = threading.Thread(target=_stream_producer, args=(content,), daemon=True)
        thread.start()
        logger.info("[Stream] 生产者线程已启动")

        try:
            while True:
                item = q.get(timeout=60)  # 增加超时时间到60秒
                if item is None:
                    break
                yield item
        except queue.Empty:
            logger.warning("[Stream] 队列超时（60秒内没有收到响应）")
            yield f"data: {json.dumps({'success': False, 'error': '请求处理超时（60秒），请重试'})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )