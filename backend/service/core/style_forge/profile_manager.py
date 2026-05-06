"""
风格 Profile 管理器

负责风格 Profile 的创建、读取、更新、删除和导出。

Profile 存储格式：YAML
存储位置：~/.lawyerclaw/styles/
"""
import os
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List

import yaml

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════

STYLES_DIR = os.path.expanduser("~/.lawyerclaw/styles")
SKILLS_DIR = os.path.expanduser("~/.hermes/skills")


# ═══════════════════════════════════════════════════════════
# Profile 管理
# ═══════════════════════════════════════════════════════════

def ensure_styles_dir() -> Path:
    """确保风格存储目录存在"""
    path = Path(STYLES_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _profile_path(name: str) -> Path:
    """获取 Profile 文件路径"""
    return ensure_styles_dir() / f"{name}.yaml"


def create_profile(
    name: str,
    style_data: Dict[str, Any],
    source_files: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    创建风格 Profile
    
    Args:
        name: 风格名称（唯一标识）
        style_data: 风格分析数据（来自 analyzer）
        source_files: 来源文件列表
        
    Returns:
        Profile 字典
    """
    path = _profile_path(name)
    
    if path.exists():
        raise FileExistsError(f"风格已存在: {name}。使用 --merge 合并或更换名称。")
    
    profile = {
        "style_id": name,
        "version": "1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source_files": source_files or [],
        **style_data,
    }
    
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(profile, f, allow_unicode=True, default_flow_style=False)
    
    logger.info(f"风格 Profile 已创建: {name} → {path}")
    return profile


def load_profile(name: str) -> Dict[str, Any]:
    """
    加载风格 Profile
    
    Args:
        name: 风格名称
        
    Returns:
        Profile 字典
        
    Raises:
        FileNotFoundError: Profile 不存在
    """
    path = _profile_path(name)
    
    if not path.exists():
        raise FileNotFoundError(f"风格 Profile 不存在: {name}")
    
    with open(path, "r", encoding="utf-8") as f:
        profile = yaml.safe_load(f)
    
    return profile


def update_profile(
    name: str,
    style_data: Dict[str, Any],
    merge: bool = True,
) -> Dict[str, Any]:
    """
    更新风格 Profile
    
    Args:
        name: 风格名称
        style_data: 新的风格分析数据
        merge: 是否合并（True）或覆盖（False）
        
    Returns:
        更新后的 Profile 字典
    """
    path = _profile_path(name)
    
    if merge and path.exists():
        profile = load_profile(name)
        # 合并策略：更新关键字段
        for key in ["vocabulary", "rhythm", "paragraph", "transitions", "anti_ai"]:
            if key in style_data:
                profile[key] = style_data[key]
        # 更新来源文件
        if "source_files" in style_data:
            existing = set(profile.get("source_files", []))
            existing.update(style_data["source_files"])
            profile["source_files"] = list(existing)
    else:
        profile = {
            "style_id": name,
            "version": "1.0.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            **style_data,
        }
    
    profile["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(profile, f, allow_unicode=True, default_flow_style=False)
    
    logger.info(f"风格 Profile 已更新: {name}")
    return profile


def delete_profile(name: str) -> bool:
    """
    删除风格 Profile
    
    Args:
        name: 风格名称
        
    Returns:
        是否删除成功
    """
    path = _profile_path(name)
    
    if not path.exists():
        return False
    
    path.unlink()
    logger.info(f"风格 Profile 已删除: {name}")
    return True


def list_profiles() -> List[Dict[str, Any]]:
    """
    列出所有风格 Profile
    
    Returns:
        Profile 列表（仅元数据）
    """
    styles_dir = ensure_styles_dir()
    profiles = []
    
    for path in styles_dir.glob("*.yaml"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                profile = yaml.safe_load(f)
            profiles.append({
                "name": profile.get("style_id", path.stem),
                "version": profile.get("version", "1.0.0"),
                "created_at": profile.get("created_at", ""),
                "updated_at": profile.get("updated_at", ""),
                "source_files": profile.get("source_files", []),
                "favorite_words": profile.get("vocabulary", {}).get("favorite_words", []),
            })
        except Exception as e:
            logger.warning(f"读取 Profile 失败: {path.name} - {e}")
    
    return profiles


def export_profile(name: str, output_dir: Optional[str] = None) -> str:
    """
    导出风格 Profile 为 Hermes Skill 格式
    
    Args:
        name: 风格名称
        output_dir: 输出目录（默认 ~/.hermes/skills/）
        
    Returns:
        导出文件路径
    """
    profile = load_profile(name)
    
    if output_dir is None:
        output_dir = SKILLS_DIR
    
    output_path = Path(output_dir) / f"{name}"
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 生成 SKILL.md
    skill_md = _generate_skill_md(profile)
    (output_path / "SKILL.md").write_text(skill_md, encoding="utf-8")
    
    # 同时保存原始 YAML
    (output_path / "style_profile.yaml").write_text(
        yaml.dump(profile, allow_unicode=True, default_flow_style=False),
        encoding="utf-8"
    )
    
    logger.info(f"风格 Profile 已导出: {name} → {output_path}")
    return str(output_path)


def _generate_skill_md(profile: Dict[str, Any]) -> str:
    """
    生成 Hermes Skill 格式的 SKILL.md
    
    Args:
        profile: Profile 字典
        
    Returns:
        SKILL.md 内容
    """
    vocab = profile.get("vocabulary", {})
    rhythm = profile.get("rhythm", {})
    anti_ai = profile.get("anti_ai", {})
    transitions = profile.get("transitions", {})
    
    favorite_words = vocab.get("favorite_words", [])
    formality = vocab.get("formality_score", 0.5)
    avg_len = rhythm.get("sentence_length_avg", 18)
    short_ratio = rhythm.get("short_sentence_ratio", 0.4)
    
    replacements = anti_ai.get("replacements", {})
    personal_trans = transitions.get("personal", [])
    avoided_trans = transitions.get("avoided", [])
    
    # 语气描述
    if formality < 0.3:
        tone = "口语化、亲切、像朋友聊天"
    elif formality < 0.6:
        tone = "半正式、自然流畅"
    else:
        tone = "正式、专业、严谨"
    
    skill = f"""---
name: {profile.get('style_id', 'unknown')}
description: 个人写作风格 - {tone}
version: {profile.get('version', '1.0.0')}
category: writing-style
---

# 个人写作风格

## 风格概述
- **语气**: {tone}
- **平均句长**: {avg_len} 字
- **短句占比**: {short_ratio:.0%}
- **正式度**: {formality:.0%}

## 标志性词汇
{', '.join(favorite_words) if favorite_words else '（未检测到）'}

## 过渡词偏好
- **常用**: {', '.join(personal_trans) if personal_trans else '（无）'}
- **避免**: {', '.join(avoided_trans) if avoided_trans else '（无）'}

## 反 AI 规则
"""
    
    if replacements:
        skill += "\n| AI 套话 | 替换为 |\n|--------|--------|\n"
        for pattern, alternatives in replacements.items():
            alts = " / ".join(alternatives[:2])
            skill += f"| {pattern} | {alts} |\n"
    else:
        skill += "（无特殊规则）\n"
    
    skill += f"""
## 使用方式

当需要生成文本时，请遵循以下规则：

1. **语气**: {tone}
2. **用词**: 优先使用标志性词汇（{', '.join(favorite_words[:3]) if favorite_words else '自然用词'}）
3. **句式**: 平均句长 {avg_len} 字，短句为主（{short_ratio:.0%}）
4. **过渡**: 使用个人过渡词，避免 AI 套话
5. **反 AI**: 严格遵循上述替换规则

> 此风格 Profile 由 Style Forge 自动生成，基于个人文档分析。
"""
    
    return skill
