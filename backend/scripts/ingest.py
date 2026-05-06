#!/usr/bin/env python3
"""
通用文档入库工具 - 支持多种文档类型和分块策略

用法:
    python scripts/ingest.py <file_path> --collection <name> [options]

示例:
    python scripts/ingest.py "D:\\Downloads\\民法典.pdf" --collection minfadian
    python scripts/ingest.py "D:\\Downloads\\report.docx" --collection reports --strategy heading
    python scripts/ingest.py "D:\\Downloads\\notes.txt" --collection notes --strategy generic
"""
import os
import sys
import re
import time
import argparse
from pathlib import Path
from datetime import datetime

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent.parent))

# 配置
ZHIPU_API_KEY = os.getenv('ZHIPU_API_KEY')
if not ZHIPU_API_KEY:
    print("错误: 请设置环境变量 ZHIPU_API_KEY")
    sys.exit(1)

SUPPORTED_EXTENSIONS = {'.pdf', '.docx', '.doc', '.txt'}


# ============================================================
# 文档解析
# ============================================================

def parse_file(file_path: Path) -> str:
    """根据文件类型解析内容"""
    ext = file_path.suffix.lower()

    if ext == '.txt':
        print(f"  解析 TXT 文件...")
        return file_path.read_text(encoding='utf-8')

    if ext == '.pdf':
        import pdfplumber
        print(f"  解析 PDF 文件...")
        parts = []
        with pdfplumber.open(str(file_path)) as pdf:
            total = len(pdf.pages)
            print(f"  共 {total} 页")
            for i, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if text:
                    parts.append(text)
                if i % 50 == 0:
                    print(f"  已解析 {i}/{total} 页...")
        content = "\n\n".join(parts)
        print(f"  总字符数: {len(content):,}")
        return content

    if ext in ('.docx', '.doc'):
        from docx import Document
        print(f"  解析 Word 文件...")
        doc = Document(str(file_path))
        parts = [p.text for p in doc.paragraphs if p.text.strip()]
        content = "\n\n".join(parts)
        print(f"  总字符数: {len(content):,}")
        return content

    raise ValueError(f"不支持的文件类型: {ext}")


# ============================================================
# 分块策略
# ============================================================

def chunk_auto(content: str, doc_title: str, category: str, chunk_size: int, overlap: int) -> list:
    """自动选择分块策略"""
    # 检测法条结构
    article_pattern = re.compile(r'第[一二三四五六七八九十百千零０-９\d]+条')
    article_matches = list(article_pattern.finditer(content))
    if len(article_matches) >= 5:
        print(f"  检测到 {len(article_matches)} 个法条标记，使用法条分块策略")
        return chunk_legal(content, doc_title, category, chunk_size)

    # 检测标题结构
    heading_pattern = re.compile(
        r'^(?:#{1,4}\s+.+|第[一二三四五六七八九十百千]+(?:编|分编|章|节|部分)\s*.+|[一二三四五六七八九十]+[、.]\s*.+)',
        re.MULTILINE
    )
    heading_matches = list(heading_pattern.finditer(content))
    if len(heading_matches) >= 3:
        print(f"  检测到 {len(heading_matches)} 个标题，使用标题分块策略")
        return chunk_heading(content, doc_title, category, chunk_size)

    print(f"  未检测到特殊结构，使用通用分块策略")
    return chunk_generic(content, doc_title, category, chunk_size, overlap)


def chunk_legal(content: str, doc_title: str, category: str, chunk_size: int) -> list:
    """法律文档分块 - 按"第X条"分割"""
    article_pattern = re.compile(r'(第[一二三四五六七八九十百千零０-９\d]+条)')
    matches = list(article_pattern.finditer(content))

    # 跳过目录：找到正文起点
    content_start = 0
    for m in matches:
        after = content[m.end():m.end() + 80]
        first_line = after.split('\n')[0].strip()
        if len(first_line) > 10:
            content_start = m.start()
            break

    if content_start > 0:
        print(f"  跳过目录，正文起始位置: 字符 {content_start}")

    body = content[content_start:]
    body_matches = list(article_pattern.finditer(body))

    # 追踪章节
    chapter_pattern = re.compile(r'(第[一二三四五六七八九十百千]+(?:编|分编|章|节))\s*(.+)')
    chapter_matches = list(chapter_pattern.finditer(body))
    current_chapter = category

    chunks = []
    for i, match in enumerate(body_matches):
        start = match.start()
        end = body_matches[i + 1].start() if i + 1 < len(body_matches) else len(body)
        text = body[start:end].strip()

        if not text:
            continue

        article_num = match.group(1)

        # 更新当前章节
        for cm in chapter_matches:
            if cm.start() < start:
                current_chapter = cm.group(2).strip()

        title = f"{doc_title} {article_num}"

        # 长条文拆分
        if len(text) > chunk_size * 2:
            sub_chunks = _split_long_text(text, title, category, chunk_size)
            chunks.extend(sub_chunks)
        else:
            chunks.append({'title': title, 'content': text, 'category': f"{category}-{current_chapter}"})

    # 合并过短的块
    chunks = _merge_short_chunks(chunks, chunk_size, doc_title)
    print(f"  法条分块完成: {len(chunks)} 个块")
    return chunks


