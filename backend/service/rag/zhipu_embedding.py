"""
智谱 AI Embedding 客户端
使用 Embedding-3 模型进行文本向量化
"""
import os
import logging
from typing import List, Union
from zhipuai import ZhipuAI

logger = logging.getLogger(__name__)


class ZhipuEmbeddingClient:
    """智谱 AI Embedding 客户端"""
    
    def __init__(self, api_key: str = None):
        """
        初始化智谱 AI 客户端
        
        Args:
            api_key: 智谱 API Key，默认从环境变量读取
        """
        self.api_key = api_key or os.getenv('ZHIPU_API_KEY')
        
        if not self.api_key:
            raise ValueError("智谱 API Key 未设置，请通过参数或环境变量 ZHIPU_API_KEY 提供")
        
        self.client = ZhipuAI(api_key=self.api_key)
        self.model = "embedding-3"
        
        logger.info(f"✅ 智谱 Embedding 客户端初始化成功")
        logger.info(f"   模型：{self.model}")
        logger.info(f"   API Key: {self.api_key[:15]}...")
    
    def embed_text(self, text: str) -> List[float]:
        """
        将单个文本转换为向量
        
        Args:
            text: 输入文本
        
        Returns:
            向量表示（List[float]）
        """
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text
            )
            
            embedding = response.data[0].embedding
            logger.debug(f"✅ 文本向量化成功，维度：{len(embedding)}")
            
            return embedding
            
        except Exception as e:
            logger.error(f"❌ 文本向量化失败：{e}")
            raise
    
    def embed_texts(self, texts: List[str], batch_size: int = 10) -> List[List[float]]:
        """
        批量将文本转换为向量
        
        Args:
            texts: 文本列表
            batch_size: 批次大小
        
        Returns:
            向量列表
        """
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            logger.info(f"  处理批次 {i//batch_size + 1}/{(len(texts)-1)//batch_size + 1}")
            
            try:
                response = self.client.embeddings.create(
                    model=self.model,
                    input=batch
                )
                
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
                
                logger.debug(f"✅ 批次处理成功，本批 {len(batch_embeddings)} 个向量")
                
            except Exception as e:
                logger.error(f"❌ 批次处理失败：{e}")
                raise
        
        return all_embeddings
    
    def get_embedding_dim(self) -> int:
        """获取向量维度"""
        # Embedding-3 的维度是 2048
        return 2048
    
    def test_connection(self) -> bool:
        """测试连接是否正常"""
        try:
            test_text = "测试连接"
            embedding = self.embed_text(test_text)
            
            if len(embedding) == self.get_embedding_dim():
                logger.info("✅ 智谱 Embedding 连接测试成功")
                return True
            else:
                logger.error(f"❌ 向量维度错误：期望 {self.get_embedding_dim()}，实际 {len(embedding)}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 智谱 Embedding 连接测试失败：{e}")
            return False


# 全局单例
_embedding_instance = None

def get_zhipu_embedding_client() -> ZhipuEmbeddingClient:
    """获取智谱 Embedding 客户端单例"""
    global _embedding_instance
    if _embedding_instance is None:
        _embedding_instance = ZhipuEmbeddingClient()
    return _embedding_instance
