"""
LLM 供应商抽象基类 + 协议驱动的 ProviderRegistry
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict


@dataclass
class ChatResponse:
    """统一响应格式"""
    success: bool
    content: str
    token_count: int = 0
    tool_calls: Optional[dict] = None
    error: Optional[str] = None


class BaseProvider(ABC):
    """供应商抽象基类"""
    
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
    
    @abstractmethod
    async def chat(self, messages: List[dict], tools: List[dict] = None) -> ChatResponse:
        """
        发送对话请求
        :param messages: 消息列表 [{"role": "user", "content": "..."}]
        :param tools: 工具定义列表（可选）
        :return: ChatResponse
        """
        pass
    
    @abstractmethod
    async def chat_stream(self, messages: List[dict]):
        """
        流式对话
        :param messages: 消息列表
        :yield: 流式响应块
        """
        pass


class ProviderRegistry:
    """
    协议驱动的供应商注册表
    
    支持两种模式：
    1. 预注册模式：通过 register() 注册固定 provider（如 .env 配置的）
    2. 动态模式：通过 register_from_db() 从数据库加载配置，按需创建实例
    """
    
    def __init__(self):
        self._providers: Dict[str, BaseProvider] = {}  # 预注册的 provider 实例
        self._db_configs: Dict[str, any] = {}          # 数据库中的 provider 配置对象
    
    def register(self, name: str, provider: BaseProvider):
        """注册预配置 provider（如 .env 中的 bailian/minimax）"""
        self._providers[name] = provider
    
    def register_from_db(self, app):
        """从数据库加载 provider 配置（延迟实例化）"""
        with app.app_context():
            from service.models.database import CustomProvider
            for cp in CustomProvider.query.filter_by(is_active=True).all():
                self._db_configs[cp.name] = cp
    
    def get_active_provider(self) -> BaseProvider:
        """
        获取当前活跃的 provider 实例（不再需要 provider 名称参数）
        直接从数据库查找 is_active=True 的配置
        """
        # 1. 先查缓存
        if self._db_configs:
            cp = next(iter(self._db_configs.values()))
            return self._create_provider(cp.protocol, cp.api_key, cp.default_model, cp.base_url)
        
        # 2. 预注册的兜底
        if self._providers:
            return next(iter(self._providers.values()))
        
        # 3. 直接查数据库
        try:
            from service.models.database import CustomProvider
            cp = CustomProvider.query.filter_by(is_active=True).first()
            if cp:
                self._db_configs[cp.name] = cp
                return self._create_provider(cp.protocol, cp.api_key, cp.default_model, cp.base_url)
        except Exception:
            pass
        
        raise ValueError("没有可用的模型配置，请在设置中添加并激活一个模型配置")
    
    def get_active_protocol(self) -> str:
        """获取当前活跃配置的协议类型"""
        if self._db_configs:
            cp = next(iter(self._db_configs.values()))
            return cp.protocol
        
        if self._providers:
            provider = next(iter(self._providers.values()))
            from service.providers.claude_provider import ClaudeProvider
            from service.providers.minimax_provider import MiniMaxProvider
            if isinstance(provider, (ClaudeProvider, MiniMaxProvider)):
                return 'anthropic'
            return 'openai'
        
        try:
            from service.models.database import CustomProvider
            cp = CustomProvider.query.filter_by(is_active=True).first()
            if cp:
                return cp.protocol
        except Exception:
            pass
        
        return 'openai'
    
    def get_provider(self, name: str) -> BaseProvider:
        """
        获取 provider 实例
        
        优先级：
        1. 预注册的实例
        2. DB 配置缓存（动态创建）
        3. ⭐ 兜底：直接查数据库（兼容缓存未刷新的场景）
        """
        # 1. 预注册
        if name in self._providers:
            return self._providers[name]
        
        # 2. DB 配置缓存（动态创建）
        if name in self._db_configs:
            cp = self._db_configs[name]
            return self._create_provider(cp.protocol, cp.api_key, cp.default_model, cp.base_url)
        
        # 3. ⭐ 兜底：直接查数据库（兼容缓存未刷新的场景，支持任意自定义名称）
        try:
            from service.models.database import CustomProvider
            cp = CustomProvider.query.filter_by(name=name, is_active=True).first()
            if cp:
                # 同步到缓存
                self._db_configs[name] = cp
                return self._create_provider(cp.protocol, cp.api_key, cp.default_model, cp.base_url)
        except Exception:
            pass  # 无 app context 或查询失败时忽略
        
        raise ValueError(f"未知的 provider：{name}，可用：{list(self._providers.keys()) + list(self._db_configs.keys())}")
    
    def get_default_model(self, name: str) -> str:
        """获取 provider 的默认模型名称"""
        # 预注册的通过实例获取
        if name in self._providers:
            return self._providers[name].model
        
        # DB 配置的直接读字段
        if name in self._db_configs:
            return self._db_configs[name].default_model
        
        # 别名
        aliases = {'openai': 'bailian'}
        resolved_name = aliases.get(name, name)
        if resolved_name in self._providers:
            return self._providers[resolved_name].model
        
        # 兜底默认值
        return 'gpt-4o'
    
    def get_default_model_for_active(self) -> str:
        """获取当前活跃配置的默认模型"""
        if self._db_configs:
            cp = next(iter(self._db_configs.values()))
            return cp.default_model
        
        if self._providers:
            return next(iter(self._providers.values())).model
        
        try:
            from service.models.database import CustomProvider
            cp = CustomProvider.query.filter_by(is_active=True).first()
            if cp:
                return cp.default_model
        except Exception:
            pass
        
        return 'gpt-4o'
    
    def get_protocol(self, name: str) -> str:
        """获取 provider 的协议类型 ('openai' 或 'anthropic')"""
        # 预注册的通过实例类型判断
        if name in self._providers:
            provider = self._providers[name]
            from service.providers.claude_provider import ClaudeProvider
            from service.providers.minimax_provider import MiniMaxProvider
            if isinstance(provider, (ClaudeProvider, MiniMaxProvider)):
                return 'anthropic'
            return 'openai'
        
        # DB 配置的直接读字段
        if name in self._db_configs:
            return self._db_configs[name].protocol
        
        # 别名
        aliases = {'openai': 'bailian'}
        resolved_name = aliases.get(name, name)
        if resolved_name in self._providers:
            provider = self._providers[resolved_name]
            from service.providers.claude_provider import ClaudeProvider
            from service.providers.minimax_provider import MiniMaxProvider
            if isinstance(provider, (ClaudeProvider, MiniMaxProvider)):
                return 'anthropic'
            return 'openai'
        
        return 'openai'  # 默认
    
    def _create_provider(self, protocol: str, api_key: str, model: str, base_url: str) -> BaseProvider:
        """工厂方法：根据协议类型创建对应的 Provider"""
        if protocol == 'openai':
            from service.providers.openai_provider import OpenAIProvider
            return OpenAIProvider(api_key=api_key, model=model, base_url=base_url)
        elif protocol == 'anthropic':
            from service.providers.claude_provider import ClaudeProvider
            return ClaudeProvider(api_key=api_key, model=model, base_url=base_url)
        else:
            raise ValueError(f"不支持的协议：{protocol}，仅支持 'openai' 或 'anthropic'")
    
    def get_tools_for_protocol(self, protocol: str) -> tuple:
        """获取对应协议的工具列表和工具名列表"""
        from service.core.runtime import tool_registry
        
        if protocol == 'anthropic':
            tools = tool_registry.get_claude_tools()
            tool_names = [t['name'] for t in tools]
        else:  # openai
            tools = tool_registry.get_openai_tools()
            tool_names = [t['function']['name'] for t in tools]
        
        return tools, tool_names
    
    @property
    def available(self) -> list:
        return list(self._providers.keys()) + list(self._db_configs.keys())
    
    def get_first_active_provider_name(self) -> str:
        """获取数据库中第一个活跃配置的 name，如果都没有则返回第一个预注册的 name"""
        # 先查 DB 缓存
        if self._db_configs:
            return next(iter(self._db_configs.keys()))
        
        # 再查预注册
        if self._providers:
            return next(iter(self._providers.keys()))
        
        # 兜底：直接查数据库
        try:
            from service.models.database import CustomProvider
            cp = CustomProvider.query.filter_by(is_active=True).first()
            if cp:
                self._db_configs[cp.name] = cp
                return cp.name
        except Exception:
            pass
        
        raise ValueError("没有可用的 provider 配置，请在设置中添加并激活一个模型配置")
    
    def get_provider_or_fallback(self, name: str) -> tuple:
        """
        获取 provider 实例，如果指定的 provider 不存在则回退到第一个活跃配置
        
        Returns: (provider_instance, used_name, was_fallback)
        """
        try:
            return (self.get_provider(name), name, False)
        except ValueError:
            # 指定的 provider 不存在，尝试回退
            fallback_name = self.get_first_active_provider_name()
            if fallback_name != name:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Provider '{name}' 不存在，已自动回退到 '{fallback_name}'")
            return (self.get_provider(fallback_name), fallback_name, True)
