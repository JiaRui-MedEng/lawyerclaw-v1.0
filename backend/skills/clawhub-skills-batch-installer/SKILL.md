---
name: clawhub-skills-batch-installer
description: Batch install skills from ClawHub zip files. Handles zip extraction, skill name parsing, duplicate detection, and manifest generation. Use when user downloads multiple skills from ClawHub and needs to install them all at once.
version: 1.0.0
license: MIT-0
metadata: {"openclaw": {"emoji": "📦", "requires": {"bins": ["python3"], "env": []}}}
---

# ClawHub Skills Batch Installer

批量安装 ClawHub 下载的 skills 压缩包。

## 触发条件

- 用户从 ClawHub 下载了多个 skills 压缩包
- 用户需要将 skills 整合到项目中
- 用户有 skills-zip 目录需要批量解压

## 执行步骤

### 1. 确认目录结构

```python
SKILLS_ZIP_DIR = Path("/path/to/skills-zip")
SKILLS_TARGET_DIR = Path("/path/to/backend/skills")
```

### 2. 扫描压缩包

```python
zip_files = [f for f in SKILLS_ZIP_DIR.glob("*.zip") 
             if "hermes-agent-main" not in f.name]
```

**注意:** 排除主项目压缩包 (hermes-agent-main.zip)

### 3. 解析技能名称

```python
# 从 zip 文件名提取技能名
# 格式：skill-name-version.zip → skill-name
name_parts = zip_file.stem.split('-')

# 移除版本号 (最后 1-2 个纯数字部分)
skill_name = zip_file.stem
for i in range(len(name_parts) - 1, -1, -1):
    part = name_parts[i]
    if re.match(r'^\d+(\.\d+)*$', part):
        skill_name = '-'.join(name_parts[:i])
    else:
        break
```

**常见格式:**
- `china-legal-query-1.0.2.zip` → `china-legal-query`
- `contract-review-pro-1.0.2.zip` → `contract-review-pro`
- `wechat-mp-writer-skill-mxx-1.0.0.zip` → `wechat-mp-writer`

### 4. 检查 SKILL.md 位置

**重要发现:** ClawHub skills 的 SKILL.md 在 zip 根目录，不在子目录中！

```python
with zipfile.ZipFile(zip_file, 'r') as zf:
    file_list = zf.namelist()
    skill_md_files = [f for f in file_list if f.endswith('SKILL.md')]
    
    # SKILL.md 在根目录
    # 直接提取所有文件到技能目录
```

### 5. 处理重复名称

```python
target_skill_dir = SKILLS_TARGET_DIR / skill_name

if target_skill_dir.exists():
    # 添加时间戳
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    skill_name = f"{skill_name}_{timestamp}"
    target_skill_dir = SKILLS_TARGET_DIR / skill_name
```

### 6. 解压到目标目录

```python
target_skill_dir.mkdir(parents=True, exist_ok=True)

with zipfile.ZipFile(zip_file, 'r') as zf:
    for member in zf.namelist():
        if member.endswith('/'):
            continue  # 跳过目录
        
        source = zf.open(member)
        target_path = target_skill_dir / Path(member).name
        
        with open(target_path, 'wb') as target:
            target.write(source.read())
```

### 7. 生成安装清单

```python
manifest = {
    "installed_at": datetime.now().isoformat(),
    "source_directory": str(SKILLS_ZIP_DIR),
    "total_installed": stats["successful"],
    "skills": stats["skills_installed"],
    "errors": stats["errors"]
}

# 保存为 JSON
with open(manifest_file, 'w', encoding='utf-8') as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)

# 生成 Markdown 列表
with open(skills_list_file, 'w', encoding='utf-8') as f:
    f.write("# 百佑 LawyerClaw 已安装 Skills 清单\n\n")
    for skill in sorted(stats["skills_installed"], key=lambda x: x["name"]):
        f.write(f"## {skill['name']}\n\n")
        f.write(f"- **来源:** {skill['source']}\n")
        f.write(f"- **路径:** `{skill['path']}`\n")
```

## 常见陷阱

### ⚠️ 陷阱 1: SKILL.md 位置假设错误

**错误:** 假设 SKILL.md 在子目录中

```python
# ❌ 错误：查找子目录中的 SKILL.md
skill_root_dirs = set()
for skill_md in skill_md_files:
    parts = skill_md.split('/')
    if len(parts) > 1:
        skill_root_dirs.add(parts[0])

# ✅ 正确：SKILL.md 在根目录，直接提取
for member in zf.namelist():
    if member.endswith('/'):
        continue
    zf.extract(member, target_dir)
```

