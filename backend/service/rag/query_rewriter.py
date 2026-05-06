"""
查询理解与改写模块
用 LLM 将用户口语化问题转化为更适合检索的查询
同时判断是否需要 RAG 检索，替代简单的关键词匹配
"""
import os
import json
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# 查询改写 Prompt 模板
REWRITE_PROMPT = """你是一个法律检索查询优化器。根据用户的问题，完成以下任务：

1. 判断该问题是否需要检索法律法规数据库（纯闲聊、问候、与法律无关的问题不需要）
2. 如果需要检索，将用户问题改写为 1-3 个更适合检索的查询（去除口语化表达，提取核心法律概念）
3. 提取问题中涉及的法律术语和具体法律名称

请严格按以下 JSON 格式返回，不要输出其他内容：
{
    "should_retrieve": true/false,
    "search_queries": ["改写后的检索查询1", "检索查询2"],
    "legal_terms": ["法律术语1", "术语2"],
    "target_laws": ["具体法律名称1"]
}

示例：
用户问题："我老板拖欠我三个月工资了怎么办"
返回：
{
    "should_retrieve": true,
    "search_queries": ["用人单位拖欠劳动者工资 劳动报酬", "劳动争议 工资拖欠 维权途径"],
    "legal_terms": ["劳动报酬", "工资拖欠", "劳动争议"],
    "target_laws": ["劳动法", "劳动合同法"]
}

用户问题："你好，今天天气怎么样"
返回：
{
    "should_retrieve": false,
    "search_queries": [],
    "legal_terms": [],
    "target_laws": []
}"""


class QueryRewriter:
    """查询改写器 — 用 LLM 将用户问题转化为更适合检索的查询"""

    def __init__(self):
        self._provider = None

    def _get_provider(self):
        """懒加载 LLM provider（复用已注册的 openai provider）"""
        if self._provider is None:
            try:
                from service.core.runtime import runtime
                self._provider = runtime.registry.get_provider('bailian')
                logger.info("QueryRewriter 使用已注册的 bailian provider")
            except Exception:
                # 降级：直接实例化 DashScope provider
                try:
                    from service.providers.dashscope_provider import DashscopeProvider
                    api_key = os.getenv('DASHSCOPE_API_KEY') or os.getenv('OPENAI_API_KEY', '')
                    self._provider = DashscopeProvider(api_key=api_key, model='qwen-turbo')
                    logger.info("QueryRewriter 降级使用 DashScope qwen-turbo")
                except Exception as e:
                    logger.error(f"QueryRewriter 无法初始化 provider: {e}")
                    raise
        return self._provider

    async def rewrite(self, user_query: str, chat_history: list = None) -> Dict:
        """
        分析用户查询，判断是否需要检索并生成改写查询

        Args:
            user_query: 用户原始问题
            chat_history: 最近的对话历史（可选，用于理解上下文）

        Returns:
            {
                'should_retrieve': bool,
                'search_queries': List[str],
                'legal_terms': List[str],
                'target_laws': List[str],
            }
        """
        # 构建消息
        messages = [
            {'role': 'system', 'content': REWRITE_PROMPT}
        ]

        # 如果有对话历史，加入最近 2 轮作为上下文
        if chat_history:
            recent = chat_history[-4:]  # 最近 2 轮（user + assistant）
            for msg in recent:
                if msg.get('role') in ('user', 'assistant'):
                    messages.append({
                        'role': msg['role'],
                        'content': msg['content'][:200]  # 截断避免 token 浪费
                    })

        messages.append({'role': 'user', 'content': f"用户问题：{user_query}"})

        try:
            provider = self._get_provider()
            response = await provider.chat(messages)

            if not response.success:
                logger.warning(f"查询改写 LLM 调用失败: {response.error}")
                return self._fallback(user_query)

            return self._parse_response(response.content, user_query)

        except Exception as e:
            logger.warning(f"查询改写异常，使用降级策略: {e}")
            return self._fallback(user_query)

    def _parse_response(self, content: str, original_query: str) -> Dict:
        """解析 LLM 返回的 JSON"""
        try:
            # 尝试提取 JSON（LLM 可能包裹在 markdown 代码块中）
            text = content.strip()
            if '```' in text:
                # 提取代码块中的内容
                start = text.find('{')
                end = text.rfind('}') + 1
                if start >= 0 and end > start:
                    text = text[start:end]

            result = json.loads(text)

            # 校验必要字段
            return {
                'should_retrieve': bool(result.get('should_retrieve', False)),
                'search_queries': result.get('search_queries', [original_query]),
                'legal_terms': result.get('legal_terms', []),
                'target_laws': result.get('target_laws', []),
            }
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"查询改写结果解析失败: {e}, 原始内容: {content[:200]}")
            return self._fallback(original_query)

    @staticmethod
    def _fallback(query: str) -> Dict:
        """降级策略：使用原始查询 + 简单关键词判断"""
        legal_keywords = [
            '法律', '法规', '法条', '条例', '规定', '办法', '司法解释',
            '民法典', '劳动法', '刑法', '行政法', '合同法', '公司法',
            '诉讼', '仲裁', '判决', '裁定', '案例', '赔偿', '违约',
            '侵权', '合同', '离婚', '继承', '债务', '担保', '租赁',
        ]
        should_retrieve = any(kw in query for kw in legal_keywords)

        return {
            'should_retrieve': should_retrieve,
            'search_queries': [query] if should_retrieve else [],
            'legal_terms': [],
            'target_laws': [],
        }


# 全局单例
_rewriter_instance: Optional[QueryRewriter] = None


def get_query_rewriter() -> QueryRewriter:
    """获取查询改写器单例"""
    global _rewriter_instance
    if _rewriter_instance is None:
        _rewriter_instance = QueryRewriter()
    return _rewriter_instance
