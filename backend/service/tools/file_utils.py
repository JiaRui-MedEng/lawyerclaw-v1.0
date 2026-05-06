"""
文件操作工具模块

基于 Hermes Agent file_tools.py 架构实现:
- 文件读取/写入工具
- 安全检查机制
- 设备路径阻止
- 二进制文件检测
- 读取大小限制
- 防循环机制
"""
import os
import re
import json
import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

from service.tools.legal_tools import BaseTool, ToolResult

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# 安全配置
# ═══════════════════════════════════════════════════════════

# 工作空间根目录
from service.core.paths import get_app_root
WORKSPACE_ROOT = get_app_root()

# 读取限制
DEFAULT_MAX_CHARS = 10000  # 默认 10K 字符
DEFAULT_MAX_READ_CHARS = 100000  # 最大 100K 字符

# 设备路径阻止列表（防止挂起进程）
_BLOCKED_DEVICE_PATHS = frozenset({
    "/dev/zero", "/dev/random", "/dev/urandom", "/dev/full",
    "/dev/stdin", "/dev/tty", "/dev/console",
    "/dev/stdout", "/dev/stderr",
})

# 二进制文件扩展名（这些需要特殊处理）
_BINARY_EXTENSIONS = {
    '.exe', '.dll', '.so', '.bin', '.dat',
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico',
    '.zip', '.rar', '.tar', '.gz', '.7z',
    '.pyc', '.pyo', '.o', '.a', '.lib',
    '.mp3', '.mp4', '.avi', '.mov', '.mkv',
}

# 文档文件扩展名（可以解析）
_DOCUMENT_EXTENSIONS = {
    '.pdf': 'PDF 文档',
    '.docx': 'Word 文档',
    '.doc': 'Word 文档 (旧版)',
    '.pptx': 'PowerPoint 演示文稿',
    '.xlsx': 'Excel 工作表',
}

# 敏感路径前缀
_SENSITIVE_PATH_PREFIXES = ("/etc/", "/boot/", "/usr/lib/systemd/")
_SENSITIVE_EXACT_PATHS = {"/var/run/docker.sock", "/run/docker.sock"}


def extract_file_paths(content: str) -> List[str]:
    """
    从消息内容中提取文件路径
    
    支持格式:
    - 📎 附件文件:
    - 📎 附件文件路径:
    - 文件路径:
    - `path`
    - 纯路径（D:\\xxx 或 /xxx）
    """
    paths = []
    
    # 匹配 📎 附件文件：或 📎 附件文件路径：后面的行
    attachment_match = re.search(
        r'📎 附件文件:\s*\n([ ^\n]+(?:\n[^\n]+)*)', 
        content, 
        re.DOTALL
    )
    if attachment_match:
        path_section = attachment_match.group(1)
        for line in path_section.strip().split('\n'):
            line = line.strip()
            if line and not line.startswith('-') and not line.startswith('📎'):
                # 移除 Markdown 格式
                path = line.strip('`').strip()
                if path:
                    # ⭐ 修复：处理可能的转义字符问题
                    # 如果路径中包含 \t \n 等，尝试替换为实际字符
                    path = path.replace('\\t', '\t').replace('\\n', '\n').replace('\\r', '\r')
                    paths.append(path)
    
    # 匹配反引号包裹的路径
    backtick_paths = re.findall(r'`([^`]*?\.[\w]+)`', content)
    paths.extend(backtick_paths)
    
    # 匹配纯路径（Windows 或 Unix）
    # Windows: D:\path\to\file.ext (改进：允许路径中包含制表符等，直到行尾或双空格)
    win_paths = re.findall(r'([A-Za-z]:\\[^\n]+?)(?=\s{{2}}|\n|$)', content)
    # 清理路径末尾的空白
    win_paths = [p.rstrip() for p in win_paths]
    paths.extend(win_paths)
    
    # Unix: /path/to/file.ext
    unix_paths = re.findall(r'(?<!`)(/[^\s\n]+\.[\w]+)(?!`)', content)
    paths.extend(unix_paths)
    
    # 去重并过滤空路径
    return list(set(p for p in paths if p.strip()))


