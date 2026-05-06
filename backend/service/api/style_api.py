"""
风格 API - REST 接口

提供风格分析、润色、Profile 管理的 HTTP API。

端点：
- POST /api/style/analyze    - 分析文档，生成风格 Profile
- POST /api/style/polish     - 润色文本
- GET  /api/style/profiles   - 列出所有风格 Profile
- GET  /api/style/profile/:name - 获取指定风格 Profile
- POST /api/style/profile/:name/delete - 删除风格 Profile
- POST /api/style/export     - 导出为 Skill
- GET  /api/style/config     - 获取 API 配置
- POST /api/style/config     - 更新 API 配置
- POST /api/style/config/test - 测试 API 连通性
"""
import asyncio
import logging
from flask import Blueprint, request, jsonify

from service.core.style_forge import analyzer, polisher, profile_manager

logger = logging.getLogger(__name__)

style_bp = Blueprint('style', __name__, url_prefix='/api/style')


@style_bp.route('/analyze', methods=['POST'])
def analyze_style():
    """
    分析文档，生成风格 Profile
    
    Request JSON:
    {
        "file_paths": ["D:/docs/my_article.pdf", "D:/docs/my_article2.pdf"],  // 支持多个文件
        "style_name": "doctor-li",
        "merge": false  // 可选，默认 false
    }
    
    Response JSON:
    {
        "success": true,
        "style_name": "doctor-li",
        "vocabulary": {...},
        "rhythm": {...},
        "anti_ai": {...}
    }
    """
    try:
        data = request.get_json(force=True) or {}
        file_paths = data.get('file_paths') or []
        file_path = data.get('file_path')
        style_name = data.get('style_name')
        merge = data.get('merge', False)
        
        # 兼容单文件和多文件
        if file_path and not file_paths:
            file_paths = [file_path]
        
        if not file_paths or not style_name:
            return jsonify({
                'success': False,
                'error': '缺少 file_paths 或 style_name 参数'
            }), 400
        
        logger.info(f"[StyleAPI] 分析风格: {len(file_paths)} 个文件 → {style_name}")
        
        # 1. 解析所有文档，合并文本
        combined_text = []
        source_files = []
        for fp in file_paths:
            try:
                text = analyzer.parse_document(fp)
                if len(text) >= 50:  # 至少 50 字符才有效
                    combined_text.append(text)
                    source_files.append(fp)
                    logger.info(f"[StyleAPI] 解析成功: {fp}, {len(text)} 字符")
                else:
                    logger.warning(f"[StyleAPI] 文档过短: {fp}, {len(text)} 字符")
            except Exception as e:
                logger.warning(f"[StyleAPI] 解析失败: {fp} - {e}")
        
        if not combined_text:
            return jsonify({
                'success': False,
                'error': '所有文档解析失败或内容过短'
            }), 400
        
        full_text = '\n\n'.join(combined_text)
        
        if len(full_text) < 100:
            return jsonify({
                'success': False,
                'error': f'所有文档内容过短（{len(full_text)} 字符），需要至少 100 字符'
            }), 400
        
        # 2. 风格分析
        style_data = analyzer.analyze_style(full_text)
        
        # 3. 保存 Profile
        try:
            if merge:
                profile = profile_manager.update_profile(style_name, style_data, merge=True)
                action = "合并更新"
            else:
                profile = profile_manager.create_profile(
                    style_name, style_data, source_files=source_files
                )
                action = "创建"
        except FileExistsError:
            return jsonify({
                'success': False,
                'error': f'风格已存在: {style_name}。使用 merge=true 合并。'
            }), 409
        
        return jsonify({
            'success': True,
            'action': action,
            'style_name': style_name,
            'vocabulary': style_data.get('vocabulary', {}),
            'rhythm': style_data.get('rhythm', {}),
            'paragraph': style_data.get('paragraph', {}),
            'transitions': style_data.get('transitions', {}),
            'anti_ai': style_data.get('anti_ai', {}),
        })
        
    except FileNotFoundError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"[StyleAPI] 分析失败: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@style_bp.route('/polish', methods=['POST'])
