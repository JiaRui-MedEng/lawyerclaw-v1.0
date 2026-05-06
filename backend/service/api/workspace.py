"""
工作空间文件管理 API
"""
import os
import stat
import sys
import subprocess
import tempfile
import logging
from pathlib import Path
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)


def _safe_log(msg):
    """将日志安全写入文件（绕过 Windows 控制台编码问题）"""
    log_file = os.path.join(tempfile.gettempdir(), 'lawyerclaw_workspace.log')
    try:
        with open(log_file, 'a', encoding='utf-8') as f:
            from datetime import datetime
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass

workspace_bp = Blueprint('workspace', __name__, url_prefix='/api/workspace')

# 默认工作空间根目录（可配置）
from service.core.paths import get_app_root
DEFAULT_WORKSPACE_ROOT = str(get_app_root())


def safe_resolve(base, rel):
    """确保路径不会逃逸工作空间根目录"""
    # 如果是绝对路径，直接使用（但要在允许的根目录下）
    if Path(rel).is_absolute():
        target = Path(rel).resolve()
        base_path = Path(base).resolve()
        
        # 检查是否在允许的根目录下（或者是根目录本身）
        try:
            # 允许访问根目录及其子目录
            if str(target) == str(base_path) or str(target).startswith(str(base_path) + os.sep):
                return target
            # 也允许访问同级目录（如 D:\Projects 下的其他项目）
            elif str(target).startswith(str(base_path.parent) + os.sep):
                return target
            else:
                _safe_log(f"[safe_resolve] 路径越界阻止: {target} (base: {base_path})")
                return None
        except Exception as e:
            _safe_log(f"[safe_resolve] 路径检查错误: {e}")
            return target  # 宽松模式：允许访问
    else:
        # 相对路径：相对于 base 解析
        base_path = Path(base).resolve()
        target = (base_path / rel).resolve()
        try:
            target.relative_to(base_path)
            return target
        except ValueError:
            return None


def build_tree(path, max_depth=5, current_depth=0):
    """递归构建文件树"""
    if current_depth >= max_depth:
        return []
    
    items = []
    try:
        entries = sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name.lower()))
    except PermissionError:
        return items
    
    for entry in entries:
        # 跳过隐藏文件和 node_modules
        if entry.name.startswith('.') or entry.name == 'node_modules':
            continue
        
        is_dir = entry.is_dir(follow_symlinks=False)
        size = 0
        if not is_dir:
            try:
                size = entry.stat().st_size
            except OSError:
                continue
        
        item = {
            'name': entry.name,
            'path': entry.name,  # 相对路径
            'is_directory': is_dir,
            'size': size,
        }
        
        if is_dir:
            item['children'] = build_tree(entry.path, max_depth, current_depth + 1)
        
        items.append(item)
    
    return items


@workspace_bp.route('/config', methods=['GET'])
def get_config():
    """获取工作空间配置"""
    return jsonify({
        'success': True,
        'root': os.environ.get('LAWYERCLAW_WORKSPACE', DEFAULT_WORKSPACE_ROOT)
    })


@workspace_bp.route('/config', methods=['POST'])
def set_config():
    """设置工作空间根目录"""
    data = request.get_json(force=True) or {}
    root = data.get('root', DEFAULT_WORKSPACE_ROOT)
    if not os.path.isdir(root):
        return jsonify({'success': False, 'message': f'目录不存在: {root}'}), 400
    os.environ['LAWYERCLAW_WORKSPACE'] = root
    return jsonify({'success': True, 'root': root})


@workspace_bp.route('/files', methods=['GET'])
def list_files():
    """获取工作空间文件列表"""
    root = os.environ.get('LAWYERCLAW_WORKSPACE', DEFAULT_WORKSPACE_ROOT)
    subdir = request.args.get('path', '')
    
    _safe_log(f"[list_files] 请求路径: root={root}, subdir={subdir}")
    
    # 允许访问任意路径
    if not subdir or subdir == '/':
        target = Path(root).resolve()
    else:
        # 直接使用用户提供的路径，不检查是否在工作空间内
        target = Path(subdir).resolve()
    
    if not target.exists():
        _safe_log(f"[list_files] 目录不存在: {target}")
        return jsonify({'success': False, 'message': '目录不存在'}), 404
    
    if not target.is_dir():
        _safe_log(f"[list_files] 不是目录: {target}")
        return jsonify({'success': False, 'message': '不是目录'}), 400
    
    _safe_log(f"[list_files] 访问目录: {target}")
    max_depth = int(request.args.get('max_depth', 2))
    tree = build_tree(str(target), max_depth)
    
    # 转换为前端期望的格式（items + is_dir）
    items = []
    for item in tree:
        items.append({
            'name': item['name'],
            'path': str(target / item['name']) if item['name'] else str(target),  # 完整路径
            'is_dir': item['is_directory'],
            'size': item.get('size', 0)
        })
    
    return jsonify({
        'success': True,
        'path': str(target),
        'items': items
    })


