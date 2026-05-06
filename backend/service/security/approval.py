"""
百佑 LawyerClaw 命令审批模块
基于 Hermes approval.py 简化版

功能:
- 50+ 危险命令模式检测
- 会话级审批状态管理
- 永久允许列表
"""
import re
import logging
from typing import Tuple, Optional, Set, Dict

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
# 危险命令模式 (50+ 模式)
# ═══════════════════════════════════════════════════════════

DANGEROUS_PATTERNS = [
    # ── 文件删除类 ──
    (r'\brm\s+(-[^\s]*\s+)*/', "delete in root path"),
    (r'\brm\s+-[^\s]*r', "recursive delete"),
    (r'\brm\s+--recursive\b', "recursive delete (long flag)"),
    (r'\bxargs\s+.*\brm\b', "xargs with rm"),
    (r'\bfind\b.*-exec\s+(/\S*/)?rm\b', "find -exec rm"),
    (r'\bfind\b.*-delete\b', "find -delete"),
    
    # ── 权限修改类 ──
    (r'\bchmod\s+(-[^\s]*\s+)*(777|666|o\+[rwx]*w|a\+[rwx]*w)\b', "world/other-writable permissions"),
    (r'\bchmod\s+--recursive\b.*(777|666|o\+[rwx]*w)', "recursive world/other-writable"),
    (r'\bchown\s+(-[^\s]*)?R\s+root', "recursive chown to root"),
    
    # ── 系统破坏类 ──
    (r'\bmkfs\b', "format filesystem"),
    (r'\bdd\s+.*if=', "disk copy"),
    (r'>\s*/dev/sd', "write to block device"),
    (r'>\s*/etc/', "overwrite system config"),
    (r'\bsystemctl\s+(stop|disable|mask)\b', "stop/disable system service"),
    (r'\bkill\s+-9\s+-1\b', "kill all processes"),
    (r'\bpkill\s+-9\b', "force kill processes"),
    
    # ── 数据库破坏类 ──
    (r'\bDROP\s+(TABLE|DATABASE)\b', "SQL DROP"),
    (r'\bDELETE\s+FROM\b(?!.*\bWHERE\b)', "SQL DELETE without WHERE"),
    (r'\bTRUNCATE\s+(TABLE)?\s*\w', "SQL TRUNCATE"),
    
    # ── 远程代码执行类 ──
    (r'\b(bash|sh|zsh|ksh)\s+-[^\s]*c(\s+|$)', "shell command via -c/-lc flag"),
    (r'\b(python[23]?|perl|ruby|node)\s+-[ec]\s+', "script execution via -e/-c flag"),
    (r'\b(curl|wget)\b.*\|\s*(ba)?sh\b', "pipe remote content to shell"),
    (r'\b(python[23]?|perl|ruby|node)\s+<<', "script execution via heredoc"),
    
    # ── Git 破坏类 ──
    (r'\bgit\s+reset\s+--hard\b', "git reset --hard (destroys uncommitted changes)"),
    (r'\bgit\s+push\b.*--force\b', "git force push (rewrites remote history)"),
    (r'\bgit\s+push\b.*-f\b', "git force push short flag"),
    (r'\bgit\s+clean\s+-[^\s]*f', "git clean with force (deletes untracked files)"),
    (r'\bgit\s+branch\s+-D\b', "git branch force delete"),
]


def _normalize_command_for_detection(command: str) -> str:
    """
    标准化命令字符串（去除 ANSI 转义序列、Unicode 规范化）
    """
    import unicodedata
    
    # 去除 ANSI 转义序列
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    command = ansi_escape.sub('', command)
    
    # 去除 null 字节
    command = command.replace('\x00', '')
    
    # Unicode 规范化
    command = unicodedata.normalize('NFKC', command)
    
    return command


def detect_dangerous_command(command: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    检测危险命令
    
    Args:
        command: 要检测的命令字符串
        
    Returns:
        (is_dangerous, pattern_key, description)
        - is_dangerous: 是否为危险命令
        - pattern_key: 匹配的模式标识
        - description: 危险描述
    """
    command_lower = _normalize_command_for_detection(command).lower()
    
    for pattern, description in DANGEROUS_PATTERNS:
        if re.search(pattern, command_lower, re.IGNORECASE | re.DOTALL):
            return (True, description, description)
    
    return (False, None, None)


class ApprovalManager:
    """
    审批管理器
    
    管理:
    - 会话级审批状态
    - 永久允许列表
    """
    
    def __init__(self):
        self._session_approved: Dict[str, Set[str]] = {}
        self._permanent_approved: Set[str] = set()
        self._lock = __import__('threading').Lock()
    
    def is_approved(self, session_id: str, pattern_key: str) -> bool:
        """
        检查命令是否已审批
        
        Args:
            session_id: 会话 ID
            pattern_key: 危险模式标识
            
        Returns:
            bool: 是否已审批
        """
        with self._lock:
            # 检查永久允许
            if pattern_key in self._permanent_approved:
                return True
            
            # 检查会话级审批
            if session_id in self._session_approved:
                if pattern_key in self._session_approved[session_id]:
                    return True
            
            return False
    
    def approve_session(self, session_id: str, pattern_key: str):
        """
        会话级审批（仅当前会话有效）
        
        Args:
            session_id: 会话 ID
            pattern_key: 危险模式标识
        """
        with self._lock:
            if session_id not in self._session_approved:
                self._session_approved[session_id] = set()
            self._session_approved[session_id].add(pattern_key)
            
            logger.info(f"会话级审批：{session_id} - {pattern_key}")
    
    def approve_permanent(self, pattern_key: str):
        """
        永久审批（所有会话有效）
        
        Args:
            pattern_key: 危险模式标识
        """
        with self._lock:
            self._permanent_approved.add(pattern_key)
            logger.info(f"永久审批：{pattern_key}")
    
    def clear_session(self, session_id: str):
        """
        清除会话审批状态
        
        Args:
            session_id: 会话 ID
        """
        with self._lock:
            if session_id in self._session_approved:
                del self._session_approved[session_id]
    
    def get_permanent_approved(self) -> Set[str]:
        """
        获取永久允许列表
        
        Returns:
            Set[str]: 永久允许的模式集合
        """
        with self._lock:
            return self._permanent_approved.copy()
    
    def load_from_config(self, allowlist: list):
        """
        从配置加载永久允许列表
        
        Args:
            allowlist: 允许的模式列表
        """
        with self._lock:
            self._permanent_approved.update(allowlist)
            logger.info(f"从配置加载 {len(allowlist)} 个永久允许模式")


# 全局实例
approval_manager = ApprovalManager()
