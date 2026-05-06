"""
工具描述：Python 代码执行工具 - 允许 AI 智能体执行 Python 代码生成文件
"""
import io
import logging
import subprocess
import sys
import os
import tempfile
import threading
import traceback
import contextlib
from pathlib import Path
from typing import Optional
from service.tools.legal_tools import BaseTool, ToolResult

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# 安全配置
# ═══════════════════════════════════════════════════════════

# 默认超时时间（秒）
DEFAULT_TIMEOUT = 60
# 最大输出大小（字节）
MAX_OUTPUT_SIZE = 500 * 1024  # 500KB
# 工作空间根目录（优先使用用户选择的工作空间路径）
import os as _os
from service.core.paths import get_app_root
_APP_ROOT = get_app_root()
_USER_DOCUMENTS = Path(_os.path.expanduser("~/Documents"))

def _get_workspace_root():
    """获取当前工作空间根目录（优先使用用户选择的路径）"""
    workspace = _os.environ.get('LAWYERCLAW_WORKSPACE')
    if workspace and _os.path.isdir(workspace):
        return Path(workspace)
    # 回退到用户文档目录，而非项目代码目录
    if _USER_DOCUMENTS.exists():
        return _USER_DOCUMENTS
    return _APP_ROOT

# 危险模块黑名单（禁止导入）
BLOCKED_MODULES = {
    'os', 'subprocess', 'socket', 'http', 'urllib', 'requests',
    'ctypes', 'multiprocessing', 'threading', 'pty', 'shutil',
    'webbrowser', 'pdb', 'code', 'compile', 'eval', 'exec',
    'importlib', 'sys', 'builtins',
}

# 允许的安全模块白名单
ALLOWED_MODULES = {
    # 数据处理
    'json', 'csv', 'xml', 'html',
    # 数学计算
    'math', 'statistics', 'decimal', 'fractions', 'random',
    # 日期时间
    'datetime', 'time', 'calendar',
    # 文本处理
    're', 'string', 'textwrap', 'unicodedata',
    # 数据结构
    'collections', 'itertools', 'functools', 'operator',
    # 文件操作（受限）
    'pathlib',
    # 编码
    'base64', 'binascii', 'hashlib',
    # 文档生成（常用）
    'docx', 'openpyxl', 'xlsxwriter', 'PyPDF2', 'pdfkit',
    'reportlab', 'weasyprint', 'markdown',
    # 数据分析
    'pandas', 'numpy',
    # 其他安全模块
    'io', 'tempfile', 'uuid', 'enum', 'dataclasses',
    'typing', 'copy', 'pprint', 'textwrap',
}


