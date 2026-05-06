# -*- mode: python ; coding: utf-8 -*-
"""
百佑 LawyerClaw PyInstaller 打包配置

使用方法:
  cd D:\Projects\Pycharm\lawyerclaw
  pyinstaller lawyerclaw.spec
"""

import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# 项目根目录
ROOT = os.path.abspath('.')
BACKEND = os.path.join(ROOT, 'backend')
FRONTEND_DIST = os.path.join(ROOT, 'frontend', 'dist')

# ==================== 数据文件 ====================
datas = []

# 前端打包产物
if os.path.exists(FRONTEND_DIST):
    datas.append((FRONTEND_DIST, 'frontend_dist'))

# backend 下的 .env 文件（放到 backend/ 目录，同时也放到 exe 同级 backend/）
env_file = os.path.join(BACKEND, '.env')
if os.path.exists(env_file):
    datas.append((env_file, 'backend'))

# .env.example 作为参考
env_example = os.path.join(BACKEND, '.env.example')
if os.path.exists(env_example):
    datas.append((env_example, 'backend'))

# skills 目录（技能元数据）
skills_dir = os.path.join(BACKEND, 'skills')
if os.path.exists(skills_dir):
    datas.append((skills_dir, 'backend/skills'))

# ==================== Hidden Imports ====================
# Flask 蓝图和服务模块
hidden_imports = [
    # Flask 相关
    'flask',
    'flask_cors',
    'flask_sqlalchemy',

    # API 蓝图
    'service.api.auth',
    'service.api.sessions',
    'service.api.chat',
    'service.api.chat_enhanced',
    'service.api.tools',
    'service.api.plugins',
    'service.api.workspace',
    'service.api.upload',
    'service.api.vision',
    'service.api.memory',
    'service.api.skills',
    'service.api.hermes',
    'service.api.settings',
    'service.api.rag',
    'service.api.file_operations',
    'service.api.chat_sync_file_processor',
    'service.api.security',
    'service.api.shutdown',
    'service.api.providers_config',

    # Core
    'service.core',
    'service.core.paths',
    'service.core.runtime',
    'service.core.runtime_hermes',
    'service.core.hermes_core',
    'service.core.system_prompt_builder',
    'service.core.question_classifier',
    'service.core.compact',
    'service.core.shutdown',

    # Models
    'service.models',
    'service.models.database',
    'service.models.database_enhanced',

    # Providers
    'service.providers',
    'service.providers.base',
    'service.providers.openai_provider',
    'service.providers.claude_provider',
    'service.providers.dashscope_provider',
    'service.providers.minimax_provider',

    # Security
    'service.security',
    'service.security.approval',
    'service.security.approval_enhanced',
    'service.security.memory_guard',
    'service.security.skills_guard',
    'service.security.skills_guard_enhanced',

    # Plugins
    'service.plugins',
    'service.plugins.plugin_manager',

    # Self Evolution
    'service.self_evolution',
    'service.self_evolution.memory',
    'service.self_evolution.skills',

    # Tools
    'service.tools',
    'service.tools.file_tools',
    'service.tools.file_operations',
    'service.tools.legal_tools',
    'service.tools.skills_tools',
    'service.tools.vision_tools',
    'service.tools.file_utils',
    'service.tools.file_tool_registry',
    'service.tools.file_reader_enhanced',
    'service.tools.document_parser',
    'service.tools.concurrent_file_processor',
    'service.tools.search_intent',
    'service.tools.python_executor',

    # RAG
    'service.rag',
    'service.rag.chroma_store',
    'service.rag.rag_simple',
    'service.rag.rag_integration',
    'service.rag.rag_context',
    'service.rag.zhipu_embedding',
    'service.rag.reranker',
    'service.rag.query_rewriter',
    'service.rag.document_parser',
    'service.rag.vector_store',

    # Tools (additional)
    'service.tools.tavily_search',

    # RAG / Document dependencies — collect ALL chromadb submodules to avoid missing dynamic imports
    *collect_submodules('chromadb'),
    'pdfplumber',
    # pdfplumber 的深层依赖（打包后常因缺少子模块导致 PDF 解析失败）
    'pdfminer',
    'pdfminer.pdfparser',
    'pdfminer.pdfdocument',
    'pdfminer.pdfpage',
    'pdfminer.pdfinterp',
    'pdfminer.pdfdevice',
    'pdfminer.pdfcolor',
    'pdfminer.pdfcid',
    'pdfminer.pdffont',
    'pdfminer.pdfencoding',
    'pdfminer.converter',
    'pdfminer.layout',
    'pdfminer.image',
    'pdfminer.arabic',
    'pdfminer.utils',
    'pdfminer.runlength',
    'pdfminer.lzw',
    'pdfminer.ccitt',
    'pdfminer.pdfexceptions',
    'pdfminer.glyphlist',
    'pdfminer.encodingdb',
    'pdfminer.cmapdb',
    'pdfminer.psparser',
    'pdfminer.fontmetrics',
    'charset_normalizer',
    'pikepdf',
    'PIL',
    'PIL.Image',
    # PyMuPDF (fitz) — used by service/tools/document_parser.py for PDF parsing
    'pymupdf',
    'fitz',
    'zhipuai',
    'tavily',
    'docx',
    'docx.opc',
    'docx.opc.constants',
    'docx.opc.packager',
    'docx.opc.part',
    'docx.opc.phys_packager',
    'docx.opc.rel',
    'docx.oxml',
    'docx.oxml.parser',
    'docx.oxml.ns',
    'docx.oxml.shape',
    'docx.oxml.text',
    'docx.oxml.table',
    'docx.oxml.xmlchemy',
    'docx.shared',
    'docx.enum',
    'docx.enum.text',
    'docx.enum.table',
    'docx.enum.section',
    'docx.enum.style',
    'docx.enum.dml',
    'docx.text',
    'docx.text.font',
    'docx.text.parfmt',
    'docx.text.tab',
    # Additional document parsers
    'openpyxl',
    'pptx',

    # LLM SDKs
    'openai',
    'anthropic',
    'dashscope',
    'httpx',

    # LangChain
    'langchain',
    'langchain_core',
    'langchain_community',
    'langchain_text_splitters',
    'langchain_openai',

    # Database
    'sqlalchemy',
    'sqlalchemy.dialects.sqlite',

    # Utilities
    'dotenv',
    'jwt',
    'markdown',
    'tenacity',
    'sse_starlette',
    'pystray',
    'pystray._win32',
]

a = Analysis(
    [os.path.join(ROOT, 'run.py')],
    pathex=[BACKEND],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Qt bindings conflict
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
        # Unnecessary large packages
        'tkinter',
        'matplotlib',
        'scipy',
        'numpy.testing',
        'cv2',
        'torch',
        'tensorflow',
        'IPython',
        'jupyter',
        'notebook',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='lawyerclaw',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 打包发布时隐藏控制台窗口
    icon=os.path.join(ROOT, 'frontend', 'public', 'favicon.ico')
        if os.path.exists(os.path.join(ROOT, 'frontend', 'public', 'favicon.ico'))
        else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='lawyerclaw',
)
