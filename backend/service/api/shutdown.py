"""
百佑 LawyerClaw 应用关闭 API
POST /api/shutdown — 仅允许本机调用
"""
from flask import Blueprint, request, jsonify

shutdown_bp = Blueprint('shutdown', __name__, url_prefix='/api')


@shutdown_bp.route('/shutdown', methods=['POST'])
def shutdown():
    """关闭应用进程，仅限 localhost 访问"""
    remote = request.remote_addr
    if remote not in ('127.0.0.1', '::1', 'localhost'):
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    from service.core.shutdown import shutdown_app
    shutdown_app()

    return jsonify({'success': True, 'message': '正在关闭...'})
