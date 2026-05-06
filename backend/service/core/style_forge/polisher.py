"""
润色智能体 - 将 AI 生成文本改写为个人风格

通过在线 API 调用 + 本地后处理，去除 AI 味，赋予个人写作风格。

功能：
- 风格化 Prompt 构建
- OpenAI 兼容 API 调用
- 本地反 AI 规则强制替换
- 润色强度控制（light/medium/strong）
"""
import os
import re
import logging
import json
from typing import Dict, Any, Optional, List

import requests
import yaml

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# 润色强度配置
# ═══════════════════════════════════════════════════════════

INTENSITY_CONFIG = {
    "light": {
        "style_weight": 0.3,
        "original_retention": 0.8,
        "temperature": 0.6,
        "description": "轻微调整语气，保留 80% 原文",
    },
    "medium": {
        "style_weight": 0.6,
        "original_retention": 0.5,
        "temperature": 0.8,
        "description": "适度改写，保留 50% 原文",
    },
    "strong": {
        "style_weight": 1.0,
        "original_retention": 0.2,
        "temperature": 1.0,
        "description": "彻底重写，仅保留 20% 原文",
    },
}


# ═══════════════════════════════════════════════════════════
# Prompt 构建
# ═══════════════════════════════════════════════════════════

def build_polish_prompt(
    text: str,
    style_profile: Dict[str, Any],
    intensity: str = "medium",
) -> str:
    """
    构建风格化润色 Prompt
    
    Args:
        text: 待润色文本
        style_profile: 风格 Profile（来自 analyzer）
        intensity: 润色强度（light/medium/strong）
        
    Returns:
        润色 Prompt
    """
    config = INTENSITY_CONFIG.get(intensity, INTENSITY_CONFIG["medium"])
    vocab = style_profile.get("vocabulary", {})
    rhythm = style_profile.get("rhythm", {})
    anti_ai = style_profile.get("anti_ai", {})
    transitions = style_profile.get("transitions", {})
    
    # 构建风格描述
    favorite_words = vocab.get("favorite_words", [])
    formality = vocab.get("formality_score", 0.5)
    avg_len = rhythm.get("sentence_length_avg", 18)
    short_ratio = rhythm.get("short_sentence_ratio", 0.4)
    
    # 语气描述
    if formality < 0.3:
        tone = "口语化、亲切、像朋友聊天"
    elif formality < 0.6:
        tone = "半正式、自然流畅"
    else:
        tone = "正式、专业、严谨"
    
    # 反 AI 规则
    replacements = anti_ai.get("replacements", {})
    anti_ai_rules = ""
    if replacements:
        rules_list = []
        for pattern, alternatives in replacements.items():
            alts = " / ".join(alternatives[:2])
            rules_list.append(f"  - 将「{pattern}」替换为「{alts}」")
        anti_ai_rules = "\n".join(rules_list)
    
    # 个人过渡词
    personal_trans = transitions.get("personal", [])
    
    prompt = f"""你是一个专业的文本润色助手。请将以下 AI 生成的文本改写为具有个人风格的"人味"文本。

## 风格参数
- **语气**: {tone}
- **标志性词汇**: {', '.join(favorite_words) if favorite_words else '无'}
- **平均句长**: {avg_len} 字
- **短句占比**: {short_ratio:.0%}
- **润色强度**: {intensity}（{config['description']}）

## 润色要求
1. 去除所有 AI 套话和模板化表达
2. 使用个人标志性词汇（如 {', '.join(favorite_words[:3]) if favorite_words else '自然用词'}）
3. 保持短句为主，长短句交错
4. 让文本读起来像真人写的，不要有机器感

## 反 AI 规则（必须遵守）
{anti_ai_rules if anti_ai_rules else '（无特殊规则）'}

## 个人过渡词偏好
优先使用：{', '.join(personal_trans) if personal_trans else '自然过渡'}

## 待润色文本
{text}

请直接输出润色后的文本，不要添加额外说明。"""
    
    return prompt


# ═══════════════════════════════════════════════════════════
# API 配置管理
# ═══════════════════════════════════════════════════════════

CONFIG_DIR = os.path.expanduser("~/.style-forge")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.yaml")

DEFAULT_CONFIG = {
    "api": {
        "active": "default",
        "profiles": {
            "default": {
                "name": "OpenAI 兼容",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4o",
                "timeout": 60,
                "max_retries": 2,
                "env_key_name": "STYLE_FORGE_API_KEY",
            }
        }
    },
    "polish": {
        "temperature": 0.8,
        "max_tokens": 4000,
        "intensity": "medium",
    }
}


