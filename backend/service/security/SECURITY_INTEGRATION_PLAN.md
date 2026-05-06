"""
百佑 LawyerClaw 安全架构整合方案
基于 Hermes Agent 安全模块增强版

整合内容:
1. 命令审批系统 (approval.py) - 增强到 100+ 危险模式
2. 技能安全扫描 (skills_guard.py) - 增强到 200+ 威胁模式
3. 记忆内容安全扫描 - 新增注入/泄露检测
4. FTS5 全文搜索 - 会话检索优化
5. 前端安全 UI - 审批对话框、扫描报告

作者：Hermes Agent 安全架构迁移
日期：2026 年 1 月
"""

# ═══════════════════════════════════════════════════════════
# 第一部分：后端安全模块增强
# ═══════════════════════════════════════════════════════════

# 1.1 更新 app/security/approval.py
# 增强危险命令模式到 100+

DANGEROUS_PATTERNS_ENHANCED = [
    # ── 原有模式保留 (50+) ──
    # ... (保留原有的所有模式)
    
    # ── 新增：法律数据敏感操作 ──
    (r'\b(身份证号 | 身份证号码)\s*[:：]?\s*\d{17}[\dXx]', "expose_id_number"),
    (r'\b(银行卡号 | 信用卡号)\s*[:：]?\s*\d{16,19}', "expose_bank_card"),
    (r'\b(手机号 | 手机号码 | 电话)\s*[:：]?\s*1[3-9]\d{9}', "expose_phone_number"),
    (r'\b(案件编号 | 案号)\s*[:：]?\s*[\u4e00-\u9fa5 第\d 号]+', "expose_case_number"),
    (r'\b(判决书编号 | 文书编号)\s*[:：]?\s*[\u4e00-\u9fa5 第\d 号]+', "expose_judgment_number"),
    (r'\b(律师执业证 | 律师证)\s*[:：]?\s*\d{12,14}', "expose_lawyer_license"),
    (r'\b(统一社会信用代码 | 税号)\s*[:：]?\s*[A-Z0-9]{18}', "expose_credit_code"),
    
    # ── 新增：数据批量导出 ──
    (r'\bSELECT\s+.*\bINTO\s+OUTFILE\b', "sql_export_to_file"),
    (r'\bCOPY\s+.*\bTO\s+\'[^\']+\'', "postgres_export_to_file"),
    (r'\b\.export\s+', "sqlite_export"),
    (r'\b(mysqldump|pg_dump|sqlite3\.dump)\b', "database_dump"),
    
    # ── 新增：隐私侵犯 ──
    (r'\b(人肉 | 开盒 | 曝光)\s*(信息 | 数据 | 隐私)', "doxxing_attempt"),
    (r'\b(窃取 | 盗取 | 非法获取)\s*(数据 | 信息 | 隐私)', "data_theft"),
    
    # ── 新增：法律规避 ──
    (r'\b(绕过 | 规避 | 逃避)\s*(监管 | 审查 | 法律)', "regulatory_evasion"),
    (r'\b(洗钱 | 逃税 | 偷税)\b', "illegal_activity"),
    (r'\b(伪造 | 变造 | 篡改)\s*(证据 | 文件 | 合同)', "evidence_tampering"),
]

# 1.2 新增：记忆内容安全扫描模块
# 文件：app/security/memory_guard.py

