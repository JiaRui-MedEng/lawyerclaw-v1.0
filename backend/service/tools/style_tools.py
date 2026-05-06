"""
风格工具 - 注册到 LawyerClaw ToolRegistry

提供两个工具：
- style_analyze: 从文档中提取个人写作风格
- style_polish: 将 AI 生成的文本润色为个人风格
"""
import logging
from typing import Optional

from service.tools.legal_tools import BaseTool, ToolResult
from service.core.style_forge import analyzer, polisher, profile_manager

logger = logging.getLogger(__name__)


class StyleAnalyzeTool(BaseTool):
    """风格分析工具 - 从文档中提取个人写作风格"""
    
    name = "style_analyze"
    description = (
        "从 PDF/Word/纯文本文档中提取个人写作风格，生成风格 Profile。"
        "用于后续文本润色，去除 AI 味。"
        "当用户需要分析写作风格、生成个人风格文件时使用此工具。"
    )
    
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "文档路径（支持 .pdf, .docx, .txt, .md）"
            },
            "style_name": {
                "type": "string",
                "description": "风格名称（唯一标识，如 'doctor-li'）"
            },
            "merge": {
                "type": "boolean",
                "description": "是否合并到已有风格（默认 false，即新建）",
                "default": False
            }
        },
        "required": ["file_path", "style_name"]
    }
    
    async def execute(
        self,
        file_path: str,
        style_name: str,
        merge: bool = False,
    ) -> ToolResult:
        """执行风格分析"""
        try:
            # 1. 解析文档
            logger.info(f"[StyleAnalyze] 解析文档: {file_path}")
            text = analyzer.parse_document(file_path)
            
            if len(text) < 100:
                return ToolResult(
                    success=False,
                    content="",
                    error=f"文档内容过短（{len(text)} 字符），需要至少 100 字符才能有效分析风格"
                )
            
            # 2. 风格分析
            logger.info(f"[StyleAnalyze] 分析风格: {style_name}")
            style_data = analyzer.analyze_style(text)
            
            # 3. 保存 Profile
            try:
                if merge:
                    profile = profile_manager.update_profile(
                        style_name, style_data, merge=True
                    )
                    action = "合并更新"
                else:
                    profile = profile_manager.create_profile(
                        style_name, style_data, source_files=[file_path]
                    )
                    action = "创建"
            except FileExistsError:
                return ToolResult(
                    success=False,
                    content="",
                    error=f"风格已存在: {style_name}。使用 merge=true 合并或更换名称。"
                )
            
            # 4. 构建结果
            vocab = style_data.get("vocabulary", {})
            rhythm = style_data.get("rhythm", {})
            ai_score = style_data.get("anti_ai", {})
            
            content = (
                f"✅ 风格 Profile {action}成功: {style_name}\n\n"
                f"📊 分析结果:\n"
                f"- 标志性词汇: {', '.join(vocab.get('favorite_words', [])[:5])}\n"
                f"- 平均句长: {rhythm.get('sentence_length_avg', 0)} 字\n"
                f"- 短句占比: {rhythm.get('short_sentence_ratio', 0):.0%}\n"
                f"- 正式度: {vocab.get('formality_score', 0):.0%}\n"
                f"- AI 套话检测率: {ai_score.get('detection_rate', 0):.0%}\n"
                f"- 检测到 {len(ai_score.get('detected_patterns', []))} 种 AI 套话\n\n"
                f"💡 使用 style_polish 工具进行文本润色"
            )
            
            return ToolResult(
                success=True,
                content=content,
                data={
                    "style_name": style_name,
                    "action": action,
                    "vocabulary": vocab,
                    "rhythm": rhythm,
                    "anti_ai": ai_score,
                }
            )
            
        except FileNotFoundError as e:
            return ToolResult(success=False, content="", error=str(e))
        except ValueError as e:
            return ToolResult(success=False, content="", error=str(e))
        except Exception as e:
            logger.error(f"[StyleAnalyze] 分析失败: {e}", exc_info=True)
            return ToolResult(
                success=False,
                content="",
                error=f"风格分析失败: {str(e)}"
            )