def load_config() -> Dict[str, Any]:
    """加载 API 配置"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        # 合并默认配置
        for key, value in DEFAULT_CONFIG.items():
            if key not in config:
                config[key] = value
        return config
    return DEFAULT_CONFIG.copy()


def save_config(config: Dict[str, Any]) -> None:
    """保存 API 配置"""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)


def get_api_key(config: Dict[str, Any]) -> Optional[str]:
    """从环境变量获取 API Key"""
    active = config["api"]["active"]
    profiles = config["api"]["profiles"]
    profile = profiles.get(active, {})
    env_key_name = profile.get("env_key_name", "STYLE_FORGE_API_KEY")
    return os.environ.get(env_key_name)


def test_api_connection(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    测试 API 连通性
    
    Returns:
        测试结果字典
    """
    if config is None:
        config = load_config()
    
    active = config["api"]["active"]
    profiles = config["api"]["profiles"]
    profile = profiles.get(active)
    
    if not profile:
        return {"success": False, "error": f"未找到 API 配置: {active}"}
    
    api_key = get_api_key(config)
    if not api_key:
        return {"success": False, "error": f"未设置环境变量: {profile.get('env_key_name', 'STYLE_FORGE_API_KEY')}"}
    
    base_url = profile["base_url"].rstrip("/")
    model = profile.get("model", "")
    
    # 测试连通性
    try:
        response = requests.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": "你好"}],
                "max_tokens": 10,
            },
            timeout=profile.get("timeout", 30),
        )
        
        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "model": model,
                "message": "API 连通正常",
                "usage": data.get("usage", {}),
            }
        else:
            return {
                "success": False,
                "error": f"API 返回错误: {response.status_code} - {response.text[:200]}",
            }
            
    except requests.exceptions.Timeout:
        return {"success": False, "error": "API 请求超时"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "无法连接到 API 服务器"}
    except Exception as e:
        return {"success": False, "error": f"API 测试失败: {str(e)}"}


# ═══════════════════════════════════════════════════════════
# API 润色
# ═══════════════════════════════════════════════════════════

async def call_polish_api(
    prompt: str,
    config: Optional[Dict[str, Any]] = None,
) -> str:
    """
    调用 API 进行文本润色
    
    Args:
        prompt: 润色 Prompt
        config: API 配置（默认加载）
        
    Returns:
        润色后的文本
        
    Raises:
        Exception: API 调用失败
    """
    if config is None:
        config = load_config()
    
    active = config["api"]["active"]
    profiles = config["api"]["profiles"]
    profile = profiles.get(active)
    
    if not profile:
        raise ValueError(f"未找到 API 配置: {active}")
    
    api_key = get_api_key(config)
    if not api_key:
        raise ValueError(f"未设置环境变量: {profile.get('env_key_name', 'STYLE_FORGE_API_KEY')}")
    
    base_url = profile["base_url"].rstrip("/")
    model = profile.get("model", "")
    timeout = profile.get("timeout", 60)
    max_retries = profile.get("max_retries", 2)
    
    polish_config = config.get("polish", {})
    temperature = polish_config.get("temperature", 0.8)
    max_tokens = polish_config.get("max_tokens", 4000)
    
    last_error = None
    for attempt in range(max_retries):
        try:
            response = requests.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "你是一个专业的文本润色助手。"},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                timeout=timeout,
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"].strip()
                logger.info(f"API 润色成功: {len(content)} 字符")
                return content
            else:
                last_error = f"API 返回错误: {response.status_code}"
                logger.warning(f"API 调用失败 ({attempt + 1}/{max_retries}): {last_error}")
                
        except requests.exceptions.Timeout:
            last_error = "API 请求超时"
            logger.warning(f"API 超时 ({attempt + 1}/{max_retries})")
        except Exception as e:
            last_error = str(e)
            logger.warning(f"API 异常 ({attempt + 1}/{max_retries}): {e}")
    
    raise Exception(f"API 润色失败（重试 {max_retries} 次）: {last_error}")


# ═══════════════════════════════════════════════════════════
# 本地后处理
# ═══════════════════════════════════════════════════════════

def post_process(text: str, style_profile: Dict[str, Any]) -> str:
    """
    本地后处理 - 强制替换 AI 套话
    
    Args:
        text: 待处理文本
        style_profile: 风格 Profile
        
    Returns:
        处理后的文本
    """
    anti_ai = style_profile.get("anti_ai", {})
    replacements = anti_ai.get("replacements", {})
    
    if not replacements:
        return text
    
    original_text = text
    for pattern, alternatives in replacements.items():
        if alternatives:
            replacement = alternatives[0]  # 取第一个替代词
            text = text.replace(pattern, replacement)
    
    # 统计替换次数
    replaced_count = sum(1 for p in replacements if p in original_text and p not in text)
    
    if replaced_count > 0:
        logger.info(f"后处理完成: 强制替换 {replaced_count} 处 AI 套话")
    
    return text


# ═══════════════════════════════════════════════════════════
# 主入口：润色函数
# ═══════════════════════════════════════════════════════════

async def polish_text(
    text: str,
    style_profile: Dict[str, Any],
    intensity: str = "medium",
    config: Optional[Dict[str, Any]] = None,
    use_api: bool = True,
) -> Dict[str, Any]:
    """
    润色文本（主入口）
    
    Args:
        text: 待润色文本
        style_profile: 风格 Profile
        intensity: 润色强度（light/medium/strong）
        config: API 配置
        use_api: 是否调用 API（False 则仅本地后处理）
        
    Returns:
        润色结果字典
    """
    logger.info(f"开始润色: 文本长度 {len(text)}, 强度 {intensity}")
    
    result = {
        "success": False,
        "original": text,
        "polished": "",
        "method": "",
    }
    
    try:
        if use_api:
            # API 润色 + 本地后处理
            prompt = build_polish_prompt(text, style_profile, intensity)
            polished = await call_polish_api(prompt, config)
            polished = post_process(polished, style_profile)
            result["method"] = "api + post_process"
        else:
            # 仅本地后处理
            polished = post_process(text, style_profile)
            result["method"] = "post_process_only"
        
        result["success"] = True
        result["polished"] = polished
        result["length_diff"] = len(polished) - len(text)
        
        logger.info(f"润色完成: {len(text)} → {len(polished)} 字符")
        
    except Exception as e:
        logger.error(f"润色失败: {e}", exc_info=True)
        result["error"] = str(e)
    
    return result
