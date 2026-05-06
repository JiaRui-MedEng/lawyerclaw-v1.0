"""
文件操作工具 - Hermes 风格

提供文件读取、列表等工具，供 AI 主动调用。
"""
from service.tools.legal_tools import BaseTool, ToolResult
from service.tools.file_utils import read_file_content, safe_resolve_path
from pathlib import Path
import os


class FileReadTool(BaseTool):
    """
    文件读取工具
    
    当用户提到某个文件但 AI 没有内容时，使用此工具读取文件。
    """
    
    name = "file_read"
    description = "读取本地文件内容。当用户提到某个文件（如合同、文档、图片等）但你没有看到内容时，使用此工具读取。支持读取文本文件（.md, .txt, .py, .js, .json 等）。"
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "要读取的文件路径（绝对路径或相对于工作空间的路径）"
            }
        },
        "required": ["file_path"]
    }
    
    async def execute(self, file_path: str, **kwargs) -> ToolResult:
        """执行文件读取"""
        result = read_file_content(file_path, max_chars=50000)  # 增加限制到 50KB
        
        if result['success']:
            # 构建工具返回内容
            content = f"📄 文件：{result['path']}\n"
            content += f"大小：{result.get('file_size', 0)} 字节\n\n"
            content += "--- 文件内容开始 ---\n"
            content += result['content']
            content += "\n--- 文件内容结束 ---"
            
            if result.get('truncated'):
                content += "\n\n⚠️ 注意：文件内容已截断，只显示前 50000 字符。"
            
            return ToolResult(
                success=True,
                content=content,
                data=result
            )
        else:
            return ToolResult(
                success=False,
                error=result['error']
            )


class FileListTool(BaseTool):
    """
    目录列表工具
    
    列出指定目录中的文件和子目录。
    """
    
    name = "file_list"
    description = "列出目录中的文件和子目录。当用户需要了解某个目录的内容时使用此工具。"
    parameters = {
        "type": "object",
        "properties": {
            "dir_path": {
                "type": "string",
                "description": "要列出的目录路径"
            },
            "include_hidden": {
                "type": "boolean",
                "description": "是否包含隐藏文件（以.开头的文件）",
                "default": False
            }
        },
        "required": ["dir_path"]
    }
    
    async def execute(self, dir_path: str, include_hidden: bool = False, **kwargs) -> ToolResult:
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
                # 跳过隐藏文件（除非明确要求）
                if not include_hidden and item.name.startswith('.'):
                    continue
                
                # 跳过 node_modules 等大目录
                if item.name == 'node_modules' or item.name.startswith('__'):
                    continue
                
                items.append({
                    'name': item.name,
                    'is_dir': item.is_dir(),
                    'path': str(item),
                    'size': item.stat().st_size if item.is_file() else 0
                })
                
                # 限制返回数量
                if len(items) >= 100:
                    break
            
            # 构建返回内容
            dirs = [i for i in items if i['is_dir']]
            files = [i for i in items if not i['is_dir']]
            
            content = f"📁 目录：{path}\n\n"
            content += f"共 {len(items)} 项（{len(dirs)} 个目录，{len(files)} 个文件）\n\n"
            
            if dirs:
                content += "📂 目录:\n"
                for d in dirs[:50]:
                    content += f"  📁 {d['name']}/\n"
                if len(dirs) > 50:
                    content += f"  ... 还有 {len(dirs) - 50} 个目录\n"
                content += "\n"
            
            if files:
                content += "📄 文件:\n"
                for f in files[:50]:
                    size_str = f"({self._format_size(f['size'])})" if f['size'] > 0 else ""
                    content += f"  📄 {f['name']} {size_str}\n"
                if len(files) > 50:
                    content += f"  ... 还有 {len(files) - 50} 个文件\n"
            
            return ToolResult(
                success=True,
                content=content,
                data={'items': items}
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f'列出目录失败：{str(e)}'
            )
    
    def _format_size(self, size: int) -> str:
        """格式化文件大小"""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size/1024:.1f} KB"
        else:
            return f"{size/(1024*1024):.1f} MB"


class FileSearchTool(BaseTool):
    """
    文件搜索工具
    
    在指定目录中搜索匹配的文件。
    """
    
    name = "file_search"
    description = "在目录中搜索匹配的文件。支持通配符（*, ?）。例如：*.py 搜索所有 Python 文件。"
    parameters = {
        "type": "object",
        "properties": {
            "dir_path": {
                "type": "string",
                "description": "搜索的目录路径"
            },
            "pattern": {
                "type": "string",
                "description": "搜索模式（支持通配符 *, ?）"
            },
            "recursive": {
                "type": "boolean",
                "description": "是否递归搜索子目录",
                "default": False
            }
        },
        "required": ["dir_path", "pattern"]
    }
    
    async def execute(self, dir_path: str, pattern: str, recursive: bool = False, **kwargs) -> ToolResult:
        """执行文件搜索"""
        try:
            path = safe_resolve_path(dir_path)
            
            if not path.exists():
                return ToolResult(
                    success=False,
                    error=f'目录不存在：{dir_path}'
                )
            
            import fnmatch
            
            matches = []
            
            if recursive:
                # 递归搜索
                for root, dirs, files in os.walk(path):
                    # 跳过隐藏目录
                    dirs[:] = [d for d in dirs if not d.startswith('.')]
                    
                    for filename in files:
                        if fnmatch.fnmatch(filename, pattern):
                            matches.append(os.path.join(root, filename))
                            if len(matches) >= 100:
                                break
                    if len(matches) >= 100:
                        break
            else:
                # 只搜索当前目录
                for item in path.iterdir():
                    if item.is_file() and fnmatch.fnmatch(item.name, pattern):
                        matches.append(str(item))
            
            # 构建返回内容
            content = f"🔍 搜索结果：{pattern}\n"
            content += f"搜索目录：{path}\n"
            content += f"找到 {len(matches)} 个匹配的文件\n\n"
            
            if matches:
                content += "匹配的文件:\n"
                for m in matches[:50]:
                    content += f"  📄 {m}\n"
                if len(matches) > 50:
                    content += f"  ... 还有 {len(matches) - 50} 个文件\n"
            else:
                content += "没有找到匹配的文件。\n"
            
            return ToolResult(
                success=True,
                content=content,
                data={'matches': matches}
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f'搜索失败：{str(e)}'
            )


# 工具注册表
file_tools_registry = {
    'file_read': FileReadTool(),
    'file_list': FileListTool(),
    'file_search': FileSearchTool()
}