def chunk_heading(content: str, doc_title: str, category: str, chunk_size: int) -> list:
    """按标题/章节分块 - 适合技术文档、论文、合同"""
    heading_pattern = re.compile(
        r'^(#{1,4}\s+.+|第[一二三四五六七八九十百千]+(?:编|分编|章|节|部分)\s*.+|[一二三四五六七八九十]+[、.]\s*.+|\d+[、.]\s*.+)',
        re.MULTILINE
    )

    matches = list(heading_pattern.finditer(content))

    if not matches:
        return chunk_generic(content, doc_title, category, chunk_size, 80)

    chunks = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        text = content[start:end].strip()

        if not text:
            continue

        # 提取标题文本
        heading_text = match.group(1).lstrip('#').strip()
        title = f"{doc_title} - {heading_text}"

        if len(text) > chunk_size * 2:
            sub_chunks = _split_long_text(text, title, category, chunk_size)
            chunks.extend(sub_chunks)
        else:
            chunks.append({'title': title, 'content': text, 'category': category})

    # 处理第一个标题之前的内容
    if matches[0].start() > 50:
        preamble = content[:matches[0].start()].strip()
        if preamble:
            chunks.insert(0, {'title': f"{doc_title} - 前言", 'content': preamble, 'category': category})

    chunks = _merge_short_chunks(chunks, chunk_size, doc_title)
    print(f"  标题分块完成: {len(chunks)} 个块")
    return chunks


def chunk_generic(content: str, doc_title: str, category: str, chunk_size: int, overlap: int) -> list:
    """通用分块 - 固定窗口 + 句子边界对齐"""
    chunks = []
    start = 0

    while start < len(content):
        end = start + chunk_size

        # 在句子边界处断开
        if end < len(content):
            for sep in ['。\n', '\n\n', '。', '；', '\n', '，']:
                pos = content[start:end].rfind(sep)
                if pos > chunk_size * 0.3:  # 至少用掉 30% 的窗口
                    end = start + pos + len(sep)
                    break

        text = content[start:end].strip()
        if text:
            chunks.append({
                'title': f"{doc_title} - 段落{len(chunks) + 1}",
                'content': text,
                'category': category,
            })

        start = end - overlap

    print(f"  通用分块完成: {len(chunks)} 个块")
    return chunks


# ============================================================
# 分块辅助函数
# ============================================================

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
    min_size = 80
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
        if merged and len(buf['content']) < min_size:
            merged[-1]['content'] += "\n" + buf['content']
        else:
            merged.append(buf)

    return merged


# ============================================================
# 向量化 & 存储
# ============================================================

def embed_chunks(chunks: list, batch_size: int) -> list:
    """批量向量化"""
    from zhipuai import ZhipuAI

    client = ZhipuAI(api_key=ZHIPU_API_KEY)
    all_embeddings = []
    total_batches = (len(chunks) - 1) // batch_size + 1

    for i in range(0, len(chunks), batch_size):
        batch = [c['content'] for c in chunks[i:i + batch_size]]
        batch_num = i // batch_size + 1

        try:
            response = client.embeddings.create(model="embedding-3", input=batch)
            all_embeddings.extend([item.embedding for item in response.data])
        except Exception as e:
            print(f"  批次 {batch_num} 失败: {e}，重试...")
            time.sleep(2)
            response = client.embeddings.create(model="embedding-3", input=batch)
            all_embeddings.extend([item.embedding for item in response.data])

        if batch_num % 10 == 0 or batch_num == total_batches:
            print(f"  向量化进度: {batch_num}/{total_batches}")

        if i + batch_size < len(chunks):
            time.sleep(0.3)

    return all_embeddings


