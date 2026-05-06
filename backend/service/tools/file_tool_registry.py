"""
文件操作工具注册表

基于 Hermes Agent 架构实现，提供完整的文件操作能力:
- read_file: 读取文件（支持分页、二进制检测）
- write_file: 写入文件（原子操作、安全审批）
- patch_file: 修改文件（模糊匹配）
- search_files: 搜索文件（内容/文件名）
- list_directory: 列出目录
- create_directory: 创建目录
- delete_file: 删除文件

用法:
    from service.tools.file_tool_registry import FILE_TOOLS, register_all
    
    # 注册到主 registry
    register_all()
"""
import logging
from typing import Any, Dict, List
from pathlib import Path
import os
import re
import json
import tempfile
import shutil

from service.tools.legal_tools import BaseTool, ToolResult

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# 安全配置
# ═══════════════════════════════════════════════════════════

# 工作空间根目录（默认为用户的 lawyerclaw workspace）
from service.core.paths import get_app_root
_APP_ROOT = get_app_root()
_USER_DOCUMENTS = Path(os.path.expanduser("~/Documents"))
DEFAULT_WORKSPACE_ROOT = _USER_DOCUMENTS if _USER_DOCUMENTS.exists() else _APP_ROOT

# 读取限制
DEFAULT_MAX_CHARS = 10000  # 默认 10K 字符
MAX_FILE_SIZE = 50 * 1024  # 50KB

# 设备路径阻止列表
_BLOCKED_DEVICE_PATHS = frozenset({
    "/dev/zero", "/dev/random", "/dev/urandom", "/dev/full",
    "/dev/stdin", "/dev/tty", "/dev/console",
    "/dev/stdout", "/dev/stderr",
})

# 二进制文件扩展名
_BINARY_EXTENSIONS = {
    '.exe', '.dll', '.so', '.bin', '.dat',
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.webp',
    '.zip', '.rar', '.tar', '.gz', '.7z',
    '.pyc', '.pyo', '.o', '.a', '.lib',
    '.mp3', '.mp4', '.avi', '.mov', '.mkv',
}

# 文档文件扩展名（可通过专用解析器读取）
_DOCUMENT_EXTENSIONS = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx'}

# 敏感路径（拒绝写入）
_SENSITIVE_PATH_PREFIXES = ("/etc/", "/boot/", "/usr/lib/systemd/")
_SENSITIVE_EXACT_PATHS = {"/var/run/docker.sock", "/run/docker.sock"}

# 写入 deny list
_WRITE_DENIED_PATHS = {
    ".ssh/authorized_keys", ".ssh/id_rsa", ".ssh/id_ed25519",
    ".bashrc", ".zshrc", ".profile", ".bash_profile",
    ".netrc", ".pgpass", ".npmrc", ".pypirc",
}


# ═══════════════════════════════════════════════════════════
# 工具实现
# ═══════════════════════════════════════════════════════════

