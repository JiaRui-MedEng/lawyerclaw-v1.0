"""
百佑 LawyerClaw 安全 API 路由
基于 Hermes 安全架构

功能:
- 命令审批
- 技能安全扫描
- 记忆内容扫描
- 安全审计日志
"""
from flask import Blueprint, request, jsonify
from service.models.database import db, SecurityAuditLog, ApprovalRecord, SkillScanRecord
from service.security.approval_enhanced import check_command_approval, approval_manager
from service.security.skills_guard_enhanced import scan_skill, should_allow_install, format_scan_report
from service.security.memory_guard import scan_memory_content, should_allow_memory
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

security_bp = Blueprint('security', __name__, url_prefix='/api/security')


# ═══════════════════════════════════════════════════════════
# 命令审批 API
# ═══════════════════════════════════════════════════════════

@security_bp.route('/command/check', methods=['POST'])
def check_command():
    """
    检查命令审批状态
    
    Request:
        {
            "command": "rm -rf /tmp/test",
            "session_id": "uuid"
        }
    
    Response:
        {
            "approved": bool,
            "is_dangerous": bool,
            "pattern_key": str or null,
            "severity": str or null,
            "description": str or null,
            "requires_approval": bool
        }
    """
    data = request.get_json()
    
    if not data or 'command' not in data:
        return jsonify({'error': 'command is required'}), 400
    
    command = data['command']
    session_id = data.get('session_id', 'default')
    
    result = check_command_approval(command, session_id)
    
    # 记录审计日志
    if result['is_dangerous']:
        audit_log = SecurityAuditLog(
            session_id=session_id,
            audit_type='command_approval',
            action=command[:500],
            target=result.get('pattern_key'),
            result='approved' if result['approved'] else 'blocked',
            details={
                'severity': result.get('severity'),
                'description': result.get('description')
            }
        )
        db.session.add(audit_log)
        db.session.commit()
    
    return jsonify(result)


