"""
OpenAI 供应商适配
"""
import re
from typing import List, Optional
from openai import AsyncOpenAI

from service.providers.base import BaseProvider, ChatResponse


class OpenAIProvider(BaseProvider):
    """OpenAI API 适配"""

    def __init__(self, api_key: str, model: str = 'gpt-4o', base_url: str = None):
        super().__init__(api_key, model)
        client_kwargs = {'api_key': api_key}
        if base_url:
            client_kwargs['base_url'] = base_url
        self.client = AsyncOpenAI(**client_kwargs)

    def _process_messages_for_vision(self, messages: List[dict]) -> List[dict]:
        """
        处理消息中的图片(base64),转换为多模态格式

        支持格式:data:image/png;base64,xxxxx
        """
        processed = []

        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')

            # 只处理 user 消息中的图片
            if role != 'user' or not isinstance(content, str):
                processed.append(msg)
                continue

            # 检测是否包含 base64 图片（至少 20 个字符，避免误匹配）
            image_pattern = r'data:(image/[\w]+);base64,([A-Za-z0-9+/=]{20,})'
            matches = re.findall(image_pattern, content)

            if not matches:
                # 没有图片,保持原样
                processed.append(msg)
                continue

            # 有图片,转换为多模态格式
            content_parts = []
            remaining_text = content

            for mime_type, base64_data in matches:
                # 提取图片前的文本
                img_marker = f'data:{mime_type};base64,{base64_data}'
                parts = remaining_text.split(img_marker, 1)

                if parts[0].strip():
                    content_parts.append({'type': 'text', 'text': parts[0].strip()})

                # 添加图片
                content_parts.append({
                    'type': 'image_url',
                    'image_url': {'url': img_marker}
                })

                remaining_text = parts[1] if len(parts) > 1 else ''

            # 添加剩余文本
            if remaining_text.strip():
                content_parts.append({'type': 'text', 'text': remaining_text.strip()})

            processed.append({
                'role': role,
                'content': content_parts if content_parts else [{'type': 'text', 'text': content}]
            })

        return processed

    async def chat(self, messages: List[dict], tools: List[dict] = None) -> ChatResponse:
        try:
            # ⭐ 处理消息中的图片（转换为多模态格式）
            processed_messages = self._process_messages_for_vision(messages)
            
            kwargs = {
                'model': self.model,
                'messages': processed_messages,
            }
            if tools:
                kwargs['tools'] = tools
            
            response = await self.client.chat.completions.create(**kwargs)

            choice = response.choices[0]
            message = choice.message

            tool_calls = None
            if hasattr(message, 'tool_calls') and message.tool_calls:
                tool_calls = [
                    {
                        'id': tc.id,
                        'name': tc.function.name,
                        'arguments': tc.function.arguments
                    }
                    for tc in message.tool_calls
                ]

            return ChatResponse(
                success=True,
                content=message.content or '',
                token_count=response.usage.total_tokens if response.usage else 0,
                tool_calls=tool_calls
            )
        except Exception as e:
            return ChatResponse(success=False, content='', error=str(e))

    async def chat_stream(self, messages: List[dict]):
        """流式对话"""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"[OpenAIProvider] chat_stream 调用开始")
        logger.info(f"[OpenAIProvider] 消息数：{len(messages)}")
        logger.info(f"[OpenAIProvider] 模型：{self.model}")
        
        # ⭐ 处理消息中的图片（转换为多模态格式）
        processed_messages = self._process_messages_for_vision(messages)
        
        try:
            logger.info(f"[OpenAIProvider] 调用 client.chat.completions.create(stream=True)")
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=processed_messages,
                stream=True,
                stream_options={'include_usage': True}
            )
            
            logger.info(f"[OpenAIProvider] 开始接收流式数据")
            chunk_idx = 0
            reasoning_chunks = []
            has_content = False
            async for chunk in stream:
                chunk_idx += 1
                # ⭐ 详细日志：查看 chunk 结构
                if chunk_idx <= 5 or chunk_idx % 10 == 0:
                    logger.debug(f"[OpenAIProvider] 原始 chunk[{chunk_idx}]: {chunk}")
                
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    # ⭐ 检查 delta 的所有属性
                    if hasattr(delta, 'content') and delta.content:
                        logger.info(f"[OpenAIProvider] chunk[{chunk_idx}]: {delta.content[:30]}...")
                        has_content = True
                        yield delta.content
                    elif hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                        # Qwen 等模型可能将回复放在 reasoning_content 中
                        logger.info(f"[OpenAIProvider] chunk[{chunk_idx}] reasoning: {delta.reasoning_content[:30]}...")
                        reasoning_chunks.append(delta.reasoning_content)
                    else:
                        logger.debug(f"[OpenAIProvider] chunk[{chunk_idx}]: 无 content (delta={delta})")
                else:
                    logger.debug(f"[OpenAIProvider] chunk[{chunk_idx}]: 无 choices (chunk={chunk})")
            
            logger.info(f"[OpenAIProvider] 流式接收完成，共{chunk_idx}个 chunk")

            # ⭐ 如果没有 content 但有 reasoning_content，将其作为回复输出
            if not has_content and reasoning_chunks:
                logger.warning(f"[OpenAIProvider] 无 content，回退到 reasoning_content ({len(reasoning_chunks)} chunks)")
                reasoning_text = ''.join(reasoning_chunks)
                yield reasoning_text
            
        except Exception as e:
            logger.error(f"[OpenAIProvider] chat_stream 错误：{e}")
            import traceback
            logger.error(traceback.format_exc())
            raise
