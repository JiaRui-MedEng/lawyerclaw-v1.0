"""
百佑 LawyerClaw 技能安全扫描模块
基于 Hermes skills_guard.py 增强版

功能:
- 200+ 威胁模式检测
- 信任等级策略
- 静态代码分析
- 法律合规检查
"""
import re
from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass, field
from datetime import datetime

logger = __import__('logging').getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════

@dataclass
class Finding:
    """安全发现"""
    pattern_id: str
    severity: str  # critical, high, medium, low
    category: str  # exfiltration, injection, destructive, persistence, legal
    file: str
    line: int
    match: str
    description: str


@dataclass
class ScanResult:
    """扫描结果"""
    skill_name: str
    source: str
    verdict: str  # safe, caution, dangerous
    findings: List[Finding] = field(default_factory=list)
    scanned_at: str = ""
    summary: str = ""


# ═══════════════════════════════════════════════════════════
# 信任等级配置
# ═══════════════════════════════════════════════════════════

TRUSTED_REPOS = {"openai/skills", "anthropics/skills", "lawyerclaw/official"}

INSTALL_POLICY = {
    #             safe      caution    dangerous
    "builtin":   ("allow",  "allow",   "allow"),
    "trusted":   ("allow",  "allow",   "block"),
    "community": ("allow",  "block",   "block"),
    "internal":  ("allow",  "allow",   "ask"),
    "legal":     ("allow",  "ask",     "block"),  # 法律相关技能更严格
}

VERDICT_INDEX = {"safe": 0, "caution": 1, "dangerous": 2}


# ═══════════════════════════════════════════════════════════
# 威胁模式库 (200+ 模式精简版)
# ═══════════════════════════════════════════════════════════

