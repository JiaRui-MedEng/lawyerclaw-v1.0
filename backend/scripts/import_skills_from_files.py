#!/usr/bin/env python3
"""
批量导入 Skills 到数据库

从 backend/skills/ 目录读取所有 SKILL.md 文件，导入到 skills 表。
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from service.models.database import db, Skill, app
from service.self_evolution.skills import SkillManager

# 解析 SKILL.md 的 frontmatter
def parse_frontmatter(content: str):
    """解析 YAML frontmatter"""
    import re
    
    if not content.startswith('---'):
        return {}, content
    
    # 查找 frontmatter 结束位置
    match = re.search(r'\n---\s*\n', content[3:])
    if not match:
        return {}, content
    
    yaml_content = content[3:match.start() + 3]
    
    # 简单解析 YAML（不依赖 yaml 库）
    frontmatter = {}
    for line in yaml_content.split('\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip().strip('"\'')
            
            # 处理列表
            if value.startswith('[') and value.endswith(']'):
                value = [v.strip() for v in value[1:-1].split(',')]
            
            frontmatter[key] = value
    
    body = content[match.end() + 4:].strip()
    return frontmatter, body


def import_skills():
    """导入所有技能"""
    
    skills_dir = Path(__file__).parent.parent / 'skills'
    
    if not skills_dir.exists():
        print(f"❌ Skills 目录不存在：{skills_dir}")
        return
    
    print(f"📂 扫描目录：{skills_dir}")
    
    imported_count = 0
    skipped_count = 0
    error_count = 0
    
    with app.app_context():
        # 遍历所有技能目录
        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            
            # 跳过特殊目录
            if skill_dir.name.startswith('.') or skill_dir.name == '__pycache__':
                continue
            
            skill_file = skill_dir / 'SKILL.md'
            
            if not skill_file.exists():
                print(f"⚠️  跳过 {skill_dir.name}（无 SKILL.md）")
                skipped_count += 1
                continue
            
            # 检查是否已存在
            existing = Skill.query.filter_by(name=skill_dir.name).first()
            if existing:
                print(f"⚠️  跳过 {skill_dir.name}（已存在于数据库）")
                skipped_count += 1
                continue
            
            try:
                # 读取文件
                content = skill_file.read_text(encoding='utf-8')
                frontmatter, body = parse_frontmatter(content)
                
                # 创建技能记录
                skill = Skill(
                    name=skill_dir.name,
                    description=frontmatter.get('description', ''),
                    category=frontmatter.get('category', 'general'),
                    content=content  # 保存完整内容（包含 frontmatter）
                )
                
                db.session.add(skill)
                imported_count += 1
                print(f"✅ 导入：{skill_dir.name}")
                
            except Exception as e:
                error_count += 1
                print(f"❌ 错误 {skill_dir.name}: {e}")
        
        # 提交事务
        db.session.commit()
    
    print("\n" + "="*50)
    print(f"✅ 导入完成！")
    print(f"   成功：{imported_count} 个")
    print(f"   跳过：{skipped_count} 个")
    print(f"   错误：{error_count} 个")
    print("="*50)


if __name__ == '__main__':
    import_skills()
