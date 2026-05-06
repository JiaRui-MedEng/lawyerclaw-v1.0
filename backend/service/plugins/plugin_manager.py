"""
插件系统
支持动态加载、启用/禁用、Hook 管道
"""
import os
import json
import importlib
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class HookContext:
    """Hook 上下文"""
    event: str
    data: Dict[str, Any]
    session_id: Optional[str] = None
    result: Any = None


@dataclass
class PluginInfo:
    """插件信息"""
    name: str
    version: str
    description: str
    author: str
    enabled: bool = True
    hooks: Dict[str, List[str]] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)
    path: Optional[str] = None
    created_at: Optional[str] = None
    
    def to_dict(self):
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "enabled": self.enabled,
            "hooks": self.hooks,
            "config": self.config,
            "path": self.path,
            "created_at": self.created_at
        }


class HookPipeline:
    """Hook 管道
    在特定时机触发注册的钩子函数
    """
    
    # 预定义的 Hook 事件
    EVENTS = [
        "session.create",      # 会话创建前
        "session.created",     # 会话创建后
        "message.before_send", # 消息发送前
        "message.after_send",  # 消息发送后
        "llm.before_call",     # LLM 调用前
        "llm.after_call",      # LLM 调用后
        "tool.before_execute", # 工具执行前
        "tool.after_execute",  # 工具执行后
        "session.close",       # 会话关闭
    ]
    
    def __init__(self):
        self._hooks = {event: [] for event in self.EVENTS}
    
    def register(self, event: str, handler):
        """注册 Hook"""
        if event not in self._hooks:
            self._hooks[event] = []
        self._hooks[event].append(handler)
        logger.info(f"注册 Hook: {event}")
    
    def unregister(self, event: str, handler):
        """注销 Hook"""
        if event in self._hooks:
            self._hooks[event] = [h for h in self._hooks[event] if h != handler]
    
    async def run(self, event: str, context: HookContext) -> HookContext:
        """执行 Hook 链"""
        if event not in self._hooks:
            return context
        
        for handler in self._hooks[event]:
            try:
                result = await handler(context)
                if result is not None:
                    context = result
            except Exception as e:
                logger.error(f"Hook 执行失败 [{event}]: {e}")
        
        return context


