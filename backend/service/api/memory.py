"""
记忆管理 API
"""
from flask import Blueprint, request, jsonify
from service.models.database import db
from service.self_evolution.memory import MemoryManager

memory_bp = Blueprint('memory', __name__, url_prefix='/api/memory')
memory_manager = MemoryManager()


@memory_bp.route('', methods=['GET'])
def list_memories():
    """列出记忆"""
    target = request.args.get('target')
    limit = int(request.args.get('limit', 50))
    
    memories = memory_manager.prefetch(target=target, limit=limit)
    
    # 解析为列表
    if not memories:
        return jsonify({'success': True, 'memories': []})
    
    # 简单解析 Markdown 格式
    lines = memories.split('\n')
    parsed = []
    current_target = None
    
    for line in lines:
        if line.startswith('## '):
            current_target = line.replace('## ', '').strip()
        elif line.startswith('- ') and current_target:
            parsed.append({
                'target': current_target.lower().replace(' ', '_'),
                'content': line[2:]
            })
    
    return jsonify({'success': True, 'memories': parsed})


@memory_bp.route('', methods=['POST'])
def add_memory():
    """添加记忆"""
    data = request.get_json(force=True) or {}
    target = data.get('target')
    content = data.get('content')
    
    if not target or not content:
        return jsonify({'success': False, 'message': '缺少参数'}), 400
    
    result = memory_manager.add(target, content)
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400


@memory_bp.route('/<int:memory_id>', methods=['PUT'])
def update_memory(memory_id):
    """更新记忆"""
    data = request.get_json(force=True) or {}
    new_content = data.get('content')
    
    if not new_content:
        return jsonify({'success': False, 'message': '缺少 content'}), 400
    
    result = memory_manager.replace(memory_id, new_content)
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400


@memory_bp.route('/<int:memory_id>', methods=['DELETE'])
def delete_memory(memory_id):
    """删除记忆"""
    result = memory_manager.remove(memory_id)
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400


@memory_bp.route('/search', methods=['GET'])
def search_memory():
    """搜索记忆"""
    query = request.args.get('q')
    limit = int(request.args.get('limit', 10))
    
    if not query:
        return jsonify({'success': False, 'message': '缺少搜索关键词'}), 400
    
    memories = memory_manager.search(query, limit=limit)
    
    return jsonify({'success': True, 'memories': memories})
