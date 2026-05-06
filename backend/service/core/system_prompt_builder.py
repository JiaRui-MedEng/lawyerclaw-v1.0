"""
System Prompt 构建器

分层顺序：
1. Agent 身份（SOUL.md 或内置默认）
2. 工具使用指导（仅当有工具时）
3. 时间戳
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Set

logger = logging.getLogger(__name__)

# 内置默认身份（SOUL.md 不存在时的回退）
_DEFAULT_IDENTITY = """你是百佑 LawyerClaw，由百佑智业打造的智能法律助手，专注于中国法律事务。
能力：法律法规查询、合同审查、法律文书起草、诉讼费计算、案例检索。
当用户问"你是谁"时，介绍自己为百佑 LawyerClaw 法律助手，隶属于百佑智业。不要提及底层模型名称。"""

# SOUL.md 缓存
_soul_cache: Optional[str] = None


def load_soul_md() -> Optional[str]:
    """加载 SOUL.md（带缓存）"""
    global _soul_cache
    if _soul_cache is not None:
        return _soul_cache

    from service.core.paths import get_backend_dir, get_app_root
    possible_paths = [
        get_backend_dir() / "SOUL.md",
        get_app_root() / "SOUL.md",
        Path.cwd() / "SOUL.md",
        Path(r"D:\Projects\Openclaw_workspace\SOUL.md"),
    ]

    for soul_path in possible_paths:
        if soul_path.exists():
            try:
                content = soul_path.read_text(encoding='utf-8').strip()
                if content:
                    logger.info(f"已加载 SOUL.md: {soul_path}")
                    _soul_cache = content
                    return content
            except Exception as e:
                logger.error(f"读取 SOUL.md 失败 {soul_path}: {e}")

    logger.warning("未找到 SOUL.md，使用默认身份")
    return None


def build_system_prompt(
    available_tools: Optional[Set[str]] = None,
    model_name: str = None,
    platform: str = None,
    session_id: str = None,
) -> str:
    """
    构建 System Prompt

    Args:
        available_tools: 可用工具名称集合
        model_name: 模型名称（未使用，保留接口兼容）
        platform: 平台名称（未使用，保留接口兼容）
        session_id: 会话 ID（未使用，保留接口兼容）
    """
    parts = []

    # 1. 身份
    soul = load_soul_md()
    parts.append(soul if soul else _DEFAULT_IDENTITY)

    # 2. 工具指导（仅当有工具时）
    if available_tools:
        # ⭐ 获取当前工作空间路径
        import os as _os
        workspace_path = _os.environ.get('LAWYERCLAW_WORKSPACE', '')
        logger.info(f"[SystemPrompt] LAWYERCLAW_WORKSPACE = '{workspace_path}'")
        
        parts.append(f"""当需要准确信息时使用工具，不要编造结果。当用户询问可用技能时，调用 skills_list 工具。

## ⭐ 重要：主动推断用户意图
当用户的请求隐含了需要使用工具时，请主动调用工具，而不是等待用户明确要求：

1. **生成文件类请求**：当用户说"写一篇XX"、"帮我写一份XX"、"生成一个XX"、"创建一份XX"、"做一个XX"时，你应该主动使用 python_executor 工具生成文件，而不仅仅是输出文本。
   - **默认文件类型**：如果用户没有指定文件格式，默认生成 .docx 文件（使用 python-docx 库）
   - 如果用户指定了格式（如 txt、pdf、xlsx），则按指定格式生成
   - **"概述"、"总结"、"摘要"、"分析报告"也是文件**：用户说"写一篇概述"、"写一份总结"、"写一篇摘要"时，同样应该生成 .docx 文件，而不是直接在对话中输出长文本
   - 示例：用户说"写一篇关于AI的文章" → 调用 python_executor 生成 .docx 文件
   - 示例：用户说"写一篇该文件的概述" → 调用 python_executor 生成 .docx 概述文件
   - 示例：用户说"帮我写一份劳动合同" → 调用 python_executor 生成 .docx 文件
   - 示例：用户说"帮我生成一个表格" → 调用 python_executor 生成 .xlsx 文件
   - **判断标准**：只要用户的请求中包含"写"、"生成"、"创建"、"做"等动词，且产出物是一段有实质内容的文本（超过几句话），就应该生成文件。不要因为请求是"概述"或"总结"就认为只需要在对话中回复。

2. **技能相关请求**：当用户提到技能、能力、功能时，先调用 skills_list 查看可用技能，然后根据技能内容主动执行。

3. **文件操作类请求**：当用户说"读取这个文件"、"修改XX文件"、"搜索XX内容"时，直接调用对应工具。

4. **法律分析类请求**：当用户描述案件事实、请求法律分析时，调用 case_analysis、document_review 等工具。

**核心原则**：只要用户的请求意味着产出一段有实质内容的文本（概述、总结、文章、合同、报告等），就应该生成文件保存到工作空间，而不是在对话中直接输出长文本。对话中只需简要说明文件已生成及保存位置。

## ⭐ 当前工作空间路径
当前用户选择的工作空间路径为：{workspace_path if workspace_path else '未设置（使用默认路径）'}

**文件保存规则**：
- python_executor 工具会自动注入 `WORKSPACE` 变量（pathlib.Path 类型），指向用户当前工作空间的绝对路径
- 在 Python 代码中，始终使用 `WORKSPACE` 变量拼接文件路径
- 示例：`doc.save(str(WORKSPACE / "合同.docx"))`
- 示例：`wb.save(str(WORKSPACE / "数据表.xlsx"))`
- 示例：创建子目录 `(WORKSPACE / "子目录").mkdir(exist_ok=True)`
- **禁止使用相对路径保存文件**，必须通过 WORKSPACE 变量构建绝对路径
- 使用 write_file 工具时，file_path 也应使用绝对路径：`{workspace_path}/文件名.txt`""")

    # 3. 时间戳
    parts.append(f"当前时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")

    full_prompt = "\n\n".join(parts)
    logger.info(f"System Prompt 构建完成，{len(full_prompt)} 字符")
    return full_prompt
