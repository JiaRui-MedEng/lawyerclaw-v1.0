"""
百佑 LawyerClaw 安全模块
基于 Hermes Agent 安全系统简化版
"""

from .approval import ApprovalManager, detect_dangerous_command
from .skills_guard import scan_skill, should_allow_install, ScanResult, Finding

__version__ = "0.1.0"
__all__ = [
    "ApprovalManager",
    "detect_dangerous_command",
    "scan_skill",
    "should_allow_install",
    "ScanResult",
    "Finding",
]
