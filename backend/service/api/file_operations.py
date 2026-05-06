"""
百佑 LawyerClaw 文件操作 API

提供:
1. 文件读取/写入/修改/删除
2. 安全审批机制
3. 工作空间管理
"""
from flask import Blueprint, request, jsonify
from service.tools.file_operations import file_tool
from service.security.approval_enhanced import approval_manager
import logging

logger = logging.getLogger(__name__)

file_ops_bp = Blueprint('file_ops', __name__, url_prefix='/api/file-ops')


# ═══════════════════════════════════════════════════════════
# 工作空间管理
# ═══════════════════════════════════════════════════════════

@file_ops_bp.route('/workspace', methods=['GET'])
def get_workspace():
    """获取当前工作空间"""
    return jsonify({
        'root': str(file_tool.workspace_root) if file_tool.workspace_root else None
    })


@file_ops_bp.route('/workspace', methods=['POST'])
def set_workspace():
    """设置工作空间"""
    data = request.get_json()
    
    if not data or 'path' not in data:
        return jsonify({'error': 'path is required'}), 400
    
    file_tool.set_workspace(data['path'])
    
    return jsonify({
        'success': True,
        'root': str(file_tool.workspace_root)
    })


# ═══════════════════════════════════════════════════════════
# 文件操作
# ═══════════════════════════════════════════════════════════

@file_ops_bp.route('/read', methods=['POST'])
def read_file():
    """读取文件"""
    data = request.get_json()
    
    if not data or 'file_path' not in data:
        return jsonify({'error': 'file_path is required'}), 400
    
    result = file_tool.read_file(
        file_path=data['file_path'],
        limit=data.get('limit', 10000)
    )
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400


@file_ops_bp.route('/write', methods=['POST'])
def write_file():
    """写入文件"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body required'}), 400
    
    file_path = data.get('file_path')
    content = data.get('content')
    session_id = data.get('session_id')
    
    if not file_path or content is None:
        return jsonify({'error': 'file_path and content are required'}), 400
    
    result = file_tool.write_file(file_path, content, session_id)
    
    if result.get('requires_approval'):
        # 需要审批
        return jsonify(result), 403
    elif result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 400


@file_ops_bp.route('/patch', methods=['POST'])
def patch_file():
    """修补文件"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body required'}), 400
    
    file_path = data.get('file_path')
    old_string = data.get('old_string')
    new_string = data.get('new_string')
    session_id = data.get('session_id')
    
    if not file_path or not old_string or new_string is None:
        return jsonify({'error': 'file_path, old_string and new_string are required'}), 400
    
    result = file_tool.patch_file(file_path, old_string, new_string, session_id)
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400


@file_ops_bp.route('/delete', methods=['POST'])
def delete_file():
    """删除文件"""
    data = request.get_json()
    
    if not data or 'file_path' not in data:
        return jsonify({'error': 'file_path is required'}), 400
    
    file_path = data['file_path']
    session_id = data.get('session_id')
    
    result = file_tool.delete_file(file_path, session_id)
    
    if result.get('requires_approval'):
        # 需要审批
        return jsonify(result), 403
    elif result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400


@file_ops_bp.route('/list', methods=['POST'])
def list_directory():
    """列出目录"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body required'}), 400
    
    dir_path = data.get('dir_path', '.')
    
    result = file_tool.list_directory(dir_path)
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400


@file_ops_bp.route('/mkdir', methods=['POST'])
def create_directory():
    """创建目录"""
    data = request.get_json()
    
    if not data or 'dir_path' not in data:
        return jsonify({'error': 'dir_path is required'}), 400
    
    dir_path = data['dir_path']
    session_id = data.get('session_id')
    
    result = file_tool.create_directory(dir_path, session_id)
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400


# ═══════════════════════════════════════════════════════════
# 审批管理
# ═══════════════════════════════════════════════════════════

@file_ops_bp.route('/approve', methods=['POST'])
def approve_operation():
    """审批文件操作"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body required'}), 400
    
    session_id = data.get('session_id')
    pattern_key = data.get('pattern_key')
    approval_type = data.get('approval_type', 'session')
    
    if not session_id or not pattern_key:
        return jsonify({'error': 'session_id and pattern_key are required'}), 400
    
    if approval_type == 'session':
        approval_manager.approve_session(session_id, pattern_key)
    elif approval_type == 'permanent':
        approval_manager.approve_permanent(pattern_key)
    else:
        return jsonify({'error': 'Invalid approval_type'}), 400
    
    return jsonify({
        'success': True,
        'message': f'Operation approved ({approval_type})'
    })