### ⚠️ 陷阱 2: 技能名称解析

**错误:** 直接使用 zip 文件名作为技能名

```python
# ❌ 错误：包含版本号
skill_name = zip_file.stem  # china-legal-query-1.0.2

# ✅ 正确：移除版本号
skill_name = '-'.join(name_parts[:-1])  # china-legal-query
```

### ⚠️ 陷阱 3: 重复技能名称

**错误:** 直接覆盖已存在的技能

```python
# ❌ 错误：覆盖现有技能
target_skill_dir = SKILLS_TARGET_DIR / skill_name

# ✅ 正确：添加时间戳
if target_skill_dir.exists():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    skill_name = f"{skill_name}_{timestamp}"
```

## 验证步骤

### 1. 检查技能目录

```bash
ls -la backend/skills/
# 应该看到所有解压的技能目录
```

### 2. 验证 SKILL.md

```python
for skill_dir in SKILLS_TARGET_DIR.iterdir():
    if skill_dir.is_dir():
        skill_md = skill_dir / "SKILL.md"
        assert skill_md.exists(), f"{skill_dir.name} 缺少 SKILL.md"
```

### 3. 检查安装清单

```python
with open('backend/skills/skills_manifest.json') as f:
    manifest = json.load(f)
    print(f"总安装数：{manifest['total_installed']}")
```

### 4. 测试技能加载

```python
from app.self_evolution.skills import SkillManager

skill_manager = SkillManager()
skills = skill_manager.load_skills()
print(f"加载技能数：{len(skills)}")
```

## 完整脚本示例

```python
#!/usr/bin/env python3
import os
import zipfile
import shutil
import json
import re
from pathlib import Path
from datetime import datetime

SKILLS_ZIP_DIR = Path("/path/to/skills-zip")
SKILLS_TARGET_DIR = Path("/path/to/backend/skills")

SKILLS_TARGET_DIR.mkdir(parents=True, exist_ok=True)

stats = {"total_zips": 0, "successful": 0, "failed": 0, 
         "skills_installed": [], "errors": []}

zip_files = [f for f in SKILLS_ZIP_DIR.glob("*.zip") 
             if "hermes-agent-main" not in f.name]
stats["total_zips"] = len(zip_files)

for zip_file in sorted(zip_files):
    try:
        # 解析技能名称
        name_parts = zip_file.stem.split('-')
        skill_name = zip_file.stem
        
        for i in range(len(name_parts) - 1, -1, -1):
            part = name_parts[i]
            if re.match(r'^\d+(\.\d+)*$', part):
                skill_name = '-'.join(name_parts[:i])
            else:
                break
        
        # 创建目标目录
        target_skill_dir = SKILLS_TARGET_DIR / skill_name
        if target_skill_dir.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            skill_name = f"{skill_name}_{timestamp}"
            target_skill_dir = SKILLS_TARGET_DIR / skill_name
        
        target_skill_dir.mkdir(parents=True, exist_ok=True)
        
        # 解压
        with zipfile.ZipFile(zip_file, 'r') as zf:
            for member in zf.namelist():
                if member.endswith('/'):
                    continue
                source = zf.open(member)
                target_path = target_skill_dir / Path(member).name
                with open(target_path, 'wb') as target:
                    target.write(source.read())
        
        stats["successful"] += 1
        stats["skills_installed"].append({
            "name": skill_name,
            "source": zip_file.name,
            "path": str(target_skill_dir),
            "installed_at": datetime.now().isoformat()
        })
        
    except Exception as e:
        stats["failed"] += 1
        stats["errors"].append(f"{zip_file.name}: {str(e)}")

# 生成清单
with open(SKILLS_TARGET_DIR / "skills_manifest.json", 'w') as f:
    json.dump(stats, f, ensure_ascii=False, indent=2)

print(f"✅ 安装完成：{stats['successful']}/{stats['total_zips']}")
```

## 相关文件

- `backend/skills/skills_manifest.json` - 安装清单
- `backend/skills/INSTALLED_SKILLS.md` - 技能列表
- `docs/CLAWHUB_SKILLS_INTEGRATION.md` - 整合文档

## 参考

- [ClawHub Skills Integration](docs/CLAWHUB_SKILLS_INTEGRATION.md)
- [Hermes Skills System](docs/HERMES_CORE_INTEGRATION.md)
