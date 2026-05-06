"""
百佑 LawyerClaw 应用关闭模块
托盘退出和前端退出按钮共用此逻辑
"""
import os
import logging
import threading

logger = logging.getLogger(__name__)


def shutdown_app():
    """
    优雅关闭应用：
    1. 关闭 SQLAlchemy 连接池
    2. 延迟 0.5s 后强制退出（让 HTTP 响应先返回）
    """
    logger.info("正在关闭应用...")

    # 关闭数据库连接
    try:
        from service.models.database import db
        db.session.remove()
        if hasattr(db, 'engine'):
            db.engine.dispose()
        logger.info("数据库连接已关闭")
    except Exception as e:
        logger.warning(f"数据库清理异常: {e}")

    # 延迟退出，让 HTTP 响应有时间返回
    def _exit():
        import time
        time.sleep(0.5)
        os._exit(0)

    threading.Thread(target=_exit, daemon=True).start()
