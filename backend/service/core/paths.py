"""
路径工具 - 兼容 PyInstaller 打包环境

PyInstaller frozen 模式下 __file__ 指向 _internal/ 内部，
所有模块应使用本模块提供的路径，而非 Path(__file__) 自行推算。
"""
import os
import sys
import shutil
from pathlib import Path
from typing import Optional


def _is_frozen() -> bool:
    return getattr(sys, 'frozen', False)


def get_app_root() -> Path:
    """应用根目录（exe 所在目录 / 项目根目录）"""
    if _is_frozen():
        return Path(sys.executable).parent
    # 开发环境: backend/service/core/paths.py → 上溯 3 级到 backend/
    return Path(__file__).resolve().parent.parent.parent.parent


def get_backend_dir() -> Path:
    """backend 目录"""
    if _is_frozen():
        return Path(sys.executable).parent / 'backend'
    return Path(__file__).resolve().parent.parent.parent


def get_data_dir() -> Path:
    """数据目录 (backend/data)"""
    d = get_backend_dir() / 'data'
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_uploads_dir() -> Path:
    """上传目录 (backend/uploads)"""
    d = get_backend_dir() / 'uploads'
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_skills_dir() -> Path:
    """技能目录 (backend/skills)"""
    if _is_frozen():
        # 打包后 skills 在 _internal/backend/skills/
        d = Path(sys._MEIPASS) / 'backend' / 'skills'
    else:
        d = get_backend_dir() / 'skills'
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_plugins_dir() -> Path:
    """插件目录 (backend/plugins)"""
    d = get_backend_dir() / 'plugins'
    d.mkdir(parents=True, exist_ok=True)
    return d


def find_system_python() -> Optional[str]:
    """
    找到系统中真正的 Python 解释器（非 PyInstaller 打包的 exe）。

    打包环境下 sys.executable 指向 lawyerclaw.exe，不能用于执行 Python 脚本。
    此函数从系统 PATH 中查找独立的 Python 解释器。

    开发环境下直接返回 sys.executable（当前解释器）。
    """
    # 开发环境：当前解释器就是 Python
    if not _is_frozen():
        return sys.executable

    # 打包环境：尝试从 sys._base_prefix / sys.base_prefix 找
    for attr in ('_base_prefix', 'base_prefix'):
        try:
            prefix = getattr(sys, attr, None)
            if prefix:
                candidate = os.path.join(prefix, 'python.exe')
                if os.path.exists(candidate):
                    return candidate
        except Exception:
            pass

    # 从 PATH 查找，避免 Windows Store 版本
    for name in ['python', 'python3']:
        exe = shutil.which(name)
        if exe and 'WindowsApps' not in exe:
            return exe

    return None


def get_chroma_dir() -> Path:
    """ChromaDB 持久化目录"""
    import os
    custom = os.getenv('CHROMA_PERSIST_DIR')
    if custom:
        d = Path(custom)
    else:
        d = get_data_dir() / 'chroma'
    d.mkdir(parents=True, exist_ok=True)
    return d
