"""
技能管理 API
"""
from flask import Blueprint, request, jsonify
from service.self_evolution.skills import SkillManager

skills_bp = Blueprint('skills', __name__, url_prefix='/api/skills')
skill_manager = SkillManager()


@skills_bp.route('', methods=['GET'])
def list_skills():
    """列出技能"""
    category = request.args.get('category')
    
    skills = skill_manager.load_skills(category=category)
    
    return jsonify({'success': True, 'skills': skills})


@skills_bp.route('', methods=['POST'])
def create_skill():
    """创建技能"""
    data = request.get_json(force=True) or {}
    name = data.get('name')
    content = data.get('content')
    description = data.get('description')
    category = data.get('category')
    
    if not name or not content:
        return jsonify({'success': False, 'message': '缺少参数'}), 400
    
    result = skill_manager.create_skill(name, content, description, category)
    
    if result['success']:
        return jsonify(result), 201
    else:
        return jsonify(result), 400


@skills_bp.route('/<skill_name>', methods=['PATCH'])
def patch_skill(skill_name):
    """修补技能"""
    data = request.get_json(force=True) or {}
    old_string = data.get('old_string')
    new_string = data.get('new_string')
    
    if not old_string or not new_string:
        return jsonify({'success': False, 'message': '缺少参数'}), 400
    
    result = skill_manager.patch_skill(skill_name, old_string, new_string)
    
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400


@skills_bp.route('/relevant', methods=['GET'])
def get_relevant_skills():
    """获取相关技能"""
    query = request.args.get('q')
    limit = int(request.args.get('limit', 5))
    
    if not query:
        return jsonify({'success': False, 'message': '缺少搜索关键词'}), 400
    
    skills = skill_manager.get_relevant_skills(query, limit=limit)
    
    return jsonify({'success': True, 'skills': skills})


@skills_bp.route('/search', methods=['GET'])
def search_skills():
    """搜索技能"""
    query = request.args.get('q')
    limit = int(request.args.get('limit', 10))
    
    if not query:
        return jsonify({'success': False, 'message': '缺少搜索关键词'}), 400
    
    skills = skill_manager.search(query, limit=limit)
    
    return jsonify({'success': True, 'skills': skills})
