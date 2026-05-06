"""
工具 API
"""
import asyncio
from flask import Blueprint, request, jsonify
from service.tools.legal_tools import registry

tools_bp = Blueprint('tools', __name__, url_prefix='/api/tools')


@tools_bp.route('', methods=['GET'])
def list_tools():
    """获取可用工具列表"""
    return jsonify({'success': True, 'tools': registry.list_tools()})


@tools_bp.route('/execute', methods=['POST'])
def execute_tool():
    """执行工具"""
    data = request.get_json(force=True) or {}
    tool_name = data.get('tool_name')
    parameters = data.get('parameters', {})
    
    if not tool_name:
        return jsonify({'success': False, 'message': '缺少 tool_name'}), 400
    
    try:
        result = asyncio.run(registry.execute(tool_name, **parameters))
        return jsonify({
            'success': result.success,
            'content': result.content,
            'data': result.data,
            'error': result.error
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@tools_bp.route('/schemas/openai', methods=['GET'])
def get_openai_schemas():
    """获取 OpenAI 格式的工具 schemas"""
    return jsonify({'success': True, 'tools': registry.get_openai_tools()})


@tools_bp.route('/schemas/claude', methods=['GET'])
def get_claude_schemas():
    """获取 Claude 格式的工具 schemas"""
    return jsonify({'success': True, 'tools': registry.get_claude_tools()})
