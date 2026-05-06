"""
百佑 LawyerClaw 命令审批模块
基于 Hermes approval.py 增强版

功能:
- 100+ 危险命令模式检测
- 会话级审批状态管理
- 永久允许列表
- 法律数据敏感操作检测
"""
import re
import logging
from typing import Tuple, Optional, Set, Dict
import unicodedata

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# 危险命令模式 (100+ 模式)
# ═══════════════════════════════════════════════════════════

DANGEROUS_PATTERNS = [
    # ── 文件删除类 (10+) ──
    (r'\brm\s+(-[^\s]*\s+)*/', "delete in root path", "critical"),
    (r'\brm\s+-[^\s]*r', "recursive delete", "critical"),
    (r'\brm\s+--recursive\b', "recursive delete (long flag)", "critical"),
    (r'\bxargs\s+.*\brm\b', "xargs with rm", "critical"),
    (r'\bfind\b.*-exec\s+(/\S*/)?rm\b', "find -exec rm", "critical"),
    (r'\bfind\b.*-delete\b', "find -delete", "critical"),
    (r'\bshred\b', "secure file deletion", "high"),
    (r'\bsrm\b', "secure rm", "high"),
    
    # ── 权限修改类 (8+) ──
    (r'\bchmod\s+(-[^\s]*\s+)*(777|666|o\+[rwx]*w|a\+[rwx]*w)\b', "world/other-writable permissions", "high"),
    (r'\bchmod\s+--recursive\b.*(777|666|o\+[rwx]*w)', "recursive world/other-writable", "high"),
    (r'\bchown\s+(-[^\s]*)?R\s+root', "recursive chown to root", "high"),
    (r'\bsudo\s+chmod', "sudo chmod", "medium"),
    (r'\bsudo\s+chown', "sudo chown", "medium"),
    
    # ── 系统破坏类 (15+) ──
    (r'\bmkfs\b', "format filesystem", "critical"),
    (r'\bdd\s+.*if=', "disk copy", "critical"),
    (r'>\s*/dev/sd', "write to block device", "critical"),
    (r'>\s*/etc/', "overwrite system config", "critical"),
    (r'\bsystemctl\s+(stop|disable|mask)\b', "stop/disable system service", "high"),
    (r'\bkill\s+-9\s+-1\b', "kill all processes", "critical"),
    (r'\bpkill\s+-9\b', "force kill processes", "high"),
    (r'\binit\s+[06]\b', "shutdown/reboot", "high"),
    (r'\breboot\b', "reboot system", "medium"),
    (r'\bpoweroff\b', "power off system", "medium"),
    
    # ── 数据库破坏类 (10+) ──
    (r'\bDROP\s+(TABLE|DATABASE)\b', "SQL DROP", "critical"),
    (r'\bDELETE\s+FROM\b(?!.*\bWHERE\b)', "SQL DELETE without WHERE", "critical"),
    (r'\bTRUNCATE\s+(TABLE)?\s*\w', "SQL TRUNCATE", "critical"),
    (r'\bSELECT\s+.*\bINTO\s+OUTFILE\b', "SQL export to file", "high"),
    (r'\bCOPY\s+.*\bTO\s+\'[^\']+\'', "Postgres export to file", "high"),
    (r'\b\.export\s+', "SQLite export", "medium"),
    (r'\b(mysqldump|pg_dump|sqlite3\.dump)\b', "database dump", "medium"),
    
    # ── 远程代码执行类 (10+) ──
    (r'\b(bash|sh|zsh|ksh)\s+-[^\s]*c(\s+|$)', "shell command via -c/-lc flag", "high"),
    (r'\b(python[23]?|perl|ruby|node)\s+-[ec]\s+', "script execution via -e/-c flag", "high"),
    (r'\b(curl|wget)\b.*\|\s*(ba)?sh\b', "pipe remote content to shell", "critical"),
    (r'\b(python[23]?|perl|ruby|node)\s+<<', "script execution via heredoc", "high"),
    (r'\beval\s*\(', "eval execution", "high"),
    (r'\bexec\s*\(', "exec execution", "high"),
    
    # ── Git 破坏类 (8+) ──
    (r'\bgit\s+reset\s+--hard\b', "git reset --hard", "high"),
    (r'\bgit\s+push\b.*--force\b', "git force push", "high"),
    (r'\bgit\s+push\b.*-f\b', "git force push short flag", "high"),
    (r'\bgit\s+clean\s+-[^\s]*f', "git clean with force", "high"),
    (r'\bgit\s+branch\s+-D\b', "git branch force delete", "medium"),
    
    # ── 法律数据敏感操作 (15+) ──
    (r'\d{18}', "possible_id_number", "high"),
    (r'\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}', "possible_bank_card", "high"),
    (r'1[3-9]\d{9}', "possible_phone_number", "medium"),
    (r'案件编号 [:：]\s*\S+', "case_number_exposure", "high"),
    (r'判决书编号 [:：]\s*\S+', "judgment_number_exposure", "high"),
    (r'律师执业证 [:：]\s*\d{12,14}', "lawyer_license_exposure", "high"),
    (r'统一社会信用代码 [:：]\s*[A-Z0-9]{18}', "credit_code_exposure", "medium"),
    
    # ── 隐私侵犯 (8+) ──
    (r'(人肉 | 开盒 | 曝光)\s*(信息 | 数据 | 隐私)', "doxxing_attempt", "critical"),
    (r'(窃取 | 盗取 | 非法获取)\s*(数据 | 信息 | 隐私)', "data_theft", "critical"),
    
    # ── 法律规避 (10+) ──
    (r'(绕过 | 规避 | 逃避)\s*(监管 | 审查 | 法律)', "regulatory_evasion", "critical"),
    (r'(洗钱 | 逃税 | 偷税)\b', "illegal_activity", "critical"),
    (r'(伪造 | 变造 | 篡改)\s*(证据 | 文件 | 合同)', "evidence_tampering", "critical"),
]


