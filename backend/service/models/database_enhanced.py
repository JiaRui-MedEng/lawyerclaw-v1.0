"""
数据库模型增强
添加 FTS5 全文搜索支持、安全审计日志
"""
import os
import json
from datetime import datetime, timezone, timedelta
from flask_sqlalchemy import SQLAlchemy

# UTC+8 时区
CST = timezone(timedelta(hours=8))

def now_cst():
    """获取东八区当前时间"""
    return datetime.now(CST)

db = SQLAlchemy()


class Session(db.Model):
    """会话表"""
    __tablename__ = 'sessions'
    
    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), nullable=True, index=True)
    title = db.Column(db.String(255), default='新会话')
    provider = db.Column(db.String(50), default='bailian')
    model = db.Column(db.String(100), default='gpt-4o')
    token_count = db.Column(db.Integer, default=0)
    message_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='active')
    parent_session_id = db.Column(db.String(36), db.ForeignKey('sessions.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=now_cst)
    updated_at = db.Column(db.DateTime, default=now_cst, onupdate=now_cst)
    
    messages = db.relationship('Message', backref='session', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'provider': self.provider,
            'model': self.model,
            'token_count': self.token_count,
            'message_count': self.message_count,
            'status': self.status,
            'parent_session_id': self.parent_session_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class Message(db.Model):
    """消息表"""
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.String(36), db.ForeignKey('sessions.id'), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    token_count = db.Column(db.Integer, default=0)
    tool_calls = db.Column(db.JSON, nullable=True)
    meta_data = db.Column('metadata', db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=now_cst, index=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'role': self.role,
            'content': self.content,
            'token_count': self.token_count,
            'tool_calls': self.tool_calls,
            'metadata': self.meta_data,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Memory(db.Model):
    """持久化记忆表"""
    __tablename__ = 'memories'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    target = db.Column(db.String(20), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=now_cst)
    updated_at = db.Column(db.DateTime, default=now_cst, onupdate=now_cst)
    session_id = db.Column(db.String(36), db.ForeignKey('sessions.id'), nullable=True, index=True)
    is_active = db.Column(db.Boolean, default=True, index=True)
    
    session = db.relationship('Session', backref='memory_records')
    
    def to_dict(self):
        return {
            'id': self.id,
            'target': self.target,
            'content': self.content,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'session_id': self.session_id,
            'is_active': self.is_active,
        }


class Skill(db.Model):
    """技能存储表"""
    __tablename__ = 'skills'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, default='')
    category = db.Column(db.String(50), default='general', index=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=now_cst)
    updated_at = db.Column(db.DateTime, default=now_cst, onupdate=now_cst)
    is_active = db.Column(db.Boolean, default=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'category': self.category,
            'content': self.content,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'is_active': self.is_active,
        }


# ═══════════════════════════════════════════════════════════
# 新增：安全审计日志表
# ═══════════════════════════════════════════════════════════

class SecurityAuditLog(db.Model):
    """安全审计日志表"""
    __tablename__ = 'security_audit_logs'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.String(36), db.ForeignKey('sessions.id'), nullable=True, index=True)
    user_id = db.Column(db.String(36), nullable=True, index=True)
    
    # 审计类型
    audit_type = db.Column(db.String(50), nullable=False, index=True)
    # command_approval, skill_scan, memory_scan, tool_execution
    
    # 审计内容
    action = db.Column(db.String(100), nullable=False)
    target = db.Column(db.String(255), nullable=True)
    result = db.Column(db.String(20), nullable=False)
    # approved, blocked, caution, allowed
    
    # 详细信息
    details = db.Column(db.JSON, nullable=True)
    # {pattern_key, severity, findings, etc.}
    
    # 时间戳
    created_at = db.Column(db.DateTime, default=now_cst, index=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'user_id': self.user_id,
            'audit_type': self.audit_type,
            'action': self.action,
            'target': self.target,
            'result': self.result,
            'details': self.details,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# ═══════════════════════════════════════════════════════════
# 新增：审批记录表
# ═══════════════════════════════════════════════════════════

class ApprovalRecord(db.Model):
    """审批记录表"""
    __tablename__ = 'approval_records'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.String(36), db.ForeignKey('sessions.id'), nullable=False, index=True)
    user_id = db.Column(db.String(36), nullable=True)
    
    # 审批类型
    approval_type = db.Column(db.String(20), nullable=False)
    # session, permanent
    
    # 审批内容
    pattern_key = db.Column(db.String(255), nullable=False)
    command = db.Column(db.Text, nullable=True)
    
    # 审批状态
    status = db.Column(db.String(20), nullable=False)
    # approved, revoked
    
    # 时间戳
    created_at = db.Column(db.DateTime, default=now_cst)
    expires_at = db.Column(db.DateTime, nullable=True)
    # session 类型在会话结束时过期，permanent 类型为 NULL
    
    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'user_id': self.user_id,
            'approval_type': self.approval_type,
            'pattern_key': self.pattern_key,
            'command': self.command,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
        }


# ═══════════════════════════════════════════════════════════
# 新增：技能扫描记录表
# ═══════════════════════════════════════════════════════════

class SkillScanRecord(db.Model):
    """技能扫描记录表"""
    __tablename__ = 'skill_scan_records'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    skill_id = db.Column(db.Integer, db.ForeignKey('skills.id'), nullable=False, index=True)
    skill_name = db.Column(db.String(100), nullable=False, index=True)
    
    # 扫描来源
    source = db.Column(db.String(50), nullable=False)
    # builtin, trusted, community, internal, legal
    
    # 扫描结果
    verdict = db.Column(db.String(20), nullable=False)
    # safe, caution, dangerous
    
    findings_count = db.Column(db.Integer, default=0)
    findings_summary = db.Column(db.JSON, nullable=True)
    # [{pattern_id, severity, category, file, line}, ...]
    
    # 扫描时间
    scanned_at = db.Column(db.DateTime, default=now_cst)
    
    def to_dict(self):
        return {
            'id': self.id,
            'skill_id': self.skill_id,
            'skill_name': self.skill_name,
            'source': self.source,
            'verdict': self.verdict,
            'findings_count': self.findings_count,
            'findings_summary': self.findings_summary,
            'scanned_at': self.scanned_at.isoformat() if self.scanned_at else None,
        }


def init_db(app):
    """初始化数据库"""
    if not app.config.get('SQLALCHEMY_DATABASE_URI'):
        from service.core.paths import get_data_dir
        base_dir = str(get_data_dir())
        db_path = os.path.join(base_dir, 'lawyerclaw.db')
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    
    with app.app_context():
        db.create_all()
        
        # 创建 FTS5 虚拟表（SQLite 特定）
        _create_fts5_tables(app)


def _create_fts5_tables(app):
    """创建 FTS5 全文搜索索引"""
    if 'sqlite' not in app.config.get('SQLALCHEMY_DATABASE_URI', ''):
        return  # 仅 SQLite 支持 FTS5
    
    try:
        with app.app_context():
            conn = db.engine.raw_connection()
            cursor = conn.cursor()
            
            # 创建 messages 的 FTS5 索引
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                    content,
                    content=messages,
                    content_rowid=id
                )
            """)
            
            # 创建触发器（自动同步）
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS messages_fts_insert 
                AFTER INSERT ON messages 
                BEGIN
                    INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
                END
            """)
            
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS messages_fts_delete 
                AFTER DELETE ON messages 
                BEGIN
                    INSERT INTO messages_fts(messages_fts, rowid, content) 
                    VALUES('delete', old.id, old.content);
                END
            """)
            
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS messages_fts_update 
                AFTER UPDATE ON messages 
                BEGIN
                    INSERT INTO messages_fts(messages_fts, rowid, content) 
                    VALUES('delete', old.id, old.content);
                    INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
                END
            """)
            
            # 创建 memories 的 FTS5 索引
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                    content,
                    content=memories,
                    content_rowid=id
                )
            """)
            
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS memories_fts_insert 
                AFTER INSERT ON memories 
                BEGIN
                    INSERT INTO memories_fts(rowid, content) VALUES (new.id, new.content);
                END
            """)
            
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS memories_fts_delete 
                AFTER DELETE ON memories 
                BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, content) 
                    VALUES('delete', old.id, old.content);
                END
            """)
            
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS memories_fts_update 
                AFTER UPDATE ON memories 
                BEGIN
                    INSERT INTO memories_fts(memories_fts, rowid, content) 
                    VALUES('delete', old.id, old.content);
                    INSERT INTO memories_fts(rowid, content) VALUES (new.id, new.content);
                END
            """)
            
            conn.commit()
            cursor.close()
            conn.close()
            
    except Exception as e:
        print(f"FTS5 索引创建失败：{e}")
