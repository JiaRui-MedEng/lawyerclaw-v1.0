"""
MiniMax (Anthropic 兼容) 供应商
API: https://api.minimaxi.com/anthropic
"""
import json
from typing import List, Optional
from anthropic import AsyncAnthropic

from service.providers.base import BaseProvider, ChatResponse


def _convert_messages_to_anthropic(messages: List[dict]) -> tuple:
    """将 OpenAI 格式的消息列表转换为 Anthropic 格式。

    返回 (system_msg, anthropic_messages)

    主要差异：
    - system 消息需要单独提取
    - assistant 的 tool_calls 需要转为 content blocks
    - role='tool' 需要转为 role='user' + tool_result content block
    """
    system_msg = None
    anthropic_msgs = []

    for m in messages:
        role = m.get('role', '')

        if role == 'system':
            system_msg = m['content']

        elif role == 'assistant':
            tool_calls = m.get('tool_calls')
            if tool_calls:
                # 有工具调用：构建 content blocks
                content_blocks = []
                text = m.get('content', '')
                if text:
                    content_blocks.append({'type': 'text', 'text': text})
                for tc in tool_calls:
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
                anthropic_msgs.append({'role': 'assistant', 'content': content_blocks})
            else:
                anthropic_msgs.append({'role': 'assistant', 'content': m.get('content', '')})

        elif role == 'tool':
            # OpenAI tool result → Anthropic tool_result
            tool_result_block = {
                'type': 'tool_result',
                'tool_use_id': m.get('tool_call_id', ''),
                'content': m.get('content', '')
            }
            # Anthropic 要求 tool_result 在 user 消息中
            # 如果上一条也是 user（多个 tool results），合并到同一条
            if anthropic_msgs and anthropic_msgs[-1]['role'] == 'user' and isinstance(anthropic_msgs[-1]['content'], list):
                anthropic_msgs[-1]['content'].append(tool_result_block)
            else:
                anthropic_msgs.append({'role': 'user', 'content': [tool_result_block]})

        else:
            # user 等其他角色直接传递
            anthropic_msgs.append({'role': role, 'content': m.get('content', '')})

    return system_msg, anthropic_msgs


class MiniMaxProvider(BaseProvider):
    """MiniMax API 适配 (Anthropic 协议)"""

    def __init__(self, api_key: str, model: str = 'MiniMax-M2.7', base_url: str = None):
        super().__init__(api_key, model)
        client_kwargs = {'api_key': api_key}
        if base_url:
            client_kwargs['base_url'] = base_url
        self.client = AsyncAnthropic(**client_kwargs)

    async def chat(self, messages: List[dict], tools: List[dict] = None) -> ChatResponse:
        try:
            system_msg, chat_messages = _convert_messages_to_anthropic(messages)

            kwargs = {
                'model': self.model,
                'messages': chat_messages,
                'max_tokens': 4096,
            }
            if system_msg:
                kwargs['system'] = system_msg
            if tools:
                kwargs['tools'] = tools

            response = await self.client.messages.create(**kwargs)

            content = ''
            tool_calls = None
            for block in response.content:
                if block.type == 'text':
                    content += block.text
                elif block.type == 'tool_use':
                    if tool_calls is None:
                        tool_calls = []
                    tool_calls.append({
                        'id': block.id,
                        'name': block.name,
                        'arguments': block.input
                    })

            return ChatResponse(
                success=True,
                content=content,
                token_count=response.usage.input_tokens + response.usage.output_tokens,
                tool_calls=tool_calls
            )
        except Exception as e:
            return ChatResponse(success=False, content='', error=str(e))

    async def chat_stream(self, messages: List[dict]):
        system_msg, chat_messages = _convert_messages_to_anthropic(messages)

        kwargs = {
            'model': self.model,
            'messages': chat_messages,
            'max_tokens': 4096,
            'stream': True,
        }
        if system_msg:
            kwargs['system'] = system_msg

        stream = await self.client.messages.create(**kwargs)
        async for event in stream:
            if hasattr(event, 'delta') and hasattr(event.delta, 'text') and event.delta.text:
                yield event.delta.text
            elif isinstance(event, dict) and event.get('type') == 'content_block_delta':
                delta = event.get('delta', {})
                if delta.get('type') == 'text_delta':
                    yield delta.get('text', '')