@workspace_bp.route('/tree', methods=['GET'])
def get_tree():
    """获取完整文件树（浅层，供左侧快速浏览）"""
    root = os.environ.get('LAWYERCLAW_WORKSPACE', DEFAULT_WORKSPACE_ROOT)
    tree = build_tree(root, max_depth=3)
    return jsonify({
        'success': True,
        'root': root,
        'tree': tree
    })


def _select_folder_win32():
    """
    使用 Python + tkinter 弹出文件夹选择器（打包后可用）
    
    注意：使用 Popen 异步弹出对话框，避免阻塞 Flask worker 线程。
    对话框在独立进程中运行，结果写入临时文件，前端轮询获取。
    
    使用 tkinter（Python 标准库自带），通过 CREATE_NEW_CONSOLE 确保 GUI 能正常显示。
    """
    import uuid
    result_file = os.path.join(tempfile.gettempdir(), f'lawyerclaw_folder_{uuid.uuid4().hex}.txt')

    _rf = result_file
    py_lines = [
        'import tkinter as tk',
        'from tkinter import filedialog',
        '',
        'result_file = r"{}"'.format(_rf),
        '',
        'try:',
        '    root = tk.Tk()',
        '    root.withdraw()',
        '    root.attributes("-topmost", True)',
        '    root.update()',
        '',
        '    path = filedialog.askdirectory(title="选择工作空间文件夹", parent=root)',
        '    root.destroy()',
        '',
        '    with open(result_file, "w", encoding="utf-8") as f:',
        '        f.write(path if path else "CANCELLED")',
        'except Exception as e:',
        '    try:',
        '        with open(result_file, "w", encoding="utf-8") as f:',
        '            f.write("ERROR:" + str(e))',
        '    except Exception:',
        '        pass',
    ]
    py_script = '\n'.join(py_lines) + '\n'

    # 将脚本写入调试文件，便于诊断
    debug_file = result_file + '.debug.py'
    try:
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write(py_script)
    except Exception:
        pass

    try:
        # 查找真正的 Python 解释器
        python_exe = _find_real_python()
        if not python_exe:
            _safe_log("[select-folder] 找不到 Python 解释器")
            return None

        # 将脚本写入临时文件执行
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(py_script)
            temp_script = f.name

        _safe_log(f"[select-folder] 启动对话框: python={python_exe}")

        # 使用 CREATE_NO_WINDOW 避免弹出终端窗口（Windows 专用标志 0x08000000）
        # tkinter 使用 Windows 消息循环，不需要控制台窗口
        subprocess.Popen(
            [python_exe, temp_script],
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # 返回结果文件路径，前端轮询获取
        return f'__POLL__:{result_file}'
    except Exception as e:
        _safe_log(f"[select-folder] 启动失败: {e}")
        return None


def _find_real_python():
    """找到真正的 Python 解释器（委托给 paths 模块）"""
    from service.core.paths import find_system_python
    return find_system_python()


def _select_folder_tkinter():
    """
    使用 tkinter 选择文件夹（开发环境 / 非 Windows 系统回退方案）
    在子进程中运行，避免阻塞 Flask 线程
    结果通过临时文件传递，避免 stdout 被污染
    """
    import uuid
    result_file = os.path.join(tempfile.gettempdir(), f'lawyerclaw_tkinter_{uuid.uuid4().hex}.txt')
    
    script = (
        'import tkinter as tk\n'
        'from tkinter import filedialog\n'
        'root = tk.Tk()\n'
        'root.withdraw()\n'
        'path = filedialog.askdirectory(title="选择工作空间文件夹")\n'
        f'with open(r"{result_file}", "w", encoding="utf-8") as f:\n'
        '    f.write(path)\n'
        'root.destroy()\n'
    )
    temp_path = None
    try:
        python_exe = _find_real_python()
        if not python_exe:
            return None  # 找不到独立的 Python 解释器

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(script)
            temp_path = f.name

        subprocess.run(
            [python_exe, temp_path],
            capture_output=True,
            text=True,
            timeout=300,
        )
        
        # 从结果文件读取路径
        if os.path.exists(result_file):
            with open(result_file, 'r', encoding='utf-8') as f:
                selected_path = f.read().strip()
            try:
                os.unlink(result_file)
            except Exception:
                pass
            return selected_path or None
        return None
    except Exception:
        return None
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception:
                pass


@workspace_bp.route('/open-file', methods=['POST'])
def open_file():
    """使用系统默认程序打开文件"""
    data = request.get_json(force=True) or {}
    file_path = data.get('path', '')

    if not file_path:
        return jsonify({'success': False, 'message': '未提供文件路径'}), 400

    target = Path(file_path).resolve()
    if not target.exists():
        return jsonify({'success': False, 'message': f'文件不存在: {file_path}'}), 404

    try:
        if sys.platform == 'win32':
            os.startfile(str(target))
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', str(target)])
        else:
            subprocess.Popen(['xdg-open', str(target)])

        return jsonify({'success': True, 'path': str(target)})
    except Exception as e:
        logger.error(f"打开文件失败: {e}")
        return jsonify({'success': False, 'message': f'打开文件失败: {str(e)}'}), 500


@workspace_bp.route('/select-folder', methods=['POST'])
def select_folder():
    print(f"\n{'='*50}\n[DEBUG] select-folder 接口被调用了！\n{'='*50}\n", flush=True)
    """
    调起系统文件夹选择器
    - Windows 打包环境：使用 PowerShell + .NET FolderBrowserDialog（异步弹出，不阻塞）
    - 开发环境 / 其他系统：回退到 tkinter
    """
    try:
        selected_path = None
        _safe_log("[select-folder] 收到请求，开始选择文件夹...")

        # Windows 优先使用原生方式（打包后也能正常工作）
        if sys.platform == 'win32':
            selected_path = _select_folder_win32()
            _safe_log(f"[select-folder] _select_folder_win32 返回: {selected_path!r}")

        # 非 Windows 或 PowerShell 方式失败时，回退到 tkinter
        if selected_path is None and not getattr(sys, 'frozen', False):
            _safe_log("[select-folder] PowerShell 方式失败，回退到 tkinter...")
            selected_path = _select_folder_tkinter()
            _safe_log(f"[select-folder] _select_folder_tkinter 返回: {selected_path!r}")

        # 异步模式（PowerShell 方式）：对话框已在后台弹出，前端轮询获取结果
        # _select_folder_win32() 返回 '__POLL__:{result_file}' 格式
        if isinstance(selected_path, str) and selected_path.startswith('__POLL__:'):
            result_file = selected_path[len('__POLL__:'):]  # 提取结果文件路径
            return jsonify({
                'success': True,
                'async': True,
                'message': '文件夹选择器已弹出，请选择文件夹',
                'result_file': result_file,
            })

        # 旧版异步标记兼容（如果未来改为直接返回 __ASYNC__）
        if selected_path == '__ASYNC__':
            return jsonify({
                'success': True,
                'async': True,
                'message': '文件夹选择器已弹出，请选择后点击确定'
            })

        if selected_path and isinstance(selected_path, str):
            selected_path = selected_path.strip().strip('\ufeff').strip('\x00').strip()
            selected_path = os.path.normpath(selected_path) if selected_path else selected_path
            _safe_log(f"[select-folder sync] path={selected_path!r} isdir={os.path.isdir(selected_path) if selected_path else 'N/A'}")

        if selected_path and os.path.isdir(selected_path):
            return jsonify({'success': True, 'path': selected_path})
        elif selected_path is None:
            return jsonify({'success': False, 'message': '未选择文件夹'}), 400
        else:
            _safe_log(f"[select-folder sync] 无效路径: {selected_path!r}")
            return jsonify({'success': False, 'message': f'无效路径: {selected_path}'}), 400

    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'message': '选择文件夹超时'}), 408
    except Exception as e:
        return jsonify({'success': False, 'message': f'无法打开文件夹选择器: {str(e)}'}), 500


