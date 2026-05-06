"""
用户自定义 LLM 提供商管理 API

提供自定义模型的 CRUD、激活切换、连接测试功能。
"""
import json
import logging
import asyncio
from flask import Blueprint, request, jsonify, current_app
from service.models.database import db, CustomProvider


def _refresh_registry():
    """刷新 runtime 中的 ProviderRegistry，确保 CRUD 后生效"""
    from service.core.runtime import runtime
    runtime.registry._db_configs.clear()
    runtime.registry.register_from_db(current_app)
    logger.info(f"🔄 已刷新 ProviderRegistry，当前 {len(runtime.registry._db_configs)} 个活跃配置")

logger = logging.getLogger(__name__)

providers_bp = Blueprint('providers', __name__, url_prefix='/api/providers')


@providers_bp.route('', methods=['GET'])
def list_providers():
    """获取所有自定义提供商列表"""
    try:
        providers = CustomProvider.query.order_by(CustomProvider.created_at.desc()).all()
        return jsonify({
            'success': True,
            'providers': [p.to_dict() for p in providers]
        })
    except Exception as e:
        logger.error(f"获取提供商列表失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@providers_bp.route('', methods=['POST'])
def create_provider():
    """添加新提供商"""
    data = request.get_json(force=True) or {}
    
    name = data.get('name', '').strip()
    protocol = data.get('protocol', 'openai').strip()
    base_url = data.get('base_url', '').strip()
    api_key = data.get('api_key', '').strip()
    default_model = data.get('default_model', '').strip()
    is_active = data.get('is_active', False)
    
    # ⭐ 如果当前没有其他活跃配置，新配置自动激活
    if not is_active:
        has_active = CustomProvider.query.filter_by(is_active=True).first()
        if not has_active:
            is_active = True
    
    # 验证必填字段
    if not name:
        return jsonify({'success': False, 'error': '配置名称不能为空'}), 400
    if protocol not in ('openai', 'anthropic'):
        return jsonify({'success': False, 'error': '协议类型仅支持 openai 或 anthropic'}), 400
    if not base_url:
        return jsonify({'success': False, 'error': 'Base URL 不能为空'}), 400
    if not api_key:
        return jsonify({'success': False, 'error': 'API Key 不能为空'}), 400
    if not default_model:
        return jsonify({'success': False, 'error': '模型名称不能为空'}), 400
    
    try:
        # 检查名称是否已存在
        existing = CustomProvider.query.filter_by(name=name).first()
        if existing:
            return jsonify({'success': False, 'error': f'配置名称 "{name}" 已存在'}), 400
        
        # 如果设为活跃，先取消其他活跃状态
        if is_active:
            CustomProvider.query.update({'is_active': False})
        
        provider = CustomProvider(
            name=name,
            protocol=protocol,
            base_url=base_url,
            api_key=api_key,
            default_model=default_model,
            is_active=is_active
        )
        db.session.add(provider)
        db.session.commit()
        
        logger.info(f"✅ 新增提供商配置: {name} ({protocol})")
        _refresh_registry()
        
        return jsonify({
            'success': True,
            'message': '配置已添加',
            'provider': provider.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"添加提供商失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@providers_bp.route('/<int:provider_id>', methods=['PUT'])
def update_provider(provider_id):
    """更新提供商配置"""
    data = request.get_json(force=True) or {}
    
    try:
        provider = CustomProvider.query.get(provider_id)
        if not provider:
            return jsonify({'success': False, 'error': '配置不存在'}), 404
        
        # 更新字段
        if 'name' in data:
            provider.name = data['name'].strip()
        if 'protocol' in data:
            provider.protocol = data['protocol'].strip()
        if 'base_url' in data:
            provider.base_url = data['base_url'].strip()
        if 'api_key' in data:
            provider.api_key = data['api_key'].strip()
        if 'default_model' in data:
            provider.default_model = data['default_model'].strip()
        if 'is_active' in data:
            # 如果设为活跃，先取消其他活跃状态
            if data['is_active']:
                CustomProvider.query.update({'is_active': False})
            provider.is_active = data['is_active']
        
        db.session.commit()
        logger.info(f"✅ 更新提供商配置: {provider.name}")
        _refresh_registry()
        
        return jsonify({
            'success': True,
            'message': '配置已更新',
            'provider': provider.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"更新提供商失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@providers_bp.route('/<int:provider_id>', methods=['DELETE'])
def delete_provider(provider_id):
    """删除提供商配置"""
    try:
        provider = CustomProvider.query.get(provider_id)
        if not provider:
            return jsonify({'success': False, 'error': '配置不存在'}), 404
        
        db.session.delete(provider)
        db.session.commit()
        logger.info(f"🗑️ 删除提供商配置: {provider.name}")
        _refresh_registry()
        
        return jsonify({
            'success': True,
            'message': '配置已删除'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"删除提供商失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@providers_bp.route('/<int:provider_id>/raw-key', methods=['GET'])
def get_raw_api_key(provider_id):
    """获取原始 API Key（仅用于编辑时回填，不脱敏）"""
    try:
        provider = CustomProvider.query.get(provider_id)
        if not provider:
            return jsonify({'success': False, 'error': '配置不存在'}), 404
        return jsonify({
            'success': True,
            'api_key': provider.api_key
        })
    except Exception as e:
        logger.error(f"获取 API Key 失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@providers_bp.route('/<int:provider_id>/activate', methods=['POST'])
def activate_provider(provider_id):
    """设为活跃配置（自动取消其他活跃状态）"""
    try:
        provider = CustomProvider.query.get(provider_id)
        if not provider:
            return jsonify({'success': False, 'error': '配置不存在'}), 404
        
        # 取消所有活跃状态
        CustomProvider.query.update({'is_active': False})
        
        # 设为活跃
        provider.is_active = True
        db.session.commit()
        
        logger.info(f"🟢 激活提供商配置: {provider.name}")
        _refresh_registry()
        
        return jsonify({
            'success': True,
            'message': f'已激活 {provider.name}',
            'provider': provider.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"激活提供商失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@providers_bp.route('/test', methods=['POST'])
def test_connection():
    """测试连接（不保存配置，仅验证 API Key 和 Base URL 是否有效）"""
    data = request.get_json(force=True) or {}
    
    protocol = data.get('protocol', 'openai').strip()
    base_url = data.get('base_url', '').strip()
    api_key = data.get('api_key', '').strip()
    model = data.get('default_model', '').strip()
    
    if not base_url or not api_key:
        return jsonify({'success': False, 'error': 'Base URL 和 API Key 不能为空'}), 400
    
    try:
        # 根据协议创建对应的 Provider 实例进行测试
        if protocol == 'openai':
            from service.providers.openai_provider import OpenAIProvider
            provider = OpenAIProvider(api_key=api_key, model=model or 'gpt-4o', base_url=base_url)
        elif protocol == 'anthropic':
            from service.providers.claude_provider import ClaudeProvider
            provider = ClaudeProvider(api_key=api_key, model=model or 'claude-sonnet-4-20250514', base_url=base_url)
        else:
            return jsonify({'success': False, 'error': '不支持的协议类型'}), 400
        
        # 发送一个简单的测试请求
        test_messages = [{'role': 'user', 'content': 'Hello'}]
        
        # 使用 asyncio.run 执行异步调用
        import nest_asyncio
        nest_asyncio.apply()
        
        result = asyncio.run(provider.chat(test_messages))
        
        if result.success:
            return jsonify({
                'success': True,
                'message': '连接成功！API Key 和 Base URL 验证通过。',
                'model': model or provider.model,
                'response': result.content[:100] + '...' if result.content else '(空响应)'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'连接失败：{result.error}'
            }), 400
            
    except Exception as e:
        logger.error(f"测试连接失败: {e}")
        return jsonify({
            'success': False,
            'error': f'测试失败：{str(e)}'
        }), 400
