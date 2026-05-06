# RAG 法条检索系统 - 使用指南

## 📦 一、安装依赖

```bash
cd backend
.venv\Scripts\Activate.ps1

# 安装 LangChain 相关依赖
pip install -r requirements.txt
```

## ⚙️ 二、环境变量配置

确保 `.env` 文件中配置了以下变量：

```bash
# OpenAI 兼容接口（支持百炼）
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1  # 百炼地址（可选）

# 嵌入模型（可选，默认 text-embedding-3-small）
EMBEDDING_MODEL=text-embedding-3-small
```

**支持的服务商**：
- OpenAI（默认）
- 阿里云百炼（通过 `OPENAI_BASE_URL` 配置）
- 其他 OpenAI 兼容接口

## 🚀 三、初始化向量存储

### 3.1 导入示例法条

```bash
python scripts/init_vectorstore.py
```

这将：
1. 创建 `data/vectorstore` 目录
2. 导入示例法条（民法典、劳动法、刑法等）
3. 生成向量嵌入并存储
4. 测试检索功能

### 3.2 查看向量存储状态

```python
from app.langchain_integration.rag.vector_store import get_vectorstore

vectorstore = get_vectorstore()
print(vectorstore.get_stats())
# 输出：{'available': True, 'document_count': 17, 'persist_dir': 'data/vectorstore'}
```

## 📚 四、导入更多法条

### 4.1 修改法条数据文件

编辑 `app/langchain_integration/rag/legal_articles.py`，添加更多法条：

```python
CUSTOM_ARTICLES = [
    {
        "title": "中华人民共和国 XXX 法",
        "article_number": "第 X 条",
        "content": "法条内容...",
        "category": "类别"
    },
    # 更多法条...
]

def get_all_sample_articles() -> list:
    return CIVIL_CODE_ARTICLES + LABOR_LAW_ARTICLES + CRIMINAL_LAW_ARTICLES + CUSTOM_ARTICLES
```

### 4.2 从外部数据源导入

创建自定义导入脚本：

```python
# scripts/import_custom_articles.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.langchain_integration.rag.vector_store import LegalVectorStore

vectorstore = LegalVectorStore()

# 你的法条数据
articles = [
    {"title": "...", "article_number": "...", "content": "...", "category": "..."},
    # ...
]

vectorstore.add_law_articles(articles)
```

## 🔍 五、测试 RAG 检索

### 5.1 命令行测试

```bash
python scripts/init_vectorstore.py
```

脚本最后会执行测试检索，显示类似输出：

```
🔍 测试检索示例：

查询：'拖欠工资怎么办'
  - 中华人民共和国劳动法 第 50 条
  - 中华人民共和国劳动合同法 第 85 条

查询：'离婚的条件'
  - 中华人民共和国民法典 第 1079 条
```

### 5.2 Python 代码测试

```python
from app.langchain_integration.rag.vector_store import get_vectorstore

vectorstore = get_vectorstore()

# 简单检索
results = vectorstore.search("拖欠工资", k=3)
for doc in results:
    print(f"{doc.metadata['source']} {doc.metadata['article_number']}")
    print(f"内容：{doc.page_content}\n")

# 带分数检索
results = vectorstore.search_with_score("工伤赔偿", k=3)
for doc, score in results:
    print(f"相关度：{score:.4f} - {doc.metadata['article_number']}")
```

## 🎯 六、RAG 如何工作

### 6.1 运行时集成

RAG 已集成到 `app/core/runtime.py` 的 `send_message` 方法中：

```
用户提问（深度模式）
    ↓
1. 问题分类器判断启用工具
    ↓
2. Skill 检索（关键词匹配）
    ↓
3. RAG 法条检索（语义相似度）⭐ 新增
    ↓
4. 构建 System Prompt:
   - 基础人设
   - 文件内容（如果有）
   - 记忆上下文
   - 相关法条（RAG）⭐ 新增
   - 可用技能
    ↓
5. 调用 LLM（带工具支持）
    ↓
6. AI 回答（可引用法条）
```

### 6.2 日志输出

启用 RAG 后，你会看到类似日志：

```
🔍 RAG 检索到 5 条相关法条
📋 System Prompt 包含文件内容 (前 500 字符):...
```

## 📊 七、性能优化建议

### 7.1 向量存储优化

- **Chunk 大小**：法条较短，使用 500 字符（已配置）
- **重叠**：50 字符（已配置）
- **索引**：ChromaDB 自动管理

### 7.2 检索优化

```python
# 调整检索数量
results = vectorstore.search(query, k=3)  # 默认 5，可减少到 3

# 按法律类别过滤
results = vectorstore.search_by_metadata(
    query,
    filter_dict={"source": "中华人民共和国民法典"},
    k=3
)
```

### 7.3 缓存

可以考虑添加检索结果缓存（避免重复查询）：

```python
from functools import lru_cache

@lru_cache(maxsize=100)
def cached_search(query: str, k: int = 5):
    return vectorstore.search(query, k=k)
```

## 🔧 八、故障排查

### 问题 1：向量存储不可用

**症状**：日志显示 `向量存储不可用，返回空结果`

**原因**：`OPENAI_API_KEY` 未设置

**解决**：
```bash
# 检查.env 文件
cat .env | grep OPENAI_API_KEY

# 设置环境变量
$env:OPENAI_API_KEY="your_key"
```

### 问题 2：检索结果为空

**原因**：
- 向量存储为空（未导入法条）
- 查询与法条内容不相关

**解决**：
```bash
# 重新初始化
python scripts/init_vectorstore.py

# 检查统计信息
python -c "from app.langchain_integration.rag.vector_store import get_vectorstore; print(get_vectorstore().get_stats())"
```

### 问题 3：ChromaDB 错误

**症状**：`Error importing ChromaDB`

**解决**：
```bash
# 重新安装
pip uninstall chromadb chroma-hnswlib
pip install chromadb
```

## 📈 九、进阶用法

### 9.1 添加更多法律数据库

可以扩展 `legal_articles.py` 导入真实法律数据库：

- 国家法律法规数据库
- 北大法宝
- 法信

### 9.2 混合检索（关键词 + 语义）

```python
# 结合 BM25 和向量检索
from langchain.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever

bm25_retriever = BM25Retriever.from_documents(documents)
vector_retriever = vectorstore.as_retriever()

ensemble_retriever = EnsembleRetriever(
    retrievers=[bm25_retriever, vector_retriever],
    weights=[0.5, 0.5]
)
```

### 9.3 添加引用标注

在回答中自动标注法条来源：

```python
# 在 prompt 中添加要求
system_parts.append("""
回答时请准确引用上述法条，格式为：
"根据《XXX 法》第 X 条规定：..."
""")
```

## 🎓 十、最佳实践

1. **法条准确性**：定期同步最新法律法规
2. **检索质量**：监控检索结果相关度，调整 k 值
3. **性能**：向量存储初始化一次，后续持久化使用
4. **成本控制**：嵌入模型调用次数有限，批量导入更经济

---

**下一步**：运行 `python scripts/init_vectorstore.py` 开始使用 RAG！
