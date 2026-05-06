"""
数据库模型 - SQLite 嵌入式版（合并增强版）
支持 PyInstaller 打包，无需外部数据库
集成 FTS5 全文搜索、安全审计日志、审批记录、技能扫描

合并自 database.py + database_enhanced.py
"""
import os
import json
import uuid
from datetime import datetime, timezone, timedelta
from flask_sqlalchemy import SQLAlchemy

# UTC+8 时区
CST = timezone(timedelta(hours=8))

def now_cst():
    """获取东八区当前时间"""
    return datetime.now(CST)

db = SQLAlchemy()


# ═══════════════════════════════════════════════════════════
# 用户表
# ═══════════════════════════════════════════════════════════

class User(db.Model):
    """用户表"""
    __tablename__ = 'users'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    email = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='user')  # user / admin / super_admin
    is_active = db.Column(db.Boolean, default=True)
    is_superuser = db.Column(db.Boolean, default=False)
    avatar_url = db.Column(db.String(500), nullable=True)
    last_login = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=now_cst, index=True)
    updated_at = db.Column(db.DateTime, default=now_cst, onupdate=now_cst)
    
    # 关联关系
    sessions = db.relationship('Session', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    settings = db.relationship('UserSettings', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    # 索引
    __table_args__ = (
        db.Index('idx_users_username', 'username'),
        db.Index('idx_users_email', 'email'),
        db.Index('idx_users_role', 'role'),
        db.Index('idx_users_created', 'created_at'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'is_active': self.is_active,
            'is_superuser': self.is_superuser,
            'avatar_url': self.avatar_url,
            'last_login': self.last_login.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z') if self.last_login else None,
            'created_at': self.created_at.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z') if self.created_at else None,
            'updated_at': self.updated_at.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z') if self.updated_at else None,
        }
    
    def set_password(self, password):
        """设置密码（哈希）"""
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    
    def check_password(self, password):
        """验证密码"""
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)


# ═══════════════════════════════════════════════════════════
# 会话表（增强版：含 parent_session_id）
# ═══════════════════════════════════════════════════════════

class Session(db.Model):
    """会话表"""
    __tablename__ = 'sessions'
    
    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True, index=True)
    title = db.Column(db.String(255), default='新会话')
    provider = db.Column(db.String(50), default='bailian')  # bailian / minimax
    model = db.Column(db.String(100), default='gpt-4o')
    token_count = db.Column(db.Integer, default=0)
    message_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='active')  # active / archived / deleted
    parent_session_id = db.Column(db.String(36), db.ForeignKey('sessions.id'), nullable=True)  # ⭐ 增强：支持会话分支
    created_at = db.Column(db.DateTime, default=now_cst)
    updated_at = db.Column(db.DateTime, default=now_cst, onupdate=now_cst)
    
    # 关联关系 - 消息（手动删除，避免 cascade 与外键约束冲突）
    messages = db.relationship('Message', backref='session', lazy='dynamic')
    
    # ⭐ 复合索引
    __table_args__ = (
        db.Index('idx_sessions_user_status', 'user_id', 'status'),
        db.Index('idx_sessions_user_created', 'user_id', 'created_at'),
        db.Index('idx_sessions_created', 'created_at'),
    )
    
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
            'parent_session_id': self.parent_session_id,  # ⭐ 增强
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


# ═══════════════════════════════════════════════════════════
# 消息表（增强版：含 extra_data + metadata）
# ═══════════════════════════════════════════════════════════

class Message(db.Model):
    """消息表"""
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.String(36), db.ForeignKey('sessions.id'), nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True, index=True)
    role = db.Column(db.String(20), nullable=False)  # user / assistant / system / tool
    content = db.Column(db.Text, nullable=False)
    token_count = db.Column(db.Integer, default=0)
    tool_calls = db.Column(db.JSON, nullable=True)
    # 使用 db.JSON（SQLite 兼容）
    extra_data = db.Column('extra_data', db.JSON, nullable=True)
    meta_data = db.Column('meta_data', db.JSON, nullable=True)  # ⭐ 增强：通用元数据（避免与 SQLAlchemy 保留字 metadata 冲突）
    created_at = db.Column(db.DateTime, default=now_cst, index=True)
    
    # 复合索引
    __table_args__ = (
        db.Index('idx_messages_session_time', 'session_id', 'created_at'),
        db.Index('idx_messages_user_time', 'user_id', 'created_at'),
    )
    
    def to_dict(self):
        # ⭐ 从 extra_data 中提取 rag_status
        rag_status = None
        if self.extra_data and 'rag_status' in self.extra_data:
            rag_status = self.extra_data['rag_status']
        
        return {
            'id': self.id,
            'session_id': self.session_id,
            'role': self.role,
            'content': self.content,
            'token_count': self.token_count,
            'tool_calls': self.tool_calls,
            'extra_data': self.extra_data,
            'metadata': self.meta_data,  # ⭐ 增强（返回时保持 metadata 字段名兼容）
            'rag_status': rag_status,
            'created_at': self.created_at.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z') if self.created_at else None,
        }


# ═══════════════════════════════════════════════════════════
# 插件表
# ═══════════════════════════════════════════════════════════

class Plugin(db.Model):
    """插件表"""
    __tablename__ = 'plugins'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(500), default='')
    enabled = db.Column(db.Boolean, default=True)
    config = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=now_cst)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'enabled': self.enabled,
            'config': self.config,
            'created_at': self.created_at.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z') if self.created_at else None,
        }


# ═══════════════════════════════════════════════════════════
# 自我进化系统：记忆表
# ═══════════════════════════════════════════════════════════

