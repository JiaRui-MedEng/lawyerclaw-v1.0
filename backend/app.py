"""
百佑 LawyerClaw Backend - Flask 应用入口
"""
import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

from flask import Flask, request, jsonify
from flask_cors import CORS

# 日志配置：打包环境用 WARNING，开发环境用 DEBUG
import sys as _sys
_log_level = logging.DEBUG if not getattr(_sys, 'frozen', False) else logging.WARNING
logging.basicConfig(
    level=_log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def get_base_dir():
    """获取基础目录，兼容 PyInstaller 打包环境"""
    from service.core.paths import get_backend_dir
    return get_backend_dir()


BASE_DIR = get_base_dir()
load_dotenv(BASE_DIR / '.env')


def create_app():
    """应用工厂"""
    app = Flask(__name__)
    
    # 配置
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'lawyerclaw-secret')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
        'DATABASE_URL', 'sqlite:///' + str(BASE_DIR / 'data' / 'lawyerclaw.db')
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

    # CORS
    allowed_origins = os.getenv('CORS_ORIGINS', 'http://localhost:3000,http://localhost:5004').split(',')
    CORS(app, supports_credentials=True, origins=allowed_origins)

    # 调试：记录所有请求
    @app.before_request
    def debug_request():
        print(f"[DEBUG-REQUEST] {request.method} {request.path} {request.url}", flush=True)

    # 数据库
    from service.models.database import init_db
    init_db(app)

    # ⭐ Hermes 记忆架构初始化 (FTS5 索引 + WAL 模式 + 记忆快照)
    from service.core.hermes_core import db_manager as hermes_db_manager, memory_manager as hermes_memory
    hermes_db_manager.initialize(app)
    with app.app_context():
        hermes_memory.load_from_db()

    # 默认启用 RAG 知识库
    os.environ.setdefault('RAG_ENABLED', '1')

    # 蓝图注册
    from service.api.sessions import sessions_bp
    from service.api.chat import chat_bp
    from service.api.chat_enhanced import chat_enhanced_bp  # 新增：支持工具调用的流式 API
    from service.api.tools import tools_bp
    from service.api.plugins import plugins_bp
    from service.api.workspace import workspace_bp
    from service.api.upload import upload_bp  # 文件上传
    from service.api.vision import vision_bp  # Vision 图片分析 API
    from service.api.style_api import style_bp  # Style Forge 风格分析/润色 API
    
    # 自我进化系统蓝图
    from service.api.memory import memory_bp
    from service.api.skills import skills_bp
    from service.api.hermes import hermes_bp
    from service.api.settings import settings_bp  # 用户设置蓝图
    from service.api.rag import rag_bp  # RAG 知识库管理 API
    from service.api.shutdown import shutdown_bp  # 应用关闭 API
    from service.api.providers_config import providers_bp  # 自定义 LLM 提供商管理 API

    app.register_blueprint(sessions_bp)
    # app.register_blueprint(chat_bp)  # ❌ 已禁用：使用增强版本替代
    app.register_blueprint(chat_enhanced_bp, url_prefix='/api/chat')  # ✅ 注册增强版流式 API
    app.register_blueprint(tools_bp)
    app.register_blueprint(plugins_bp)
    app.register_blueprint(workspace_bp)
    app.register_blueprint(upload_bp)  # 注册上传 API
    app.register_blueprint(vision_bp)  # 注册 Vision API
    app.register_blueprint(style_bp)  # 注册 Style Forge API
    app.register_blueprint(memory_bp)  # 新增
    app.register_blueprint(skills_bp)  # 新增
    app.register_blueprint(hermes_bp)  # Hermes 审批 API
    app.register_blueprint(settings_bp)  # 用户设置 API
    app.register_blueprint(rag_bp)  # RAG 知识库管理 API
    app.register_blueprint(shutdown_bp)  # 应用关闭 API
    app.register_blueprint(providers_bp)  # 自定义 LLM 提供商管理 API

    # 初始化默认知识库 collection（如果不存在）
    try:
        from service.rag.chroma_store import get_chroma_store
        store = get_chroma_store()
        if not store.collection_exists('legal_default'):
            store._get_collection('legal_default')
            logger.info("已创建默认知识库 collection: legal_default")
    except Exception as e:
        logger.warning(f"初始化默认知识库失败: {e}")
    # 静态文件服务（用于提供上传的图片）
    from flask import send_from_directory, send_file
    @app.route('/api/uploads/<filename>')
    def serve_upload(filename):
        return send_from_directory(BASE_DIR / 'uploads', filename)

    # ==================== 前端静态文件托管 ====================
    # 让 Flask 直接服务前端 dist 目录，实现单进程启动
    if getattr(sys, 'frozen', False):
        # 打包环境：前端在 _internal/frontend_dist/ 目录
        frontend_dir = Path(sys._MEIPASS) / 'frontend_dist'
    else:
        # 开发环境：上级目录下的 frontend/dist
        frontend_dir = BASE_DIR.parent / 'frontend' / 'dist'

    if frontend_dir.exists():
        @app.route('/')
        def serve_index():
            return send_file(frontend_dir / 'index.html')

        @app.errorhandler(404)
        def serve_frontend_or_404(error):
            """未匹配的路由：API 请求返回 404 JSON，其他回退到 index.html（SPA）"""
            path = request.path.lstrip('/')
            if path.startswith('api/'):
                return jsonify({'success': False, 'message': '接口不存在'}), 404
            # 尝试提供静态文件
            file_path = frontend_dir / path
            if file_path.exists() and file_path.is_file():
                return send_from_directory(frontend_dir, path)
            return send_file(frontend_dir / 'index.html')

    # 注册 LLM 提供商（从数据库加载自定义配置）
    from service.providers.base import ProviderRegistry

    registry = ProviderRegistry()
    
    # ⭐ 从数据库加载自定义 provider 配置（按需动态创建实例）
    registry.register_from_db(app)
    logger.info(f"✅ 已加载 {len(registry._db_configs)} 个自定义 Provider 配置")

    # 注入 registry 到 runtime
    from service.core.runtime import runtime
    runtime.registry = registry

    # 错误处理
    @app.errorhandler(500)
    def internal_error(error):
        from flask import jsonify
        return jsonify({'success': False, 'message': '服务器内部错误'}), 500

    return app


app = create_app()

if __name__ == '__main__':
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    port = int(os.getenv('PORT', 5004))
    app.run(host='0.0.0.0', port=port, debug=debug)