class ReadFileTool(BaseTool):
    """读取文件工具"""
    
    name = "read_file"
    description = "读取本地文件内容。支持分页（offset/limit），自动检测二进制文件和敏感路径。当 AI 需要查看文件内容时使用此工具。"
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "要读取的文件路径（绝对路径或相对于工作空间的路径）"
            },
            "offset": {
                "type": "integer",
                "description": "起始行号（1-indexed），默认 1",
                "default": 1
            },
            "limit": {
                "type": "integer",
                "description": "读取行数，默认 500",
                "default": 500
            }
        },
        "required": ["file_path"]
    }
    
    async def execute(self, file_path: str, offset: int = 1, limit: int = 500, **kwargs) -> ToolResult:
        """执行文件读取"""
        try:
            # 1. 设备路径检查
            if _is_blocked_device(file_path):
                return ToolResult(
                    success=False,
                    content='',
                    error=f"无法读取 '{file_path}': 这是设备文件"
                )
            
            # 2. 敏感路径检查
            sensitive_error = _check_sensitive_path(file_path)
            if sensitive_error:
                return ToolResult(success=False, content='', error=sensitive_error)
            
            # 3. 解析路径
            path = _safe_resolve_path(file_path)
            
            if not path.exists():
                return ToolResult(
                    success=False,
                    content='',
                    error=f'文件不存在：{file_path}\n\n[提示：使用 file_list 工具查看目录内容，或使用 search_files 查找文件]'
                )
            
            if not path.is_file():
                return ToolResult(
                    success=False,
                    content='',
                    error=f'不是文件：{file_path}'
                )
            
            # 4. 二进制文件检查
            if _is_binary_file(str(path)):
                ext = path.suffix.lower()
                return ToolResult(
                    success=False,
                    content='',
                    error=f'无法读取二进制文件 ({ext})。图片文件请使用 vision_analyze 工具'
                )

            # 4.5 文档文件：使用专用解析器
            ext = path.suffix.lower()
            if ext in _DOCUMENT_EXTENSIONS:
                try:
                    from service.tools.document_parser import parse_document
                    result = parse_document(str(path))
                    if result.get('success'):
                        content = result['content']
                        if len(content) > DEFAULT_MAX_CHARS * 5:
                            content = content[:DEFAULT_MAX_CHARS * 5]
                        return ToolResult(
                            success=True,
                            content=f"📄 文件：{path}\n类型：{ext.upper()} 文档\n\n{content}",
                            data={'path': str(path), 'file_type': result.get('file_type'), 'pages': result.get('pages', 0)}
                        )
                    else:
                        return ToolResult(success=False, content='', error=f'文档解析失败：{result.get("error")}')
                except Exception as e:
                    return ToolResult(success=False, content='', error=f'文档解析失败：{str(e)}')
            
            # 5. 文件大小检查
            file_size = path.stat().st_size
            if file_size > MAX_FILE_SIZE * 10:
                return ToolResult(
                    success=False,
                    content='',
                    error=f'文件过大 ({file_size:,} 字节)，最大支持 {MAX_FILE_SIZE * 10:,} 字节。请使用 offset 和 limit 参数读取部分内容'
                )
            
            # 6. 读取文件
            with open(path, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
            
            total_lines = len(all_lines)
            
            # 7. 分页处理
            start_idx = max(0, offset - 1)
            end_idx = min(total_lines, start_idx + limit)
            content_lines = all_lines[start_idx:end_idx]
            
            # 8. 添加行号
            numbered_content = ''.join([
                f"{i + start_idx + 1:6d}: {line}"
                for i, line in enumerate(content_lines)
            ])
            
            # 9. 构建返回
            result_text = f"📄 文件：{path}\n"
            result_text += f"大小：{file_size:,} 字节 | 总行数：{total_lines}\n"
            result_text += f"显示：第 {start_idx + 1}-{end_idx} 行\n\n"
            result_text += "--- 文件内容 ---\n"
            result_text += numbered_content
            result_text += "--- 文件结束 ---\n"
            
            if end_idx < total_lines:
                result_text += f"\n[提示：文件还有 {total_lines - end_idx} 行未显示。使用 offset={end_idx + 1} 继续阅读]"
            
            return ToolResult(
                success=True,
                content=result_text,
                data={
                    'path': str(path),
                    'file_size': file_size,
                    'total_lines': total_lines,
                    'offset': offset,
                    'limit': limit,
                    'content': numbered_content
                }
            )
            
        except UnicodeDecodeError as e:
            return ToolResult(
                success=False,
                content='',
                error=f'文件编码错误：{str(e)}。文件可能不是 UTF-8 编码'
            )
        except Exception as e:
            logger.error(f"读取文件失败 {file_path}: {e}")
            return ToolResult(
                success=False,
                content='',
                error=f'读取失败：{str(e)}'
            )


class WriteFileTool(BaseTool):
    """写入文件工具"""
    
    name = "write_file"
    description = "写入文件内容，完全替换现有内容。自动创建父目录。危险操作需要用户审批。"
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "文件路径（将创建或覆盖）"
            },
            "content": {
                "type": "string",
                "description": "完整的文件内容"
            }
        },
        "required": ["file_path", "content"]
    }
    
    async def execute(self, file_path: str, content: str, **kwargs) -> ToolResult:
        """执行文件写入"""
        try:
            # 1. 敏感路径检查
            sensitive_error = _check_sensitive_path(file_path)
            if sensitive_error:
                return ToolResult(success=False, error=sensitive_error)
            
            # 2. 写入 deny list 检查
            if _is_write_denied(file_path):
                return ToolResult(
                    success=False,
                    error=f"拒绝写入：'{file_path}' 是受保护的系统/凭证文件"
                )
            
            # 3. 解析路径
            path = _safe_resolve_path(file_path)
            
            # 4. 原子写入
            path.parent.mkdir(parents=True, exist_ok=True)
            
            fd, tmp_path = tempfile.mkstemp(
                dir=str(path.parent),
                prefix=f".{path.name}.tmp.",
                suffix=""
            )
            
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    f.write(content)
                    f.flush()
                    os.fsync(f.fileno())
                
                # 备份原文件
                backup_path = None
                if path.exists():
                    backup_path = str(path) + ".backup"
                    shutil.copy2(path, backup_path)
                
                # 原子替换
                os.replace(tmp_path, str(path))
                
                result_text = f"✅ 文件已写入：{path}\n"
                result_text += f"大小：{len(content.encode('utf-8')):,} 字节"
                if backup_path:
                    result_text += f"\n备份：{backup_path}"
                
                return ToolResult(
                    success=True,
                    content=result_text,
                    data={'path': str(path), 'backup_path': backup_path}
                )
                
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
                
        except Exception as e:
            logger.error(f"写入文件失败 {file_path}: {e}")
            return ToolResult(
                success=False,
                error=f'写入失败：{str(e)}'
            )