class StylePolishTool(BaseTool):
    """风格润色工具 - 将 AI 生成文本改写为个人风格"""
    
    name = "style_polish"
    description = (
        "将 AI 生成的文本润色为个人风格，去除 AI 味。"
        "需要先用 style_analyze 生成风格 Profile。"
        "支持 light/medium/strong三档润色强度。"
    )
    
    parameters = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "待润色文本"
            },
            "style_name": {
                "type": "string",
                "description": "风格名称（需要先通过 style_analyze 生成）"
            },
            "intensity": {
                "type": "string",
                "enum": ["light", "medium", "strong"],
                "description": "润色强度: light=轻微调整, medium=适度改写, strong=彻底重写",
                "default": "medium"
            },
            "use_api": {
                "type": "boolean",
                "description": "是否调用 API 润色（false 则仅本地替换 AI 套话）",
                "default": True
            }
        },
        "required": ["text", "style_name"]
    }
    
    async def execute(
        self,
        text: str,
        style_name: str,
        intensity: str = "medium",
        use_api: bool = True,
    ) -> ToolResult:
        """执行文本润色"""
        try:
            # 1. 加载风格 Profile
            logger.info(f"[StylePolish] 加载风格: {style_name}")
            profile = profile_manager.load_profile(style_name)
            
            # 2. 执行润色
            logger.info(f"[StylePolish] 润色文本: {len(text)} 字符, 强度 {intensity}")
            result = await polisher.polish_text(
                text=text,
                style_profile=profile,
                intensity=intensity,
                use_api=use_api,
            )
            
            if not result.get("success"):
                error = result.get("error", "未知错误")
                return ToolResult(
                    success=False,
                    content="",
                    error=f"润色失败: {error}"
                )
            
            # 3. 构建结果
            polished = result["polished"]
            method = result.get("method", "unknown")
            length_diff = result.get("length_diff", 0)
            diff_str = f"+{length_diff}" if length_diff > 0 else str(length_diff)
            
            content = (
                f"✅ 润色完成（{method}）\n\n"
                f"📊 统计:\n"
                f"- 原文: {len(text)} 字符\n"
                f"- 润色后: {len(polished)} 字符 (变化 {diff_str})\n"
                f"- 强度: {intensity}\n\n"
                f"--- 润色结果 ---\n{polished}\n--- 结果结束 ---"
            )
            
            return ToolResult(
                success=True,
                content=content,
                data={
                    "polished": polished,
                    "method": method,
                    "intensity": intensity,
                    "original_length": len(text),
                    "polished_length": len(polished),
                }
            )
            
        except FileNotFoundError as e:
            return ToolResult(success=False, content="", error=str(e))
        except ValueError as e:
            return ToolResult(success=False, content="", error=str(e))
        except Exception as e:
            logger.error(f"[StylePolish] 润色失败: {e}", exc_info=True)
            return ToolResult(
                success=False,
                content="",
                error=f"润色失败: {str(e)}"
            )


class StyleListTool(BaseTool):
    """风格列表工具 - 列出所有已保存的风格 Profile"""
    
    name = "style_list"
    description = "列出所有已保存的个人写作风格 Profile"
    
    parameters = {
        "type": "object",
        "properties": {},
        "required": []
    }
    
    async def execute(self) -> ToolResult:
        """列出所有风格"""
        try:
            profiles = profile_manager.list_profiles()
            
            if not profiles:
                return ToolResult(
                    success=True,
                    content="暂无风格 Profile。使用 style_analyze 创建第一个风格。",
                    data=[]
                )
            
            lines = [f"📋 共 {len(profiles)} 个风格 Profile:\n"]
            for p in profiles:
                words = p.get("favorite_words", [])
                words_str = ", ".join(words[:3]) if words else "（无）"
                lines.append(
                    f"- **{p['name']}**\n"
                    f"  词汇: {words_str}\n"
                    f"  来源: {len(p.get('source_files', []))} 个文件\n"
                    f"  更新: {p.get('updated_at', '')[:10]}"
                )
            
            content = "\n\n".join(lines)
            return ToolResult(success=True, content=content, data=profiles)
            
        except Exception as e:
            logger.error(f"[StyleList] 列表失败: {e}", exc_info=True)
            return ToolResult(
                success=False,
                content="",
                error=f"列出风格失败: {str(e)}"
            )


class StyleExportTool(BaseTool):
    """风格导出工具 - 导出为 Hermes Skill 格式"""
    
    name = "style_export"
    description = "将风格 Profile 导出为 Hermes Skill 格式，供 AI 智能体使用"
    
    parameters = {
        "type": "object",
        "properties": {
            "style_name": {
                "type": "string",
                "description": "风格名称"
            },
            "output_dir": {
                "type": "string",
                "description": "输出目录（默认 ~/.hermes/skills/）",
                "default": ""
            }
        },
        "required": ["style_name"]
    }
    
    async def execute(
        self,
        style_name: str,
        output_dir: str = "",
    ) -> ToolResult:
        """导出风格为 Skill"""
        try:
            output_path = profile_manager.export_profile(
                style_name,
                output_dir=output_dir if output_dir else None
            )
            
            content = (
                f"✅ 风格已导出为 Skill: {style_name}\n"
                f"📁 路径: {output_path}\n\n"
                f"包含文件:\n"
                f"- SKILL.md（Hermes Skill 格式）\n"
                f"- style_profile.yaml（原始风格数据）"
            )
            
            return ToolResult(
                success=True,
                content=content,
                data={"output_path": output_path}
            )
            
        except FileNotFoundError as e:
            return ToolResult(success=False, content="", error=str(e))
        except Exception as e:
            logger.error(f"[StyleExport] 导出失败: {e}", exc_info=True)
            return ToolResult(
                success=False,
                content="",
                error=f"导出失败: {str(e)}"
            )
