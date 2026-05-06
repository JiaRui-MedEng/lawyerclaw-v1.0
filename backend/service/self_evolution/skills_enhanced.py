"""
百佑 LawyerClaw 技能管理增强模块
添加类似 Hermes-Agent 的 skills_list 工具和技能就绪检查
"""
import json
import logging
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class SkillsListTool:
    """Skills List 工具 - 提供技能查询功能"""
    
    def __init__(self, skills_dir: str = None):
        if skills_dir:
            self.skills_dir = Path(skills_dir).expanduser()
        else:
            from service.core.paths import get_skills_dir
            self.skills_dir = get_skills_dir()
        
        self.skills_dir.mkdir(parents=True, exist_ok=True)
    
    def _parse_frontmatter(self, content: str) -> Tuple[Dict[str, Any], str]:
        """解析 YAML frontmatter"""
        if not content.startswith('---'):
            return {}, content
        
        match = re.search(r'\n---\s*(\n|$)', content[3:])
        if not match:
            return {}, content
        
        yaml_content = content[3:match.start() + 3]
        frontmatter = {}
        
        for line in yaml_content.split('\n'):
            line = line.strip()
            if not line or ':' not in line:
                continue
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip().strip('"\'')
            if not key:
                continue
            
            # 处理列表
            if value.startswith('[') and value.endswith(']'):
                value = [v.strip().strip('"\'') for v in value[1:-1].split(',') if v.strip()]
            
            frontmatter[key] = value
        
        body = content[match.end() + 3:].strip()
        return frontmatter, body
    
    def _scan_skills_directory(self) -> List[Dict[str, Any]]:
        """扫描文件系统获取所有技能"""
        skills = []
        
        if not self.skills_dir.exists():
            logger.warning(f"Skills 目录不存在：{self.skills_dir}")
            return skills
        
        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            if skill_dir.name.startswith('.') or skill_dir.name == '__pycache__':
                continue
            
            skill_file = skill_dir / 'SKILL.md'
            if not skill_file.exists():
                continue
            
            try:
                content = skill_file.read_text(encoding='utf-8')
                frontmatter, body = self._parse_frontmatter(content)
                
                skills.append({
                    'name': frontmatter.get('name', skill_dir.name),
                    'description': frontmatter.get('description', ''),
                    'category': frontmatter.get('category', 'general'),
                    'content': content,
                    'path': str(skill_file),
                    'dir': str(skill_dir),
                })
            except Exception as e:
                logger.error(f"读取技能失败 {skill_dir.name}: {e}")
        
        logger.info(f"扫描到 {len(skills)} 个技能")
        return skills
    
    def _get_category_from_path(self, skill_path: Path) -> Optional[str]:
        """从路径提取分类"""
        try:
            rel_path = skill_path.relative_to(self.skills_dir)
            parts = rel_path.parts
            if len(parts) >= 2:
                return parts[0]  # 返回第一级目录
        except ValueError:
            pass
        return None
    
    def skills_list(self, category: str = None, verbose: bool = False) -> Dict[str, Any]:
        """
        列出所有可用技能（类似 Hermes-Agent 的 skills_list 工具）
        
        Args:
            category: 可选，按分类筛选
            verbose: 可选，是否显示详细信息
        
        Returns:
            技能列表 JSON
        """
        # 扫描所有技能
        all_skills = self._scan_skills_directory()
        
        if not all_skills:
            return {
                "success": True,
                "message": "未找到任何技能",
                "total": 0,
                "categories": [],
                "skills_by_category": {}
            }
        
        # 按分类组织
        by_category = {}
        for skill in all_skills:
            cat = skill.get('category', 'general')
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(skill)
        
        # 如果指定分类，只返回该分类
        if category:
            if category in by_category:
                by_category = {category: by_category[category]}
            else:
                return {
                    "success": True,
                    "message": f"未找到分类：{category}",
                    "total": 0,
                    "categories": [],
                    "skills_by_category": {}
                }
        
        # 构建返回结果
        result = {
            "success": True,
            "message": f"找到 {len(all_skills)} 个技能",
            "total": len(all_skills),
            "categories": sorted(by_category.keys()),
            "skills_by_category": {}
        }
        
        for cat in sorted(by_category.keys()):
            skills_in_cat = by_category[cat]
            result["skills_by_category"][cat] = [
                {
                    "name": skill['name'],
                    "description": skill.get('description', '')[:200],
                    "category": cat,
                }
                for skill in skills_in_cat
            ]
            
            # 如果详细模式，添加更多信息
            if verbose:
                for i, skill in enumerate(skills_in_cat):
                    result["skills_by_category"][cat][i]["path"] = skill.get('path', '')
                    result["skills_by_category"][cat][i]["content_length"] = len(skill.get('content', ''))
        
        return result
    
    def check_skill_readiness(self, skill_name: str) -> Dict[str, Any]:
        """
        检查技能是否就绪（依赖是否满足）
        
        Args:
            skill_name: 技能名称
        
        Returns:
            检查结果
        """
        # 查找技能
        all_skills = self._scan_skills_directory()
        skill = next((s for s in all_skills if s['name'] == skill_name), None)
        
        if not skill:
            return {
                "success": False,
                "error": f"未找到技能：{skill_name}"
            }
        
        # 解析 frontmatter 获取依赖
        frontmatter, _ = self._parse_frontmatter(skill.get('content', ''))
        
        missing = []
        warnings = []
        
        # 检查环境变量
        required_env = frontmatter.get('required_environment_variables', [])
        if isinstance(required_env, str):
            required_env = [required_env]
        
        for env_var in required_env:
            if isinstance(env_var, dict):
                env_name = env_var.get('name', '')
            else:
                env_name = env_var
            
            if env_name and not os.getenv(env_name):
                missing.append({
                    "type": "env_var",
                    "name": env_name,
                    "message": f"缺少环境变量：{env_name}"
                })
        
        # 检查命令
        prerequisites = frontmatter.get('prerequisites', {})
        commands = prerequisites.get('commands', []) if isinstance(prerequisites, dict) else []
        
        for cmd in commands:
            if not shutil.which(cmd):
                missing.append({
                    "type": "command",
                    "name": cmd,
                    "message": f"缺少命令：{cmd}"
                })
        
        # 检查平台兼容性
        platforms = frontmatter.get('platforms', [])
        if platforms:
            platform_map = {'darwin': 'macos', 'linux': 'linux', 'win32': 'windows'}
            current = platform_map.get(sys.platform, 'unknown')
            
            if current not in platforms:
                warnings.append({
                    "type": "platform",
                    "message": f"当前平台 {current} 不在支持列表中：{platforms}"
                })
        
        # 构建结果
        is_ready = len(missing) == 0
        
        return {
            "success": True,
            "skill_name": skill_name,
            "is_ready": is_ready,
            "missing": missing,
            "warnings": warnings,
            "message": "技能就绪" if is_ready else f"缺少 {len(missing)} 个依赖"
        }
    
    def get_skill_info(self, skill_name: str) -> Dict[str, Any]:
        """
        获取技能详细信息
        
        Args:
            skill_name: 技能名称
        
        Returns:
            技能详细信息
        """
        # 查找技能
        all_skills = self._scan_skills_directory()
        skill = next((s for s in all_skills if s['name'] == skill_name), None)
        
        if not skill:
            return {
                "success": False,
                "error": f"未找到技能：{skill_name}"
            }
        
        # 解析 frontmatter
        frontmatter, body = self._parse_frontmatter(skill.get('content', ''))
        
        # 估算 token 数
        content_length = len(skill.get('content', ''))
        estimated_tokens = content_length // 4
        
        return {
            "success": True,
            "skill": {
                "name": skill['name'],
                "description": frontmatter.get('description', ''),
                "category": frontmatter.get('category', 'general'),
                "version": frontmatter.get('version', '1.0.0'),
                "path": skill['path'],
                "content_preview": body[:500] + "..." if len(body) > 500 else body,
                "estimated_tokens": estimated_tokens,
                "prerequisites": frontmatter.get('prerequisites', {}),
                "required_environment_variables": frontmatter.get('required_environment_variables', []),
                "platforms": frontmatter.get('platforms', []),
            }
        }


# 工具函数（可以直接从 tools 导入使用）
def skills_list_tool(category: str = None, verbose: bool = False) -> str:
    """
    Skills List 工具函数（供 Agent 调用）
    
    Returns:
        JSON 字符串
    """
    tool = SkillsListTool()
    result = tool.skills_list(category=category, verbose=verbose)
    return json.dumps(result, ensure_ascii=False, indent=2)


def check_skill_readiness_tool(skill_name: str) -> str:
    """
    检查技能就绪工具函数（供 Agent 调用）
    
    Returns:
        JSON 字符串
    """
    tool = SkillsListTool()
    result = tool.check_skill_readiness(skill_name)
    return json.dumps(result, ensure_ascii=False, indent=2)


def get_skill_info_tool(skill_name: str) -> str:
    """
    获取技能信息工具函数（供 Agent 调用）
    
    Returns:
        JSON 字符串
    """
    tool = SkillsListTool()
    result = tool.get_skill_info(skill_name)
    return json.dumps(result, ensure_ascii=False, indent=2)