class PatchFileTool(BaseTool):
    """修补文件工具"""
    
    name = "patch_file"
    description = "针对性修改文件内容（查找替换）。使用模糊匹配，容忍小的格式差异。返回修改的 diff。"
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "要修改的文件路径"
            },
            "old_string": {
                "type": "string",
                "description": "要查找的文本（必须唯一，包含足够上下文）"
            },
            "new_string": {
                "type": "string",
                "description": "替换文本（可以为空字符串来删除）"
            },
            "replace_all": {
                "type": "boolean",
                "description": "替换所有出现（默认 false）",
                "default": False
            }
        },
        "required": ["file_path", "old_string", "new_string"]
    }
    
    async def execute(self, file_path: str, old_string: str, new_string: str,
                      replace_all: bool = False, **kwargs) -> ToolResult:
        """执行文件修补"""
        try:
            # 1. 敏感路径检查
            sensitive_error = _check_sensitive_path(file_path)
            if sensitive_error:
                return ToolResult(success=False, error=sensitive_error)
            
            # 2. 解析路径
            path = _safe_resolve_path(file_path)
            
            if not path.exists():
                return ToolResult(
                    success=False,
                    error=f'文件不存在：{file_path}'
                )
            
            # 3. 读取原内容
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 4. 模糊查找替换
            new_content, match_count, strategy, error = _fuzzy_find_and_replace(
                content, old_string, new_string, replace_all
            )
            
            if error:
                return ToolResult(
                    success=False,
                    error=f'查找失败：{error}\n\n[提示：使用 read_file 查看文件当前内容，确保 old_string 完全匹配]'
                )
            
            if match_count == 0:
                return ToolResult(
                    success=False,
                    error=f'未找到匹配项：{old_string[:50]}...\n\n[提示：使用 read_file 查看文件当前内容，或检查 old_string 是否唯一]'
                )
            
            # 5. 写入新内容
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            # 6. 生成 diff
            diff = _generate_diff(content, new_content, str(path))
            
            result_text = f"✅ 文件已修改：{path}\n"
            result_text += f"匹配数：{match_count} | 策略：{strategy}\n\n"
            result_text += "--- 修改 diff ---\n"
            result_text += diff
            
            return ToolResult(
                success=True,
                content=result_text,
                data={'path': str(path), 'match_count': match_count, 'diff': diff}
            )
            
        except Exception as e:
            logger.error(f"修补文件失败 {file_path}: {e}")
            return ToolResult(
                success=False,
                error=f'修补失败：{str(e)}'
            )


