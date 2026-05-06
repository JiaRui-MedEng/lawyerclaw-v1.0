"""
RAG 知识库管理 API
支持 Collection 管理、文档上传与向量化入库
使用 ChromaDB 替代 pgvector
"""
import os
import re
import time
import logging
import uuid
import hashlib
import threading
from pathlib import Path
from datetime import datetime
from flask import Blueprint, request, jsonify

logger = logging.getLogger(__name__)

# 异步任务存储
_tasks = {}
_tasks_lock = threading.Lock()

rag_bp = Blueprint('rag', __name__, url_prefix='/api/rag')

# 上传目录
from service.core.paths import get_uploads_dir
UPLOAD_DIR = get_uploads_dir() / 'rag'
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.doc', '.txt'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


def _get_store():
    """获取 ChromaDB 存储实例"""
    from service.rag.chroma_store import get_chroma_store
    return get_chroma_store()


# ============================================================
# GET /api/rag/collections - 列出所有 Collection
# ============================================================
@rag_bp.route('/collections', methods=['GET'])
def list_collections():
    """列出所有知识库 Collection"""
    try:
        store = _get_store()
        collections = store.list_collections()

        return jsonify({
            'success': True,
            'collections': collections,
            'total': len(collections)
        })

    except Exception as e:
        logger.error(f"列出 Collection 失败: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ============================================================
# GET /api/rag/stats - 知识库总体统计
# ============================================================
@rag_bp.route('/stats', methods=['GET'])
def rag_stats():
    """获取 RAG 知识库统计信息"""
    try:
        store = _get_store()
        stats = store.get_total_stats()

        return jsonify({
            'success': True,
            'stats': stats
        })

    except Exception as e:
        logger.error(f"获取 RAG 统计失败: {e}")
        return jsonify({
            'success': True,
            'stats': {
                'enabled': False,
                'doc_count': 0,
                'chunk_count': 0,
                'collections': [],
            }
        })


# ============================================================
# POST /api/rag/toggle - 切换 RAG 启用状态
# ============================================================
@rag_bp.route('/toggle', methods=['POST'])
def toggle_rag():
    """切换 RAG 启用/禁用"""
    data = request.get_json(force=True) or {}
    enabled = data.get('enabled', True)
    os.environ['RAG_ENABLED'] = '1' if enabled else '0'
    return jsonify({'success': True, 'enabled': enabled})


# ============================================================
# GET /api/rag/collections/<name>/detail - Collection 详情
# ============================================================
@rag_bp.route('/collections/<name>/detail', methods=['GET'])
def collection_detail(name):
    """获取单个 Collection 的详细信息"""
    try:
        store = _get_store()

        if not store.collection_exists(name):
            return jsonify({'success': False, 'message': f'Collection {name} 不存在'}), 404

        stats = store.get_collection_stats(name)
        sample_data = store.get_sample_data(name, limit=10)

        return jsonify({
            'success': True,
            'detail': {
                'name': name,
                'entity_count': stats['entity_count'],
                'fields': [
                    {'name': 'id', 'type': 'VARCHAR'},
                    {'name': 'title', 'type': 'VARCHAR'},
                    {'name': 'content', 'type': 'TEXT'},
                    {'name': 'chunk_index', 'type': 'INTEGER'},
                    {'name': 'category', 'type': 'VARCHAR'},
                    {'name': 'embedding', 'type': 'vector(2048)'},
                ],
                'sample_data': sample_data,
            }
        })

    except Exception as e:
        logger.error(f"获取 Collection 详情失败: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ============================================================
# DELETE /api/rag/collections/<name> - 删除 Collection
# ============================================================
@rag_bp.route('/collections/<name>', methods=['DELETE'])
def delete_collection(name):
    """删除 Collection"""
    try:
        store = _get_store()

        if not store.collection_exists(name):
            return jsonify({'success': False, 'message': f'Collection {name} 不存在'}), 404

        store.delete_collection(name)
        logger.info(f"已删除 Collection: {name}")

        return jsonify({'success': True, 'message': f'Collection {name} 已删除'})

    except Exception as e:
        logger.error(f"删除 Collection 失败: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ============================================================
# POST /api/rag/upload - 上传文档并向量化入库
# ============================================================
@rag_bp.route('/upload', methods=['POST'])
def upload_and_ingest():
    """
    上传文档 → 立即返回 task_id → 后台异步处理

    Form 参数:
        file: 上传的文件 (PDF/Word/TXT)
        collection_name: 目标 Collection 名称
        title: 文档标题（可选，默认用文件名）
        category: 分类（可选）
    """
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '未上传文件'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'success': False, 'message': '文件名为空'}), 400

    # 检查扩展名
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({
            'success': False,
            'message': f'不支持的文件类型: {ext}，支持: {", ".join(ALLOWED_EXTENSIONS)}'
        }), 400

    collection_name = request.form.get('collection_name', '').strip() or request.form.get('collection', '').strip()
    doc_title = request.form.get('title', '').strip() or Path(file.filename).stem
    category = request.form.get('category', '').strip() or doc_title

    if not collection_name:
        return jsonify({'success': False, 'message': '请选择目标 Collection'}), 400

    # 保存文件
    safe_name = f"{uuid.uuid4().hex[:8]}_{file.filename}"
    save_path = UPLOAD_DIR / safe_name
    file.save(str(save_path))
    file_size = save_path.stat().st_size

    logger.info(f"文件已保存: {save_path} ({file_size} bytes)")

    # 创建异步任务
    task_id = uuid.uuid4().hex[:12]
    with _tasks_lock:
        _tasks[task_id] = {
            'status': 'running',
            'stage': 'parsing',
            'progress': 0,
            'message': '正在解析文档...',
            'file_name': file.filename,
            'result': None,
            'created_at': time.time(),
        }

    # 启动后台线程
    from flask import current_app
    app = current_app._get_current_object()

    thread = threading.Thread(
        target=_ingest_worker,
        args=(app, task_id, save_path, ext, collection_name, doc_title, category, file.filename, file_size),
        daemon=True,
    )
    thread.start()

    return jsonify({'success': True, 'task_id': task_id})


@rag_bp.route('/upload/progress/<task_id>', methods=['GET'])
def upload_progress(task_id):
    """查询上传任务进度"""
    with _tasks_lock:
        task = _tasks.get(task_id)

    if not task:
        return jsonify({'success': False, 'message': '任务不存在'}), 404

    return jsonify({'success': True, **task})


@rag_bp.route('/ingest-local', methods=['POST'])
def ingest_local_files():
    """
    将服务器本地文件（如工作空间文件）直接存入知识库

    JSON 参数:
        file_paths: 文件路径列表
        collection_name: 目标 Collection 名称（可选，默认 legal_default）
    """
    data = request.get_json(force=True) or {}
    file_paths = data.get('file_paths', [])
    collection_name = data.get('collection_name', '').strip() or 'legal_default'

    if not collection_name.startswith('legal_'):
        collection_name = f'legal_{collection_name}'

    if not file_paths:
        return jsonify({'success': False, 'message': '未提供文件路径'}), 400

    from flask import current_app
    app = current_app._get_current_object()

    valid_files = []
    for file_path_str in file_paths:
        path = Path(file_path_str)
        if not path.exists():
            return jsonify({'success': False, 'message': f'文件不存在: {file_path_str}'}), 400
        if not path.is_file():
            continue
        valid_files.append(file_path_str)

    if not valid_files:
        return jsonify({'success': False, 'message': '没有有效的文件（请确保选择的是文件而非文件夹）'}), 400

    tasks = []

    for file_path_str in valid_files:
        path = Path(file_path_str)
        ext = path.suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            return jsonify({
                'success': False,
                'message': f'不支持的文件类型: {ext}，支持: {", ".join(ALLOWED_EXTENSIONS)}'
            }), 400

        task_id = uuid.uuid4().hex[:12]
        with _tasks_lock:
            _tasks[task_id] = {
                'status': 'running',
                'stage': 'parsing',
                'progress': 0,
                'message': '正在解析文档...',
                'file_name': path.name,
                'result': None,
                'created_at': time.time(),
            }

        doc_title = path.stem
        category = path.stem
        file_size = path.stat().st_size

        thread = threading.Thread(
            target=_run_ingest,
            args=(app, task_id, path, ext, collection_name, doc_title, category, path.name, file_size),
            daemon=True,
        )
        thread.start()

        tasks.append({'task_id': task_id, 'file_name': path.name})

    return jsonify({'success': True, 'tasks': tasks, 'collection_name': collection_name})


def _run_ingest(app, task_id, save_path, ext, collection_name, doc_title, category, file_name, file_size):
    """执行入库（可被上传和本地入库复用）"""
    with app.app_context():
        try:
            store = _get_store()

            # 阶段 1: 解析文档
            _update_task(task_id, stage='parsing', progress=10, message=f'正在解析文档: {file_name}')
            content = _parse_file(save_path, ext)
            if not content or len(content.strip()) < 10:
                _update_task(task_id, status='failed', message='文档内容为空或过短')
                return

            # 去重检查：基于内容哈希
            content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()[:12]
            if store.check_duplicate(collection_name, content_hash):
                _update_task(task_id, status='failed',
                             message=f'文档已存在（内容哈希: {content_hash}），请勿重复上传')
                return

            # 阶段 2: 分块
            _update_task(task_id, stage='chunking', progress=25, message='正在智能分块...')
            chunks = _smart_chunk(content, doc_title, category)
            _update_task(task_id, progress=35, message=f'分块完成: {len(chunks)} 个块，开始向量化...')
            logger.info(f"[Task {task_id}] 分块完成: {len(chunks)} 个块")

            # 阶段 3: 分批向量化 + 写入（边算边存，降低内存占用）
            _update_task(task_id, stage='embedding', progress=40, message='正在向量化并写入...')
            inserted = _embed_and_store_batched(
                store, collection_name, chunks, task_id, doc_hash=content_hash
            )

            # 完成
            _update_task(task_id, status='done', stage='done', progress=100,
                         message='入库完成',
                         result={
                             'file_name': file_name,
                             'file_size': file_size,
                             'collection': collection_name,
                             'chunk_count': len(chunks),
                             'entity_count': inserted,
                         })
            logger.info(f"[Task {task_id}] 入库完成: {inserted} 条")

        except Exception as e:
            logger.error(f"[Task {task_id}] 入库失败: {e}", exc_info=True)
            _update_task(task_id, status='failed', message=f'入库失败: {str(e)}')


def _ingest_worker(app, task_id, save_path, ext, collection_name, doc_title, category, file_name, file_size):
    """后台入库工作线程（上传文件用）"""
    _run_ingest(app, task_id, save_path, ext, collection_name, doc_title, category, file_name, file_size)


def _update_task(task_id, **kwargs):
    """更新任务状态"""
    with _tasks_lock:
        if task_id in _tasks:
            _tasks[task_id].update(kwargs)


def _embed_and_store_batched(store, collection_name, chunks, task_id, doc_hash=None, batch_size=8):
    """
    分批向量化 + 写入：每批向量化后立即写入数据库

    优势：
    - 内存占用低（不需要一次性持有所有向量）
    - 中途失败时已写入的数据不丢失
    - 进度更平滑
    """
    from zhipuai import ZhipuAI

    api_key = os.getenv('ZHIPU_API_KEY')
    if not api_key:
        raise ValueError("ZHIPU_API_KEY 未配置")

    client = ZhipuAI(api_key=api_key)
    total_batches = (len(chunks) - 1) // batch_size + 1
    total_inserted = 0

    for i in range(0, len(chunks), batch_size):
        batch_chunks = chunks[i:i + batch_size]
        batch_num = i // batch_size + 1

        # 1) 向量化当前批次
        batch_texts = [c['content'] for c in batch_chunks]
        response = client.embeddings.create(model="embedding-3", input=batch_texts)
        batch_embeddings = [item.embedding for item in response.data]

        # 2) 立即写入数据库
        # 只有第一批的第一条使用 doc_hash 作为 ID（用于去重）
        batch_hash = doc_hash if i == 0 else None
        inserted = store.insert_chunks(
            collection_name, batch_chunks, batch_embeddings,
            doc_hash=batch_hash, index_offset=i
        )
        total_inserted += inserted

        # 3) 更新进度（40% ~ 98%）
        progress = 40 + int((batch_num / total_batches) * 58)
        _update_task(task_id, progress=progress,
                     message=f'向量化并写入中 ({batch_num}/{total_batches})... 已入库 {total_inserted} 条')

        logger.info(f"[Task {task_id}] 批次 {batch_num}/{total_batches} 完成，写入 {inserted} 条")

        # 限速（避免触发智谱 API 频率限制）
        if i + batch_size < len(chunks):
            time.sleep(0.3)

    return total_inserted


# ============================================================
# POST /api/rag/collections/create - 创建新 Collection
# ============================================================
@rag_bp.route('/collections/create', methods=['POST'])
def create_collection():
    """创建新的 Collection"""
    data = request.get_json(force=True) or {}
    name = data.get('name', '').strip()

    if not name:
        return jsonify({'success': False, 'message': '请输入 Collection 名称'}), 400

    # 自动加 legal_ 前缀
    if not name.startswith('legal_'):
        name = f'legal_{name}'

    # 名称校验
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
        return jsonify({'success': False, 'message': '名称只能包含字母、数字和下划线'}), 400

    try:
        store = _get_store()

        if store.collection_exists(name):
            return jsonify({'success': False, 'message': f'Collection {name} 已存在'}), 409

        logger.info(f"创建 Collection: {name}")

        return jsonify({
            'success': True,
            'message': f'Collection {name} 创建成功',
            'collection': {'name': name, 'entity_count': 0}
        })

    except Exception as e:
        logger.error(f"创建 Collection 失败: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ============================================================
# 内部工具函数（文档解析和分块 - 保持不变）
# ============================================================

def _parse_file(file_path: Path, ext: str) -> str:
    """解析文件内容"""
    if ext == '.txt':
        return file_path.read_text(encoding='utf-8')

    if ext == '.pdf':
        try:
            import pdfplumber
        except ImportError as e:
            raise ImportError(f"pdfplumber 导入失败: {e}。请确保已安装 pdfplumber 及其依赖。打包后请检查 spec 文件是否包含 pdfplumber 的所有子模块。") from e
        parts = []
        with pdfplumber.open(str(file_path)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    parts.append(text)
        return "\n\n".join(parts)

    if ext in ('.docx', '.doc'):
        try:
            from docx import Document
        except ImportError as e:
            raise ImportError(f"python-docx 导入失败: {e}。请确保已安装 python-docx。打包后请检查 spec 文件是否包含 docx 的所有子模块。") from e
        doc = Document(str(file_path))
        parts = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(parts)

    raise ValueError(f"不支持的文件类型: {ext}")


def _smart_chunk(content: str, doc_title: str, category: str) -> list:
    """智能分块：自动检测文档结构，选择最佳分块策略"""
    chunk_size = 500
    overlap = 80

    # 检测法条结构
    article_pattern = re.compile(r'(第[一二三四五六七八九十百千零０-９\d]+条)')
    article_matches = list(article_pattern.finditer(content))
    if len(article_matches) >= 5:
        logger.info(f"检测到 {len(article_matches)} 个法条标记，使用法条分块")
        return _chunk_by_articles(content, article_matches, doc_title, category, chunk_size)

    # 检测标题结构
    heading_pattern = re.compile(
        r'^(?:#{1,4}\s+.+|第[一二三四五六七八九十百千]+(?:编|分编|章|节|部分)\s*.+|[一二三四五六七八九十]+[、.]\s*.+|\d+[、.]\s*.+)',
        re.MULTILINE
    )
    heading_matches = list(heading_pattern.finditer(content))
    if len(heading_matches) >= 3:
        logger.info(f"检测到 {len(heading_matches)} 个标题，使用标题分块")
        return _chunk_by_headings(content, heading_matches, doc_title, category, chunk_size)

    # 回退通用分块
    logger.info("未检测到特殊结构，使用通用分块")
    return _chunk_generic(content, doc_title, category, chunk_size, overlap)


def _chunk_by_articles(content: str, matches, doc_title: str, category: str, chunk_size: int = 500) -> list:
    """
    按法条分块 — 保证每条法条完整性

    策略：
    1. 按"第X条"切分，每条法条完整保留（绝不拆分单条法条）
    2. 短法条按章节就近合并，直到接近 chunk_size
    3. 超长法条（超过 chunk_size）单独成块，不做截断
    4. 跨章节时强制切分，保持语义边界
    """
    # 跳过目录
    content_start = 0
    for m in matches:
        after = content[m.end():m.end() + 80]
        first_line = after.split('\n')[0].strip()
        if len(first_line) > 10:
            content_start = m.start()
            break

    body = content[content_start:]
    body_matches = list(re.compile(r'(第[一二三四五六七八九十百千零０-９\d]+条)').finditer(body))

    if not body_matches:
        return None

    # 追踪章节
    chapter_pattern = re.compile(r'(第[一二三四五六七八九十百千]+(?:编|分编|章|节))\s*(.+)')
    chapter_matches = list(chapter_pattern.finditer(body))

    # 提取每条法条及其所属章节
    articles = []
    for i, match in enumerate(body_matches):
        start = match.start()
        end = body_matches[i + 1].start() if i + 1 < len(body_matches) else len(body)
        text = body[start:end].strip()
        if not text:
            continue

        article_num = match.group(1)

        # 确定当前章节
        current_chapter = category
        for cm in chapter_matches:
            if cm.start() < start:
                current_chapter = cm.group(2).strip()

        articles.append({
            'article_num': article_num,
            'text': text,
            'chapter': current_chapter,
        })

    # 按章节分组，同章节内合并短法条
    chunks = []
    buffer_text = ""
    buffer_first_article = ""
    buffer_last_article = ""
    buffer_chapter = None

    for art in articles:
        # 跨章节时强制切分
        if buffer_chapter is not None and art['chapter'] != buffer_chapter:
            if buffer_text:
                title = f"{doc_title} {buffer_first_article}"
                if buffer_first_article != buffer_last_article:
                    title += f"~{buffer_last_article}"
                chunks.append({
                    'title': title,
                    'content': buffer_text.strip(),
                    'category': f"{category}-{buffer_chapter}",
                })
            buffer_text = ""
            buffer_first_article = ""
            buffer_last_article = ""

        # 合并判断：加入当前法条后是否超过 chunk_size
        new_len = len(buffer_text) + len(art['text']) + 1
        if buffer_text and new_len > chunk_size:
            # buffer 已满，先存入
            title = f"{doc_title} {buffer_first_article}"
            if buffer_first_article != buffer_last_article:
                title += f"~{buffer_last_article}"
            chunks.append({
                'title': title,
                'content': buffer_text.strip(),
                'category': f"{category}-{buffer_chapter}",
            })
            buffer_text = art['text']
            buffer_first_article = art['article_num']
            buffer_last_article = art['article_num']
        else:
            # 合并到 buffer
            if buffer_text:
                buffer_text += "\n" + art['text']
            else:
                buffer_text = art['text']
                buffer_first_article = art['article_num']
            buffer_last_article = art['article_num']

        buffer_chapter = art['chapter']

    # 处理剩余 buffer
    if buffer_text.strip():
        title = f"{doc_title} {buffer_first_article}"
        if buffer_first_article != buffer_last_article:
            title += f"~{buffer_last_article}"
        chunks.append({
            'title': title,
            'content': buffer_text.strip(),
            'category': f"{category}-{buffer_chapter}",
        })

    logger.info(f"法条分块完成: {len(articles)} 条法条 → {len(chunks)} 个 chunk")
    return chunks


def _chunk_by_headings(content: str, matches, doc_title: str, category: str, chunk_size: int = 800) -> list:
    """按标题/章节分块"""
    chunks = []

    if matches[0].start() > 50:
        preamble = content[:matches[0].start()].strip()
        if preamble:
            chunks.append({'title': f"{doc_title} - 前言", 'content': preamble, 'category': category})

    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        text = content[start:end].strip()

        if not text:
            continue

        heading_text = match.group(0).lstrip('#').strip()
        title = f"{doc_title} - {heading_text}"

        if len(text) > chunk_size * 2:
            chunks.extend(_split_long_text(text, title, category, chunk_size))
        else:
            chunks.append({'title': title, 'content': text, 'category': category})

    return _merge_short_chunks(chunks, chunk_size, doc_title)


def _chunk_generic(content: str, doc_title: str, category: str, chunk_size: int = 500, overlap: int = 80) -> list:
    """通用分块"""
    chunks = []
    start = 0

    while start < len(content):
        end = start + chunk_size
        if end < len(content):
            for sep in ['。\n', '\n\n', '。', '；', '\n', '，']:
                pos = content[start:end].rfind(sep)
                if pos > chunk_size * 0.3:
                    end = start + pos + len(sep)
                    break

        text = content[start:end].strip()
        if text:
            chunks.append({
                'title': f"{doc_title} - 段落{len(chunks)+1}",
                'content': text,
                'category': category,
            })
        start = end - overlap

    return chunks


def _split_long_text(text: str, title: str, category: str, max_size: int) -> list:
    """拆分过长的文本块"""
    chunks = []
    sentences = re.split(r'(?<=[。；！？])', text)
    current = ""
    part = 1

    for sent in sentences:
        if len(current) + len(sent) > max_size and current:
            chunks.append({
                'title': f"{title}（第{part}部分）",
                'content': current.strip(),
                'category': category,
            })
            current = sent
            part += 1
        else:
            current += sent

    if current.strip():
        chunks.append({
            'title': f"{title}（第{part}部分）" if part > 1 else title,
            'content': current.strip(),
            'category': category,
        })

    return chunks


def _merge_short_chunks(chunks: list, max_size: int, doc_title: str) -> list:
    """合并过短的块"""
    merged = []
    buf = None

    for c in chunks:
        if buf is None:
            buf = c
        elif len(buf['content']) + len(c['content']) < max_size:
            buf['content'] += "\n" + c['content']
            short_title = c['title'].replace(doc_title + ' ', '').replace(doc_title + ' - ', '')
            buf['title'] += f" ~ {short_title}"
        else:
            merged.append(buf)
            buf = c

    if buf:
        if merged and len(buf['content']) < 80:
            merged[-1]['content'] += "\n" + buf['content']
        else:
            merged.append(buf)

    return merged