def polish_text():
    """
    润色文本
    
    Request JSON:
    {
        "text": "首先，我们需要认识到...",
        "style_name": "doctor-li",
        "intensity": "medium",  // 可选：light/medium/strong
        "use_api": true         // 可选，默认 true
    }
    
    Response JSON:
    {
        "success": true,
        "polished": "第一，我们要明白...",
        "method": "api + post_process",
        "original_length": 100,
        "polished_length": 120
    }
    """
    try:
        data = request.get_json(force=True) or {}
        text = data.get('text')
        style_name = data.get('style_name')
        intensity = data.get('intensity', 'medium')
        use_api = data.get('use_api', True)
        
        if not text or not style_name:
            return jsonify({
                'success': False,
                'error': '缺少 text 或 style_name 参数'
            }), 400
        
        if intensity not in ('light', 'medium', 'strong'):
            return jsonify({
                'success': False,
                'error': f'无效的润色强度: {intensity}。可选: light, medium, strong'
            }), 400
        
        logger.info(f"[StyleAPI] 润色文本: {style_name}, 强度 {intensity}")
        
        # 加载风格 Profile
        profile = profile_manager.load_profile(style_name)
        
        # 执行润色（同步调用异步函数）
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                polisher.polish_text(
                    text=text,
                    style_profile=profile,
                    intensity=intensity,
                    use_api=use_api,
                )
            )
        finally:
            loop.close()
        
        if not result.get('success'):
            return jsonify({
                'success': False,
                'error': result.get('error', '润色失败')
            }), 500
        
        return jsonify({
            'success': True,
            'polished': result['polished'],
            'method': result.get('method', 'unknown'),
            'intensity': intensity,
            'original_length': len(text),
            'polished_length': len(result['polished']),
            'length_diff': result.get('length_diff', 0),
        })
        
    except FileNotFoundError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except Exception as e:
        logger.error(f"[StyleAPI] 润色失败: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@style_bp.route('/profiles', methods=['GET'])
def list_profiles():
    """
    列出所有风格 Profile
    
    Response JSON:
    {
        "success": true,
        "profiles": [...]
    }
    """
    try:
        profiles = profile_manager.list_profiles()
        return jsonify({
            'success': True,
            'profiles': profiles,
            'count': len(profiles),
        })
    except Exception as e:
        logger.error(f"[StyleAPI] 列表失败: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@style_bp.route('/profile/<name>', methods=['GET'])
def get_profile(name: str):
    """
    获取指定风格 Profile
    
    Response JSON:
    {
        "success": true,
        "profile": {...}
    }
    """
    try:
        profile = profile_manager.load_profile(name)
        return jsonify({
            'success': True,
            'profile': profile,
        })
    except FileNotFoundError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except Exception as e:
        logger.error(f"[StyleAPI] 获取 Profile 失败: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@style_bp.route('/profile/<name>/delete', methods=['POST'])
def delete_profile(name: str):
    """
    删除风格 Profile
    
    Response JSON:
    {
        "success": true,
        "message": "风格已删除"
    }
    """
    try:
        deleted = profile_manager.delete_profile(name)
        if deleted:
            return jsonify({
                'success': True,
                'message': f'风格 {name} 已删除'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'风格不存在: {name}'
            }), 404
    except Exception as e:
        logger.error(f"[StyleAPI] 删除失败: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@style_bp.route('/export', methods=['POST'])
def export_profile():
    """
    导出风格为 Skill
    
    Request JSON:
    {
        "style_name": "doctor-li",
        "output_dir": "~/.hermes/skills/"  // 可选
    }
    
    Response JSON:
    {
        "success": true,
        "output_path": "..."
    }
    """
    try:
        data = request.get_json(force=True) or {}
        style_name = data.get('style_name')
        output_dir = data.get('output_dir', '')
        
        if not style_name:
            return jsonify({
                'success': False,
                'error': '缺少 style_name 参数'
            }), 400
        
        output_path = profile_manager.export_profile(
            style_name,
            output_dir=output_dir if output_dir else None
        )
        
        return jsonify({
            'success': True,
            'output_path': output_path,
            'message': f'风格 {style_name} 已导出为 Skill'
        })
        
    except FileNotFoundError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except Exception as e:
        logger.error(f"[StyleAPI] 导出失败: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@style_bp.route('/config', methods=['GET'])
def get_config():
    """
    获取 API 配置
    
    Response JSON:
    {
        "success": true,
        "config": {...}
    }
    """
    try:
        config = polisher.load_config()
        # 脱敏显示
        active = config.get("api", {}).get("active", "")
        profiles = config.get("api", {}).get("profiles", {})
        for name, profile in profiles.items():
            if "env_key_name" in profile:
                profile["api_key_masked"] = "****"
        
        return jsonify({
            'success': True,
            'config': config,
        })
    except Exception as e:
        logger.error(f"[StyleAPI] 获取配置失败: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@style_bp.route('/config', methods=['POST'])
def update_config():
    """
    更新 API 配置
    
    Request JSON:
    {
        "base_url": "https://api.example.com/v1",
        "model": "gpt-4o",
        "env_key_name": "STYLE_FORGE_API_KEY"
    }
    
    Response JSON:
    {
        "success": true,
        "message": "配置已更新"
    }
    """
    try:
        data = request.get_json(force=True) or {}
        config = polisher.load_config()
        
        # 更新配置
        if "base_url" in data:
            active = config["api"]["active"]
            config["api"]["profiles"][active]["base_url"] = data["base_url"]
        if "model" in data:
            active = config["api"]["active"]
            config["api"]["profiles"][active]["model"] = data["model"]
        if "env_key_name" in data:
            active = config["api"]["active"]
            config["api"]["profiles"][active]["env_key_name"] = data["env_key_name"]
        if "timeout" in data:
            active = config["api"]["active"]
            config["api"]["profiles"][active]["timeout"] = data["timeout"]
        
        polisher.save_config(config)
        
        return jsonify({
            'success': True,
            'message': 'API 配置已更新'
        })
        
    except Exception as e:
        logger.error(f"[StyleAPI] 更新配置失败: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@style_bp.route('/config/test', methods=['POST'])
def test_config():
    """
    测试 API 连通性
    
    Response JSON:
    {
        "success": true,
        "message": "API 连通正常",
        "model": "gpt-4o"
    }
    """
    try:
        config = polisher.load_config()
        result = polisher.test_api_connection(config)
        
        if result.get("success"):
            return jsonify(result)
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"[StyleAPI] 配置测试失败: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@style_bp.route('/check', methods=['GET'])
def check_style():
    """检查风格服务状态"""
    return jsonify({
        'status': 'ok',
        'message': 'Style Forge 服务正常运行',
        'endpoints': {
            'analyze': '/api/style/analyze',
            'polish': '/api/style/polish',
            'profiles': '/api/style/profiles',
            'config': '/api/style/config',
            'export': '/api/style/export',
        }
    })