class SearchFilesTool(BaseTool):
    """搜索文件工具"""
    
    name = "search_files"
    description = "搜索文件内容或按名称查找文件。支持正则表达式和 glob 模式。"
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "搜索模式（正则表达式用于内容搜索，glob 用于文件搜索）"
            },
            "target": {
                "type": "string",
                "enum": ["content", "files"],
                "description": "'content' 搜索文件内容，'files' 搜索文件名",
                "default": "content"
            },
            "path": {
                "type": "string",
                "description": "搜索目录（默认当前工作空间）",
                "default": "."
            },
            "file_glob": {
                "type": "string",
                "description": "文件过滤模式（如 '*.py' 只搜索 Python 文件）"
            },
            "limit": {
                "type": "integer",
                "description": "最大结果数",
                "default": 50
            }
        },
        "required": ["pattern"]
    }
    
    async def execute(self, pattern: str, target: str = "content", path: str = ".",
                      file_glob: str = None, limit: int = 50, **kwargs) -> ToolResult:
        """执行搜索"""
        try:
            search_path = _safe_resolve_path(path)
            
            if not search_path.exists():
                return ToolResult(
                    success=False,
                    error=f'搜索路径不存在：{path}'
                )
            
            if target == "files":
                # 文件搜索（glob）
                import glob as glob_module
                glob_pattern = str(search_path / "**" / pattern)
                files = glob_module.glob(glob_pattern, recursive=True)
                
                if file_glob:
                    files = [f for f in files if Path(f).match(file_glob)]
                
                files = files[:limit]
                
                result_text = f"🔎 找到 {len(files)} 个文件:\n\n"
                for f in files[:20]:
                    result_text += f"📄 {f}\n"
                
                if len(files) > 20:
                    result_text += f"\n... 还有 {len(files) - 20} 个文件"
                
                return ToolResult(
                    success=True,
                    content=result_text,
                    data={'files': files, 'total': len(files)}
                )
            
            else:
                # 内容搜索（grep）
                matches = []
                regex = re.compile(pattern, re.MULTILINE)
                
                for file_path in search_path.rglob(file_glob or "*"):
                    if file_path.is_file() and not _is_binary_file(str(file_path)):
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                            
                            for i, line in enumerate(content.split('\n'), 1):
                                if regex.search(line):
                                    matches.append({
                                        'file': str(file_path),
                                        'line': i,
                                        'content': line[:200]
                                    })
                                    if len(matches) >= limit:
                                        break
                        except Exception:
                            pass
                    
                    if len(matches) >= limit:
                        break
                
                result_text = f"🔎 找到 {len(matches)} 个匹配:\n\n"
                for m in matches[:20]:
                    result_text += f"📄 {m['file']}:{m['line']}\n"
                    result_text += f"   {m['content']}\n\n"
                
                if len(matches) > 20:
                    result_text += f"\n... 还有 {len(matches) - 20} 个匹配"
                
                return ToolResult(
                    success=True,
                    content=result_text,
                    data={'matches': matches, 'total': len(matches)}
                )
                
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return ToolResult(
                success=False,
                error=f'搜索失败：{str(e)}'
            )


