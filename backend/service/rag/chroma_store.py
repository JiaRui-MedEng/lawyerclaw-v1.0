"""
ChromaDB 向量存储 - 替代 pgvector
嵌入式向量数据库，支持 PyInstaller 打包
"""
import os
import logging
import hashlib
from typing import List, Dict, Optional
from pathlib import Path

import chromadb

logger = logging.getLogger(__name__)

# 向量维度（智谱 Embedding-3）
VECTOR_DIM = 2048


class ChromaVectorStore:
    """ChromaDB 向量存储 - 替代 pgvector"""

    def __init__(self, persist_dir: str = None):
        from service.core.paths import get_chroma_dir
        self.persist_dir = persist_dir or str(get_chroma_dir())
        Path(self.persist_dir).mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(path=self.persist_dir)
        logger.info(f"ChromaDB 向量存储初始化成功，持久化目录：{self.persist_dir}")

    def _get_collection(self, name: str):
        """获取或创建 collection"""
        return self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"}
        )

    def collection_exists(self, collection_name: str) -> bool:
        """检查 collection 是否存在"""
        try:
            existing = [c.name for c in self._client.list_collections()]
            return collection_name in existing
        except Exception:
            return False

    def check_duplicate(self, collection_name: str, content_hash: str) -> bool:
        """检查文档是否已存在（基于内容哈希）"""
        try:
            if not self.collection_exists(collection_name):
                return False
            col = self._get_collection(collection_name)
            results = col.get(where={"content_hash": content_hash}, limit=1)
            return len(results['ids']) > 0
        except Exception as e:
            logger.warning(f"去重检查失败: {e}")
            return False

    def insert_chunks(self, collection: str, chunks: List[Dict],
                      embeddings: List[List[float]],
                      doc_hash: str = None, index_offset: int = 0) -> int:
        """
        批量插入文本块和向量

        Args:
            collection: Collection 名称
            chunks: 文本块列表 [{'title', 'content', 'category', ...}]
            embeddings: 对应的向量列表

        Returns:
            成功插入的数量
        """
        if not chunks or not embeddings:
            return 0

        col = self._get_collection(collection)
        inserted = 0

        # ChromaDB 单次 upsert 上限较大，但分批处理更稳定
        batch_size = 100
        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i:i + batch_size]
            batch_embeddings = embeddings[i:i + batch_size]

            ids = []
            documents = []
            metadatas = []
            batch_embs = []

            for j, chunk in enumerate(batch_chunks):
                content = chunk.get('content', '')
                content_hash = hashlib.md5(content.encode()).hexdigest()
                chunk_id = f"{collection}_{content_hash}"

                ids.append(chunk_id)
                documents.append(content)
                metadatas.append({
                    'title': chunk.get('title', ''),
                    'category': chunk.get('category', 'general'),
                    'article_number': chunk.get('article_number', ''),
                    'chapter': chunk.get('chapter', ''),
                    'law_name': chunk.get('law_name', ''),
                    'chunk_index': index_offset + i + j,
                    'content_hash': doc_hash if doc_hash else content_hash,
                })
                batch_embs.append(batch_embeddings[j])

            try:
                col.upsert(
                    ids=ids,
                    embeddings=batch_embs,
                    documents=documents,
                    metadatas=metadatas,
                )
                inserted += len(ids)
            except Exception as e:
                logger.error(f"ChromaDB 插入失败: {e}")

        logger.info(f"ChromaDB 插入 {inserted} 条向量到 '{collection}'")
        return inserted

    def search(self, query_embedding: List[float], collection: str = None,
               top_k: int = 5, threshold: float = 0.5,
               category: str = None) -> List[Dict]:
        """
        向量相似度检索

        Args:
            query_embedding: 查询向量
            collection: Collection 名称（None 搜索所有 legal_ 开头的）
            top_k: 返回数量
            threshold: 相似度阈值（cosine similarity）
            category: 分类过滤

        Returns:
            检索结果列表
        """
        collections_to_search = []

        if collection:
            collections_to_search = [collection]
        else:
            # 搜索所有 legal_ 开头的 collection
            for c in self._client.list_collections():
                if c.name.startswith('legal_'):
                    collections_to_search.append(c.name)

        if not collections_to_search:
            return []

        all_results = []

        for col_name in collections_to_search:
            try:
                col = self._client.get_collection(col_name)

                where_filter = None
                if category:
                    where_filter = {"category": category}

                results = col.query(
                    query_embeddings=[query_embedding],
                    n_results=top_k,
                    where=where_filter,
                    include=["documents", "metadatas", "distances"]
                )

                if results and results['ids'] and results['ids'][0]:
                    for idx in range(len(results['ids'][0])):
                        # ChromaDB cosine distance → similarity: 1 - distance
                        distance = results['distances'][0][idx]
                        similarity = 1.0 - distance

                        if similarity < threshold:
                            continue

                        metadata = results['metadatas'][0][idx] if results['metadatas'] else {}
                        all_results.append({
                            'id': results['ids'][0][idx],
                            'content': results['documents'][0][idx] if results['documents'] else '',
                            'title': metadata.get('title', ''),
                            'category': metadata.get('category', ''),
                            'collection': col_name,
                            'score': similarity,
                            'article_number': metadata.get('article_number', ''),
                            'chapter': metadata.get('chapter', ''),
                            'law_name': metadata.get('law_name', ''),
                        })
            except Exception as e:
                logger.error(f"ChromaDB 检索 '{col_name}' 失败: {e}")

        # 按相似度降序排序
        all_results.sort(key=lambda x: x['score'], reverse=True)
        return all_results[:top_k]

    def keyword_search(self, query_text: str, collection: str = None,
                       top_k: int = 10) -> List[Dict]:
        """
        关键词检索（使用 ChromaDB 的 where_document 过滤）

        Args:
            query_text: 搜索文本
            collection: Collection 名称
            top_k: 返回数量

        Returns:
            检索结果列表
        """
        collections_to_search = []

        if collection:
            collections_to_search = [collection]
        else:
            for c in self._client.list_collections():
                if c.name.startswith('legal_'):
                    collections_to_search.append(c.name)

        all_results = []

        for col_name in collections_to_search:
            try:
                col = self._client.get_collection(col_name)
                results = col.get(
                    where_document={"$contains": query_text},
                    limit=top_k,
                    include=["documents", "metadatas"]
                )

                if results and results['ids']:
                    for idx in range(len(results['ids'])):
                        metadata = results['metadatas'][idx] if results['metadatas'] else {}
                        all_results.append({
                            'id': results['ids'][idx],
                            'content': results['documents'][idx] if results['documents'] else '',
                            'title': metadata.get('title', ''),
                            'category': metadata.get('category', ''),
                            'collection': col_name,
                            'score': 0.5,  # 关键词匹配无精确分数
                            'article_number': metadata.get('article_number', ''),
                            'law_name': metadata.get('law_name', ''),
                        })
            except Exception as e:
                logger.error(f"ChromaDB 关键词检索 '{col_name}' 失败: {e}")

        return all_results[:top_k]

    def hybrid_search(self, query_embedding: List[float], query_text: str,
                      collection: str = None, top_k: int = 5,
                      threshold: float = 0.5, vector_weight: float = 0.7,
                      keyword_weight: float = 0.3,
                      category: str = None) -> List[Dict]:
        """
        混合检索（向量 + 关键词，RRF 融合）

        Args:
            query_embedding: 查询向量
            query_text: 查询文本
            collection: Collection 名称
            top_k: 返回数量
            threshold: 相似度阈值
            vector_weight: 向量检索权重
            keyword_weight: 关键词检索权重
            category: 分类过滤

        Returns:
            融合后的检索结果
        """
        # 向量检索
        vector_results = self.search(
            query_embedding=query_embedding,
            collection=collection,
            top_k=top_k * 2,
            threshold=threshold,
            category=category,
        )

        # 关键词检索
        keyword_results = self.keyword_search(
            query_text=query_text,
            collection=collection,
            top_k=top_k * 2,
        )

        # RRF 融合
        rrf_k = 60
        scores = {}
        result_map = {}

        for rank, r in enumerate(vector_results):
            rid = r['id']
            scores[rid] = scores.get(rid, 0) + vector_weight / (rrf_k + rank + 1)
            result_map[rid] = r

        for rank, r in enumerate(keyword_results):
            rid = r['id']
            scores[rid] = scores.get(rid, 0) + keyword_weight / (rrf_k + rank + 1)
            if rid not in result_map:
                result_map[rid] = r

        # 按 RRF 分数排序
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

        results = []
        for rid in sorted_ids[:top_k]:
            item = result_map[rid]
            item['score'] = scores[rid]
            results.append(item)

        return results

    def list_collections(self) -> List[Dict]:
        """列出所有 legal_ 开头的 Collection"""
        result = []
        for col in self._client.list_collections():
            if col.name.startswith('legal_'):
                try:
                    c = self._client.get_collection(col.name)
                    count = c.count()
                    result.append({
                        'name': col.name,
                        'entity_count': count,
                    })
                except Exception:
                    result.append({'name': col.name, 'entity_count': 0})
        return result

    def get_collection_stats(self, collection_name: str) -> Dict:
        """获取 Collection 统计信息"""
        try:
            col = self._client.get_collection(collection_name)
            count = col.count()
            return {
                'name': collection_name,
                'entity_count': count,
                'exists': True,
            }
        except Exception:
            return {
                'name': collection_name,
                'entity_count': 0,
                'exists': False,
            }

    def get_total_stats(self) -> Dict:
        """获取所有 legal_ Collection 的总体统计"""
        collections = self.list_collections()
        total_chunks = sum(c.get('entity_count', 0) for c in collections)
        total_docs = len(collections)
        enabled = os.environ.get('RAG_ENABLED', '1') == '1'

        return {
            'enabled': enabled,
            'doc_count': total_docs,
            'chunk_count': total_chunks,
            'collections': [c['name'] for c in collections],
        }

    def delete_collection(self, collection_name: str) -> bool:
        """删除 Collection"""
        try:
            self._client.delete_collection(collection_name)
            logger.info(f"已删除 Collection: {collection_name}")
            return True
        except Exception as e:
            logger.error(f"删除 Collection '{collection_name}' 失败: {e}")
            return False

    def close(self):
        """关闭（ChromaDB PersistentClient 无需显式关闭）"""
        logger.info("ChromaDB 向量存储已关闭")


# 全局单例
_store_instance: Optional[ChromaVectorStore] = None


def get_chroma_store() -> ChromaVectorStore:
    """获取 ChromaDB 存储单例"""
    global _store_instance
    if _store_instance is None:
        _store_instance = ChromaVectorStore()
    return _store_instance