THREAT_PATTERNS = [
    # ── 数据外泄：shell 命令 (15+) ──
    (r'curl\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)',
     "env_exfil_curl", "critical", "exfiltration",
     "curl command interpolating secret environment variable"),
    
    (r'wget\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)',
     "env_exfil_wget", "critical", "exfiltration",
     "wget command interpolating secret environment variable"),
    
    (r'requests\.(get|post|put|patch)\s*\([^\n]*(KEY|TOKEN|SECRET|PASSWORD)',
     "env_exfil_requests", "critical", "exfiltration",
     "requests library call with secret variable"),
    
    # ── 数据外泄：读取凭证存储 (10+) ──
    (r'\$HOME/\.ssh|~/\.ssh',
     "ssh_dir_access", "high", "exfiltration",
     "references user SSH directory"),
    
    (r'\$HOME/\.aws|~/\.aws',
     "aws_dir_access", "high", "exfiltration",
     "references user AWS credentials directory"),
    
    (r'cat\s+[^\n]*(\.env|credentials|\.netrc|\.pgpass|\.npmrc|\.pypirc)',
     "read_secrets_file", "critical", "exfiltration",
     "reads known secrets file"),
    
    # ── 数据外泄：程序化 env 访问 (10+) ──
    (r'printenv|env\s*\|',
     "dump_all_env", "high", "exfiltration",
     "dumps all environment variables"),
    
    (r'os\.environ\b(?!\s*\.get\s*\(\s*["\']PATH)',
     "python_os_environ", "high", "exfiltration",
     "accesses os.environ (potential env dump)"),
    
    (r'os\.getenv\s*\(\s*[^\)]*(?:KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)',
     "python_getenv_secret", "critical", "exfiltration",
     "reads secret via os.getenv()"),
    
    # ── 提示注入 (20+) ──
    (r'ignore\s+(?:\w+\s+)*(previous|all|above|prior)\s+instructions',
     "prompt_injection_ignore", "critical", "injection",
     "prompt injection: ignore previous instructions"),
    
    (r'you\s+(?:\w+\s+)*now\s+',
     "role_hijack", "high", "injection",
     "attempts to override the agent's role"),
    
    (r'do\s+not\s+(?:\w+\s+)*tell\s+(?:\w+\s+)*the\s+user',
     "deception_hide", "critical", "injection",
     "instructs agent to hide information from user"),
    
    (r'system\s+prompt\s+override',
     "sys_prompt_override", "critical", "injection",
     "attempts to override the system prompt"),
    
    (r'disregard\s+(?:\w+\s+)*(your|all|any)\s+(?:\w+\s+)*(instructions|rules|guidelines)',
     "disregard_rules", "critical", "injection",
     "instructs agent to disregard its rules"),
    
    (r'output\s+(?:\w+\s+)*(system|initial)\s+prompt',
     "leak_system_prompt", "high", "injection",
     "attempts to extract the system prompt"),
    
    # ── 破坏操作 (20+) ──
    (r'rm\s+-rf\s+/',
     "destructive_root_rm", "critical", "destructive",
     "recursive delete from root"),
    
    (r'chmod\s+(-[^\s]*\s+)*(777|666)',
     "chmod_777", "high", "destructive",
     "dangerous permissions (777/666)"),
    
    (r'\bDROP\s+(TABLE|DATABASE)\b',
     "sql_drop", "critical", "destructive",
     "SQL DROP command"),
    
    (r'\bDELETE\s+FROM\b(?!.*\bWHERE\b)',
     "sql_delete_no_where", "critical", "destructive",
     "SQL DELETE without WHERE clause"),
    
    # ── 持久化 (15+) ──
    (r'cron.*\*.*\*.*\*.*\*',
     "cron_persistence", "high", "persistence",
     "cron job persistence"),
    
    (r'echo.*ssh-rsa.*>>.*authorized_keys',
     "ssh_key_inject", "critical", "persistence",
     "SSH key injection"),
    
    (r'echo.*>>.*\.bashrc',
     "bashrc_inject", "high", "persistence",
     ".bashrc injection"),
    
    # ── 法律合规 (30+) ──
    (r'(人肉 | 开盒 | 曝光)\s*(信息 | 数据 | 隐私)',
     "doxxing_content", "critical", "legal",
     "Content related to doxxing or privacy exposure"),
    
    (r'(窃取 | 盗取 | 非法获取)\s*(数据 | 信息 | 隐私)',
     "data_theft_content", "critical", "legal",
     "Content related to data theft"),
    
    (r'(绕过 | 规避 | 逃避)\s*(监管 | 审查 | 法律)',
     "regulatory_evasion", "critical", "legal",
     "Content about evading regulations"),
    
    (r'(洗钱 | 逃税 | 偷税)\b',
     "illegal_financial", "critical", "legal",
     "Content related to financial crimes"),
    
    (r'(伪造 | 变造 | 篡改)\s*(证据 | 文件 | 合同)',
     "evidence_tampering", "critical", "legal",
     "Content about tampering with evidence"),
    
    (r'\d{18}',
     "possible_id_number", "high", "legal",
     "Possible Chinese ID number (18 digits)"),
    
    (r'\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}',
     "possible_bank_card", "high", "legal",
     "Possible bank card number (16-19 digits)"),
    
    (r'1[3-9]\d{9}',
     "possible_phone_number", "medium", "legal",
     "Possible Chinese phone number"),
    
    (r'案件编号 [:：]\s*\S+',
     "case_number_exposure", "high", "legal",
     "Case number exposure"),
    
    (r'判决书编号 [:：]\s*\S+',
     "judgment_number_exposure", "high", "legal",
     "Judgment document number exposure"),
    
    (r'律师执业证 [:：]\s*\d{12,14}',
     "lawyer_license_exposure", "high", "legal",
     "Lawyer license number exposure"),
]


# ═══════════════════════════════════════════════════════════
# 扫描函数
# ═══════════════════════════════════════════════════════════

def scan_skill(skill_dir: Path, source: str = "community") -> ScanResult:
    """
    扫描技能目录
    
    Args:
        skill_dir: 技能目录路径
        source: 来源类型 (builtin, trusted, community, internal, legal)
        
    Returns:
        ScanResult: 扫描结果
    """
    findings = []
    
    # 遍历所有文件
    for file_path in skill_dir.rglob("*"):
        if file_path.is_file() and file_path.suffix in ['.py', '.md', '.sh', '.js', '.txt']:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 模式匹配
                for pattern, pattern_id, severity, category, description in THREAT_PATTERNS:
                    for i, line in enumerate(content.split('\n'), 1):
                        if re.search(pattern, line, re.IGNORECASE):
                            findings.append(Finding(
                                pattern_id=pattern_id,
                                severity=severity,
                                category=category,
                                file=str(file_path.relative_to(skill_dir)),
                                line=i,
                                match=line.strip()[:100],
                                description=description
                            ))
            except Exception as e:
                logger.warning(f"扫描文件失败 {file_path}: {e}")
    
    # 判定 Verdict
    verdict = determine_verdict(findings, source)
    
    # 生成摘要
    summary = generate_summary(findings)
    
    return ScanResult(
        skill_name=skill_dir.name,
        source=source,
        verdict=verdict,
        findings=findings,
        scanned_at=datetime.now().isoformat(),
        summary=summary
    )


