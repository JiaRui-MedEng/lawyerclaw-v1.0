"""
RAG 基础设施集成模块
整合智谱 Embedding-3 + ChromaDB + 文档解析
自动从 ChromaDB 检索相关法条并注入 System Prompt
"""
import os
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class RAGIntegration:
    """RAG 基础设施集成器"""

    def __init__(self, zhipu_api_key: str = None):
        self.zhipu_api_key = zhipu_api_key or os.getenv('ZHIPU_API_KEY')
        self.embedding_client = None
        self.reranker = None
        logger.info("RAG 基础设施集成器初始化")

    def _init_embedding(self):
        """初始化智谱 Embedding 客户端"""
        if self.embedding_client is None:
            try:
                from zhipuai import ZhipuAI
                self.embedding_client = ZhipuAI(api_key=self.zhipu_api_key)
                logger.info("智谱 Embedding 客户端初始化成功")
            except Exception as e:
                logger.error(f"智谱 Embedding 初始化失败：{e}")
                raise

    def embed_text(self, text: str) -> List[float]:
        """
        将文本转换为向量

        Args:
            text: 输入文本

        Returns:
            向量表示（2048 维）
        """
        self._init_embedding()

        try:
            response = self.embedding_client.embeddings.create(
                model="embedding-3",
                input=text
            )
            embedding = response.data[0].embedding
            logger.debug(f"文本向量化成功，维度：{len(embedding)}")
            return embedding
        except Exception as e:
            logger.error(f"文本向量化失败：{e}")
            raise

    def search_legal_articles(
        self,
        query: str,
        collection_names: List[str] = None,
        top_k: int = 5,
        threshold: float = 0.6,
        enable_rerank: bool = True
    ) -> List[Dict]:
        """
        检索相关法律法条（混合检索 + 可选 Reranker）

        Args:
            query: 搜索查询
            collection_names: Collection 名称列表（None 表示搜索所有）
            top_k: 返回结果数量
            threshold: 相似度阈值
            enable_rerank: 是否启用 Reranker 二次排序

        Returns:
            检索结果列表
        """
        try:
            from service.rag.chroma_store import get_chroma_store

            logger.info(f"RAG 检索：\"{query}\"")
            query_embedding = self.embed_text(query)

            store = get_chroma_store()

            # 初检取更多候选（rerank 时取 top-20，否则取 top_k）
            initial_top_k = 20 if enable_rerank else top_k

            # 如果指定了 collection_names，逐个搜索并合并
            if collection_names:
                all_results = []
                for name in collection_names:
                    results = store.hybrid_search(
                        query_embedding=query_embedding,
                        query_text=query,
                        collection=name,
                        top_k=initial_top_k,
                        threshold=threshold,
                    )
                    all_results.extend(results)
                # 按 rrf_score 排序（如有），否则按 score
                all_results.sort(key=lambda x: x.get('rrf_score', x.get('score', 0)), reverse=True)
            else:
                # 搜索所有 legal_ 开头的 collection — 使用混合检索
                all_results = store.hybrid_search(
                    query_embedding=query_embedding,
                    query_text=query,
                    collection=None,
                    top_k=initial_top_k,
                    threshold=threshold,
                )

            # 添加 retrieved_at 字段
            for r in all_results:
                r['retrieved_at'] = datetime.now().isoformat()

            # 去重（保留最相似的）
            seen_contents = set()
            unique_results = []
            for result in all_results:
                content_key = result['content'][:100]
                if content_key not in seen_contents:
                    seen_contents.add(content_key)
                    unique_results.append(result)

            logger.info(f"RAG 检索到 {len(unique_results)} 条相关法条")

            # Reranker 二次排序
            if enable_rerank and len(unique_results) > top_k:
                try:
                    from service.rag.reranker import get_reranker
                    reranker = get_reranker()
                    unique_results = reranker.rerank(query, unique_results, top_k=top_k)
                    logger.info(f"Rerank 后保留 {len(unique_results)} 条")
                except Exception as e:
                    logger.warning(f"Reranker 失败，使用原始排序: {e}")
                    unique_results = unique_results[:top_k]

            return unique_results

        except Exception as e:
            logger.error(f"RAG 检索失败：{e}")
            return []

    def build_rag_context(
        self,
        results: List[Dict],
        query: str = None,
        style: str = 'detailed'
    ) -> str:
        """
        构建 RAG 上下文

        Args:
            results: 检索结果
            query: 原始查询
            style: 'detailed' | 'brief' | 'summary'

        Returns:
            格式化的 RAG 上下文
        """
        if not results:
            return ""

        lines = []

        if style == 'detailed':
            lines.append("## 相关法律法规（RAG 检索）\n")

            if query:
                lines.append(f"**检索查询**: {query}\n")

            lines.append(f"**找到 {len(results)} 条相关法条**\n")
            lines.append("---\n")

            for i, result in enumerate(results, 1):
                lines.append(f"\n**{i}. {result.get('title', '未知法条')}**")
                lines.append(f"- **相关度**: {result.get('score', 0):.2%}")

                # 结构化出处信息
                law_name = result.get('law_name', '')
                chapter = result.get('chapter', '')
                article_number = result.get('article_number', '')
                if law_name or article_number:
                    source_parts = [p for p in [law_name, chapter, article_number] if p]
                    lines.append(f"- **出处**: {' / '.join(source_parts)}")

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

        elif style == 'brief':
            lines.append("## 相关法律法规\n")

            for i, result in enumerate(results, 1):
                lines.append(f"{i}. **{result.get('title')}**")
                content = result.get('content', '')[:200] + "..." if len(result.get('content', '')) > 200 else result.get('content', '')
                lines.append(f"   {content}\n")

        elif style == 'summary':
            titles = [r.get('title', '') for r in results[:3]]
            lines.append(f"已检索到 {len(results)} 条相关法条，包括：{'、'.join(titles)}")

        return "\n".join(lines)

    def search_and_build_context(
        self,
        query: str,
        collection_names: List[str] = None,
        top_k: int = 5,
        threshold: float = 0.6,
        style: str = 'detailed'
    ) -> str:
        """
        一站式：检索 + 构建上下文
        """
        results = self.search_legal_articles(
            query=query,
            collection_names=collection_names,
            top_k=top_k,
            threshold=threshold
        )

        if results:
            return self.build_rag_context(results=results, query=query, style=style)
        else:
            return ""

    def close(self):
        """关闭资源"""
        pass


# 全局单例
_rag_instance: Optional[RAGIntegration] = None

def get_rag_integration() -> RAGIntegration:
    """获取 RAG 集成器单例"""
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = RAGIntegration()
    return _rag_instance
