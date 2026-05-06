"""
问题复杂度分类器

根据用户问题的复杂度，自动切换到非深度思考模式或深度思考模式。

非深度思考模式（快速模式）:
- 使用便宜/快速的模型
- 不启用工具调用
- 适合简单问答、闲聊

深度思考模式（完整模式）:
- 使用强力模型
- 启用工具调用（文件读取、技能等）
- 适合复杂任务、代码、分析
"""
import re
from typing import Dict, Any, Optional, Tuple


# 复杂任务关键词
COMPLEX_KEYWORDS = {
    # 编程相关
    "debug", "debugging", "implement", "implementation",
    "refactor", "patch", "traceback", "stacktrace",
    "exception", "error", "compile", "build",
    
    # 分析相关
    "analyze", "analysis", "investigate", "examine",
    "review", "audit", "inspect",
    
    # 架构设计
    "architecture", "design", "plan", "planning",
    "structure", "framework", "system",
    
    # 工具调用
    "file", "read", "write", "search", "list",
    "tool", "tools", "execute", "run",
    
    # 测试部署
    "test", "testing", "pytest", "deploy",
    "docker", "kubernetes", "ci/cd",
    
    # 法律专业（百佑 LawyerClaw 特有）
    "合同", "审查", "起草", "分析",
    "案件", "诉讼", "法律", "法规",
    "检索", "案例", "判决书",
    
    # ⭐ 新增：技能查询相关
    "技能", "skill", "skills",
    "能力", "capability", "capabilities",
    "工具", "tool", "tools",
    "功能", "function", "functions",
    "你能做什么", "可以做什么",
}

# 简单任务关键词
SIMPLE_KEYWORDS = {
    "你好", "hello", "hi", "hey",
    "谢谢", "thank", "thanks",
    "再见", "bye", "goodbye",
    "是什么", "what is", "who is",
    "定义", "definition",
    "解释", "explain",
}

# URL 检测
URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)

# 代码块检测
CODE_BLOCK_RE = re.compile(r"```|`[^`]+`")


class QuestionClassifier:
    """问题复杂度分类器"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化分类器
        
        Args:
            config: 配置字典，包含：
                - enabled: 是否启用分类
                - max_simple_chars: 简单问题最大字符数（默认 200）
                - max_simple_words: 简单问题最大词数（默认 30）
                - cheap_model: 非深度思考模式使用的模型
                - powerful_model: 深度思考模式使用的模型
        """
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)
        self.max_simple_chars = self.config.get("max_simple_chars", 200)
        self.max_simple_words = self.config.get("max_simple_words", 30)
        
        # 模型配置
        self.cheap_model = self.config.get("cheap_model", {
            "provider": "bailian",
            "model": "qwen-max",  # 快速/便宜模型
        })
        self.powerful_model = self.config.get("powerful_model", {
            "provider": "bailian",
            "model": "gpt-4o",  # 强力模型
        })
    
    def classify(self, question: str) -> Tuple[str, Dict[str, Any]]:
        """
        分类问题复杂度
        
        Args:
            question: 用户问题
            
        Returns:
            (mode, model_config)
            - mode: "shallow" 或 "deep"
            - model_config: 模型配置字典
        """
        if not self.enabled:
            return "deep", self.powerful_model
        
        question = question.strip()
        
        # 空问题 → 深度模式
        if not question:
            return "deep", self.powerful_model
        
        # 检查是否包含复杂关键词
        lowered = question.lower()
        words = {token.strip(".,:;!?()[]{}\"'`") for token in lowered.split()}
        
        if words & COMPLEX_KEYWORDS:
            return "deep", self.powerful_model
        
        # 检查长度
        if len(question) > self.max_simple_chars:
            return "deep", self.powerful_model
        
        # 检查词数
        if len(question.split()) > self.max_simple_words:
            return "deep", self.powerful_model
        
        # 检查多行
        if question.count("\n") > 1:
            return "deep", self.powerful_model
        
        # 检查代码块
        if CODE_BLOCK_RE.search(question):
            return "deep", self.powerful_model
        
        # 检查 URL
        if URL_RE.search(question):
            return "deep", self.powerful_model
        
        # 检查是否包含简单关键词 → 非深度模式
        if words & SIMPLE_KEYWORDS:
            return "shallow", self.cheap_model
        
        # 默认：根据长度判断
        if len(question) < 50:
            return "shallow", self.cheap_model
        else:
            return "deep", self.powerful_model
    
    def get_model_for_turn(self, question: str) -> Dict[str, Any]:
        """
        获取当前对话轮次应使用的模型
        
        Args:
            question: 用户问题
            
        Returns:
            模型配置字典
        """
        mode, config = self.classify(question)
        
        # 添加模式标签
        config["mode"] = mode
        config["routing_reason"] = f"{mode}_mode"
        
        return config
    
    def should_enable_tools(self, question: str) -> bool:
        """
        判断是否应该启用工具调用
        
        Args:
            question: 用户问题
            
        Returns:
            bool: 是否启用工具
        """
        question = question.strip()
        
        # ⭐ 修复：中文关键词检测（中文没有空格分隔，需要子串匹配）
        lowered = question.lower()
        
        # 检查复杂关键词（支持子串匹配，兼容中文）
        for keyword in COMPLEX_KEYWORDS:
            if keyword in lowered:
                return True
        
        # 检查生成/创建类关键词（用户期望得到实际产出物）
        GENERATE_KEYWORDS = {
            "帮我写", "帮我生成", "帮我创建", "帮我做", "帮我起草",
            "写一份", "生成一份", "创建一份", "做一个", "出一份",
            "写个", "生成个", "创建个", "做个", "出个",
            "生成", "创建", "起草", "编写", "制作",
            "样例", "示例", "模板", "范文",
        }
        for keyword in GENERATE_KEYWORDS:
            if keyword in lowered:
                return True
        
        # 检查长度
        if len(question) > self.max_simple_chars:
            return True
        
        # 检查多行
        if question.count("\n") > 1:
            return True
        
        # 检查代码块
        if CODE_BLOCK_RE.search(question):
            return True
        
        # 检查 URL
        if URL_RE.search(question):
            return True
        
        # 检查简单关键词 → 不启用工具
        for keyword in SIMPLE_KEYWORDS:
            if keyword in lowered:
                return False
        
        # 默认：根据长度判断
        if len(question) < 50:
            return False
        else:
            return True


# 全局分类器实例
classifier = QuestionClassifier()


def get_model_for_question(question: str) -> Dict[str, Any]:
    """快捷函数：获取问题对应的模型配置"""
    return classifier.get_model_for_turn(question)


def should_use_tools(question: str) -> bool:
    """快捷函数：判断是否应该使用工具"""
    return classifier.should_enable_tools(question)