@workspace_bp.route('/select-folder/result', methods=['POST'])
def select_folder_result():
    """
    轮询获取文件夹选择结果（异步模式）
    前端通过 result_file 参数传递结果文件路径
    """
    data = request.get_json(force=True) or {}
    result_file = data.get('result_file', '')
    _safe_log(f"[select-folder/result] 轮询请求, result_file={result_file!r}, exists={os.path.exists(result_file) if result_file else False}")

    if not result_file or not os.path.exists(result_file):
        return jsonify({
            'success': False,
            'message': '结果文件不存在或尚未生成',
            'ready': False,
        }), 200

    try:
        # 先读原始字节，用于诊断
        with open(result_file, 'rb') as f:
            raw_bytes = f.read()
        _safe_log(f"[select-folder/result] raw_bytes={raw_bytes!r} hex={raw_bytes.hex()}")

        # 清理结果文件
        try:
            os.unlink(result_file)
        except Exception:
            pass

        # 根据 BOM 检测编码，支持 UTF-16 LE/BE 和 UTF-8
        if raw_bytes.startswith(b'\xff\xfe'):
            raw_content = raw_bytes.decode('utf-16-le')
        elif raw_bytes.startswith(b'\xfe\xff'):
            raw_content = raw_bytes.decode('utf-16-be')
        else:
            try:
                raw_content = raw_bytes.decode('utf-8-sig')
            except UnicodeDecodeError:
                raw_content = raw_bytes.decode('gbk', errors='replace')
        
        # 如果解码后的内容包含大量 null 字符，可能是无 BOM 的 UTF-16 LE
        if raw_content.count('\x00') > 2:
            try:
                raw_content = raw_bytes.decode('utf-16-le')
            except UnicodeDecodeError:
                pass

        # 清洗路径：去除 BOM 残留、null 字节、零宽字符、首尾空白、换行符
        selected_path = raw_content.strip()
        selected_path = selected_path.strip('\ufeff')  # BOM
        selected_path = selected_path.replace('\x00', '')  # 所有 Null 字节
        selected_path = selected_path.replace('\r', '').replace('\n', '')  # 换行符
        selected_path = selected_path.strip()
        _safe_log(f"[select-folder/result] raw_content={raw_content!r}, cleaned={selected_path!r}")

        if selected_path == 'CANCELLED' or not selected_path:
            return jsonify({
                'success': False,
                'message': '用户取消了选择',
                'ready': True,
            }), 200

        # 处理 PowerShell 异常写入的 ERROR: 前缀
        if selected_path.startswith('ERROR:'):
            error_msg = selected_path[len('ERROR:'):].strip()
            _safe_log(f"[select-folder/result] PowerShell 异常: {error_msg}")
            return jsonify({
                'success': False,
                'message': f'文件夹选择器出错: {error_msg}',
                'ready': True,
            }), 200

        # 规范化路径
        selected_path = os.path.normpath(selected_path)
        
        # 去除所有控制字符和格式字符（保留正常路径字符）
        import unicodedata
        cleaned_chars = []
        for ch in selected_path:
            cat = unicodedata.category(ch)
            # 去除控制字符(Cc)和格式字符(Cf)，但保留常规空白
            if cat in ('Cc', 'Cf') and ch not in ('\t', '\n', '\r', ' '):
                continue
            cleaned_chars.append(ch)
        selected_path = ''.join(cleaned_chars).strip()

        # 只保留合法路径字符（字母、数字、中文、日韩文、空格及路径符号）
        import re
        selected_path = re.sub(r'[^\w\s\-.:;/\\()（）\u4e00-\u9fff\u3400-\u4dbf\uac00-\ud7af]', '', selected_path).strip()
        _safe_log(f"[select-folder/result] regex-cleaned={selected_path!r} chars_hex={[hex(ord(c)) for c in selected_path]}")

        is_dir = os.path.isdir(selected_path)
        exists = os.path.exists(selected_path)
        _safe_log(f"[select-folder/result] normpath={selected_path!r} isdir={is_dir} exists={exists} len={len(selected_path)} chars={[hex(ord(c)) for c in selected_path[:20]]}")

        if is_dir:
            os.environ['LAWYERCLAW_WORKSPACE'] = selected_path
            return jsonify({
                'success': True,
                'ready': True,
                'path': selected_path,
            })
        else:
            # 将诊断信息写入调试日志文件，便于排查
            debug_log_file = os.path.join(tempfile.gettempdir(), 'lawyerclaw_folder_debug.log')
            try:
                with open(debug_log_file, 'a', encoding='utf-8') as f:
                    f.write(f"\n{'='*60}\n")
                    f.write(f"时间: {__import__('datetime').datetime.now().isoformat()}\n")
                    f.write(f"result_file: {result_file}\n")
                    f.write(f"raw_bytes: {raw_bytes!r}\n")
                    f.write(f"raw_content: {raw_content!r}\n")
                    f.write(f"cleaned_path: {selected_path!r}\n")
                    f.write(f"is_dir: {is_dir}\n")
                    f.write(f"exists: {exists}\n")
                    f.write(f"path_bytes_hex: {raw_bytes.hex()}\n")
            except Exception as e:
                _safe_log(f"[select-folder/result] 写入调试日志失败: {e}")
            
            return jsonify({
                'success': False,
                'message': f'无效路径: {selected_path}',
                'ready': True,
            }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'读取结果失败: {str(e)}',
            'ready': False,
        }), 200