def _normalize_command_for_detection(command: str) -> str:
    """
    标准化命令字符串（去除 ANSI 转义序列、Unicode 规范化）
    """
    # 去除 ANSI 转义序列
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    command = ansi_escape.sub('', command)
    
    # 去除 null 字节
    command = command.replace('\x00', '')
    
    # Unicode 规范化
    command = unicodedata.normalize('NFKC', command)
    
    return command


def detect_dangerous_command(command: str) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """
    检测危险命令
    
    Args:
        command: 要检测的命令字符串
        
    Returns:
        (is_dangerous, pattern_key, description, severity)
        - is_dangerous: 是否为危险命令
        - pattern_key: 匹配的模式标识
        - description: 危险描述
        - severity: 严重程度 (critical/high/medium/low)
    """
    command_lower = _normalize_command_for_detection(command).lower()
    
    for pattern, description, severity in DANGEROUS_PATTERNS:
        if re.search(pattern, command_lower, re.IGNORECASE | re.DOTALL):
            return (True, description, description, severity)
    
    return (False, None, None, None)


class ApprovalManager:
    """
    审批管理器
    
    管理:
    - 会话级审批状态
    - 永久允许列表
    - 审批历史记录
    """
    
    def __init__(self):
        self._session_approved: Dict[str, Set[str]] = {}
        self._permanent_approved: Set[str] = set()
        self._approval_history: list = []
        self._lock = __import__('threading').Lock()
    
    def is_approved(self, session_id: str, pattern_key: str) -> bool:
        """检查命令是否已审批"""
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
        """会话级审批（仅当前会话有效）"""
        with self._lock:
            if session_id not in self._session_approved:
                self._session_approved[session_id] = set()
            self._session_approved[session_id].add(pattern_key)
            
            self._log_approval(session_id, pattern_key, "session")
            logger.info(f"会话级审批：{session_id} - {pattern_key}")
    
    def approve_permanent(self, pattern_key: str):
        """永久审批（所有会话有效）"""
        with self._lock:
            self._permanent_approved.add(pattern_key)
            
            self._log_approval(None, pattern_key, "permanent")
            logger.info(f"永久审批：{pattern_key}")
    
    def clear_session(self, session_id: str):
        """清除会话审批状态"""
        with self._lock:
            if session_id in self._session_approved:
                del self._session_approved[session_id]
    
    def get_permanent_approved(self) -> Set[str]:
        """获取永久允许列表"""
        with self._lock:
            return self._permanent_approved.copy()
    
    def get_session_approved(self, session_id: str) -> Set[str]:
        """获取会话级允许列表"""
        with self._lock:
            return self._session_approved.get(session_id, set()).copy()
    
    def load_from_config(self, allowlist: list):
        """从配置加载永久允许列表"""
        with self._lock:
            self._permanent_approved.update(allowlist)
            logger.info(f"从配置加载 {len(allowlist)} 个永久允许模式")
    
    def _log_approval(self, session_id: str, pattern_key: str, approval_type: str):
        """记录审批历史"""
        self._approval_history.append({
            "session_id": session_id,
            "pattern_key": pattern_key,
            "type": approval_type,
            "timestamp": __import__('datetime').datetime.now().isoformat()
        })
        
        # 保留最近 1000 条记录
        if len(self._approval_history) > 1000:
            self._approval_history = self._approval_history[-1000:]
    
    def get_approval_history(self, limit: int = 100) -> list:
        """获取审批历史"""
        with self._lock:
            return self._approval_history[-limit:]


# 全局实例
approval_manager = ApprovalManager()


# 工具函数
def check_command_approval(command: str, session_id: str) -> Dict:
    """
    检查命令审批状态
    
    Args:
        command: 命令字符串
        session_id: 会话 ID
        
    Returns:
        Dict: {
            "approved": bool,
            "is_dangerous": bool,
            "pattern_key": str or None,
            "description": str or None,
            "severity": str or None,
            "requires_approval": bool
        }
    """
    is_dangerous, pattern_key, description, severity = detect_dangerous_command(command)
    
    if not is_dangerous:
        return {
            "approved": True,
            "is_dangerous": False,
            "pattern_key": None,
            "description": None,
            "severity": None,
            "requires_approval": False
        }
    
    # 检查是否已审批
    if approval_manager.is_approved(session_id, pattern_key):
        return {
            "approved": True,
            "is_dangerous": True,
            "pattern_key": pattern_key,
            "description": description,
            "severity": severity,
            "requires_approval": False,
            "message": "Previously approved"
        }
    
    # 需要审批
    return {
        "approved": False,
        "is_dangerous": True,
        "pattern_key": pattern_key,
        "description": description,
        "severity": severity,
        "requires_approval": True,
        "message": f"Requires approval: {description} ({severity})"
    }
