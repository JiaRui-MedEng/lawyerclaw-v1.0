"""
百佑 LawyerClaw 记忆内容安全扫描模块
基于 Hermes memory_tool.py 安全扫描增强

功能:
- 提示注入检测 (12 种模式)
- 信息泄露检测 (10 种模式)
- 法律数据敏感词检测 (8 种模式)
- 不可见 Unicode 字符检测
"""
import re
from typing import Optional, List, Dict

logger = __import__('logging').getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# 威胁模式库 (30+ 模式)
# ═══════════════════════════════════════════════════════════

_MEMORY_THREAT_PATTERNS = [
    # ── 提示注入 ──
    (r'ignore\s+(previous|all|above|prior)\s+instructions', "prompt_injection", "critical"),
    (r'you\s+are\s+now\s+', "role_hijack", "high"),
    (r'do\s+not\s+tell\s+the\s+user', "deception_hide", "critical"),
    (r'system\s+prompt\s+override', "sys_prompt_override", "critical"),
    (r'disregard\s+(your|all|any)\s+(instructions|rules|guidelines)', "disregard_rules", "critical"),
    (r'act\s+as\s+(if|though)\s+you\s+(have\s+no|don\'t\s+have)\s+(restrictions|limits|rules)', "bypass_restrictions", "high"),
    (r'output\s+(system|initial)\s+prompt', "leak_system_prompt", "high"),
    (r'print\s+your\s+instructions', "leak_instructions", "medium"),
    
    # ── 信息泄露：shell 命令 ──
    (r'curl\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)', "exfil_curl", "critical"),
    (r'wget\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)', "exfil_wget", "critical"),
    (r'requests\.(get|post|put|patch)\s*\([^\n]*(KEY|TOKEN|SECRET|PASSWORD)', "exfil_requests", "critical"),
    
    # ── 信息泄露：读取敏感文件 ──
    (r'cat\s+[^\n]*(\.env|credentials|\.netrc|\.pgpass|\.npmrc|\.pypirc)', "read_secrets_file", "critical"),
    (r'\$HOME/\.ssh|~/\.ssh', "ssh_dir_access", "high"),
    (r'\$HOME/\.aws|~/\.aws', "aws_dir_access", "high"),
    (r'backend/\.env\b', "backend_env_access", "high"),
    
    # ── 法律数据敏感词 ──
    (r'\d{18}', "possible_id_number", "high"),  # 身份证号
    (r'\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}', "possible_bank_card", "high"),  # 银行卡号
    (r'1[3-9]\d{9}', "possible_phone_number", "medium"),  # 手机号
    (r'案件编号 [:：]\s*\S+', "case_number", "high"),
    (r'判决书编号 [:：]\s*\S+', "judgment_number", "high"),
    (r'律师执业证 [:：]\s*\d{12,14}', "lawyer_license", "high"),
    (r'统一社会信用代码 [:：]\s*[A-Z0-9]{18}', "credit_code", "medium"),
]

# 不可见 Unicode 字符 (用于注入攻击)
_INVISIBLE_CHARS = {
    '\u200b', '\u200c', '\u200d', '\u2060', '\ufeff',  # 零宽字符
    '\u202a', '\u202b', '\u202c', '\u202d', '\u202e',  # 方向控制
    '\u2066', '\u2067', '\u2068', '\u2069',  # 隔离控制
}


def scan_memory_content(content: str) -> Dict:
    """
    扫描记忆内容，检测安全威胁
    
    Args:
        content: 要扫描的记忆内容
        
    Returns:
        Dict: {
            "safe": bool,
            "findings": List[Dict],
            "verdict": str (safe/caution/dangerous)
        }
    """
    findings = []
    
    # 1. 检查不可见字符
    for char in _INVISIBLE_CHARS:
        if char in content:
            findings.append({
                "pattern_id": "invisible_unicode",
                "severity": "high",
                "category": "injection",
                "description": f"Content contains invisible unicode character U+{ord(char):04X}",
                "match": f"Invisible char U+{ord(char):04X}"
            })
    
    # 2. 检查威胁模式
    for pattern, pattern_id, severity in _MEMORY_THREAT_PATTERNS:
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            # 确定类别
            if "injection" in pattern_id or "override" in pattern_id:
                category = "injection"
            elif "exfil" in pattern_id or "access" in pattern_id or "read" in pattern_id:
                category = "exfiltration"
            else:
                category = "sensitive_data"
            
            findings.append({
                "pattern_id": pattern_id,
                "severity": severity,
                "category": category,
                "description": get_pattern_description(pattern_id),
                "match": match.group(0)[:100],
                "line": content[:match.start()].count('\n') + 1
            })
    
    # 3. 判定 Verdict
    verdict = determine_memory_verdict(findings)
    
    return {
        "safe": verdict == "safe",
        "findings": findings,
        "verdict": verdict,
        "count": len(findings)
    }