class Memory(db.Model):
    """持久化记忆表"""
    __tablename__ = 'memories'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    target = db.Column(db.String(20), nullable=False)  # 'memory' or 'user'
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=now_cst, index=True)
    updated_at = db.Column(db.DateTime, default=now_cst, onupdate=now_cst)
    session_id = db.Column(db.String(36), db.ForeignKey('sessions.id'), nullable=True, index=True)
    is_active = db.Column(db.Boolean, default=True, index=True)
    
    # 关联（带 backref，支持 enhanced 的 memory_records 访问）
    session = db.relationship('Session', backref='memory_records')
    
    # ⭐ 索引
    __table_args__ = (
        db.Index('idx_memories_target_time', 'target', 'created_at'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'target': self.target,
            'content': self.content,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'session_id': self.session_id,
            'is_active': self.is_active,
        }


# ═══════════════════════════════════════════════════════════
# 自我进化系统：技能表
# ═══════════════════════════════════════════════════════════

class Skill(db.Model):
    """技能存储表"""
    __tablename__ = 'skills'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, default='')
    category = db.Column(db.String(50), default='general', index=True)
    content = db.Column(db.Text, nullable=False)  # SKILL.md 全文
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
# 用户设置表
# ═══════════════════════════════════════════════════════════

class UserSettings(db.Model):
    """用户个性化设置表"""
    __tablename__ = 'user_settings'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True, index=True)
    setting_key = db.Column(db.String(50), nullable=False, index=True)
    setting_value = db.Column(db.Text, nullable=False)
    updated_at = db.Column(db.DateTime, default=now_cst, onupdate=now_cst)
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'setting_key', name='uq_user_setting'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'setting_key': self.setting_key,
            'setting_value': self.setting_value,
            'updated_at': self.updated_at.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z') if self.updated_at else None,
        }


# ═══════════════════════════════════════════════════════════
# ⭐ 增强：安全审计日志表
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
# ⭐ 增强：审批记录表
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
# ⭐ 增强：技能扫描记录表
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


# ═══════════════════════════════════════════════════════════
# ⭐ 用户自定义 LLM 提供商
# ═══════════════════════════════════════════════════════════

class CustomProvider(db.Model):
    """用户自定义 LLM 提供商"""
    __tablename__ = 'custom_providers'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    protocol = db.Column(db.String(20), nullable=False, default='openai')
    # 'openai' → OpenAIProvider (AsyncOpenAI SDK)
    # 'anthropic' → ClaudeProvider (AsyncAnthropic SDK)
    
    base_url = db.Column(db.String(500), nullable=False)
    api_key = db.Column(db.String(500), nullable=False)
    default_model = db.Column(db.String(100), default='')
    is_active = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=now_cst)
    updated_at = db.Column(db.DateTime, default=now_cst, onupdate=now_cst)
    
    def to_dict(self):
        # API Key 脱敏显示
        masked_key = self._mask_api_key(self.api_key)
        return {
            'id': self.id,
            'name': self.name,
            'protocol': self.protocol,
            'base_url': self.base_url,
            'api_key': masked_key,
            'default_model': self.default_model,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
    
    def _mask_api_key(self, key: str) -> str:
        """API Key 脱敏：显示前4后4位"""
        if len(key) <= 8:
            return '****'
        return key[:4] + '***' + key[-4:]


# ═══════════════════════════════════════════════════════════
# 数据库初始化
# ═══════════════════════════════════════════════════════════

def init_db(app):
    """
    初始化数据库（SQLite 嵌入式 + FTS5 全文搜索）
    """
    from service.core.paths import get_data_dir
    DATA_DIR = get_data_dir()

    db_uri = os.getenv('DATABASE_URL', f'sqlite:///{DATA_DIR / "lawyerclaw.db"}')

    app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()
        _migrate_add_columns(app)
        _create_fts5_tables(app)  # ⭐ 增强：FTS5 全文搜索索引
        app.logger.info("✅ 数据库初始化完成（含 FTS5 全文搜索 + 安全审计）")


def _migrate_add_columns(app):
    """为已有数据库添加缺失列（幂等操作）"""
    migrations = [
        ("memories", "ALTER TABLE memories ADD COLUMN is_active BOOLEAN DEFAULT 1"),
        ("skills",   "ALTER TABLE skills ADD COLUMN is_active BOOLEAN DEFAULT 1"),
        ("sessions", "ALTER TABLE sessions ADD COLUMN parent_session_id VARCHAR(36)"),  # ⭐ 增强
        ("messages", "ALTER TABLE messages ADD COLUMN meta_data JSON"),  # ⭐ 增强
        ("custom_providers", "CREATE TABLE IF NOT EXISTS custom_providers (id INTEGER PRIMARY KEY AUTOINCREMENT, name VARCHAR(100) UNIQUE NOT NULL, protocol VARCHAR(20) NOT NULL DEFAULT 'openai', base_url VARCHAR(500) NOT NULL, api_key VARCHAR(500) NOT NULL, default_model VARCHAR(100) DEFAULT '', is_active BOOLEAN DEFAULT 0, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)"),  # ⭐ 自定义 Provider
    ]
    conn = db.engine.raw_connection()
    cursor = conn.cursor()
    try:
        for table, sql in migrations:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = {row[1] for row in cursor.fetchall()}
            col_name = sql.split("ADD COLUMN ")[1].split()[0]
            if col_name not in columns:
                cursor.execute(sql)
                app.logger.info(f"迁移：{table}.{col_name} 已添加")
        conn.commit()
    except Exception as e:
        conn.rollback()
        app.logger.warning(f"迁移失败（可忽略）：{e}")
    finally:
        cursor.close()
        conn.close()


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
            app.logger.info("✅ FTS5 全文搜索索引创建完成")
            
    except Exception as e:
        app.logger.warning(f"FTS5 索引创建失败：{e}")
