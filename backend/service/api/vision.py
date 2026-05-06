"""
Vision API - 图片分析和 OCR

提供专门的图片分析接口，不依赖对话系统
"""
import asyncio
import logging
from flask import Blueprint, request, jsonify

from service.tools.vision_tools import vision_analyze_tool, ocr_tool

logger = logging.getLogger(__name__)

vision_bp = Blueprint('vision', __name__, url_prefix='/api/vision')


@vision_bp.route('/analyze', methods=['POST'])
def analyze_image():
    """
    分析图片内容
    
    Request JSON:
    {
        "image_source": "D:/image.png" 或 "https://example.com/image.jpg",
        "prompt": "描述这张图片" (可选，默认"请详细描述这张图片的内容")
    }
    
    Response JSON:
    {
        "success": true,
        "content": "图片分析结果...",
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 200,
            "total_tokens": 300
        }
    }
    """
    try:
        data = request.get_json(force=True) or {}
        image_source = data.get('image_source')
        prompt = data.get('prompt', '请详细描述这张图片的内容')
        
        if not image_source:
            return jsonify({
                'success': False,
                'error': '缺少 image_source 参数'
            }), 400
        
        logger.info(f"[Vision] 分析图片：{image_source[:60]}...")
        logger.info(f"[Vision] Prompt: {prompt[:50]}...")
        
        # 调用 Vision 工具
        result = asyncio.run(vision_analyze_tool(image_source, prompt))
        
        if result['success']:
            logger.info(f"[Vision] 分析成功，{len(result['content'])} 字符")
            return jsonify(result)
        else:
            logger.error(f"[Vision] 分析失败：{result.get('error')}")
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"[Vision] 异常：{e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@vision_bp.route('/ocr', methods=['POST'])
def ocr_image():
    """
    OCR 文字提取
    
    Request JSON:
    {
        "image_source": "D:/image.png" 或 "https://example.com/image.jpg"
    }
    
    Response JSON:
    {
        "success": true,
        "content": "提取的文字内容..."
    }
    """
    try:
        data = request.get_json(force=True) or {}
        image_source = data.get('image_source')
        
        if not image_source:
            return jsonify({
                'success': False,
                'error': '缺少 image_source 参数'
            }), 400
        
        logger.info(f"[OCR] 提取文字：{image_source[:60]}...")
        
        # 调用 OCR 工具
        result = asyncio.run(ocr_tool(image_source))
        
        if result['success']:
            logger.info(f"[OCR] 提取成功，{len(result['content'])} 字符")
            return jsonify(result)
        else:
            logger.error(f"[OCR] 提取失败：{result.get('error')}")
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"[OCR] 异常：{e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@vision_bp.route('/check', methods=['GET'])
def check_vision():
    """检查 Vision 服务状态"""
    return jsonify({
        'status': 'ok',
        'message': 'Vision API 正常运行',
        'endpoints': {
            'analyze': '/api/vision/analyze',
            'ocr': '/api/vision/ocr'
        }
    })