def get_pattern_description(pattern_id: str) -> str:
    """获取模式描述"""
    descriptions = {
        "prompt_injection": "提示注入：忽略先前指令",
        "role_hijack": "角色劫持：尝试覆盖代理角色",
        "deception_hide": "欺骗隐藏：指示对用户提供信息",
        "sys_prompt_override": "系统提示覆盖：尝试修改系统提示",
        "disregard_rules": "无视规则：指示代理忽略规则",
        "bypass_restrictions": "绕过限制：尝试绕过安全限制",
        "leak_system_prompt": "系统提示泄露：尝试提取系统提示",
        "leak_instructions": "指令泄露：尝试获取内部指令",
        "exfil_curl": "信息外泄：curl 命令窃取环境变量",
        "exfil_wget": "信息外泄：wget 命令窃取环境变量",
        "exfil_requests": "信息外泄：requests 库窃取敏感数据",
        "read_secrets_file": "读取敏感文件：访问已知凭证文件",
        "ssh_dir_access": "SSH 目录访问：引用用户 SSH 目录",
        "aws_dir_access": "AWS 目录访问：引用 AWS 凭证目录",
        "hermes_env_access": "Hermes 环境访问：尝试读取.env 文件",
        "possible_id_number": "疑似身份证号：18 位数字",
        "possible_bank_card": "疑似银行卡号：16-19 位数字",
        "possible_phone_number": "疑似手机号：11 位手机号",
        "case_number": "案件编号：法律案件标识符",
        "judgment_number": "判决书编号：法律文书标识符",
        "lawyer_license": "律师执业证：律师资质编号",
        "credit_code": "统一社会信用代码：企业信用标识",
        "invisible_unicode": "不可见 Unicode 字符：可能用于注入攻击",
    }
    return descriptions.get(pattern_id, f"Unknown threat: {pattern_id}")


def determine_memory_verdict(findings: List[Dict]) -> str:
    """
    判定记忆内容风险等级
    
    Returns:
        str: safe, caution, dangerous
    """
    if not findings:
        return "safe"
    
    has_critical = any(f["severity"] == "critical" for f in findings)
    has_high = any(f["severity"] == "high" for f in findings)
    
    if has_critical:
        return "dangerous"
    elif has_high:
        return "caution"
    else:
        return "safe"


def format_memory_scan_report(result: Dict) -> str:
    """
    格式化记忆扫描报告
    
    Args:
        result: scan_memory_content() 返回的结果
        
    Returns:
        str: 格式化的报告文本
    """
    if result["safe"]:
        return "✅ 记忆内容安全检查通过"
    
    lines = [
        "╔══════════════════════════════════════════════════════════╗",
        "║  Memory Guard 安全扫描报告",
        "╠══════════════════════════════════════════════════════════╣",
        f"║  判定：{result['verdict'].upper():<42}║",
        f"║  发现 {result['count']} 个安全问题：{' ' * 20}║",
        "╠══════════════════════════════════════════════════════════╣",
    ]
    
    for i, finding in enumerate(result["findings"][:5], 1):
        severity_icon = "🔴" if finding["severity"] == "critical" else "🟠" if finding["severity"] == "high" else "🟡"
        lines.append(f"║  [{severity_icon}] {finding['pattern_id']}")
        lines.append(f"║      分类：{finding['category']}")
        lines.append(f"║      描述：{finding['description'][:40]}")
        lines.append(f"║      匹配：{finding['match'][:40]}")
        lines.append("║")
    
    if len(result["findings"]) > 5:
        lines.append(f"║  ... 还有 {len(result['findings']) - 5} 个问题")
    
    lines.append("╚══════════════════════════════════════════════════════════╝")
    
    return "\n".join(lines)


# 全局扫描函数
def should_allow_memory(content: str, source: str = "user") -> tuple:
    """
    决定是否允许记忆写入
    
    Args:
        content: 记忆内容
        source: 来源 (user/agent/system)
        
    Returns:
        (allowed: bool, reason: str)
    """
    # 系统来源跳过扫描
    if source == "system":
        return (True, "System source, skipped scan")
    
    # 扫描内容
    result = scan_memory_content(content)
    
    if result["safe"]:
        return (True, "Content passed security scan")
    
    if result["verdict"] == "dangerous":
        report = format_memory_scan_report(result)
        return (False, f"Blocked: dangerous content detected\n{report}")
    
    if result["verdict"] == "caution":
        report = format_memory_scan_report(result)
        return (None, f"Caution: review recommended\n{report}")  # None 表示需要用户决定
    
    return (True, "Content allowed with minor findings")