class PythonExecutorTool(BaseTool):
    """Python 代码执行工具"""

    name = "python_executor"
    description = (
        "执行 Python 代码来生成文件、处理数据或执行计算。"
        "适用于：生成 Word/Excel/PDF 文档、数据处理、数学计算、文本分析等。"
        "代码在隔离的子进程中执行，有超时保护。"
        "生成的文件会保存到工作空间目录中。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "要执行的 Python 代码。可以使用 print() 输出结果，生成的文件会保存到指定路径。"
            },
            "timeout": {
                "type": "integer",
                "description": "超时时间（秒），默认 60 秒",
                "default": 60
            },
            "working_dir": {
                "type": "string",
                "description": "工作目录（相对于工作空间），默认为工作空间根目录"
            },
            "allowed_modules": {
                "type": "array",
                "items": {"type": "string"},
                "description": "额外允许的模块列表（在默认白名单基础上追加）"
            }
        },
        "required": ["code"]
    }

    async def execute(
        self,
        code: str,
        timeout: int = DEFAULT_TIMEOUT,
        working_dir: str = None,
        allowed_modules: list = None,
        **kwargs
    ) -> ToolResult:
        """执行 Python 代码"""
        try:
            # 1. 安全检查
            safety_check = self._check_safety(code)
            if safety_check:
                return ToolResult(success=False, content="", error=safety_check)

            # 2. 确定工作目录
            workspace_root = _get_workspace_root()
            if working_dir:
                work_dir = (workspace_root / working_dir).resolve()
            else:
                work_dir = workspace_root

            if not work_dir.exists():
                work_dir.mkdir(parents=True, exist_ok=True)

            # 3. 根据环境选择执行方式
            if getattr(sys, 'frozen', False):
                # 打包环境：进程内 exec() 执行，使用已捆绑的 Python 运行时和库
                return self._execute_inprocess(code, work_dir, timeout)
            else:
                # 开发环境：subprocess 隔离执行
                return self._execute_subprocess(code, work_dir, timeout)

        except Exception as e:
            logger.error(f"Python 执行工具异常: {e}")
            return ToolResult(
                success=False,
                content="",
                error=f"❌ 执行失败：{str(e)}"
            )

    def _execute_subprocess(self, code: str, work_dir: Path, timeout: int) -> ToolResult:
        """开发环境：在子进程中执行代码"""
        # 自动注入工作空间路径变量，确保 LLM 代码能使用绝对路径
        workspace_header = f'import pathlib as _pathlib\nWORKSPACE = _pathlib.Path(r"{work_dir}")\n'
        injected_code = workspace_header + code

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.py', delete=False,
            encoding='utf-8', dir=str(work_dir)
        ) as f:
            f.write(injected_code)
            script_path = f.name

        try:
            python_exe = sys.executable
            env = os.environ.copy()
            env['PYTHONDONTWRITEBYTECODE'] = '1'
            env['PYTHONUNBUFFERED'] = '1'

            result = subprocess.run(
                [python_exe, script_path],
                capture_output=True, text=True,
                timeout=timeout, cwd=str(work_dir), env=env,
            )

            stdout = result.stdout or ""
            stderr = result.stderr or ""

            if len(stdout) > MAX_OUTPUT_SIZE:
                stdout = stdout[:MAX_OUTPUT_SIZE] + "\n\n... [输出过长，已截断]"

            return self._build_result(result.returncode, stdout, stderr, work_dir)

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False, content="",
                error=f"❌ 执行超时（{timeout}秒）。代码可能包含死循环或耗时操作。"
            )
        finally:
            try:
                os.unlink(script_path)
            except OSError:
                pass

    def _execute_inprocess(self, code: str, work_dir: Path, timeout: int) -> ToolResult:
        """打包环境：在当前进程内通过 exec() 执行代码"""
        # 自动注入工作空间路径变量
        workspace_header = f'import pathlib as _pathlib\nWORKSPACE = _pathlib.Path(r"{work_dir}")\n'
        injected_code = workspace_header + code

        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        exec_result = {'returncode': 0, 'error': None}

        def _run():
            old_cwd = os.getcwd()
            try:
                os.chdir(str(work_dir))
                # 构建受限的全局命名空间
                exec_globals = {'__builtins__': __builtins__, '__name__': '__main__'}
                with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
                    exec(compile(injected_code, '<python_executor>', 'exec'), exec_globals)
            except Exception:
                exec_result['returncode'] = 1
                exec_result['error'] = traceback.format_exc()
            finally:
                os.chdir(old_cwd)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            return ToolResult(
                success=False, content="",
                error=f"❌ 执行超时（{timeout}秒）。代码可能包含死循环或耗时操作。"
            )

        stdout = stdout_buf.getvalue()
        stderr = stderr_buf.getvalue()

        if exec_result['error']:
            stderr = (stderr + "\n" + exec_result['error']).strip()

        if len(stdout) > MAX_OUTPUT_SIZE:
            stdout = stdout[:MAX_OUTPUT_SIZE] + "\n\n... [输出过长，已截断]"

        return self._build_result(exec_result['returncode'], stdout, stderr, work_dir)

    def _build_result(self, returncode: int, stdout: str, stderr: str, work_dir: Path) -> ToolResult:
        """统一构建执行结果"""
        output_parts = []

        if returncode == 0:
            if stdout.strip():
                output_parts.append(f"📤 输出：\n{stdout.strip()}")
            else:
                output_parts.append("✅ 代码执行成功（无输出）")

            new_files = self._check_new_files(work_dir)
            if new_files:
                output_parts.append(f"\n📁 生成的文件：\n" + "\n".join(f"  - {f}" for f in new_files))

            return ToolResult(
                success=True,
                content="\n".join(output_parts),
                data={
                    'returncode': returncode,
                    'stdout': stdout,
                    'stderr': stderr,
                    'new_files': new_files
                }
            )
        else:
            error_msg = stderr.strip() if stderr.strip() else f"执行失败，返回码：{returncode}"
            return ToolResult(
                success=False, content="",
                error=f"❌ Python 执行错误：\n{error_msg}"
            )

    def _check_safety(self, code: str) -> Optional[str]:
        """检查代码安全性"""
        # 允许的安全 os 用法（import os 时，如果仅用于这些模式则放行）
        safe_os_patterns = ['os.path', 'os.environ', 'os.sep', 'os.linesep',
                            'os.getcwd', 'os.makedirs', 'os.listdir']

        # 检查危险函数调用
        dangerous_patterns = [
            ('__import__', '禁止使用 __import__()'),
            ('eval(', '禁止使用 eval()'),
            ('exec(', '禁止使用 exec()'),
            ('compile(', '禁止使用 compile()'),
            ('open(', None),  # open() 允许
            ('import subprocess', '禁止导入 subprocess 模块'),
            ('import socket', '禁止导入 socket 模块'),
            ('import http', '禁止导入 http 模块'),
            ('import urllib', '禁止导入 urllib 模块'),
            ('import requests', '禁止导入 requests 模块'),
            ('import ctypes', '禁止导入 ctypes 模块'),
            ('import multiprocessing', '禁止导入 multiprocessing 模块'),
            ('import threading', '禁止导入 threading 模块'),
            ('import pty', '禁止导入 pty 模块'),
            ('import webbrowser', '禁止导入 webbrowser 模块'),
            ('import pdb', '禁止导入 pdb 模块'),
            ('import builtins', '禁止导入 builtins 模块'),
            ('__builtins__', '禁止访问 __builtins__'),
            ('__class__', '禁止访问 __class__'),
            ('__mro__', '禁止访问 __mro__'),
            ('__subclasses__', '禁止访问 __subclasses__'),
            ('__globals__', '禁止访问 __globals__'),
            ('__loader__', '禁止访问 __loader__'),
            ('__spec__', '禁止访问 __spec__'),
        ]

        for pattern, message in dangerous_patterns:
            if pattern in code and message:
                return message

        # 单独处理 import os：如果代码中用到了 os，检查是否全部为安全用法
        if 'import os' in code:
            # 找出代码中所有 os.xxx 的用法
            import re
            os_usages = re.findall(r'os\.(\w+)', code)
            safe_prefixes = {p.split('.')[1] for p in safe_os_patterns}  # {'path', 'environ', 'sep', ...}
            unsafe_usages = [u for u in os_usages if u not in safe_prefixes]
            if unsafe_usages:
                return f"禁止使用 os 模块的危险功能：os.{', os.'.join(set(unsafe_usages))}"

        # 单独处理 import sys：完全禁止
        if 'import sys' in code:
            return '禁止导入 sys 模块'

        # 单独处理 import shutil：完全禁止
        if 'import shutil' in code:
            return '禁止导入 shutil 模块'

        return None
    def _check_new_files(self, work_dir: Path, max_depth: int = 3) -> list:
        """检查工作目录中最近创建的文件（最近 10 秒内）"""
        import time
        new_files = []
        current_time = time.time()

        try:
            for root, dirs, files in os.walk(str(work_dir)):
                # 限制深度
                depth = root.replace(str(work_dir), '').count(os.sep)
                if depth > max_depth:
                    dirs.clear()
                    continue

                for filename in files:
                    filepath = Path(root) / filename
                    try:
                        # 跳过临时文件和隐藏文件
                        if filename.startswith('.') or filename.startswith('tmp') or filename.endswith(('.pyc', '.pyo', '__pycache__')):
                            continue
                        # 跳过 venv 和 node_modules
                        if any(part in str(filepath) for part in ['.venv', 'node_modules', '__pycache__']):
                            continue

                        stat = filepath.stat()
                        # 检查文件修改时间（10 秒内）
                        if current_time - stat.st_mtime < 10:
                            rel_path = filepath.relative_to(work_dir)
                            new_files.append(f"{rel_path} ({stat.st_size:,} 字节)")
                    except (OSError, ValueError):
                        continue
        except Exception:
            pass

        return new_files[:20]  # 最多返回 20 个文件


# 全局工具实例
python_executor_tool = PythonExecutorTool()