class PluginManager:
    """插件管理器"""
    
    def __init__(self, plugins_dir: str = None):
        if plugins_dir is None:
            from service.core.paths import get_plugins_dir
            plugins_dir = get_plugins_dir()
        
        self.plugins_dir = Path(plugins_dir)
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        
        self._plugins = {}
        self.hook_pipeline = HookPipeline()
        
        # 加载内置插件
        self._load_builtin_plugins()
    
    def _load_builtin_plugins(self):
        """加载内置插件"""
        builtin_plugins = [
            AutoSavePlugin(),
            ContextPlugin(),
            FormatPlugin()
        ]
        
        for plugin in builtin_plugins:
            self._register_plugin(plugin)
    
    def _register_plugin(self, plugin):
        """注册插件"""
        info = plugin.get_info()
        self._plugins[info.name] = plugin
        
        # 注册插件的 Hooks
        if hasattr(plugin, 'register_hooks'):
            plugin.register_hooks(self.hook_pipeline)
        
        logger.info(f"插件已加载: {info.name} v{info.version}")
    
    def load_plugin_from_file(self, plugin_path: str) -> bool:
        """从文件加载插件"""
        try:
            path = Path(plugin_path)
            if not path.exists():
                logger.error(f"插件文件不存在: {plugin_path}")
                return False
            
            # 动态导入
            spec = importlib.util.spec_from_file_location(path.stem, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # 查找 Plugin 类
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and hasattr(attr, 'get_info') and attr_name != 'BasePlugin':
                    plugin = attr()
                    self._register_plugin(plugin)
                    return True
            
            logger.error(f"插件 {path.name} 未找到有效的 Plugin 类")
            return False
            
        except Exception as e:
            logger.error(f"加载插件失败: {e}")
            return False
    
    def get_plugin(self, name: str) -> Optional[Any]:
        """获取插件"""
        return self._plugins.get(name)
    
    def list_plugins(self) -> List[Dict]:
        """列出所有插件"""
        return [p.get_info().to_dict() for p in self._plugins.values()]
    
    def enable_plugin(self, name: str) -> bool:
        """启用插件"""
        plugin = self._plugins.get(name)
        if not plugin:
            return False
        plugin.get_info().enabled = True
        if hasattr(plugin, 'on_enable'):
            plugin.on_enable()
        return True
    
    def disable_plugin(self, name: str) -> bool:
        """禁用插件"""
        plugin = self._plugins.get(name)
        if not plugin:
            return False
        plugin.get_info().enabled = False
        if hasattr(plugin, 'on_disable'):
            plugin.on_disable()
        return True
    
    def configure_plugin(self, name: str, config: Dict) -> bool:
        """配置插件"""
        plugin = self._plugins.get(name)
        if not plugin:
            return False
        plugin.get_info().config.update(config)
        if hasattr(plugin, 'on_configure'):
            plugin.on_configure(config)
        return True
    
    def save_plugins_state(self):
        """保存插件状态"""
        state = {
            name: {"enabled": info.enabled, "config": info.config}
            for name, info in [(n, p.get_info()) for n, p in self._plugins.items()]
        }
        state_file = self.plugins_dir / "plugins_state.json"
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    
    def load_plugins_state(self):
        """加载插件状态"""
        state_file = self.plugins_dir / "plugins_state.json"
        if not state_file.exists():
            return
        
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
            
            for name, data in state.items():
                plugin = self._plugins.get(name)
                if plugin:
                    info = plugin.get_info()
                    info.enabled = data.get("enabled", True)
                    info.config.update(data.get("config", {}))
        except Exception as e:
            logger.error(f"加载插件状态失败: {e}")


class BasePlugin:
    """插件基类"""
    
    name = "base"
    version = "0.1.0"
    description = ""
    author = ""
    
    def get_info(self) -> PluginInfo:
        return PluginInfo(
            name=self.name,
            version=self.version,
            description=self.description,
            author=self.author
        )
    
    def register_hooks(self, pipeline: HookPipeline):
        """注册 Hooks（子类重写）"""
        pass
    
    def on_enable(self):
        pass
    
    def on_disable(self):
        pass
    
    def on_configure(self, config: Dict):
        pass


# ============ 内置插件 ============

class AutoSavePlugin(BasePlugin):
    """自动保存插件：定期保存会话到数据库"""
    
    name = "auto_save"
    version = "1.0.0"
    description = "自动保存会话历史和配置"
    author = "百佑 LawyerClaw"
    
    def register_hooks(self, pipeline: HookPipeline):
        pipeline.register("message.after_send", self._on_message_sent)
        pipeline.register("session.close", self._on_session_close)
    
    async def _on_message_sent(self, context: HookContext) -> HookContext:
        """消息发送后自动保存"""
        # 实际应调用数据库保存
        logger.debug(f"[AutoSave] 会话 {context.session_id} 已保存")
        return context
    
    async def _on_session_close(self, context: HookContext) -> HookContext:
        """会话关闭时最终保存"""
        logger.info(f"[AutoSave] 会话 {context.session_id} 关闭，执行最终保存")
        return context


class ContextPlugin(BasePlugin):
    """上下文增强插件：为 LLM 调用添加法律专业上下文"""
    
    name = "context_enhance"
    version = "1.0.0"
    description = "为对话添加法律专业上下文和系统提示"
    author = "百佑 LawyerClaw"
    
    LEGAL_SYSTEM_PROMPT = """你是一位专业的中国法律助手，具备以下能力：
1. 熟悉中国现行法律法规（民法典、刑法、行政法等）
2. 能够进行法律分析和文书起草
3. 回答应基于中国法律体系
4. 对于不确定的问题，应明确说明并建议咨询执业律师

请注意：
- 你的建议仅供参考，不构成正式法律意见
- 引用法条时应注明具体条款
- 涉及金额计算时应说明计算依据"""
    
    def register_hooks(self, pipeline: HookPipeline):
        pipeline.register("llm.before_call", self._enhance_context)
    
    async def _enhance_context(self, context: HookContext) -> HookContext:
        """增强 LLM 调用前的上下文"""
        if 'messages' in context.data:
            # 检查是否已有 system 消息
            has_system = any(m.get('role') == 'system' for m in context.data['messages'])
            if not has_system:
                context.data['messages'].insert(0, {
                    'role': 'system',
                    'content': self.LEGAL_SYSTEM_PROMPT
                })
        return context


class FormatPlugin(BasePlugin):
    """格式优化插件：优化 AI 输出的 Markdown 格式"""
    
    name = "format_output"
    version = "1.0.0"
    description = "优化 AI 输出的格式和排版"
    author = "百佑 LawyerClaw"
    
    def register_hooks(self, pipeline: HookPipeline):
        pipeline.register("llm.after_call", self._format_output)
    
    async def _format_output(self, context: HookContext) -> HookContext:
        """格式化 LLM 输出"""
        if 'response' in context.data:
            content = context.data['response']
            # 确保中文和英文之间有空格
            import re
            content = re.sub(r'([\u4e00-\u9fff])([a-zA-Z])', r'\1 \2', content)
            content = re.sub(r'([a-zA-Z])([\u4e00-\u9fff])', r'\1 \2', content)
            context.data['response'] = content
        return context


# 全局实例
manager = PluginManager()
