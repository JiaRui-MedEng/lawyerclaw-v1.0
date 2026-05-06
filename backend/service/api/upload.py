"""
文件上传 API - 支持图片上传
"""
import os
import uuid
from pathlib import Path
from flask import Blueprint, request, jsonify

upload_bp = Blueprint('upload', __name__, url_prefix='/api/upload')

# 上传目录
from service.core.paths import get_uploads_dir
UPLOAD_DIR = get_uploads_dir()

# 允许的文件类型
ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def allowed_file(filename):
    """检查文件类型是否允许"""
    ext = Path(filename).suffix.lower()
    return ext in ALLOWED_EXTENSIONS


@upload_bp.route('/image', methods=['POST'])
def upload_image():
    """上传图片文件"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': '没有文件'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'success': False, 'message': '文件名为空'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({
                'success': False,
                'message': f'不支持的文件类型。允许：{", ".join(ALLOWED_EXTENSIONS)}'
            }), 400
        
        # 检查文件大小
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > MAX_FILE_SIZE:
            return jsonify({
                'success': False,
                'message': f'文件过大 ({file_size:,} 字节)，最大支持 {MAX_FILE_SIZE:,} 字节'
            }), 400
        
        # 生成唯一文件名
        ext = Path(file.filename).suffix.lower()
        filename = f"{uuid.uuid4().hex}{ext}"
        filepath = UPLOAD_DIR / filename
        
        # 保存文件
        file.save(str(filepath))
        
        # 生成访问 URL
        # 注意：这里生成的是本地路径，需要前端能访问
        # 生产环境应该上传到 OSS/CDN
        image_url = f"/api/uploads/{filename}"
        
        return jsonify({
            'success': True,
            'url': image_url,
            'filename': filename,
            'size': file_size
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'上传失败：{str(e)}'
        }), 500


@upload_bp.route('/files', methods=['POST'])
def upload_file():
    """上传任意文件"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': '没有文件'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'success': False, 'message': '文件名为空'}), 400
        
        # 检查文件大小
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > MAX_FILE_SIZE:
            return jsonify({
                'success': False,
                'message': f'文件过大，最大支持 {MAX_FILE_SIZE:,} 字节'
            }), 400
        
        # 生成唯一文件名
        filename = f"{uuid.uuid4().hex}_{file.filename}"
        filepath = UPLOAD_DIR / filename
        
        # 保存文件
        file.save(str(filepath))
        
        # 生成访问 URL
        file_url = f"/api/uploads/{filename}"
        
        return jsonify({
            'success': True,
            'url': file_url,
            'filename': file.filename,
            'size': file_size
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'上传失败：{str(e)}'
        }), 500
