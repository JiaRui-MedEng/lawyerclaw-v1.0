"""
RAG 上下文构建器
将 ChromaDB 检索结果注入 System Prompt
"""
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class RAGContextBuilder:
    """RAG 上下文构建器"""
    
    @staticmethod
    def build_context(
        results: List[Dict],
        query: str = None,
        include_scores: bool = True,
        max_content_length: int = 500
    ) -> str:
        """
        构建 RAG 检索上下文
        
        Args:
            results: ChromaDB 检索结果
            query: 原始查询（可选）
            include_scores: 是否包含相似度评分
            max_content_length: 法条内容最大长度
        
        Returns:
            格式化的 RAG 上下文字符串
        """
        if not results:
            return ""
        
        lines = []
        
        # 标题
        lines.append("## 📚 相关法律法规（RAG 检索）\n")
        
        # 查询信息
        if query:
            lines.append(f"**检索查询**: {query}\n")
        
        lines.append(f"**找到 {len(results)} 条相关法条**\n")
        lines.append("---\n")
        
        # 法条列表
        for i, result in enumerate(results, 1):
            lines.append(f"\n**{i}. {result.get('title', '未知法条')}**")
            
            # 相似度评分
            if include_scores and 'score' in result:
                score_percent = result['score'] * 100
                lines.append(f"- **相关度**: {score_percent:.1f}%")
            
            # 法条来源
            if result.get('law_name'):
                article_num = result.get('article_number', '')
                lines.append(f"- **来源**: {result['law_name']} {article_num}".strip())
            
            # 分类
            if result.get('category'):
                lines.append(f"- **分类**: {result['category']}")
            
            # 生效日期
            if result.get('effective_date'):
                lines.append(f"- **生效日期**: {result['effective_date']}")
            
            # 法条内容
            content = result.get('content', '')
            if len(content) > max_content_length:
                content = content[:max_content_length] + "..."
            lines.append(f"\n**内容**:\n{content}\n")
            
            # 分隔线
            lines.append("---\n")
        
        # 系统提示
        lines.append("\n> **System note**: 以上是检索到的相关法律法规。在回答用户问题时，请优先参考并准确引用上述法条。如果法条内容与问题相关，请明确标注出处（法律名称 + 法条编号）。")
        
        return "\n".join(lines)
    
    @staticmethod
    def build_summary(results: List[Dict]) -> str:
        """
        构建 RAG 检索摘要（简短版）
        
        Args:
            results: ChromaDB 检索结果

        Returns:
            简短的摘要
        """
        if not results:
            return "未检索到相关法律法规。"
        
        titles = [r.get('title', '') for r in results[:3]]
        return f"已检索到 {len(results)} 条相关法条，包括：{'、'.join(titles)}"
    
    @staticmethod
    def extract_key_articles(results: List[Dict], min_score: float = 0.8) -> List[Dict]:
        """
        提取关键法条（高相似度）
        
        Args:
            results: ChromaDB 检索结果
            min_score: 最低相似度阈值
        
        Returns:
            关键法条列表
        """
        return [r for r in results if r.get('score', 0) >= min_score]


def build_rag_context(
    results: List[Dict],
    query: str = None,
    style: str = 'detailed'
) -> str:
    """
    便捷函数：构建 RAG 上下文
    
    Args:
        results: ChromaDB 检索结果
        query: 原始查询
        style: 'detailed' | 'brief' | 'summary'
    
    Returns:
        格式化的 RAG 上下文
    """
    builder = RAGContextBuilder()
    
    if style == 'detailed':
        return builder.build_context(results, query, include_scores=True, max_content_length=500)
    elif style == 'brief':
        return builder.build_context(results, query, include_scores=False, max_content_length=300)
    elif style == 'summary':
        return builder.build_summary(results)
    else:
        return builder.build_context(results, query)
