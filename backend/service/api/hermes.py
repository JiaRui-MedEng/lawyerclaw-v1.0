"""
百佑 LawyerClaw Hermes 核心功能 API

提供:
1. 记忆管理 (CRUD)
2. 技能管理 (创建/修补/搜索)
3. 会话搜索 (FTS5)
"""
from flask import Blueprint, request, jsonify
from service.core.hermes_core import memory_manager, skill_manager, session_search
from service.models.database import db, Memory, Skill
import logging

logger = logging.getLogger(__name__)

hermes_bp = Blueprint('hermes', __name__, url_prefix='/api/hermes')


# ═══════════════════════════════════════════════════════════
# 记忆管理 API
# ═══════════════════════════════════════════════════════════

@hermes_bp.route('/memories', methods=['GET'])
def get_memories():
    """获取所有记忆"""
    target = request.args.get('target')
    
    query = Memory.query.filter_by(is_active=True)\
        .order_by(Memory.created_at.desc())\
        .limit(100)
    
    if target:
        query = query.filter_by(target=target)
    
    memories = query.all()
    return jsonify([m.to_dict() for m in memories])


@hermes_bp.route('/memories', methods=['POST'])
def add_memory():
    """添加记忆"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body required'}), 400
    
    target = data.get('target', 'memory')
    content = data.get('content', '').strip()
    session_id = data.get('session_id')
    
    if not content:
        return jsonify({'error': 'Content cannot be empty'}), 400
    
    result = memory_manager.add(target, content, session_id)
    
    if result['success']:
        return jsonify(result), 201
    else:
        return jsonify(result), 400


@hermes_bp.route('/memories/<int:memory_id>', methods=['DELETE'])
def remove_memory(memory_id):
    """删除记忆"""
    memory = Memory.query.get(memory_id)
    if not memory:
        return jsonify({'error': 'Memory not found'}), 404
    
    memory.is_active = False
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Memory removed'})


# ═══════════════════════════════════════════════════════════
# 技能管理 API
# ═══════════════════════════════════════════════════════════

@hermes_bp.route('/skills', methods=['GET'])
def get_skills():
    """获取所有技能（从文件系统扫描，不调用大模型）"""
    category = request.args.get('category')
    
    skills = skill_manager.load_skills(category=category)
    
    # 转换为前端需要的格式
    result = []
    for s in skills:
        result.append({
            'id': s.get('dir', '').split('/')[-1],
            'name': s.get('name', ''),
            'description': s.get('description', ''),
            'category': s.get('category', ''),
            'content': s.get('content', ''),
            'is_active': True,
            'created_at': None,
        })
    
    return jsonify({
        'success': True,
        'skills': result
    })


@hermes_bp.route('/skills/search', methods=['GET'])
def search_skills():
    """搜索技能 (FTS5)"""
    query = request.args.get('query', '')
    limit = min(int(request.args.get('limit', 10)), 50)
    
    if not query:
        return jsonify([])
    
    results = skill_manager.search_skills(query, limit)
    return jsonify(results)


@hermes_bp.route('/skills', methods=['POST'])
def create_skill():
    """创建技能"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body required'}), 400
    
    name = data.get('name', '').strip()
    content = data.get('content', '').strip()
    description = data.get('description', '')
    category = data.get('category', 'general')
    
    if not name:
        return jsonify({'error': 'Skill name is required'}), 400
    
    if not content:
        return jsonify({'error': 'Skill content is required'}), 400
    
    result = skill_manager.create_skill(name, content, description, category)
    
    if result['success']:
        return jsonify(result), 201
    else:
        return jsonify(result), 400


@hermes_bp.route('/skills/<name>', methods=['PATCH'])
def patch_skill(name):
    """修补技能"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body required'}), 400
    
    old_string = data.get('old_string', '').strip()
    new_string = data.get('new_string', '')
    
    if not old_string:
        return jsonify({'error': 'old_string is required'}), 400
    
    result = skill_manager.patch_skill(name, old_string, new_string)
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400


@hermes_bp.route('/skills/<name>', methods=['DELETE'])
def delete_skill(name):
    """删除技能"""
    skill = Skill.query.filter_by(name=name).first()
    if not skill:
        return jsonify({'error': 'Skill not found'}), 404
    
    skill.is_active = False
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Skill deleted'})


# ═══════════════════════════════════════════════════════════
# 会话搜索 API
# ═══════════════════════════════════════════════════════════

@hermes_bp.route('/sessions/search', methods=['GET'])
def search_sessions():
    """搜索会话 (FTS5)"""
    query = request.args.get('query', '')
    session_id = request.args.get('session_id')
    limit = min(int(request.args.get('limit', 5)), 20)
    role_filter = request.args.get('role_filter')
    
    if not query:
        return jsonify({
            'success': True,
            'query': '',
            'results': [],
            'count': 0
        })
    
    result = session_search.search(
        query=query,
        session_id=session_id,
        limit=limit,
        role_filter=role_filter
    )
    
    return jsonify(result)


@hermes_bp.route('/sessions/recent', methods=['GET'])
def get_recent_sessions():
    """获取最近会话"""
    limit = min(int(request.args.get('limit', 5)), 20)
    
    results = session_search._get_recent_sessions(limit)
    return jsonify(results)
