"""
百佑 LawyerClaw 技能管理模块
基于 SQLAlchemy + 文件系统
"""
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import yaml

from service.models.database import db, Skill

logger = logging.getLogger(__name__)


class SkillManager:
    """技能管理器 - 文件系统版本（类似 Hermes-Agent）"""
    
    def __init__(self, skills_dir: str = None):
        # 默认从 backend/skills/ 目录读取
        if skills_dir:
            self.skills_dir = Path(skills_dir).expanduser()
        else:
            # 自动定位到 backend/skills/
            from service.core.paths import get_skills_dir
            self.skills_dir = get_skills_dir()
        
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Skills 目录：{self.skills_dir}")
    
    def create_skill(self, name: str, content: str, description: str = None, category: str = None) -> Dict[str, Any]:
        """创建技能"""
        # 验证名称
        if not self._validate_name(name):
            return {"success": False, "error": "Invalid skill name"}
        
        # 检查是否已存在
        existing = Skill.query.filter_by(name=name).first()
        if existing:
            return {"success": False, "error": f"Skill '{name}' already exists"}
        
        # 解析 frontmatter (如果有)
        frontmatter = self._parse_frontmatter(content)
        
        # 保存到数据库
        skill = Skill(
            name=name,
            description=description or frontmatter.get('description', ''),
            category=category or frontmatter.get('category', ''),
            content=content
        )
        
        db.session.add(skill)
        db.session.commit()
        
        logger.info(f"技能已创建：{name}, id={skill.id}")
        
        return {
            "success": True,
            "skill_id": skill.id,
            "name": name,
            "message": f"Skill '{name}' created successfully"
        }
    
    def patch_skill(self, name: str, old_string: str, new_string: str) -> Dict[str, Any]:
        """修补技能"""
        skill = Skill.query.filter_by(name=name).first()
        if not skill:
            return {"success": False, "error": f"Skill '{name}' not found"}
        
        if old_string not in skill.content:
            return {
                "success": False,
                "error": "old_string not found in skill content"
            }
        
        skill.content = skill.content.replace(old_string, new_string, 1)
        skill.updated_at = datetime.now()
        db.session.commit()
        
        logger.info(f"技能已修补：{name}")
        
        return {"success": True, "message": f"Skill '{name}' patched"}
    
    def _parse_frontmatter(self, content: str) -> Tuple[Dict[str, Any], str]:
        """解析 YAML frontmatter"""
        import re
        
        if not content.startswith('---'):
            return {}, content
        
        # 查找 frontmatter 结束位置
        match = re.search(r'\n---\s*(\n|$)', content[3:])
        if not match:
            return {}, content
        
        yaml_content = content[3:match.start() + 3]
        
        # 简单解析 YAML（不依赖 yaml 库）
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
        
        # 遍历所有子目录
        for skill_dir in self.skills_dir.iterdir():
            # 跳过非目录和特殊目录
            if not skill_dir.is_dir():
                continue
            if skill_dir.name.startswith('.') or skill_dir.name == '__pycache__':
                continue
            
            # 查找 SKILL.md
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
                    'content': content,  # 完整内容（包含 frontmatter）
                    'path': str(skill_file),
                    'dir': str(skill_dir),
                })
            except Exception as e:
                logger.error(f"读取技能失败 {skill_dir.name}: {e}")
        
        logger.info(f"扫描到 {len(skills)} 个技能")
        return skills
    
    def load_skills(self, category: str = None) -> List[Dict[str, Any]]:
        """加载技能（从文件系统）"""
        all_skills = self._scan_skills_directory()
        
        if category:
            all_skills = [s for s in all_skills if s.get('category') == category]
        
        return all_skills
    
    def get_relevant_skills(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """获取相关技能（从文件系统扫描 + 关键词匹配）"""
        # 扫描文件系统获取所有技能
        all_skills = self._scan_skills_directory()
        
        if not all_skills:
            logger.warning("未找到任何技能")
            return []
        
        # 关键词匹配评分
        scored = []
        query_lower = query.lower()
        
        for skill in all_skills:
            score = 0
            
            # 名称匹配（最高优先级）
            if query_lower in skill['name'].lower():
                score += 10
            
            # 描述匹配（高优先级）
            if skill.get('description') and query_lower in skill['description'].lower():
                score += 5
            
            # 分类匹配
            if skill.get('category') and query_lower in skill['category'].lower():
                score += 3
            
            # 内容匹配（低优先级）
            if skill.get('content') and query_lower in skill['content'].lower():
                score += 1
            
            if score > 0:
                scored.append((score, skill))
        
        # 按分数排序
        scored.sort(key=lambda x: x[0], reverse=True)
        
        # 返回 top N
        result = [skill for _, skill in scored[:limit]]
        logger.info(f"匹配到 {len(result)} 个相关技能：{[s['name'] for s in result]}")
        return result
    
    def _validate_name(self, name: str) -> bool:
        """验证技能名"""
        if not name or len(name) > 100:
            return False
        
        pattern = re.compile(r'^[a-z0-9][a-z0-9._-]*$')
        return bool(pattern.match(name))
    
    def _parse_frontmatter(self, content: str) -> Dict[str, Any]:
        """解析 frontmatter"""
        if not content.startswith('---'):
            return {}
        
        try:
            end_match = re.search(r'\n---\s*\n', content[3:])
            if not end_match:
                return {}
            
            yaml_content = content[3:end_match.start() + 3]
            return yaml.safe_load(yaml_content)
        except:
            return {}
    
    def get_tool_schema(self) -> Dict[str, Any]:
        """获取 skill_manage 工具 schema"""
        return {
            "name": "skill_manage",
            "description": "Create, update, or delete skills",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["create", "patch", "delete"],
                        "description": "Action to perform"
                    },
                    "name": {
                        "type": "string",
                        "description": "Skill name"
                    },
                    "content": {
                        "type": "string",
                        "description": "Skill content (for create)"
                    },
                    "description": {
                        "type": "string",
                        "description": "Skill description"
                    },
                    "category": {
                        "type": "string",
                        "description": "Skill category"
                    },
                    "old_string": {
                        "type": "string",
                        "description": "Text to find (for patch)"
                    },
                    "new_string": {
                        "type": "string",
                        "description": "Replacement text (for patch)"
                    }
                },
                "required": ["action", "name"]
            }
        }
    
    def handle_tool_call(self, args: Dict[str, Any]) -> str:
        """处理 skill_manage 工具调用"""
        action = args.get('action')
        name = args.get('name')
        
        if action == 'create':
            result = self.create_skill(
                name=name,
                content=args.get('content', ''),
                description=args.get('description'),
                category=args.get('category')
            )
        elif action == 'patch':
            result = self.patch_skill(
                name=name,
                old_string=args.get('old_string', ''),
                new_string=args.get('new_string', '')
            )
        elif action == 'delete':
            # 简化版暂不支持删除
            result = {"success": False, "error": "Delete not implemented yet"}
        else:
            result = {"success": False, "error": f"Unknown action: {action}"}
        
        return json.dumps(result, ensure_ascii=False)
    
    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """搜索技能"""
        skills = Skill.query.filter(
            db.or_(
                Skill.name.like(f'%{query}%'),
                Skill.description.like(f'%{query}%'),
                Skill.content.like(f'%{query}%')
            )
        ).limit(limit).all()
        
        return [s.to_dict() for s in skills]
