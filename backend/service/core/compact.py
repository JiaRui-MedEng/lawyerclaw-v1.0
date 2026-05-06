"""
对话压缩模块
当会话 token 数超过阈值时，自动压缩早期对话
"""
from typing import List


class Compactor:
    """对话压缩器"""
    
    def __init__(self, max_tokens: int = 8000, keep_recent: int = 5):
        self.max_tokens = max_tokens
        self.keep_recent = keep_recent
    
    def needs_compaction(self, messages: List[dict], total_tokens: int) -> bool:
        """判断是否需要压缩"""
        return total_tokens > self.max_tokens
    
    def compact(self, messages: List[dict]) -> tuple:
        """
        压缩消息历史
        返回：(摘要, 保留的最近消息)
        """
        if len(messages) <= self.keep_recent:
            return None, messages
        
        # 分离早期和近期消息
        early = messages[:-self.keep_recent]
        recent = messages[-self.keep_recent:]
        
        # 生成早期消息摘要
        summary = self._generate_summary(early)
        
        return summary, recent
    
    def _generate_summary(self, messages: List[dict]) -> str:
        """
        生成消息摘要
        实际应用中应调用 LLM 生成摘要
        """
        # 简化实现：提取关键信息
        user_messages = [m for m in messages if m.get('role') == 'user']
        
        if not user_messages:
            return "用户之前没有发送过消息。"
        
        # 提取用户意图关键词
        topics = []
        for msg in user_messages:
            content = msg.get('content', '')[:100]
            topics.append(content)
        
        return f"之前的对话涉及以下主题：\n" + "\n".join(f"- {t}" for t in topics[:3])
    
    def estimate_tokens(self, text: str) -> int:
        """估算文本 token 数（粗略估计）"""
        # 中文约 1.5 字/token，英文约 4 字符/token
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return int(chinese_chars * 0.67 + other_chars * 0.25)