def _is_blocked_device(filepath: str) -> bool:
    """检查是否是设备文件（会挂起进程）"""
    normalized = os.path.expanduser(filepath)
    if normalized in _BLOCKED_DEVICE_PATHS:
        return True
    # /proc/self/fd/0-2
    if normalized.startswith("/proc/") and normalized.endswith(("/fd/0", "/fd/1", "/fd/2")):
        return True
    return False


def _is_binary_file(filepath: str) -> bool:
    """检查是否是二进制文件（根据扩展名）"""
    ext = Path(filepath).suffix.lower()
    # 文档文件不算二进制文件（可以解析）
    if ext in _DOCUMENT_EXTENSIONS:
        return False
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


def safe_resolve_path(file_path: str) -> Path:
    """
    安全解析文件路径
    
    Args:
        file_path: 文件路径
        
    Returns:
        Path: 解析后的路径
    """
    path = Path(file_path)
    
    # 如果是相对路径，相对于工作空间解析
    if not path.is_absolute():
        path = WORKSPACE_ROOT / path
    
    try:
        resolved = path.resolve()
        return resolved
    except Exception:
        return path


def read_file_content(
    file_path: str, 
    max_chars: int = DEFAULT_MAX_CHARS,
    offset: int = 1,
    limit: int = 500
) -> Dict[str, Any]:
    """
    读取文件内容（基于 Hermes file_tools.py 架构）
    
    Args:
        file_path: 文件路径
        max_chars: 最大读取字符数（默认 10K）
        offset: 起始行号（1-indexed）
        limit: 读取行数（默认 500）
        
    Returns:
        {
            'success': bool,
            'path': str,
            'content': str or None,
            'error': str or None,
            'truncated': bool,
            'file_size': int,
            'total_lines': int,
            'offset': int,
            'limit': int
        }
    """
    try:
        # 1. 设备路径检查
        if _is_blocked_device(file_path):
            return {
                'success': False,
                'path': file_path,
                'error': f"无法读取 '{file_path}': 这是设备文件"
            }
        
        # 2. 敏感路径检查
        sensitive_error = _check_sensitive_path(file_path)
        if sensitive_error:
            return {
                'success': False,
                'path': file_path,
                'error': sensitive_error
            }
        
        # 3. 解析路径
        path = safe_resolve_path(file_path)
        
        if not path.exists():
            return {
                'success': False,
                'path': str(path),
                'error': f'文件不存在：{file_path}'
            }
        
        if not path.is_file():
            return {
                'success': False,
                'path': str(path),
                'error': f'不是文件：{file_path}'
            }
        
        # 4. 文档文件和二进制文件检查
        ext = path.suffix.lower()
        
        # 4.1 文档文件（可以解析）
        if ext in _DOCUMENT_EXTENSIONS:
            logger.info(f"📄 检测到文档文件：{ext}")
            from service.tools.document_parser import parse_document
            
            logger.info(f"📖 解析文档：{path}")
            result = parse_document(str(path))
            
            if result.get('success'):
                content = result.get('content', '')
                file_size = path.stat().st_size
                
                # 检查是否超过限制
                truncated = False
                if len(content) > max_chars:
                    content = content[:max_chars]
                    truncated = True
                
                # 添加行号
                numbered_content = '\n'.join([
                    f"{i + 1:6d}: {line}"
                    for i, line in enumerate(content.split('\n'))
                ])
                
                return {
                    'success': True,
                    'path': str(path),
                    'content': numbered_content,
                    'truncated': truncated,
                    'file_size': file_size,
                    'total_lines': len(content.split('\n')),
                    'offset': offset,
                    'limit': limit,
                    'file_type': result.get('file_type'),
                    'pages': result.get('pages', result.get('slides', result.get('sheets', 0))),
                    'hint': f"[文档类型：{_DOCUMENT_EXTENSIONS.get(ext, '未知')}, {result.get('pages', result.get('slides', result.get('sheets', 0)))} 页/段落]"
                }
            else:
                return {
                    'success': False,
                    'path': str(path),
                    'error': f'文档解析失败：{result.get("error")}'
                }
        
        # 4.2 二进制文件（图片、视频、音频等）
        if ext in _BINARY_EXTENSIONS:
            file_size = path.stat().st_size
            
            # 图片文件提供 base64 编码 + OCR 提示
            if ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']:
                import base64
                try:
                    with open(path, 'rb') as f:
                        file_data = f.read()
                        base64_data = base64.b64encode(file_data).decode('utf-8')
                        
                        return {
                            'success': True,
                            'path': str(path),
                            'content': f'[图片文件，base64 编码，{file_size} 字节]\n\n提示：可以使用 vision_analyze 或 ocr_extract 工具分析此图片内容或提取文字。',
                            'file_size': file_size,
                            'file_type': '图片',
                            'mime_type': f'image/{ext.replace(".", "")}',
                            'base64_length': len(base64_data),
                            'hint': f"[图片文件：{ext.replace('.', '').upper()}，{file_size / 1024:.1f} KB]"
                        }
                except Exception as e:
                    return {
                        'success': False,
                        'path': str(path),
                        'error': f'图片读取失败：{str(e)}'
                    }
            else:
                return {
                    'success': False,
                    'path': str(path),
                    'error': f'二进制文件 ({ext}) 无法直接读取，请使用专用工具',
                    'file_size': file_size,
                    'file_type': 'binary',
                    'hint': f"[二进制文件：{ext[1:].upper()}，{file_size:,} 字节]"
                }
        
        # 5. 文件大小检查（根据文件类型动态调整）
        file_size = path.stat().st_size
        ext = path.suffix.lower()
        
        # 不同类型文件的大小限制
        if ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp']:
            # 图片文件：允许 5MB（但应该用 vision 工具）
            max_file_size = 5 * 1024 * 1024
        elif ext in ['.pdf', '.docx', '.pptx', '.xlsx', '.xls']:
            # 文档文件：允许 2MB
            max_file_size = 2 * 1024 * 1024
        else:
            # 文本文件：默认限制（max_chars 的 10 倍）
            max_file_size = max(max_chars * 10, 500 * 1024)  # 至少 500KB
        
        if file_size > max_file_size:
            return {
                'success': False,
                'path': str(path),
                'error': f'文件过大 ({file_size:,} 字节)，最大支持 {max_file_size:,} 字节',
                'file_size': file_size
            }
        
        # 6. 读取文件
        with open(path, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
        
        total_lines = len(all_lines)
        
        # 7. 分页处理
        start_idx = max(0, offset - 1)
        end_idx = min(total_lines, start_idx + limit)
        content_lines = all_lines[start_idx:end_idx]
        
        content = ''.join(content_lines)
        
        # 8. 字符数检查
        if len(content) > max_chars:
            content = content[:max_chars]
            truncated = True
        else:
            truncated = file_size > max_chars or end_idx < total_lines
        
        # 9. 添加行号
        numbered_content = ''.join([
            f"{i + start_idx + 1:6d}: {line}"
            for i, line in enumerate(content_lines)
        ])
        
        # 10. 大文件提示
        hint = ""
        if file_size > 512_000 and limit > 200:  # 512KB
            hint = f"[提示：此文件较大 ({file_size:,} 字节)，建议使用 offset 和 limit 参数读取特定部分]"
        
        return {
            'success': True,
            'path': str(path),
            'content': numbered_content,
            'truncated': truncated,
            'file_size': file_size,
            'total_lines': total_lines,
            'offset': offset,
            'limit': limit,
            'hint': hint if hint else None
        }
        
    except UnicodeDecodeError as e:
        return {
            'success': False,
            'path': file_path,
            'error': f'文件编码错误：{str(e)}。文件可能不是 UTF-8 编码'
        }
    except Exception as e:
        return {
            'success': False,
            'path': file_path,
            'error': f'读取失败：{str(e)}'
        }


def build_file_context(file_results: List[Dict[str, Any]]) -> str:
    """
    构建文件内容上下文，注入到 AI 系统提示中
    
    Args:
        file_results: read_file_content 返回的结果列表
        
    Returns:
        格式化的文件内容文本
    """
    if not file_results:
        return ""
    
    context_parts = []
    context_parts.append("📎 用户附件文件内容：")
    context_parts.append("=" * 60)
    
    for result in file_results:
        if result['success']:
            context_parts.append(f"\n📄 文件：{result['path']}")
            context_parts.append(f"   大小：{result.get('file_size', 0):,} 字节")
            
            # ⭐ 特殊处理图片文件
            if result.get('file_type') == 'image':
                context_parts.append(f"   类型：图片 ({result.get('mime_type', 'unknown')})")
                if result.get('hint'):
                    context_parts.append(f"   {result['hint']}")
                context_parts.append("\n--- 图片内容 (Base64) ---")
                # 包含完整的 base64 数据，供 Vision 模型使用
                context_parts.append(f"data:{result.get('mime_type', 'image/png')};base64,{result.get('base64', '')}")
                context_parts.append("--- 图片内容结束 ---\n")
            else:
                # 普通文本文件
                context_parts.append(f"   行数：{result.get('total_lines', 0)} 行")
                if result.get('truncated'):
                    context_parts.append(f"   (内容已截断，显示第 {result['offset']}-{result['offset'] + result['limit'] - 1} 行)")
                if result.get('hint'):
                    context_parts.append(f"   {result['hint']}")
                context_parts.append("\n--- 文件内容开始 ---")
                context_parts.append(result['content'])
                context_parts.append("--- 文件内容结束 ---\n")
        else:
            context_parts.append(f"\n❌ 文件读取失败：{result['path']}")
            context_parts.append(f"   错误：{result['error']}")
    
    context_parts.append("=" * 60)
    context_parts.append("\n[系统提示：以上是用户附件文件的完整内容。请根据这些文件内容和用户的问题进行分析、回答。]")
    
    return "\n".join(context_parts)


class FileReadTool(BaseTool):
    """文件读取工具（基于 Hermes 架构）"""
    
    name = "file_read"
    description = "读取本地文件内容。支持分页（offset/limit），自动检测二进制文件和敏感路径。"
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "要读取的文件路径"
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
        result = read_file_content(file_path, offset=offset, limit=limit)
        
        if result['success']:
            return ToolResult(
                success=True,
                content=f"文件内容:\n{result['content']}",
                data=result
            )
        else:
            return ToolResult(
                success=False,
                error=result['error']
            )


class FileListTool(BaseTool):
    """目录列表工具"""
    
    name = "file_list"
    description = "列出目录中的文件和子目录"
    parameters = {
        "type": "object",
        "properties": {
            "dir_path": {
                "type": "string",
                "description": "要列出的目录路径"
            }
        },
        "required": ["dir_path"]
    }
    
    async def execute(self, dir_path: str, **kwargs) -> ToolResult:
        """执行目录列表"""
        try:
            path = safe_resolve_path(dir_path)
            
            if not path.exists():
                return ToolResult(
                    success=False,
                    error=f'目录不存在：{dir_path}'
                )
            
            if not path.is_dir():
                return ToolResult(
                    success=False,
                    error=f'不是目录：{dir_path}'
                )
            
            items = []
            for item in sorted(path.iterdir()):
                if not item.name.startswith('.'):
                    items.append({
                        'name': item.name,
                        'is_dir': item.is_dir(),
                        'path': str(item),
                        'size': item.stat().st_size if item.is_file() else None,
                        'modified': datetime.fromtimestamp(item.stat().st_mtime).isoformat()
                    })
            
            return ToolResult(
                success=True,
                content=f"目录内容 ({len(items)} 项):\n" + "\n".join(
                    f"{'📁' if i['is_dir'] else '📄'} {i['name']} ({i['size']:,} bytes)" if i['size'] else f"{'📁' if i['is_dir'] else '📄'} {i['name']}"
                    for i in items[:50]
                ),
                data={'items': items}
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f'列出目录失败：{str(e)}'
            )


# 工具注册表
file_tools_registry = {
    'file_read': FileReadTool(),
    'file_list': FileListTool()
}