class ListDirectoryTool(BaseTool):
    """列出目录工具"""
    
    name = "list_directory"
    description = "列出目录中的文件和子目录"
    parameters = {
        "type": "object",
        "properties": {
            "dir_path": {
                "type": "string",
                "description": "要列出的目录路径"
            },
            "include_hidden": {
                "type": "boolean",
                "description": "是否包含隐藏文件",
                "default": False
            }
        },
        "required": ["dir_path"]
    }
    
    async def execute(self, dir_path: str, include_hidden: bool = False, **kwargs) -> ToolResult:
        """执行目录列表"""
        try:
            path = _safe_resolve_path(dir_path)
            
            if not path.exists():
                return ToolResult(success=False, error=f'目录不存在：{dir_path}')
            
            if not path.is_dir():
                return ToolResult(success=False, error=f'不是目录：{dir_path}')
            
            items = []
            for item in sorted(path.iterdir()):
                if include_hidden or not item.name.startswith('.'):
                    items.append({
                        'name': item.name,
                        'is_dir': item.is_dir(),
                        'path': str(item),
                        'size': item.stat().st_size if item.is_file() else None,
                    })
            
            result_text = f"📁 目录：{path}\n\n"
            result_text += f"共 {len(items)} 项:\n\n"
            
            dirs = [i for i in items if i['is_dir']]
            files = [i for i in items if not i['is_dir']]
            
            if dirs:
                result_text += "📁 目录:\n"
                for d in dirs[:20]:
                    result_text += f"   {d['name']}\n"
            
            if files:
                result_text += "\n📄 文件:\n"
                for f in files[:30]:
                    size_str = f" ({f['size']:,} B)" if f['size'] else ""
                    result_text += f"   {f['name']}{size_str}\n"
            
            return ToolResult(
                success=True,
                content=result_text,
                data={'items': items}
            )
            
        except Exception as e:
            logger.error(f"列出目录失败: {e}")
            return ToolResult(success=False, error=f'列出目录失败：{str(e)}')


class CreateDirectoryTool(BaseTool):
    """创建目录工具"""
    
    name = "create_directory"
    description = "创建新目录（包括父目录）"
    parameters = {
        "type": "object",
        "properties": {
            "dir_path": {
                "type": "string",
                "description": "要创建的目录路径"
            }
        },
        "required": ["dir_path"]
    }
    
    async def execute(self, dir_path: str, **kwargs) -> ToolResult:
        """执行创建目录"""
        try:
            path = _safe_resolve_path(dir_path)
            path.mkdir(parents=True, exist_ok=True)
            
            return ToolResult(
                success=True,
                content=f"✅ 目录已创建：{path}"
            )
            
        except Exception as e:
            logger.error(f"创建目录失败: {e}")
            return ToolResult(success=False, error=f'创建目录失败：{str(e)}')


class DeleteFileTool(BaseTool):
    """删除文件工具"""
    
    name = "delete_file"
    description = "删除文件。危险操作需要用户审批。"
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "要删除的文件路径"
            }
        },
        "required": ["file_path"]
    }
    
    async def execute(self, file_path: str, **kwargs) -> ToolResult:
        """执行删除文件"""
        try:
            # 1. 敏感路径检查
            sensitive_error = _check_sensitive_path(file_path)
            if sensitive_error:
                return ToolResult(success=False, error=sensitive_error)
            
            # 2. 写入 deny list 检查
            if _is_write_denied(file_path):
                return ToolResult(
                    success=False,
                    error=f"拒绝删除：'{file_path}' 是受保护的文件"
                )
            
            # 3. 解析路径
            path = _safe_resolve_path(file_path)
            
            if not path.exists():
                return ToolResult(success=False, error=f'文件不存在：{file_path}')
            
            if not path.is_file():
                return ToolResult(success=False, error=f'不是文件：{file_path}')
            
            # 4. 删除文件
            path.unlink()
            
            return ToolResult(
                success=True,
                content=f"✅ 文件已删除：{path}"
            )
            
        except Exception as e:
            logger.error(f"删除文件失败: {e}")
            return ToolResult(success=False, error=f'删除文件失败：{str(e)}')


# ═══════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════

def _is_blocked_device(filepath: str) -> bool:
    """检查是否是设备文件"""
    normalized = os.path.expanduser(filepath)
    if normalized in _BLOCKED_DEVICE_PATHS:
        return True
    if normalized.startswith("/proc/") and normalized.endswith(("/fd/0", "/fd/1", "/fd/2")):
        return True
    return False


