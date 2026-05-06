"""
会话管理 API
"""
import asyncio
from flask import Blueprint, request, jsonify
from service.core.runtime import runtime

sessions_bp = Blueprint('sessions', __name__, url_prefix='/api/sessions')


def _get_current_user_id():
    """获取当前用户 ID（已移除认证，返回 None 表示匿名用户）"""
    return None


@sessions_bp.route('', methods=['GET'])
def list_sessions():
    """获取会话列表"""
    sessions = asyncio.run(runtime.list_sessions(None))
    return jsonify({'success': True, 'sessions': sessions})


@sessions_bp.route('', methods=['POST'])
def create_session():
    """创建新会话"""
    data = request.get_json(force=True) or {}
    model = data.get('model')
    
    session_obj = asyncio.run(runtime.create_session(
        user_id=None,
        model=model
    ))
    return jsonify({'success': True, 'session': session_obj}), 201


@sessions_bp.route('/<session_id>', methods=['GET'])
def get_session(session_id):
    """获取会话详情"""
    result = asyncio.run(runtime.get_session(session_id))
    if not result:
        return jsonify({'success': False, 'message': '会话不存在'}), 404
    
    return jsonify({'success': True, 'data': result})


@sessions_bp.route('/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    """删除会话"""
    from service.models.database import Session as SessionModel, Memory, db
    import logging
    logger = logging.getLogger(__name__)

    try:
        session_obj = SessionModel.query.get(session_id)
        if not session_obj:
            return jsonify({'success': False, 'message': '会话不存在'}), 404

        # 手动清理关联数据，避免 cascade 与外键约束冲突
        from service.models.database import Message
        # 先删除关联消息
        for msg in Message.query.filter_by(session_id=session_id).all():
            db.session.delete(msg)
        # 解除记忆关联（逐个处理，避免 update() 与 session 状态冲突）
        for mem in Memory.query.filter_by(session_id=session_id).all():
            mem.session_id = None
        # 删除会话
        db.session.delete(session_obj)
        db.session.commit()
        return jsonify({'success': True, 'message': '会话已删除'})
    except Exception as e:
        db.session.rollback()
        logger.error(f'删除会话失败：{e}', exc_info=True)
        return jsonify({'success': False, 'message': f'删除失败：{str(e)}'}), 500


@sessions_bp.route('/<session_id>/messages', methods=['GET'])
def get_messages(session_id):
    """获取会话消息列表"""
    from service.models.database import Message, Session as SessionModel
    
    session_obj = SessionModel.query.get(session_id)
    if not session_obj:
        return jsonify({'success': False, 'message': '会话不存在'}), 404
    
    messages = Message.query.filter_by(session_id=session_id)\
        .order_by(Message.created_at)\
        .all()
    return jsonify({
        'success': True,
        'messages': [m.to_dict() for m in messages]
    })


@sessions_bp.route('/<session_id>/title', methods=['PATCH'])
def update_title(session_id):
    """更新会话标题"""
    data = request.get_json(force=True) or {}
    title = data.get('title', '').strip()
    if not title:
        return jsonify({'success': False, 'message': '标题不能为空'}), 400
    
    from service.models.database import Session as SessionModel, db
    
    session_obj = SessionModel.query.get(session_id)
    if not session_obj:
        return jsonify({'success': False, 'message': '会话不存在'}), 404
    
    session_obj.title = title
    db.session.commit()
    return jsonify({'success': True, 'session': session_obj.to_dict()})


@sessions_bp.route('/batch-delete', methods=['POST'])
def batch_delete_sessions():
    """批量删除会话（真正从数据库删除）"""
    import logging
    logger = logging.getLogger(__name__)
    
    data = request.get_json(force=True) or {}
    session_ids = data.get('session_ids', [])
    
    logger.info(f'🗑️ 批量删除请求：session_ids={session_ids}')
    
    if not session_ids:
        return jsonify({'success': False, 'message': '未选择要删除的会话'}), 400
    
    from service.models.database import Session as SessionModel, Message, Memory, db

    deleted_count = 0
    for session_id in session_ids:
        session = SessionModel.query.get(session_id)
        if session:
            logger.info(f'🗑️ 删除会话：{session_id}, title={session.title}')
            # 先解除记忆的外键引用
            Memory.query.filter_by(session_id=session_id).update({'session_id': None})
            # 删除关联的消息
            msg_count = Message.query.filter_by(session_id=session_id).count()
            Message.query.filter_by(session_id=session_id).delete()
            logger.info(f'   删除了 {msg_count} 条消息')
            # 删除会话
            db.session.delete(session)
            deleted_count += 1
    
    db.session.commit()
    logger.info(f'✅ 批量删除完成：删除了 {deleted_count} 个会话')
    
    return jsonify({
        'success': True,
        'message': f'已删除 {deleted_count} 个会话',
        'deleted_count': deleted_count
    })
