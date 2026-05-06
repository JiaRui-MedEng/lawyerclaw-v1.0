---
name: clawhub-skills-integration
description: 从 ClawHub 下载并集成 skills 到百佑 LawyerClaw 项目的完整流程。包括解压、加载到数据库、FTS5 索引创建。Use when user wants to install new skills from ClawHub or integrate external skills into 百佑 LawyerClaw.
version: 1.0.0
category: integration
license: MIT
---

# ClawHub Skills 集成流程

## 触发条件

当用户想要：
- 从 ClawHub 下载并安装新的 skills
- 将外部 skills 集成到百佑 LawyerClaw 项目
- 批量加载 skills 到数据库

## 完整流程

### 步骤 1: 下载 Skills 压缩包

```bash
# 从 ClawHub 下载 skills 压缩包
# 保存到 backend/skills-zip/ 目录
```

### 步骤 2: 解压到 Skills 目录

```python
#!/usr/bin/env python3
"""批量解压 ClawHub Skills 压缩包"""
import zipfile
import re
from pathlib import Path

SKILLS_ZIP_DIR = Path("backend/skills-zip")
SKILLS_TARGET_DIR = Path("backend/skills")

# 获取所有 zip 文件 (排除主项目)
zip_files = [f for f in SKILLS_ZIP_DIR.glob("*.zip") if "hermes-agent-main" not in f.name]

for zip_file in sorted(zip_files):
    # 从 zip 文件名提取技能名称
    name_parts = zip_file.stem.split('-')
    skill_name = zip_file.stem
    
    # 移除版本号
    for i in range(len(name_parts) - 1, -1, -1):
        if re.match(r'^\d+(\.\d+)*$', name_parts[i]):
            skill_name = '-'.join(name_parts[:i])
        else:
            break
    
    # 创建技能目录
    target_dir = SKILLS_TARGET_DIR / skill_name
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # 解压文件
    with zipfile.ZipFile(zip_file, 'r') as zf:
        for member in zf.namelist():
            if member.endswith('/'):
                continue
            source = zf.open(member)
            target_path = target_dir / Path(member).name
            with open(target_path, 'wb') as target:
                target.write(source.read())
```

### 步骤 3: 加载 Skills 到数据库

```python
#!/usr/bin/env python3
"""加载 Skills 到数据库"""
import sys
import os
import re
import yaml
from pathlib import Path

# 导入 Flask app
import importlib.util
spec = importlib.util.spec_from_file_location("app_main", "app.py")
app_main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app_main)
create_app = app_main.create_app

from app.models.database_enhanced import db, Skill

SKILLS_DIR = Path("backend/skills")

def parse_frontmatter(content):
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
    except:
        return {}

app = create_app()

with app.app_context():
    skill_dirs = [d for d in SKILLS_DIR.iterdir() 
                  if d.is_dir() and not d.name.startswith('.')]
    
    for skill_dir in sorted(skill_dirs):
        skill_md = skill_dir / "SKILL.md"
        
        if not skill_md.exists():
            continue
        
        # 检查是否已存在
        content = skill_md.read_text(encoding='utf-8')
        frontmatter = parse_frontmatter(content)
        
        name = frontmatter.get('name', skill_dir.name)
        existing = Skill.query.filter_by(name=name).first()
        
        if existing:
            print(f"⏭️  已存在：{name}")
            continue
        
        # 创建 skill 记录
        skill = Skill(
            name=name,
            description=frontmatter.get('description', '')[:500],
            category=frontmatter.get('category', 'clawhub'),
            content=content,
            is_active=True
        )
        
        db.session.add(skill)
        db.session.commit()
        print(f"✅ 已加载：{name}")
```

### 步骤 4: 创建 FTS5 索引

```python
# 在加载 skills 后创建 FTS5 索引
conn = db.engine.raw_connection()
cursor = conn.cursor()

# 创建 FTS5 虚拟表
cursor.execute("""
    CREATE VIRTUAL TABLE IF NOT EXISTS skills_fts USING fts5(
        name, description, content,
        content=skills, content_rowid=id
    )
""")

# 创建触发器
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
```

## 验证安装

```bash
# 检查 skills 目录
ls -la backend/skills/

# 检查数据库中的 skills
python3 -c "
from app import create_app
from app.models.database_enhanced import db, Skill

app = create_app()
with app.app_context():
    skills = Skill.query.all()
    print(f'共有 {len(skills)} 个 skills')
    for s in skills[:10]:
        print(f'  - {s.name} ({s.category})')
"
```

## 使用方式

Skills 加载后，在对话中会自动触发：

```
用户：帮我查询劳动法关于加班费的规定
AI: [自动调用 china-legal-query skill]
    根据《中华人民共和国劳动法》第四十四条...

用户：帮我起草一份技术服务合同
AI: [自动调用 contract-generator skill]
    好的，我来帮您生成一份技术服务合同...
```

## 常见问题

### 问题 1: Import Error - cannot import 'create_app'

**原因:** `app` 是包名，`app.py` 是模块名

**解决:**
```python
# 错误写法
from app import create_app

# 正确写法
import importlib.util
spec = importlib.util.spec_from_file_location("app_main", "app.py")
app_main = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app_main)
create_app = app_main.create_app
```

### 问题 2: ModuleNotFoundError: No module named 'flask'

**原因:** 未安装 Flask 依赖

**解决:**
```bash
pip install flask flask-sqlalchemy pyyaml
```

### 问题 3: 无法初始化设备 PRN

**原因:** Windows 系统保留设备名冲突

**解决:**
- 重启终端或 WSL: `wsl --shutdown`
- 或在 Linux 环境下继续操作（不受影响）

### 问题 4: Skills 未加载到数据库

**症状:** 对话中 AI 没有调用 skills

**解决:**
1. 检查 skills 目录是否有 SKILL.md 文件
2. 运行加载脚本
3. 重启后端服务

## 技能统计

成功安装后，查看技能列表：

```python
with app.app_context():
    skills = Skill.query.all()
    print(f"总技能数：{len(skills)}")
    
    # 按分类统计
    from collections import Counter
    categories = Counter(s.category for s in skills)
    for cat, count in categories.items():
        print(f"  {cat}: {count}个")
```

## 注意事项

1. **Skills 文件是只读的**: ClawHub 下载的 skills 不要直接修改
2. **自动触发**: Skills 在对话中自动触发，无需手动启用
3. **技能冲突**: 多个 skills 匹配时，AI 选择最相关的一个
4. **数据库必需**: Skills 文件需要加载到数据库才能被检索
5. **FTS5 索引**: 创建索引后支持全文搜索，提高检索准确性

## 相关文件

- `backend/skills-zip/` - Skills 压缩包目录
- `backend/skills/` - Skills 安装目录
- `backend/data/lawyerclaw.db` - 数据库文件
- `backend/check_and_load_skills.py` - 加载脚本
- `docs/CLAWHUB_SKILLS_USAGE.md` - 使用指南
