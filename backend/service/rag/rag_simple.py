"""
简化的 RAG 检索模块
使用 ChromaDB 和智谱 API
"""
import os
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


def search_legal_articles(query: str, top_k: int = 10, threshold: float = 0.3) -> List[Dict]:
    """
    检索相关法律法条

    Args:
        query: 搜索查询
        top_k: 返回结果数量
        threshold: 相似度阈值

    Returns:
        检索结果列表
    """
    try:
        from zhipuai import ZhipuAI
        from service.rag.chroma_store import get_chroma_store

        # 1. 生成查询向量
        zhipu_api_key = os.getenv('ZHIPU_API_KEY')
        if not zhipu_api_key:
            raise ValueError("ZHIPU_API_KEY 未配置")
        client = ZhipuAI(api_key=zhipu_api_key)

        query_response = client.embeddings.create(
            model="embedding-3",
            input=[query]
        )
        query_embedding = query_response.data[0].embedding

        logger.info(f"向量化成功，维度：{len(query_embedding)}")

        # 2. 在 ChromaDB 中搜索所有 legal_ collection
        store = get_chroma_store()
        all_results = store.search(
            query_embedding=query_embedding,
            collection=None,  # 搜索所有 legal_ 开头的
            top_k=top_k,
            threshold=threshold,
        )

        logger.info(f"ChromaDB 检索到 {len(all_results)} 条结果")

        # 3. 去重（保留最相似的）
        seen_contents = set()
        unique_results = []
        for result in all_results:
            content_key = result['content'][:100]
            if content_key not in seen_contents:
                seen_contents.add(content_key)
                unique_results.append(result)

        logger.info(f"RAG 检索到 {len(unique_results)} 条相关法条")

        return unique_results

    except Exception as e:
        logger.error(f"RAG 检索失败：{e}")
        return []


def build_rag_context(results: List[Dict], query: str = None) -> str:
    """
    构建 RAG 上下文

    Args:
        results: 检索结果
        query: 原始查询

    Returns:
        格式化的 RAG 上下文
    """
    if not results:
        return ""

    lines = []
    lines.append("## 相关法律法规（RAG 检索）\n")

    if query:
        lines.append(f"**检索查询**: {query}\n")

    lines.append(f"**找到 {len(results)} 条相关法条**\n")
    lines.append("---\n")

    for i, result in enumerate(results, 1):
        lines.append(f"\n**{i}. {result.get('title', '未知法条')}**")
        lines.append(f"- **相关度**: {result['score']:.2%}")

        if result.get('category'):
            lines.append(f"- **分类**: {result['category']}")

        if result.get('collection'):
            lines.append(f"- **来源**: {result['collection']}")

        content = result.get('content', '')
        if len(content) > 500:
            content = content[:500] + "..."
        lines.append(f"\n**内容**:\n{content}\n")
        lines.append("---\n")

    lines.append("\n> **System note**: 以上是检索到的相关法律法规。在回答用户问题时，请优先参考并准确引用上述法条。如果法条内容与问题相关，请明确标注出处（法律名称 + 法条编号）。")

    return "\n".join(lines)


def search_and_build_context(query: str, top_k: int = 5, threshold: float = 0.5) -> str:
    """一站式：检索 + 构建上下文"""
    results = search_legal_articles(query, top_k=top_k, threshold=threshold)

    if results:
        return build_rag_context(results, query)
    else:
        return ""
