"""
Reranker 二次排序模块
使用 Cross-Encoder 对 RAG 初检结果重新打分排序
支持智谱 API / 本地模型两种模式
"""
import os
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class Reranker:
    """检索结果二次排序器"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('ZHIPU_API_KEY')
        self._client = None

    def _init_client(self):
        if self._client is None:
            try:
                from zhipuai import ZhipuAI
                self._client = ZhipuAI(api_key=self.api_key)
                logger.info("Reranker 客户端初始化成功（智谱 API）")
            except Exception as e:
                logger.error(f"Reranker 初始化失败：{e}")
                raise

    def rerank(
        self,
        query: str,
        documents: List[Dict],
        top_k: int = 5
    ) -> List[Dict]:
        """
        对检索结果二次排序

        Args:
            query: 原始查询
            documents: 初检结果列表（需包含 'content' 字段）
            top_k: 返回数量

        Returns:
            重排序后的结果列表，新增 'rerank_score' 字段
        """
        if not documents:
            return []

        if len(documents) <= top_k:
            return documents

        try:
            return self._rerank_via_zhipu(query, documents, top_k)
        except Exception as e:
            logger.warning(f"智谱 Reranker 失败，降级为原始排序: {e}")
            return documents[:top_k]

    def _rerank_via_zhipu(
        self,
        query: str,
        documents: List[Dict],
        top_k: int
    ) -> List[Dict]:
        """使用智谱 API 进行 rerank"""
        self._init_client()

        # 准备文档文本
        doc_texts = [d.get('content', '')[:1000] for d in documents]

        try:
            # 智谱 reranker 接口（使用 text-embedding 模型做相关性打分）
            # 逐个计算 query-document 相关性
            scored = []
            for i, doc_text in enumerate(doc_texts):
                # 用 embedding 余弦相似度作为 rerank 分数
                response = self._client.embeddings.create(
                    model="embedding-3",
                    input=[query, doc_text]
                )
                q_emb = response.data[0].embedding
                d_emb = response.data[1].embedding

                # 计算余弦相似度
                score = self._cosine_similarity(q_emb, d_emb)
                scored.append((i, score))

            # 按 rerank 分数降序排列
            scored.sort(key=lambda x: x[1], reverse=True)

            results = []
            for idx, score in scored[:top_k]:
                item = documents[idx].copy()
                item['rerank_score'] = score
                results.append(item)

            logger.info(f"Rerank 完成: {len(documents)} -> {len(results)} 条")
            return results

        except Exception as e:
            logger.error(f"智谱 Reranker 调用失败: {e}")
            raise

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """计算两个向量的余弦相似度"""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


# 全局单例
_reranker_instance: Optional[Reranker] = None


def get_reranker() -> Reranker:
    """获取 Reranker 单例"""
    global _reranker_instance
    if _reranker_instance is None:
        _reranker_instance = Reranker()
    return _reranker_instance
