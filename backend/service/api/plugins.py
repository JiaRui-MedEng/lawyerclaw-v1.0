"""
插件 API
"""
from flask import Blueprint, request, jsonify
from service.plugins.plugin_manager import manager

plugins_bp = Blueprint('plugins', __name__, url_prefix='/api/plugins')


@plugins_bp.route('', methods=['GET'])
def list_plugins():
    """获取插件列表"""
    return jsonify({'success': True, 'plugins': manager.list_plugins()})


@plugins_bp.route('/<plugin_name>/enable', methods=['POST'])
def enable_plugin(plugin_name):
    """启用插件"""
    ok = manager.enable_plugin(plugin_name)
    if ok:
        manager.save_plugins_state()
        return jsonify({'success': True, 'message': f'插件 {plugin_name} 已启用'})
    return jsonify({'success': False, 'message': '插件不存在'}), 404


@plugins_bp.route('/<plugin_name>/disable', methods=['POST'])
def disable_plugin(plugin_name):
    """禁用插件"""
    ok = manager.disable_plugin(plugin_name)
    if ok:
        manager.save_plugins_state()
        return jsonify({'success': True, 'message': f'插件 {plugin_name} 已禁用'})
    return jsonify({'success': False, 'message': '插件不存在'}), 404


@plugins_bp.route('/<plugin_name>/config', methods=['PUT'])
def configure_plugin(plugin_name):
    """配置插件"""
    data = request.get_json(force=True) or {}
    ok = manager.configure_plugin(plugin_name, data.get('config', {}))
    if ok:
        manager.save_plugins_state()
        return jsonify({'success': True, 'message': '配置已保存'})
    return jsonify({'success': False, 'message': '插件不存在'}), 404


@plugins_bp.route('/upload', methods=['POST'])
def upload_plugin():
    """上传插件文件"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '未上传文件'}), 400
    
    f = request.files['file']
    if not f.filename or not f.filename.endswith('.py'):
        return jsonify({'success': False, 'message': '仅支持 .py 文件'}), 400
    
    save_path = manager.plugins_dir / f.filename
    f.save(str(save_path))
    
    ok = manager.load_plugin_from_file(str(save_path))
    if ok:
        manager.save_plugins_state()
        return jsonify({'success': True, 'message': '插件安装成功'})
    return jsonify({'success': False, 'message': '插件加载失败'}), 500