@security_bp.route('/command/approve', methods=['POST'])
def approve_command():
    """
    审批危险命令
    
    Request:
        {
            "session_id": "uuid",
            "pattern_key": "recursive delete",
            "approval_type": "session" or "permanent"
        }
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Request body required'}), 400
    
    session_id = data.get('session_id')
    pattern_key = data.get('pattern_key')
    approval_type = data.get('approval_type', 'session')
    
    if not session_id or not pattern_key:
        return jsonify({'error': 'session_id and pattern_key are required'}), 400
    
    if approval_type == 'session':
        approval_manager.approve_session(session_id, pattern_key)
    elif approval_type == 'permanent':
        approval_manager.approve_permanent(pattern_key)
    else:
        return jsonify({'error': 'Invalid approval_type'}), 400
    
    # 记录审批记录
    record = ApprovalRecord(
        session_id=session_id,
        approval_type=approval_type,
        pattern_key=pattern_key,
        status='approved'
    )
    db.session.add(record)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Command approved ({approval_type})'
    })


# ═══════════════════════════════════════════════════════════
# 技能安全扫描 API
# ═══════════════════════════════════════════════════════════

@security_bp.route('/skill/scan', methods=['POST'])
def scan_skill_api():
    """
    扫描技能安全性
    
    Request:
        {
            "skill_dir": "/path/to/skill",
            "source": "community" or "trusted" or "internal" or "legal"
        }
    
    Response:
        {
            "verdict": "safe" or "caution" or "dangerous",
            "findings_count": int,
            "findings": [...],
            "report": str,
            "allowed": bool or null
        }
    """
    data = request.get_json()
    
    if not data or 'skill_dir' not in data:
        return jsonify({'error': 'skill_dir is required'}), 400
    
    skill_dir = Path(data['skill_dir'])
    source = data.get('source', 'community')
    
    if not skill_dir.exists():
        return jsonify({'error': 'Skill directory not found'}), 404
    
    # 执行扫描
    result = scan_skill(skill_dir, source)
    
    # 判定是否允许
    allowed, reason = should_allow_install(result)
    
    # 记录扫描记录
    scan_record = SkillScanRecord(
        skill_name=skill_dir.name,
        source=source,
        verdict=result.verdict,
        findings_count=len(result.findings),
        findings_summary=[
            {
                'pattern_id': f.pattern_id,
                'severity': f.severity,
                'category': f.category,
                'file': f.file,
                'line': f.line
            }
            for f in result.findings[:10]  # 只保存前 10 个
        ]
    )
    db.session.add(scan_record)
    db.session.commit()
    
    return jsonify({
        'verdict': result.verdict,
        'findings_count': result.findings_count if hasattr(result, 'findings_count') else len(result.findings),
        'findings': [
            {
                'pattern_id': f.pattern_id,
                'severity': f.severity,
                'category': f.category,
                'file': f.file,
                'line': f.line,
                'match': f.match,
                'description': f.description
            }
            for f in result.findings[:20]  # 只返回前 20 个
        ],
        'report': format_scan_report(result),
        'allowed': allowed,
        'reason': reason
    })


# ═══════════════════════════════════════════════════════════
# 记忆内容扫描 API
# ═══════════════════════════════════════════════════════════

@security_bp.route('/memory/scan', methods=['POST'])
def scan_memory_api():
    """
    扫描记忆内容安全性
    
    Request:
        {
            "content": "记忆内容",
            "source": "user" or "agent" or "system"
        }
    
    Response:
        {
            "safe": bool,
            "verdict": "safe" or "caution" or "dangerous",
            "findings": [...],
            "allowed": bool or null,
            "reason": str
        }
    """
    data = request.get_json()
    
    if not data or 'content' not in data:
        return jsonify({'error': 'content is required'}), 400
    
    content = data['content']
    source = data.get('source', 'user')
    
    # 执行扫描
    result = scan_memory_content(content)
    
    # 判定是否允许
    allowed, reason = should_allow_memory(content, source)
    
    # 记录审计日志
    audit_log = SecurityAuditLog(
        audit_type='memory_scan',
        action='memory_write',
        target=source,
        result='allowed' if allowed else 'blocked',
        details={
            'verdict': result['verdict'],
            'findings_count': result['count']
        }
    )
    db.session.add(audit_log)
    db.session.commit()
    
    return jsonify({
        'safe': result['safe'],
        'verdict': result['verdict'],
        'findings': result['findings'][:20],  # 只返回前 20 个
        'count': result['count'],
        'allowed': allowed,
        'reason': reason
    })


# ═══════════════════════════════════════════════════════════
# 安全审计日志 API
# ═══════════════════════════════════════════════════════════

@security_bp.route('/audit/logs', methods=['GET'])
def get_audit_logs():
    """
    获取安全审计日志
    
    Query Params:
        session_id: 可选，按会话过滤
        audit_type: 可选，按类型过滤 (command_approval, skill_scan, memory_scan)
        limit: 可选，默认 100
    """
    session_id = request.args.get('session_id')
    audit_type = request.args.get('audit_type')
    limit = min(int(request.args.get('limit', 100)), 500)
    
    query = SecurityAuditLog.query
    
    if session_id:
        query = query.filter_by(session_id=session_id)
    
    if audit_type:
        query = query.filter_by(audit_type=audit_type)
    
    logs = query.order_by(SecurityAuditLog.created_at.desc()).limit(limit).all()
    
    return jsonify({
        'count': len(logs),
        'logs': [log.to_dict() for log in logs]
    })


@security_bp.route('/audit/statistics', methods=['GET'])
def get_audit_statistics():
    """
    获取安全审计统计
    
    Response:
        {
            "total_logs": int,
            "by_type": {...},
            "by_result": {...},
            "recent_blocked": [...]
        }
    """
    # 总数
    total = SecurityAuditLog.query.count()
    
    # 按类型统计
    by_type = db.session.query(
        SecurityAuditLog.audit_type,
        db.func.count(SecurityAuditLog.id)
    ).group_by(SecurityAuditLog.audit_type).all()
    
    # 按结果统计
    by_result = db.session.query(
        SecurityAuditLog.result,
        db.func.count(SecurityAuditLog.id)
    ).group_by(SecurityAuditLog.result).all()
    
    # 最近阻止的记录
    recent_blocked = SecurityAuditLog.query.filter_by(result='blocked')\
        .order_by(SecurityAuditLog.created_at.desc()).limit(10).all()
    
    return jsonify({
        'total_logs': total,
        'by_type': dict(by_type),
        'by_result': dict(by_result),
        'recent_blocked': [log.to_dict() for log in recent_blocked]
    })


# ═══════════════════════════════════════════════════════════
# 审批记录 API
# ═══════════════════════════════════════════════════════════

@security_bp.route('/approvals/list', methods=['GET'])
def list_approvals():
    """
    获取审批记录
    
    Query Params:
        session_id: 可选，按会话过滤
        approval_type: 可选，session 或 permanent
    """
    session_id = request.args.get('session_id')
    approval_type = request.args.get('approval_type')
    
    query = ApprovalRecord.query
    
    if session_id:
        query = query.filter_by(session_id=session_id)
    
    if approval_type:
        query = query.filter_by(approval_type=approval_type)
    
    records = query.order_by(ApprovalRecord.created_at.desc()).limit(100).all()
    
    return jsonify({
        'count': len(records),
        'records': [r.to_dict() for r in records]
    })


@security_bp.route('/approvals/revoke', methods=['POST'])
def revoke_approval():
    """
    撤销审批
    
    Request:
        {
            "record_id": int
        }
    """
    data = request.get_json()
    
    if not data or 'record_id' not in data:
        return jsonify({'error': 'record_id is required'}), 400
    
    record = ApprovalRecord.query.get(data['record_id'])
    if not record:
        return jsonify({'error': 'Record not found'}), 404
    
    record.status = 'revoked'
    db.session.commit()
    
    # 如果是会话级审批，从内存中清除
    if record.approval_type == 'session':
        # 这里需要从 approval_manager 中清除，但由于是内存状态，
        # 实际上需要重新初始化会话
        pass
    
    return jsonify({
        'success': True,
        'message': 'Approval revoked'
    })
