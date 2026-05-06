"""
通义千问 (DashScope) 供应商适配
"""
from typing import List, Optional
import dashscope
from dashscope.aigc.generation import Generation

from service.providers.base import BaseProvider, ChatResponse


class DashscopeProvider(BaseProvider):
    """通义千问 API 适配"""
    
    def __init__(self, api_key: str, model: str = 'qwen-max'):
        super().__init__(api_key, model)
        dashscope.api_key = api_key
    
    async def chat(self, messages: List[dict], tools: List[dict] = None) -> ChatResponse:
        try:
            response = Generation.call(
                model=self.model,
                messages=messages,
                result_format='message',
            )
            
            if response.status_code == 200:
                output = response.output.choices[0].message
                return ChatResponse(
                    success=True,
                    content=output.content or '',
                    token_count=response.usage.total_tokens if response.usage else 0
                )
            else:
                return ChatResponse(
                    success=False,
                    content='',
                    error=f"API 错误：{response.code} - {response.message}"
                )
        except Exception as e:
            return ChatResponse(success=False, content='', error=str(e))
    
    async def chat_stream(self, messages: List[dict]):
        responses = Generation.call(
            model=self.model,
            messages=messages,
            result_format='message',
            stream=True,
            incremental_output=True
        )
        for response in responses:
            if response.status_code == 200:
                content = response.output.choices[0].message.content
                if content:
                    yield content
