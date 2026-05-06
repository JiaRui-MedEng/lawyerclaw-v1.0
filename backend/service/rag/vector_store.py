"""
向量存储管理器
整合智谱 Embedding、文档解析和 ChromaDB 存储
"""
import os
import re
import logging
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class VectorStoreManager:
    """向量存储管理器"""

    def __init__(
        self,
        zhipu_api_key: str = None,
        **kwargs
    ):
        # 初始化智谱 Embedding 客户端
        from service.rag.zhipu_embedding import ZhipuEmbeddingClient
        self.embedding_client = ZhipuEmbeddingClient(api_key=zhipu_api_key)

        # 初始化 ChromaDB 存储
        from service.rag.chroma_store import get_chroma_store
        self.store = get_chroma_store()

        # 文档解析器
        from service.rag.document_parser import DocumentParser
        self.document_parser = DocumentParser()

        logger.info("向量存储管理器初始化成功")
        logger.info("   Embedding: 智谱 Embedding-3")
        logger.info("   存储: ChromaDB")

    def create_collection(self, collection_name: str = 'legal_documents'):
        """创建 Collection（如果不存在）"""
        if self.store.collection_exists(collection_name):
            logger.info(f"Collection '{collection_name}' 已存在")
        else:
            logger.info(f"Collection '{collection_name}' 已就绪")

    def ingest_document(self, file_path: str, collection_name: str = None, category: str = None):
        """
        处理单个文档：解析 → 向量化 → 存储

        Args:
            file_path: 文件路径
            collection_name: Collection 名称
            category: 文档分类
        """
        if not collection_name:
            collection_name = self._generate_collection_name(file_path)

        self.create_collection(collection_name)

        logger.info(f"解析文档：{file_path}")
        doc_data = self.document_parser.parse_file(file_path)

        self._store_chunks(doc_data, collection_name, category)
        logger.info(f"文档处理完成：{file_path}")

    def ingest_directory(self, directory_path: str, collection_name: str = None,
                        category: str = None, recursive: bool = True):
        """处理目录下所有文档"""
        if not collection_name:
            collection_name = self._generate_collection_name(directory_path)

        self.create_collection(collection_name)

        logger.info(f"解析目录：{directory_path}")
        documents = self.document_parser.parse_directory(directory_path, recursive)

        total_chunks = 0
        for doc_data in documents:
            self._store_chunks(doc_data, collection_name, category)
            total_chunks += len(doc_data['chunks'])

        logger.info(f"目录处理完成，处理文件：{len(documents)} 个，总块数：{total_chunks} 块")

    def _store_chunks(self, doc_data: Dict, collection_name: str, category: str = None):
        """将文档块向量化并存储（支持结构化 chunk）"""
        chunks = doc_data['chunks']
        if not chunks:
            logger.warning(f"文档无内容：{doc_data['file_name']}")
            return

        logger.info(f"向量化 {len(chunks)} 个文本块...")

        # chunks 可能是结构化 dict 列表或纯字符串列表
        is_structured = isinstance(chunks[0], dict)

        # 提取纯文本用于 embedding
        texts = [c['content'] if is_structured else c for c in chunks]
        embeddings = self.embedding_client.embed_texts(texts, batch_size=10)

        doc_title = doc_data['file_name']

        # 构建 chunks 字典列表（保留结构化元数据）
        chunk_dicts = []
        for i, c in enumerate(chunks):
            if is_structured:
                content = c['content']
                article_num = c.get('article_number', '')
                law_name = c.get('law_name', '')
                chapter = c.get('chapter', '')
                # 标题：法律名称 + 法条编号（如有），否则回退到文件名
                if law_name and article_num:
                    title = f"{law_name} {article_num}"
                elif law_name:
                    title = f"{law_name} - 块{i+1}"
                else:
                    title = f"{doc_title} - 块{i+1}"
            else:
                content = c
                article_num = ''
                law_name = ''
                chapter = ''
                title = f"{doc_title} - 块{i+1}"

            chunk_dicts.append({
                'title': title,
                'content': content[:9999] if len(content) > 9999 else content,
                'category': category or 'general',
                'article_number': article_num,
                'chapter': chapter,
                'law_name': law_name,
            })

        # 存入 ChromaDB
        inserted = self.store.insert_chunks(
            collection=collection_name,
            chunks=chunk_dicts,
            embeddings=embeddings,
        )

        logger.info(f"存储成功：{inserted} 个向量")

    def _generate_collection_name(self, path: str) -> str:
        """根据路径生成规范的 Collection 名称"""
        path = Path(path)
        name = path.stem if path.is_file() else path.name

        name = name.lower()
        name = re.sub(r'[^a-z0-9]', '_', name)
        name = re.sub(r'_+', '_', name)

        if len(name) > 63:
            name = name[:63]

        name = f"legal_{name}"
        logger.info(f"Collection 名称：{name}")
        return name

    def search(self, query: str, collection_name: str = None, top_k: int = 5,
              threshold: float = 0.7) -> List[Dict]:
        """语义检索"""
        query_embedding = self.embedding_client.embed_text(query)

        results = self.store.search(
            query_embedding=query_embedding,
            collection=collection_name,
            top_k=top_k,
            threshold=threshold,
        )

        logger.info(f"检索到 {len(results)} 条结果")
        return results

    def list_collections(self) -> List[str]:
        """列出所有 Collection"""
        collections = self.store.list_collections()
        return [c['name'] for c in collections]

    def get_collection_stats(self, collection_name: str) -> Dict:
        """获取 Collection 统计信息"""
        return self.store.get_collection_stats(collection_name)

    def close(self):
        """关闭连接"""
        pass


# 便捷函数
def get_vector_store() -> VectorStoreManager:
    """获取向量存储管理器单例"""
    return VectorStoreManager()
