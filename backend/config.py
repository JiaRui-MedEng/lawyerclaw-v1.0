"""
配置文件
"""
import os
from pathlib import Path
from dotenv import load_dotenv

from service.core.paths import get_backend_dir

BASE_DIR = get_backend_dir()
DATA_DIR = BASE_DIR / 'data'

for d in [DATA_DIR]:
    d.mkdir(parents=True, exist_ok=True)

load_dotenv(BASE_DIR / '.env')


class Config:
    """统一配置"""
    
    SECRET_KEY = os.getenv('SECRET_KEY', 'lawyerclaw-secret')
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    PORT = int(os.getenv('PORT', 5004))
    
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///' + str(DATA_DIR / 'lawyerclaw.db'))
    CHROMA_PERSIST_DIR = os.getenv('CHROMA_PERSIST_DIR', str(DATA_DIR / 'chroma'))
    
    # LLM 供应商配置
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
    CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY', '')
    DASHSCOPE_API_KEY = os.getenv('DASHSCOPE_API_KEY', '')
    
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o')
    CLAUDE_MODEL = os.getenv('CLAUDE_MODEL', 'claude-sonnet-4-20250514')
    DASHSCOPE_MODEL = os.getenv('DASHSCOPE_MODEL', 'qwen-max')
    
    # 会话配置
    MAX_CONTEXT_TOKENS = int(os.getenv('MAX_CONTEXT_TOKENS', 8000))
    COMPACTION_THRESHOLD = int(os.getenv('COMPACTION_THRESHOLD', 6000))
