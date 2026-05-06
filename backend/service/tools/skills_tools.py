"""
Skills 工具 - 提供技能查询和管理功能
类似 Hermes-Agent 的 skills_tool.py
"""
import logging
from typing import Any, Dict
from dataclasses import dataclass

from service.tools.legal_tools import BaseTool, ToolResult

logger = logging.getLogger(__name__)


@dataclass
class SkillsListTool(BaseTool):
    """列出所有可用技能"""
    
    name = "skills_list"
    description = "列出所有可用的技能。当用户询问\"有哪些技能\"、\"你能做什么\"或需要了解系统能力时使用。支持按分类筛选。"
    parameters = {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": "可选，按分类筛选（如：legal, patent, marketing）"
            },
            "verbose": {
                "type": "boolean",
                "description": "是否显示详细信息（包括路径、内容长度等）",
                "default": False
            }
        },
        "required": []
    }
    
    async def execute(self, category: str = None, verbose: bool = False) -> ToolResult:
        """执行技能列表查询"""
        try:
            from service.self_evolution.skills_enhanced import SkillsListTool as InnerTool
            
            tool = InnerTool()
            result = tool.skills_list(category=category, verbose=verbose)
            
            # 格式化为可读文本
            content = self._format_result(result)
            
            return ToolResult(
                success=True,
                content=content,
                data=result
            )
        except Exception as e:
            logger.error(f"Skills list 执行失败：{e}")
            return ToolResult(
                success=False,
                content=f"查询技能失败：{e}",
                error=str(e)
            )
    
    def _format_result(self, result: Dict[str, Any]) -> str:
        """格式化结果为可读文本"""
        if not result.get('success'):
            return result.get('error', '未知错误')
        
        lines = []
        lines.append(f"# 可用技能列表\n")
        lines.append(f"共找到 **{result.get('total', 0)}** 个技能\n")
        
        categories = result.get('categories', [])
        skills_by_category = result.get('skills_by_category', {})
        
        for cat in categories:
            skills = skills_by_category.get(cat, [])
            if not skills:
                continue
            
            lines.append(f"\n## {cat.upper()} ({len(skills)} 个)\n")
            
            for skill in skills:
                name = skill.get('name', 'Unknown')
                desc = skill.get('description', '无描述')
                lines.append(f"- **{name}**: {desc}")
        
        return "\n".join(lines)


@dataclass
class CheckSkillReadinessTool(BaseTool):
    """检查技能是否就绪"""
    
    name = "check_skill_readiness"
    description = "检查指定技能的依赖是否满足（环境变量、命令等）。在安装或使用技能前调用，确保技能可以正常运行。"
    parameters = {
        "type": "object",
        "properties": {
            "skill_name": {
                "type": "string",
                "description": "技能名称"
            }
        },
        "required": ["skill_name"]
    }
    
    async def execute(self, skill_name: str) -> ToolResult:
        """执行技能就绪检查"""
        try:
            from service.self_evolution.skills_enhanced import SkillsListTool as InnerTool
            
            tool = InnerTool()
            result = tool.check_skill_readiness(skill_name)
            
            # 格式化为可读文本
            content = self._format_result(result)
            
            return ToolResult(
                success=result.get('success', False),
                content=content,
                data=result
            )
        except Exception as e:
            logger.error(f"Check skill readiness 执行失败：{e}")
            return ToolResult(
                success=False,
                content=f"检查技能失败：{e}",
                error=str(e)
            )
    
    def _format_result(self, result: Dict[str, Any]) -> str:
        """格式化结果为可读文本"""
        if not result.get('success'):
            return result.get('error', '未知错误')
        
        lines = []
        skill_name = result.get('skill_name', 'Unknown')
        is_ready = result.get('is_ready', False)
        
        if is_ready:
            lines.append(f"# ✅ {skill_name} 已就绪\n")
            lines.append("所有依赖都已满足，可以正常使用。")
        else:
            lines.append(f"# ⚠️ {skill_name} 缺少依赖\n")
            lines.append("以下依赖未满足：\n")
            
            for item in result.get('missing', []):
                lines.append(f"- ❌ {item.get('message', '')}")
        
        warnings = result.get('warnings', [])
        if warnings:
            lines.append("\n## 警告\n")
            for w in warnings:
                lines.append(f"- ⚠️ {w.get('message', '')}")
        
        return "\n".join(lines)


@dataclass
class GetSkillInfoTool(BaseTool):
    """获取技能详细信息"""
    
    name = "get_skill_info"
    description = "获取指定技能的详细信息，包括描述、分类、版本、依赖、平台要求等。"
    parameters = {
        "type": "object",
        "properties": {
            "skill_name": {
                "type": "string",
                "description": "技能名称"
            }
        },
        "required": ["skill_name"]
    }
    
    async def execute(self, skill_name: str) -> ToolResult:
        """执行技能信息查询"""
        try:
            from service.self_evolution.skills_enhanced import SkillsListTool as InnerTool
            
            tool = InnerTool()
            result = tool.get_skill_info(skill_name)
            
            # 格式化为可读文本
            content = self._format_result(result)
            
            return ToolResult(
                success=result.get('success', False),
                content=content,
                data=result
            )
        except Exception as e:
            logger.error(f"Get skill info 执行失败：{e}")
            return ToolResult(
                success=False,
                content=f"获取技能信息失败：{e}",
                error=str(e)
            )
    
    def _format_result(self, result: Dict[str, Any]) -> str:
        """格式化结果为可读文本"""
        if not result.get('success'):
            return result.get('error', '未知错误')
        
        skill = result.get('skill', {})
        
        lines = []
        lines.append(f"# {skill.get('name', 'Unknown')}\n")
        lines.append(f"**描述**: {skill.get('description', '无描述')}\n")
        lines.append(f"**分类**: {skill.get('category', 'general')}\n")
        lines.append(f"**版本**: {skill.get('version', '1.0.0')}\n")
        lines.append(f"**路径**: `{skill.get('path', '')}`\n")
        lines.append(f"**预估 Token 数**: {skill.get('estimated_tokens', 0)}\n")
        
        # 依赖信息
        prereqs = skill.get('prerequisites', {})
        if prereqs:
            lines.append("\n## 前置要求\n")
            commands = prereqs.get('commands', [])
            if commands:
                lines.append(f"**命令**: {', '.join(commands)}")
            env_vars = prereqs.get('env_vars', [])
            if env_vars:
                lines.append(f"**环境变量**: {', '.join(env_vars)}")
        
        # 环境变量
        req_env = skill.get('required_environment_variables', [])
        if req_env:
            lines.append("\n## 需要的环境变量\n")
            for env in req_env:
                if isinstance(env, dict):
                    lines.append(f"- **{env.get('name', '')}**: {env.get('prompt', '')}")
                else:
                    lines.append(f"- {env}")
        
        # 平台
        platforms = skill.get('platforms', [])
        if platforms:
            lines.append("\n## 支持平台\n")
            lines.append(f"{', '.join(platforms)}")
        
        # 内容预览
        content_preview = skill.get('content_preview', '')
        if content_preview:
            lines.append("\n## 内容预览\n")
            lines.append(content_preview)
        
        return "\n".join(lines)


# 导出工具实例
skills_list_tool = SkillsListTool()
check_skill_readiness_tool = CheckSkillReadinessTool()
get_skill_info_tool = GetSkillInfoTool()

# 工具列表（用于批量注册）
SKILLS_TOOLS = [
    skills_list_tool,
    check_skill_readiness_tool,
    get_skill_info_tool,
]
