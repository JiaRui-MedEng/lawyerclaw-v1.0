"""
用户认证 API
提供注册、登录、登出、用户信息等功能
"""
import os
import uuid
import jwt
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, session, current_app
from flask_cors import CORS
from service.models.database import db, User, Session, Message
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')
CORS(auth_bp, supports_credentials=True)


def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 从请求头获取 token
        auth_header = request.headers.get('Authorization')
        user_id = None

        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header[7:]
            user_id = verify_token(token)

        # 回退到 session
        if not user_id:
            user_id = session.get('user_id')

        if user_id:
            # 验证用户是否存在且活跃
            user = User.query.get(user_id)
            if user and user.is_active:
                request.current_user_id = user_id
                request.current_user = user
                return f(*args, **kwargs)

        return jsonify({'success': False, 'message': '请先登录'}), 401
    
    return decorated_function


def verify_token(token):
    """验证 JWT token"""
    try:
        secret_key = current_app.config.get('SECRET_KEY', 'lawyerclaw-secret')
        payload = jwt.decode(token, secret_key, algorithms=['HS256'])
        user_id = payload.get('user_id')
        return user_id
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def generate_token(user_id):
    """生成 JWT token"""
    secret_key = current_app.config.get('SECRET_KEY', 'lawyerclaw-secret')
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(days=7),  # 7 天有效期
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, secret_key, algorithm='HS256')


@auth_bp.route('/register', methods=['POST'])
def register():
    """用户注册"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '')
        
        # 验证
        if not username or not email or not password:
            return jsonify({'success': False, 'message': '请填写完整信息'}), 400
        
        if len(username) < 3:
            return jsonify({'success': False, 'message': '用户名至少 3 个字符'}), 400
        
        if len(password) < 6:
            return jsonify({'success': False, 'message': '密码至少 6 个字符'}), 400
        
        # 检查是否已存在
        if User.query.filter_by(username=username).first():
            return jsonify({'success': False, 'message': '用户名已存在'}), 409
        
        if User.query.filter_by(email=email).first():
            return jsonify({'success': False, 'message': '邮箱已被注册'}), 409
        
        # 创建用户
        user = User(
            id=str(uuid.uuid4()),
            username=username,
            email=email,
            is_active=True
        )
        user.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
        
        db.session.add(user)
        db.session.commit()
        
        # 生成 token
        token = generate_token(user.id)
        
        # 设置 session
        session['user_id'] = user.id
        session['username'] = user.username
        
        return jsonify({
            'success': True,
            'message': '注册成功',
            'data': {
                'user': user.to_dict(),
                'token': token
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'注册失败：{str(e)}'}), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    """用户登录"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({'success': False, 'message': '请填写用户名和密码'}), 400
        
        # 查找用户（支持用户名或邮箱登录）
        user = User.query.filter(
            (User.username == username) | (User.email == username)
        ).first()
        
        if not user or not check_password_hash(user.password_hash, password):
            return jsonify({'success': False, 'message': '用户名或密码错误'}), 401
        
        if not user.is_active:
            return jsonify({'success': False, 'message': '账户已被禁用'}), 403
        
        # 更新最后登录时间
        user.last_login = datetime.now()
        db.session.commit()
        
        # 生成 token
        token = generate_token(user.id)
        
        # 设置 session
        session['user_id'] = user.id
        session['username'] = user.username
        session.permanent = True
        
        return jsonify({
            'success': True,
            'message': '登录成功',
            'data': {
                'user': user.to_dict(),
                'token': token
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'登录失败：{str(e)}'}), 500


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """用户登出"""
    session.clear()
    return jsonify({'success': True, 'message': '已退出登录'})


@auth_bp.route('/me', methods=['GET'])
@login_required
def get_current_user():
    """获取当前用户信息"""
    user = User.query.get(request.current_user_id)
    if not user:
        return jsonify({'success': False, 'message': '用户不存在'}), 404
    
    return jsonify({
        'success': True,
        'data': user.to_dict()
    })


@auth_bp.route('/me', methods=['PUT'])
@login_required
def update_current_user():
    """更新当前用户信息"""
    try:
        user = User.query.get(request.current_user_id)
        if not user:
            return jsonify({'success': False, 'message': '用户不存在'}), 404
        
        data = request.get_json()
        
        # 可更新的字段
        if 'avatar_url' in data:
            user.avatar_url = data['avatar_url']
        
        # 修改密码
        if 'password' in data:
            old_password = data.get('old_password', '')
            if not check_password_hash(user.password_hash, old_password):
                return jsonify({'success': False, 'message': '原密码错误'}), 400
            
            new_password = data['password']
            if len(new_password) < 6:
                return jsonify({'success': False, 'message': '密码至少 6 个字符'}), 400
            
            user.password_hash = generate_password_hash(new_password, method='pbkdf2:sha256')
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '更新成功',
            'data': user.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'更新失败：{str(e)}'}), 500


@auth_bp.route('/users', methods=['GET'])
@login_required
def get_users():
    """获取用户列表（仅管理员）"""
    user = User.query.get(request.current_user_id)
    if not user or not user.is_superuser:
        return jsonify({'success': False, 'message': '权限不足'}), 403
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    pagination = User.query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'success': True,
        'data': {
            'users': [u.to_dict() for u in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page
        }
    })


@auth_bp.route('/check', methods=['GET'])
def check_auth_status():
    """检查登录状态（支持 JWT token 和 session）"""
    user_id = None

    # 优先检查 JWT token
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]
        user_id = verify_token(token)

    # 回退到 session
    if not user_id:
        user_id = session.get('user_id')

    if user_id:
        user = User.query.get(user_id)
        if user and user.is_active:
            return jsonify({
                'success': True,
                'authenticated': True,
                'user': user.to_dict()
            })

    return jsonify({
        'success': True,
        'authenticated': False
    }), 200