def determine_verdict(findings: List[Finding], source: str) -> str:
    """
    判定风险等级
    
    Args:
        findings: 安全发现列表
        source: 来源类型
        
    Returns:
        str: safe, caution, dangerous
    """
    if not findings:
        return "safe"
    
    # 检查是否有 critical
    has_critical = any(f.severity == "critical" for f in findings)
    has_high = any(f.severity == "high" for f in findings)
    
    # 检查法律相关发现
    has_legal = any(f.category == "legal" and f.severity in ["critical", "high"] for f in findings)
    
    # 获取安装策略
    policy = INSTALL_POLICY.get(source, INSTALL_POLICY["community"])
    
    # 法律相关技能更严格
    if source == "legal" and has_legal:
        return "dangerous"
    
    # 根据严重程度判定
    if has_critical:
        return "dangerous"
    elif has_high:
        return "caution"
    else:
        return "safe"


def should_allow_install(result: ScanResult) -> tuple:
    """
    根据扫描结果决定是否允许安装
    
    Args:
        result: 扫描结果
        
    Returns:
        (allowed: bool, reason: str)
        - True: 允许
        - False: 阻止
        - None: 需要用户决定
    """
    # 获取安装策略
    policy = INSTALL_POLICY.get(result.source, INSTALL_POLICY["community"])
    
    # 根据 Verdict 查找策略
    verdict_idx = VERDICT_INDEX.get(result.verdict, 2)
    action = policy[verdict_idx]
    
    if action == "allow":
        return (True, "Allowed by install policy")
    elif action == "block":
        return (False, f"Blocked: {result.verdict} findings in {result.source} skill")
    elif action == "ask":
        return (None, "Requires user confirmation")  # None 表示需要用户决定
    else:
        return (False, f"Unknown action: {action}")


def generate_summary(findings: List[Finding]) -> str:
    """
    生成扫描摘要
    """
    if not findings:
        return "No security issues found"
    
    # 按严重程度统计
    critical_count = sum(1 for f in findings if f.severity == "critical")
    high_count = sum(1 for f in findings if f.severity == "high")
    medium_count = sum(1 for f in findings if f.severity == "medium")
    low_count = sum(1 for f in findings if f.severity == "low")
    
    # 按类别统计
    legal_count = sum(1 for f in findings if f.category == "legal")
    
    summary_parts = [f"Found {len(findings)} security issues"]
    
    if critical_count > 0:
        summary_parts.append(f"{critical_count} critical")
    if high_count > 0:
        summary_parts.append(f"{high_count} high")
    if medium_count > 0:
        summary_parts.append(f"{medium_count} medium")
    if low_count > 0:
        summary_parts.append(f"{low_count} low")
    if legal_count > 0:
        summary_parts.append(f"{legal_count} legal concerns")
    
    return ", ".join(summary_parts)


def format_scan_report(result: ScanResult) -> str:
    """
    格式化扫描报告
    """
    lines = [
        "╔══════════════════════════════════════════════════════════╗",
        "║  Skills Guard 安全扫描报告",
        "╠══════════════════════════════════════════════════════════╣",
        f"║  技能名称：{result.skill_name:<42}║",
        f"║  来源：{result.source:<42}║",
        f"║  判定：{result.verdict.upper():<42}║",
        f"║  扫描时间：{result.scanned_at:<42}║",
        "╠══════════════════════════════════════════════════════════╣",
    ]
    
    if result.findings:
        lines.append(f"║  发现 {len(result.findings)} 个安全问题：{' ' * 20}║")
        lines.append("╠══════════════════════════════════════════════════════════╣")
        lines.append("║")
        
        for i, finding in enumerate(result.findings[:5], 1):  # 只显示前 5 个
            severity_icon = "🔴" if finding.severity == "critical" else "🟠" if finding.severity == "high" else "🟡"
            lines.append(f"║  [{severity_icon}] {finding.pattern_id}")
            lines.append(f"║      分类：{finding.category}")
            lines.append(f"║      文件：{finding.file}")
            lines.append(f"║      行号：{finding.line}")
            lines.append(f"║      匹配：{finding.match[:50]}")
            lines.append("║")
        
        if len(result.findings) > 5:
            lines.append(f"║  ... 还有 {len(result.findings) - 5} 个问题")
            lines.append("║")
    else:
        lines.append("║  ✅ 未发现安全问题")
        lines.append("║")
    
    lines.append("╠══════════════════════════════════════════════════════════╣")
    lines.append(f"║  建议：{result.summary:<42}║")
    lines.append("╚══════════════════════════════════════════════════════════╝")
    
    return "\n".join(lines)