def _is_binary_file(filepath: str) -> bool:
    """检查是否是二进制文件"""
    ext = Path(filepath).suffix.lower()
    return ext in _BINARY_EXTENSIONS


def _check_sensitive_path(filepath: str) -> str:
    """检查是否是敏感路径"""
    try:
        resolved = os.path.realpath(os.path.expanduser(filepath))
        for prefix in _SENSITIVE_PATH_PREFIXES:
            if resolved.startswith(prefix):
                return f"拒绝访问敏感系统路径：{filepath}"
        if resolved in _SENSITIVE_EXACT_PATHS:
            return f"拒绝访问敏感系统路径：{filepath}"
    except Exception:
        pass
    return ""


def _is_write_denied(path: str) -> bool:
    """检查是否在写入 deny list 上"""
    resolved = os.path.realpath(os.path.expanduser(str(path)))
    for denied in _WRITE_DENIED_PATHS:
        if str(resolved).endswith(denied):
            return True
    return False


def _safe_resolve_path(file_path: str) -> Path:
    """安全解析文件路径（优先使用用户选择的工作空间路径）"""
    path = Path(file_path)
    
    if not path.is_absolute():
        # 优先使用用户选择的工作空间路径
        workspace = os.environ.get('LAWYERCLAW_WORKSPACE')
        if workspace and os.path.isdir(workspace):
            base = Path(workspace)
        else:
            base = DEFAULT_WORKSPACE_ROOT
        path = base / path
    
    try:
        return path.resolve()
    except Exception:
        return path


def _fuzzy_find_and_replace(content: str, old_string: str, new_string: str,
                            replace_all: bool = False):
    """
    模糊查找替换（简化版）
    
    Returns:
        (new_content, match_count, strategy, error)
    """
    # 策略 1: 精确匹配
    if old_string in content:
        if replace_all:
            return content.replace(old_string, new_string), content.count(old_string), "exact", None
        else:
            return content.replace(old_string, new_string, 1), 1, "exact", None
    
    # 策略 2: 忽略空白匹配
    def normalize_whitespace(s):
        return ' '.join(s.split())
    
    normalized_old = normalize_whitespace(old_string)
    normalized_content = normalize_whitespace(content)
    
    if normalized_old in normalized_content:
        # 找到位置并替换
        return content.replace(old_string, new_string, 1 if not replace_all else 0), 1, "whitespace", None
    
    # 策略 3: 行级匹配
    old_lines = old_string.split('\n')
    content_lines = content.split('\n')
    
    for i in range(len(content_lines) - len(old_lines) + 1):
        if all(normalize_whitespace(old_lines[j]) == normalize_whitespace(content_lines[i + j])
               for j in range(len(old_lines))):
            # 找到匹配
            new_lines = content_lines[:i] + new_string.split('\n') + content_lines[i + len(old_lines):]
            return '\n'.join(new_lines), 1, "line", None
    
    return content, 0, None, "未找到匹配项"


def _generate_diff(old_content: str, new_content: str, filename: str) -> str:
    """生成统一 diff"""
    import difflib
    
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)
    
    diff = difflib.unified_diff(
        old_lines, new_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}"
    )
    
    return ''.join(diff)


# ═══════════════════════════════════════════════════════════
# 工具注册
# ═══════════════════════════════════════════════════════════

# 创建工具实例
FILE_TOOLS = [
    ReadFileTool(),
    WriteFileTool(),
    PatchFileTool(),
    SearchFilesTool(),
    ListDirectoryTool(),
    CreateDirectoryTool(),
    DeleteFileTool(),
]


def register_all():
    """注册所有文件工具到主注册表"""
    # 延迟导入以避免循环依赖
    from service.tools.legal_tools import registry as main_registry
    
    for tool in FILE_TOOLS:
        try:
            main_registry.register(tool)
            logger.info(f"已注册文件工具：{tool.name}")
        except Exception as e:
            logger.error(f"注册工具失败 {tool.name}: {e}")