def store_to_chroma(collection_name: str, chunks: list, embeddings: list, drop_existing: bool):
    """存入 ChromaDB"""
    from service.rag.chroma_store import get_chroma_store

    store = get_chroma_store()
    print(f"  ChromaDB 连接成功")

    if drop_existing and store.collection_exists(collection_name):
        print(f"  删除旧 Collection: {collection_name}")
        store.delete_collection(collection_name)

    inserted = store.insert_chunks(
        collection=collection_name,
        chunks=chunks,
        embeddings=embeddings,
    )

    print(f"  数据插入成功，实体数: {inserted}")
    return inserted


# ============================================================
# CLI 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description='通用文档入库工具 - 解析、分块、向量化、存入 ChromaDB',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/ingest.py "D:\\Downloads\\民法典.pdf" --collection minfadian
  python scripts/ingest.py report.docx --collection reports --strategy heading
  python scripts/ingest.py notes.txt --collection notes --strategy generic --chunk-size 500
        """
    )

    parser.add_argument('file', type=str, help='要入库的文件路径 (PDF/DOCX/TXT)')
    parser.add_argument('--collection', '-c', required=True, help='目标 Collection 名称 (自动加 legal_ 前缀)')
    parser.add_argument('--strategy', '-s', choices=['auto', 'legal', 'heading', 'generic'],
                        default='auto', help='分块策略 (默认: auto)')
    parser.add_argument('--chunk-size', type=int, default=800, help='最大块大小 (默认: 800)')
    parser.add_argument('--overlap', type=int, default=80, help='重叠字符数, generic 模式用 (默认: 80)')
    parser.add_argument('--batch-size', type=int, default=8, help='embedding 批大小 (默认: 8)')
    parser.add_argument('--category', type=str, default='', help='文档分类 (默认: 用文件名)')
    parser.add_argument('--drop', action='store_true', help='删除已有同名 Collection 后重建')

    args = parser.parse_args()

    # 校验文件
    file_path = Path(args.file)
    if not file_path.exists():
        print(f"错误: 文件不存在: {file_path}")
        sys.exit(1)

    ext = file_path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        print(f"错误: 不支持的文件类型 {ext}，支持: {', '.join(SUPPORTED_EXTENSIONS)}")
        sys.exit(1)

    # Collection 名称
    collection_name = args.collection
    if not collection_name.startswith('legal_'):
        collection_name = f'legal_{collection_name}'

    doc_title = file_path.stem
    category = args.category or doc_title

    # 开始
    print("=" * 70)
    print(f"文档入库工具")
    print("=" * 70)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"文件: {file_path}")
    print(f"Collection: {collection_name}")
    print(f"策略: {args.strategy}")
    print(f"块大小: {args.chunk_size} | 重叠: {args.overlap} | 批大小: {args.batch_size}")
    print()

    # 1. 解析
    print("[1/4] 解析文档")
    print("-" * 70)
    content = parse_file(file_path)
    if not content or len(content.strip()) < 10:
        print("错误: 文档内容为空")
        sys.exit(1)
    print()

    # 2. 分块
    print("[2/4] 智能分块")
    print("-" * 70)
    strategy_map = {
        'auto': chunk_auto,
        'legal': lambda c, t, cat, cs, ov: chunk_legal(c, t, cat, cs),
        'heading': lambda c, t, cat, cs, ov: chunk_heading(c, t, cat, cs),
        'generic': chunk_generic,
    }
    chunks = strategy_map[args.strategy](content, doc_title, category, args.chunk_size, args.overlap)

    # 预览
    print(f"\n  前 3 个块预览:")
    for c in chunks[:3]:
        print(f"    [{c['title']}] {c['content'][:60]}...")
    print()

    # 3. 向量化
    print("[3/4] 向量化 (ZhipuAI Embedding-3)")
    print("-" * 70)
    embeddings = embed_chunks(chunks, args.batch_size)
    print(f"  完成: {len(embeddings)} 个向量, 维度 {len(embeddings[0])}")
    print()

    # 4. 存入 ChromaDB
    print("[4/4] 存入 ChromaDB")
    print("-" * 70)
    total = store_to_chroma(collection_name, chunks, embeddings, args.drop)
    print()

    # 完成
    print("=" * 70)
    print(f"入库完成!")
    print(f"  Collection: {collection_name}")
    print(f"  块数量: {len(chunks)}")
    print(f"  总实体数: {total}")
    print(f"  分块策略: {args.strategy}")
    print("=" * 70)


if __name__ == '__main__':
    main()
