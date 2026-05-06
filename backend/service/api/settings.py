"""
用户设置 API

提供用户个性化设置的获取和保存功能。
"""
import json
from flask import Blueprint, request, jsonify
from service.models.database import db, UserSettings

settings_bp = Blueprint('settings', __name__, url_prefix='/api/settings')


@settings_bp.route('', methods=['GET'])
def get_settings():
    """获取用户设置"""
    user_id = request.args.get('user_id', 'default')
    
    try:
        all_settings = UserSettings.query.filter_by(user_id=user_id).all()
        
        settings_dict = {}
        for setting in all_settings:
            try:
                settings_dict[setting.setting_key] = json.loads(setting.setting_value)
            except (json.JSONDecodeError, TypeError):
                settings_dict[setting.setting_key] = setting.setting_value
        
        return jsonify({
            'success': True,
            'settings': settings_dict,
            'user_id': user_id
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@settings_bp.route('', methods=['POST'])
def save_settings():
    """保存用户设置"""
    data = request.get_json(force=True) or {}
    user_id = data.get('user_id', 'default')
    settings = data.get('settings', {})
    
    if not settings:
        return jsonify({
            'success': False,
            'error': '设置内容不能为空'
        }), 400
    
    try:
        for key, value in settings.items():
            # 验证设置键
            if not key or not isinstance(key, str):
                continue
            
            # 序列化设置值
            if isinstance(value, (dict, list, bool, int, float)):
                value_str = json.dumps(value, ensure_ascii=False)
            else:
                value_str = str(value)
            
            # 查找现有记录
            setting = UserSettings.query.filter_by(
                user_id=user_id,
                setting_key=key
            ).first()
            
            if setting:
                # 更新现有记录
                setting.setting_value = value_str
            else:
                # 创建新记录
                setting = UserSettings(
                    user_id=user_id,
                    setting_key=key,
                    setting_value=value_str
                )
                db.session.add(setting)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '设置已保存',
            'user_id': user_id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@settings_bp.route('/<setting_key>', methods=['GET'])
def get_setting(setting_key):
    """获取单个设置项"""
    user_id = request.args.get('user_id', 'default')
    
    try:
        setting = UserSettings.query.filter_by(
            user_id=user_id,
            setting_key=setting_key
        ).first()
        
        if not setting:
            return jsonify({
                'success': True,
                'value': None,
                'message': '设置不存在'
            })
        
        try:
            value = json.loads(setting.setting_value)
        except (json.JSONDecodeError, TypeError):
            value = setting.setting_value
        
        return jsonify({
            'success': True,
            'value': value,
            'setting_key': setting_key
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@settings_bp.route('/reset', methods=['POST'])
def reset_settings():
    """重置用户设置"""
    data = request.get_json(force=True) or {}
    user_id = data.get('user_id', 'default')
    keys = data.get('keys', [])  # 指定要重置的键，空列表表示重置所有
    
    try:
        if keys:
            # 重置指定设置
            for key in keys:
                setting = UserSettings.query.filter_by(
                    user_id=user_id,
                    setting_key=key
                ).first()
                if setting:
                    db.session.delete(setting)
        else:
            # 重置所有设置
            UserSettings.query.filter_by(user_id=user_id).delete()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '设置已重置',
            'user_id': user_id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
