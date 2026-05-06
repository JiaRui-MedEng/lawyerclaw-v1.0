#!/usr/bin/env python3
"""
加载 ClawHub Skills 到数据库

功能:
1. 扫描 backend/skills/ 目录
2. 读取每个 skill 的 SKILL.md
3. 解析 frontmatter 获取元数据
4. 保存到 skills 表
5. 创建 FTS5 索引
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re
import yaml
from pathlib import Path
from datetime import datetime

# 导入 Flask app
from app import create_app
from service.models.database import db, Skill

# Skills 目录
SKILLS_DIR = Path("/mnt/d/Projects/Pycharm/lawyerclaw/backend/skills")

def parse_frontmatter(content: str) -> dict:
    """解析 YAML frontmatter"""
    if not content.startswith('---'):
        return {}
    
    try:
        end_match = re.search(r'\n---\s*\n', content[3:])
        if not end_match:
            return {}
        
        yaml_content = content[3:end_match.start() + 3]
        frontmatter = yaml.safe_load(yaml_content)
        
        return frontmatter if isinstance(frontmatter, dict) else {}
    except Exception as e:
        print(f"  ⚠️  解析 frontmatter 失败：{e}")
        return {}

def load_skills_to_db():
    """加载 skills 到数据库"""
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("📦 加载 ClawHub Skills 到数据库")
        print("=" * 60)
        
        # 统计
        stats = {
            "total": 0,
            "loaded": 0,
            "skipped": 0,
            "errors": 0,
            "skills": []
        }
        
        # 扫描 skills 目录
        skill_dirs = [d for d in SKILLS_DIR.iterdir() if d.is_dir() and not d.name.startswith('.')]
        stats["total"] = len(skill_dirs)
        
        print(f"\n📂 找到 {len(skill_dirs)} 个技能目录\n")
        
        for skill_dir in sorted(skill_dirs):
            try:
                skill_md = skill_dir / "SKILL.md"
                
                if not skill_md.exists():
                    print(f"  ⏭️  跳过：{skill_dir.name} (无 SKILL.md)")
                    stats["skipped"] += 1
                    continue
                
                # 读取 SKILL.md
                content = skill_md.read_text(encoding='utf-8')
                
                # 解析 frontmatter
                frontmatter = parse_frontmatter(content)
                
                # 提取元数据
                name = frontmatter.get('name', skill_dir.name)
                description = frontmatter.get('description', '')
                category = frontmatter.get('category', 'clawhub')
                version = frontmatter.get('version', '1.0.0')
                license_ = frontmatter.get('license', 'MIT')
                
                # 检查是否已存在
                existing = Skill.query.filter_by(name=name).first()
                
                if existing:
                    print(f"  ⏭️  已存在：{name} (ID: {existing.id})")
                    stats["skipped"] += 1
                    continue
                
                # 创建 skill 记录
                skill = Skill(
                    name=name,
                    description=description[:500] if description else '',  # 限制长度
                    category=category,
                    content=content,
                    is_active=True
                )
                
                db.session.add(skill)
                db.session.commit()
                
                print(f"  ✅ 已加载：{name}")
                stats["loaded"] += 1
                stats["skills"].append({
                    "name": name,
                    "description": description[:100],
                    "category": category,
                    "version": version
                })
                
            except Exception as e:
                print(f"  ❌ 失败：{skill_dir.name} - {e}")
                stats["errors"] += 1
                db.session.rollback()
        
        # 创建 FTS5 索引
        print("\n🔍 创建 FTS5 索引...")
        try:
            conn = db.engine.raw_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS skills_fts USING fts5(
                    name,
                    description,
                    content,
                    content=skills,
                    content_rowid=id
                )
            """)
            
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS skills_fts_insert 
                AFTER INSERT ON skills 
                BEGIN
                    INSERT INTO skills_fts(rowid, name, description, content) 
                    VALUES (new.id, new.name, new.description, new.content);
                END
            """)
            
            conn.commit()
            cursor.close()
            conn.close()
            
            print("  ✅ FTS5 索引已创建")
            
        except Exception as e:
            print(f"  ⚠️  FTS5 索引创建失败：{e}")
        
        # 打印统计
        print("\n" + "=" * 60)
        print("📊 加载统计:")
        print(f"  总技能数：{stats['total']}")
        print(f"  成功加载：{stats['loaded']}")
        print(f"  已存在：{stats['skipped']}")
        print(f"  失败：{stats['errors']}")
        
        # 列出所有 skills
        print("\n" + "=" * 60)
        print("📚 已加载的 Skills 列表:\n")
        
        for i, skill in enumerate(stats["skills"], 1):
            print(f"  {i:2d}. {skill['name']}")
            print(f"      描述：{skill['description'][:80]}...")
            print(f"      分类：{skill['category']}")
            print()
        
        print("=" * 60)
        print("✅ Skills 加载完成！现在可以在对话中使用了。")
        
        return stats

if __name__ == '__main__':
    load_skills_to_db()
