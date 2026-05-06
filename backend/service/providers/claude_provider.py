"""
Claude (Anthropic) 供应商适配 — 也兼容百炼 codingplan 等 Anthropic 兼容接口
"""
from typing import List, Optional
from anthropic import AsyncAnthropic

from service.providers.base import BaseProvider, ChatResponse


class ClaudeProvider(BaseProvider):
    """Claude API 适配"""
    
    def __init__(self, api_key: str, model: str = 'claude-sonnet-4-20250514', base_url: str = None):
        super().__init__(api_key, model)
        client_kwargs = {'api_key': api_key}
        if base_url:
            client_kwargs['base_url'] = base_url
        self.client = AsyncAnthropic(**client_kwargs)
    
    async def chat(self, messages: List[dict], tools: List[dict] = None) -> ChatResponse:
        try:
            # Claude 需要分离 system 消息
            system_msg = None
            chat_messages = []
            for m in messages:
                if m['role'] == 'system':
                    system_msg = m['content']
                else:
                    chat_messages.append(m)
            
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
        system_msg = None
        chat_messages = []
        for m in messages:
            if m['role'] == 'system':
                system_msg = m['content']
            else:
                chat_messages.append(m)
        
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
            # 处理不同 SDK 版本的 event 格式
            if hasattr(event, 'delta') and hasattr(event.delta, 'text') and event.delta.text:
                yield event.delta.text
            elif isinstance(event, dict) and event.get('type') == 'content_block_delta':
                delta = event.get('delta', {})
                if delta.get('type') == 'text_delta':
                    yield delta.get('text', '')
