"""
百佑 LawyerClaw 启动入口 (PyInstaller 打包用)
- 开发环境：直接 python run.py 即可启动
- 打包环境：exe 双击启动，自动打开浏览器
"""
import os
import sys
import webbrowser
import threading
from pathlib import Path


def get_app_dir():
    """获取应用根目录（exe 所在目录 / 项目根目录）"""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent.resolve()


def ensure_dirs(app_dir):
    """确保运行时目录存在"""
    for d in ['backend/data', 'backend/uploads', 'backend/output']:
        (app_dir / d).mkdir(parents=True, exist_ok=True)


def open_browser(port):
    """延迟 3 秒后打开浏览器"""
    import time
    time.sleep(3)
    webbrowser.open(f'http://localhost:{port}')


def start_tray_icon(port):
    """启动系统托盘图标（daemon 线程，不阻塞 Flask）"""
    try:
        import pystray
        from PIL import Image

        # 查找图标文件
        if getattr(sys, 'frozen', False):
            icon_path = Path(sys._MEIPASS) / 'frontend_dist' / 'favicon.ico'
        else:
            icon_path = Path(__file__).parent / 'frontend' / 'public' / 'favicon.ico'

        if icon_path.exists():
            image = Image.open(str(icon_path))
        else:
            # 找不到图标时生成纯色方块
            image = Image.new('RGB', (64, 64), color=(3, 22, 53))

        def on_open(icon, item):
            webbrowser.open(f'http://localhost:{port}')

        def on_exit(icon, item):
            icon.stop()
            from service.core.shutdown import shutdown_app
            shutdown_app()

        icon = pystray.Icon(
            "lawyerclaw",
            image,
            "百佑 LawyerClaw",
            menu=pystray.Menu(
                pystray.MenuItem("打开浏览器", on_open, default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("退出 百佑 LawyerClaw", on_exit),
            )
        )

        tray_thread = threading.Thread(target=icon.run, daemon=True)
        tray_thread.start()
    except ImportError:
        print("  [提示] pystray 未安装，跳过系统托盘图标")
    except Exception as e:
        print(f"  [提示] 托盘图标启动失败: {e}")


def main():
    app_dir = get_app_dir()

    if getattr(sys, 'frozen', False):
        # 打包环境：backend 代码在 _internal/ 里，由 PyInstaller 管理
        # .env 在 _internal/backend/.env（由 spec datas 打入）
        # 运行时数据目录在 exe 同级 backend/data 等
        pass
    else:
        # 开发环境：将 backend 加入 sys.path，chdir 到 backend
        backend_dir = app_dir / 'backend'
        if backend_dir.exists():
            os.chdir(backend_dir)
        if str(backend_dir) not in sys.path:
            sys.path.insert(0, str(backend_dir))

    ensure_dirs(app_dir)

    print("=" * 60)
    print("  百佑 LawyerClaw - AI Legal Assistant")
    print("=" * 60)

    # 导入并启动 Flask 应用
    from app import create_app
    app = create_app()

    port = int(os.getenv('PORT', 5004))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'

    # 打包环境下自动打开浏览器
    if getattr(sys, 'frozen', False):
        threading.Thread(target=open_browser, args=(port,), daemon=True).start()
        print(f"\n  Browser will open at: http://localhost:{port}")

    print(f"\n  Server starting on: http://localhost:{port}")
    print(f"  Press Ctrl+C to stop\n")
    print("=" * 60)

    # 启动系统托盘图标
    start_tray_icon(port)

    app.run(host='0.0.0.0', port=port, debug=debug)


if __name__ == '__main__':
    main()
