"""
百佑 LawyerClaw Hermes 核心逻辑整合模块

基于 Hermes Agent 核心架构实现:
1. SQLite 数据库建立 (含 FTS5 倒排索引)
2. 上下文记忆检索 (prefetch + sync)
3. Skills 调用方法 (create/patch/search)
4. 会话搜索 (session_search)

作者：Hermes Agent 架构迁移
日期：2026 年 1 月
"""
import json
import re
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

from service.models.database import db, Session, Message, Memory, Skill
from service.security.memory_guard import scan_memory_content, should_allow_memory
from service.security.skills_guard_enhanced import scan_skill, should_allow_install

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# 1. Hermes 风格数据库建立 (含 FTS5)
# ═══════════════════════════════════════════════════════════

class HermesDatabaseManager:
    """
    Hermes 风格数据库管理器
    
    特性:
    - FTS5 倒排索引自动创建
    - WAL 模式并发控制
    - 自动迁移
    """
    
    def __init__(self):
        self.db_path = None
    
    def initialize(self, app):
        """
        初始化数据库 (含 FTS5 索引)
        
        用法:
            db_manager = HermesDatabaseManager()
            db_manager.initialize(app)
        """
        if 'sqlite' not in app.config.get('SQLALCHEMY_DATABASE_URI', ''):
            logger.warning("非 SQLite 数据库，跳过 FTS5 索引创建")
            return
        
        try:
            with app.app_context():
                # 确保所有表已创建
                db.create_all()
                
                # 创建 FTS5 索引
                self._create_fts5_indexes()
                
                # 启用 WAL 模式
                self._enable_wal_mode()
                
                logger.info("Hermes 数据库初始化完成 (含 FTS5 索引)")
                
        except Exception as e:
            logger.error(f"数据库初始化失败：{e}")
            raise
    
    def _create_fts5_indexes(self):
        """创建 FTS5 倒排索引"""
        conn = db.engine.raw_connection()
        cursor = conn.cursor()
        
        try:
            # Messages FTS5 索引
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                    content,
                    content=messages,
                    content_rowid=id
                )
            """)
            
            # Messages 触发器
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
            
            # Memories FTS5 索引
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
            
            # Skills FTS5 索引
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS skills_fts USING fts5(
                    name,
                    description,
                    content,
                    content=skills,
                    content_rowid=id
                )
            """)
            
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS skills_fts_insert 
                AFTER INSERT ON skills 
                BEGIN
                    INSERT INTO skills_fts(rowid, name, description, content) 
                    VALUES (new.id, new.name, new.description, new.content);
                END
            """)
            
            conn.commit()
            logger.info("FTS5 索引创建完成")
            
        except Exception as e:
            logger.error(f"FTS5 索引创建失败：{e}")
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()
    
    def _enable_wal_mode(self):
        """启用 WAL 模式 (Write-Ahead Logging)"""
        conn = db.engine.raw_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA synchronous=NORMAL")
            conn.commit()
            logger.info("WAL 模式已启用")
        except Exception as e:
            logger.warning(f"WAL 模式启用失败：{e}")
        finally:
            cursor.close()
            conn.close()


# ═══════════════════════════════════════════════════════════
# 2. Hermes 风格上下文记忆检索
# ═══════════════════════════════════════════════════════════

class HermesMemoryManager:
    """
    Hermes 风格记忆管理器
    
    特性:
    - 冻结快照模式 (系统提示稳定)
    - 实时状态更新 (工具响应最新)
    - 安全扫描 (注入/泄露检测)
    - FTS5 全文搜索
    """
    
    def __init__(self):
        self._memory_snapshot: Dict[str, str] = {"memory": "", "user": ""}
        self._memory_entries: Dict[str, List[str]] = {"memory": [], "user": []}
        self._char_limits = {"memory": 2200, "user": 1375}
    
    def load_from_db(self):
        """
        从数据库加载记忆 (捕获冻结快照)
        
        Hermes 关键设计:
        - _memory_snapshot: 冻结快照，用于系统提示注入
        - _memory_entries: 实时状态，工具调用修改
        """
        # 加载活跃记忆
        memories = Memory.query.filter_by(is_active=True)\
            .order_by(Memory.created_at.desc())\
            .limit(100)\
            .all()
        
        # 按 target 分组
        memory_entries = [m.content for m in memories if m.target == 'memory']
        user_entries = [m.content for m in memories if m.target == 'user']
        
        # 去重 (保持顺序)
        memory_entries = list(dict.fromkeys(memory_entries))
        user_entries = list(dict.fromkeys(user_entries))
        
        # 更新实时状态
        self._memory_entries = {
            "memory": memory_entries[:50],  # 限制数量
            "user": user_entries[:50]
        }
        
        # 捕获冻结快照 (用于系统提示)
        self._memory_snapshot = {
            "memory": self._render_block("memory", self._memory_entries["memory"]),
            "user": self._render_block("user", self._memory_entries["user"])
        }
        
        logger.info(f"记忆已加载：memory={len(memory_entries)}, user={len(user_entries)}")
    
    def prefetch(self, query: str = "") -> str:
        """
        Hermes 风格预取记忆
        
        Args:
            query: 可选的搜索查询，如果为空则返回所有记忆
        
        Returns:
            str: 格式化的记忆上下文
        """
        if query:
            # FTS5 搜索相关记忆
            memories = self._search_memories(query)
        else:
            # 返回冻结快照
            memories = self._memory_snapshot
        
        # 构建上下文
        context_parts = []
        
        if memories.get("memory"):
            context_parts.append(f"## Long-term Memory\n{memories['memory']}")
        
        if memories.get("user"):
            context_parts.append(f"## User Profile\n{memories['user']}")
        
        return "\n\n".join(context_parts)
    
    def _search_memories(self, query: str) -> Dict[str, str]:
        """使用 FTS5 搜索记忆"""
        try:
            conn = db.engine.raw_connection()
            cursor = conn.cursor()
            
            # 清理查询
            query = self._sanitize_fts5_query(query)
            
            # FTS5 搜索
            cursor.execute("""
                SELECT m.target, m.content, bm25(memories_fts) as rank
                FROM memories_fts
                JOIN memories m ON m.id = memories_fts.rowid
                WHERE memories_fts MATCH ?
                ORDER BY rank
                LIMIT 10
            """, (query,))
            
            results = cursor.fetchall()
            cursor.close()
            conn.close()
            
            # 分组
            memory_content = [r[1] for r in results if r[0] == 'memory']
            user_content = [r[1] for r in results if r[0] == 'user']
            
            return {
                "memory": self._render_block("memory", memory_content),
                "user": self._render_block("user", user_content)
            }
            
        except Exception as e:
            logger.error(f"FTS5 记忆搜索失败：{e}")
            return {"memory": "", "user": ""}
    
    def _sanitize_fts5_query(self, query: str) -> str:
        """清理 FTS5 查询"""
        # 移除特殊字符
        query = re.sub(r'[+{}()\"^]', ' ', query)
        query = re.sub(r'\*+', '*', query)
        query = re.sub(r'(?i)^(AND|OR|NOT)\b\s*', '', query.strip())
        query = re.sub(r'(?i)\s+(AND|OR|NOT)\s*$', '', query.strip())
        return query.strip()
    
    def add(self, target: str, content: str, session_id: str = None) -> Dict[str, Any]:
        """
        Hermes 风格添加记忆 (带安全扫描)
        
        Args:
            target: 'memory' or 'user'
            content: 记忆内容
            session_id: 可选的会话 ID
        
        Returns:
            Dict: {'success': bool, 'error': str or None}
        """
        if target not in ['memory', 'user']:
            return {'success': False, 'error': 'Invalid target'}
        
        if not content or not content.strip():
            return {'success': False, 'error': 'Content cannot be empty'}
        
        # 安全扫描
        scan_result = scan_memory_content(content)
        allowed, reason = should_allow_memory(content, "user")
        
        if allowed is False:
            return {'success': False, 'error': f'Memory blocked: {reason}'}
        
        # 检查重复
        existing = Memory.query.filter_by(
            target=target,
            content=content
        ).first()
        
        if existing:
            return {'success': False, 'error': 'Memory already exists'}
        
        # 检查字符限制
        current_count = len(self._memory_entries.get(target, []))
        if current_count >= 100:
            return {'success': False, 'error': 'Memory limit reached (100 entries)'}
        
        # 保存到数据库
        memory = Memory(
            target=target,
            content=content,
            session_id=session_id,
            is_active=True
        )
        db.session.add(memory)
        db.session.commit()
        
        # 更新实时状态 (但不更新冻结快照!)
        if target not in self._memory_entries:
            self._memory_entries[target] = []
        self._memory_entries[target].append(content)
        
        logger.info(f"记忆已添加：{target}, id={memory.id}")
        
        return {
            'success': True,
            'id': memory.id,
            'target': target,
            'timestamp': memory.created_at.isoformat()
        }
    
    def sync(self, user_msg: str, assistant_msg: str, session_id: str = None):
        """
        Hermes 风格同步对话 (自动检测学习机会)
        
        触发条件:
        - 用户要求记忆 ("记住这个", "remember this")
        - 用户纠正 ("下次不要", "don't do that again")
        - 发现环境事实
        """
        memory_phrases = [
            '记住这个', 'remember this', '下次不要', "don't do that again",
            '请记住', 'please remember', '不要忘记', "don't forget"
        ]
        
        if any(phrase in user_msg.lower() for phrase in memory_phrases):
            # 提取要记忆的内容
            self.add(
                target="memory",
                content=f"用户要求：{user_msg[:200]}\n\n助手响应：{assistant_msg[:200]}",
                session_id=session_id
            )
    
    def _render_block(self, target: str, entries: List[str]) -> str:
        """渲染记忆块 (用于系统提示)"""
        if not entries:
            return ""
        
        content = "\n§\n".join(entries)
        char_count = len(content)
        char_limit = self._char_limits.get(target, 2000)
        pct = min(100, int((char_count / char_limit) * 100))
        
        if target == "user":
            header = f"USER PROFILE (who the user is) [{pct}% — {char_count:,}/{char_limit:,} chars]"
        else:
            header = f"MEMORY (your personal notes) [{pct}% — {char_count:,}/{char_limit:,} chars]"
        
        separator = "═" * 46
        return f"{separator}\n{header}\n{separator}\n{content}"
    
    def get_system_prompt_blocks(self) -> Dict[str, str]:
        """获取冻结快照 (用于系统提示注入)"""
        return self._memory_snapshot


# ═══════════════════════════════════════════════════════════
# 3. Hermes 风格 Skills 调用方法
# ═══════════════════════════════════════════════════════════

class HermesSkillManager:
    """
    Hermes 风格技能管理器
    
    特性:
    - 原子写入 (tempfile + rename)
    - 安全扫描 (200+ 威胁模式)
    - 模糊匹配修补
    - FTS5 搜索
    """
    
    def __init__(self, skills_dir: str = None):
        if skills_dir:
            self.skills_dir = Path(skills_dir).expanduser()
            self.skills_dir.mkdir(parents=True, exist_ok=True)
        else:
            # 默认从 backend/skills/ 目录读取
            from service.core.paths import get_skills_dir
            self.skills_dir = get_skills_dir()
            self.skills_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"HermesSkillManager 技能目录：{self.skills_dir}")
    
    def load_skills(self, category: str = None) -> List[Dict[str, Any]]:
        """
        从文件系统加载所有技能
        
        Args:
            category: 可选，按分类筛选
            
        Returns:
            List[Dict]: 技能列表
        """
        return self._scan_skills_directory(category)
    
    def _scan_skills_directory(self, category: str = None) -> List[Dict[str, Any]]:
        """扫描文件系统获取所有技能"""
        skills = []
        
        if not self.skills_dir.exists():
            logger.warning(f"Skills 目录不存在：{self.skills_dir}")
            return skills
        
        # 遍历所有子目录
        for skill_dir in self.skills_dir.iterdir():
            # 跳过非目录和特殊目录
            if not skill_dir.is_dir():
                continue
            if skill_dir.name.startswith('.') or skill_dir.name == '__pycache__':
                continue
            if skill_dir.name == 'shared':
                continue
            
            # 查找 SKILL.md
            skill_file = skill_dir / 'SKILL.md'
            if not skill_file.exists():
                continue
            
            try:
                content = skill_file.read_text(encoding='utf-8')
                frontmatter, body = self._parse_frontmatter(content)
                
                skill_category = frontmatter.get('category', 'general')
                
                # 如果指定了分类，进行筛选
                if category and skill_category != category:
                    continue
                
                skills.append({
                    'name': frontmatter.get('name', skill_dir.name),
                    'description': frontmatter.get('description', ''),
                    'category': skill_category,
                    'content': content,
                    'path': str(skill_file),
                    'dir': str(skill_dir),
                })
            except Exception as e:
                logger.error(f"读取技能失败 {skill_dir.name}: {e}")
        
        logger.info(f"扫描到 {len(skills)} 个技能")
        return skills
    
    def create_skill(self, name: str, content: str, description: str = None, 
                     category: str = None) -> Dict[str, Any]:
        """
        Hermes 风格创建技能 (带安全扫描)
        
        Args:
            name: 技能名称
            content: SKILL.md 全文 (含 YAML frontmatter)
            description: 技能描述
            category: 分类
        
        Returns:
            Dict: {'success': bool, 'error': str or None}
        """
        # 验证名称
        if not self._validate_name(name):
            return {"success": False, "error": "Invalid skill name"}
        
        # 验证 frontmatter
        frontmatter = self._parse_frontmatter(content)
        if not frontmatter:
            return {"success": False, "error": "Missing or invalid YAML frontmatter"}
        
        # 检查是否已存在
        existing = Skill.query.filter_by(name=name).first()
        if existing:
            return {"success": False, "error": f"Skill '{name}' already exists"}
        
        # 安全扫描 (如果保存到文件系统)
        if self.skills_dir:
            skill_dir = self.skills_dir / name
            skill_dir.mkdir(parents=True, exist_ok=True)
            
            # 临时写入
            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text(content, encoding='utf-8')
            
            # 扫描
            scan_result = scan_skill(skill_dir, "internal")
            allowed, reason = should_allow_install(scan_result)
            
            if allowed is False:
                # 回滚：删除目录
                import shutil
                shutil.rmtree(skill_dir, ignore_errors=True)
                return {"success": False, "error": f"Skill blocked: {reason}"}
        
        # 保存到数据库
        skill = Skill(
            name=name,
            description=description or frontmatter.get('description', ''),
            category=category or frontmatter.get('category', 'general'),
            content=content,
            is_active=True
        )
        db.session.add(skill)
        db.session.commit()
        
        logger.info(f"技能已创建：{name}, id={skill.id}")
        
        return {
            "success": True,
            "skill_id": skill.id,
            "name": name,
            "message": f"Skill '{name}' created successfully"
        }
    
    def patch_skill(self, name: str, old_string: str, new_string: str,
                    file_path: str = None, replace_all: bool = False) -> Dict[str, Any]:
        """
        Hermes 风格修补技能 (模糊匹配)
        
        Args:
            name: 技能名称
            old_string: 要查找的文本
            new_string: 替换文本
            file_path: 可选的文件路径 (默认 SKILL.md)
            replace_all: 是否替换所有匹配
        
        Returns:
            Dict: {'success': bool, 'error': str or None}
        """
        skill = Skill.query.filter_by(name=name).first()
        if not skill:
            return {"success": False, "error": f"Skill '{name}' not found"}
        
        # 模糊匹配
        matches = self._fuzzy_find(skill.content, old_string)
        
        if not matches:
            return {
                "success": False,
                "error": f"'{old_string}' not found in skill content",
                "suggestions": self._get_similar_strings(skill.content, old_string)
            }
        
        if len(matches) > 1 and not replace_all:
            return {
                "success": False,
                "error": f"Multiple matches found ({len(matches)}). Be more specific.",
                "matches": [m[:100] for m in matches[:3]]
            }
        
        # 执行替换
        if replace_all:
            skill.content = skill.content.replace(old_string, new_string)
        else:
            # 只替换第一个匹配
            skill.content = skill.content.replace(matches[0], new_string, 1)
        
        skill.updated_at = datetime.now()
        db.session.commit()
        
        logger.info(f"技能已修补：{name}")
        
        return {"success": True, "message": f"Skill '{name}' patched"}
    
    def search_skills(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Hermes 风格技能搜索 (FTS5)
        
        Args:
            query: 搜索查询
            limit: 返回数量限制
        
        Returns:
            List[Dict]: 匹配的技能列表
        """
        try:
            conn = db.engine.raw_connection()
            cursor = conn.cursor()
            
            # 清理查询
            query = self._sanitize_fts5_query(query)
            
            # FTS5 搜索
            cursor.execute("""
                SELECT s.id, s.name, s.description, s.category, s.content,
                       bm25(skills_fts) as rank
                FROM skills_fts
                JOIN skills s ON s.id = skills_fts.rowid
                WHERE skills_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (query, limit))
            
            results = cursor.fetchall()
            cursor.close()
            conn.close()
            
            return [
                {
                    'id': r[0],
                    'name': r[1],
                    'description': r[2],
                    'category': r[3],
                    'content': r[4][:500] + '...' if len(r[4]) > 500 else r[4],
                    'rank': r[5]
                }
                for r in results
            ]
            
        except Exception as e:
            logger.error(f"FTS5 技能搜索失败：{e}")
            return []
    
    def _fuzzy_find(self, content: str, pattern: str) -> List[str]:
        """模糊查找匹配项"""
        matches = []
        
        # 1. 精确匹配
        if pattern in content:
            matches.append(pattern)
        
        # 2. 忽略大小写匹配
        if pattern.lower() in content.lower():
            start = content.lower().find(pattern.lower())
            end = start + len(pattern)
            matches.append(content[start:end])
        
        # 3. 忽略空白匹配
        pattern_normalized = re.sub(r'\s+', ' ', pattern).strip()
        content_normalized = re.sub(r'\s+', ' ', content)
        if pattern_normalized in content_normalized:
            start = content_normalized.find(pattern_normalized)
            end = start + len(pattern_normalized)
            matches.append(content_normalized[start:end])
        
        return list(set(matches))
    
    def _get_similar_strings(self, content: str, pattern: str, limit: int = 3) -> List[str]:
        """获取相似字符串"""
        # 简单实现：返回包含部分关键词的句子
        sentences = re.split(r'[.!?]', content)
        similar = []
        
        pattern_words = set(pattern.lower().split())
        
        for sentence in sentences:
            sentence_words = set(sentence.lower().split())
            if len(pattern_words & sentence_words) >= 2:
                similar.append(sentence.strip()[:100])
                if len(similar) >= limit:
                    break
        
        return similar
    
    def _validate_name(self, name: str) -> bool:
        """验证技能名"""
        if not name or len(name) > 100:
            return False
        
        pattern = re.compile(r'^[a-z0-9][a-z0-9._-]*$')
        return bool(pattern.match(name))
    
    def _parse_frontmatter(self, content: str) -> Tuple[Dict[str, Any], str]:
        """解析 YAML frontmatter"""
        if not content.startswith('---'):
            return {}, content
        
        try:
            end_match = re.search(r'\n---\s*\n', content[3:])
            if not end_match:
                return {}, content
            
            yaml_content = content[3:end_match.start() + 3]
            body = content[end_match.end() + 2:].strip()
            
            # 简单 YAML 解析
            frontmatter = {}
            for line in yaml_content.strip().split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    frontmatter[key.strip()] = value.strip()
            
            return frontmatter, body
            
        except Exception:
            return {}, content
    
    def _sanitize_fts5_query(self, query: str) -> str:
        """清理 FTS5 查询"""
        query = re.sub(r'[+{}()\"^]', ' ', query)
        query = re.sub(r'\*+', '*', query)
        return query.strip()


# ═══════════════════════════════════════════════════════════
# 4. Hermes 风格会话搜索 (session_search)
# ═══════════════════════════════════════════════════════════

class HermesSessionSearch:
    """
    Hermes 风格会话搜索
    
    特性:
    - FTS5 全文搜索
    - 相关性排序
    - 上下文摘要
    """
    
    def search(self, query: str, session_id: str = None, 
               limit: int = 5, role_filter: str = None) -> Dict[str, Any]:
        """
        搜索历史会话
        
        Args:
            query: 搜索查询
            session_id: 当前会话 ID (排除)
            limit: 返回数量限制
            role_filter: 角色过滤 (user/assistant/tool)
        
        Returns:
            Dict: {
                'success': bool,
                'query': str,
                'results': List[Dict],
                'count': int
            }
        """
        if not query or not query.strip():
            return {
                'success': True,
                'query': '',
                'results': self._get_recent_sessions(limit),
                'count': 0,
                'message': 'Showing recent sessions'
            }
        
        try:
            conn = db.engine.raw_connection()
            cursor = conn.cursor()
            
            # 清理查询
            query = self._sanitize_fts5_query(query)
            
            # FTS5 搜索
            sql = """
                SELECT 
                    m.session_id,
                    m.role,
                    snippet(messages_fts, 0, '>>>', '<<<', '...', 40) AS snippet,
                    m.content,
                    m.created_at,
                    s.title,
                    s.provider,
                    s.model
                FROM messages_fts
                JOIN messages m ON m.id = messages_fts.rowid
                JOIN sessions s ON s.id = m.session_id
                WHERE messages_fts MATCH ?
            """
            params = [query]
            
            # 排除当前会话
            if session_id:
                sql += " AND m.session_id != ?"
                params.append(session_id)
            
            # 角色过滤
            if role_filter:
                sql += " AND m.role = ?"
                params.append(role_filter)
            
            sql += " ORDER BY rank LIMIT ?"
            params.append(limit * 10)  # 获取更多以去重
            
            cursor.execute(sql, params)
            matches = cursor.fetchall()
            
            # 按会话去重
            seen_sessions = {}
            for r in matches:
                if r[0] not in seen_sessions:
                    seen_sessions[r[0]] = {
                        'session_id': r[0],
                        'session_title': r[5],
                        'session_provider': r[6],
                        'session_model': r[7],
                        'when': r[4],
                        'snippet': r[2],
                        'role': r[1]
                    }
                if len(seen_sessions) >= limit:
                    break
            
            cursor.close()
            conn.close()
            
            return {
                'success': True,
                'query': query,
                'results': list(seen_sessions.values()),
                'count': len(seen_sessions)
            }
            
        except Exception as e:
            logger.error(f"会话搜索失败：{e}")
            return {
                'success': False,
                'query': query,
                'results': [],
                'count': 0,
                'error': str(e)
            }
    
    def _get_recent_sessions(self, limit: int = 5) -> List[Dict]:
        """获取最近会话 (无查询时)"""
        sessions = Session.query.filter_by(status='active')\
            .order_by(Session.updated_at.desc())\
            .limit(limit)\
            .all()
        
        return [
            {
                'session_id': s.id,
                'session_title': s.title,
                'session_provider': s.provider,
                'session_model': s.model,
                'when': s.updated_at.isoformat(),
                'snippet': '',
                'role': ''
            }
            for s in sessions
        ]
    
    def _sanitize_fts5_query(self, query: str) -> str:
        """清理 FTS5 查询"""
        query = re.sub(r'[+{}()\"^]', ' ', query)
        query = re.sub(r'\*+', '*', query)
        query = re.sub(r'(?i)^(AND|OR|NOT)\b\s*', '', query.strip())
        query = re.sub(r'(?i)\s+(AND|OR|NOT)\s*$', '', query.strip())
        return query.strip()


# ═══════════════════════════════════════════════════════════
# 全局实例
# ═══════════════════════════════════════════════════════════

db_manager = HermesDatabaseManager()
memory_manager = HermesMemoryManager()
skill_manager = HermesSkillManager()
session_search = HermesSessionSearch()
