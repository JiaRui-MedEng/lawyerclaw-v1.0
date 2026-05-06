---
name: tavily-web-search
description: "Search the web for latest information using Tavily AI. Use when: user asks to '查询', '搜索', '查找', '帮我看看', or requests current/latest news, laws, cases, or real-time information. NOT for: historical data, static knowledge, or file operations."
homepage: https://docs.tavily.com
required_environment_variables:
  - name: TAVILY_API_KEY
    prompt: 输入 Tavily API 密钥
    help: https://tavily.com/
    value: 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
metadata:
  {
    "openclaw":
      {
        "emoji": "🔍",
        "requires": { "env": ["TAVILY_API_KEY"] },
        "install":
          [
            {
              "id": "tavily-py",
              "kind": "pip",
              "package": "tavily-python",
              "label": "Install Tavily Python SDK",
            },
          ],
      },
  }
---

# Tavily Web Search Skill

Search the internet for latest information using Tavily AI search engine.

## When to Use

✅ **USE this skill when:**

- "帮我查询..." (Help me search...)
- "搜索一下..." (Search for...)
- "查找最新的..." (Find the latest...)
- "帮我看看..." (Help me check...)
- "最近有什么..." (What's recent...)
- "2024/2025 年最新..." (Latest 2024/2025...)
- "现在的..." (Current...)
- "最新新闻/案例/法规" (Latest news/cases/laws)
- Questions requiring real-time or current information
- Legal research needing latest regulations or cases

## When NOT to Use

❌ **DON'T use this skill when:**

- Historical facts (e.g., "民法典什么时候颁布的") → Use knowledge
- File operations (read/write files) → Use file tools
- Mathematical calculations → Use calculator
- Code generation → Use coding tools
- Static knowledge (e.g., "什么是刑法") → Use knowledge
- Local data queries → Use database tools

## Trigger Patterns

识别以下用户意图时调用此技能：

### 1. 明确查询请求
- "帮我查询 [关键词]"
- "搜索一下 [关键词]"
- "查找 [关键词] 的相关信息"
- "帮我看看 [关键词]"

### 2. 最新信息请求
- "最新的 [主题]"
- "2024/2025 年 [主题]"
- "最近 [主题] 有什么变化"
- "现在 [主题] 的情况"

### 3. 实时信息请求
- "今天/本周/本月 [主题]"
- "[主题] 的最新动态"
- "[主题] 的进展情况"

### 4. 法律专业查询
- "最新法律法规"
- "最新司法解释"
- "类似案例"
- "赔偿标准"
- "量刑标准"

## Search Parameters

### search_depth
- `basic` (默认): 快速搜索，适合日常查询
- `advanced`: 深度搜索，适合复杂问题研究

### limit
- 默认：5 条结果
- 范围：1-10 条
- 建议：3-5 条（避免信息过载）

### include_domains (可选)
限定搜索特定网站：
- `["gov.cn", "court.gov.cn"]` - 政府/法院官网
- `["pkulaw.com"]` - 北大法宝

### exclude_domains (可选)
排除低质量网站：
- `["zhihu.com", "baike.baidu.com", "sohu.com"]`

## Examples

### Example 1: 查询最新法律
**User:** "帮我查询 2024 年最新的工伤保险赔偿标准"

**Assistant:** 调用 tavily-web-search
```python
query = "2024 年 工伤保险 赔偿标准 最新"
search_depth = "basic"
limit = 5
include_domains = ["gov.cn", "court.gov.cn"]
```

### Example 2: 搜索类似案例
**User:** "搜索一下交通事故十级伤残的赔偿案例"

**Assistant:** 调用 tavily-web-search
```python
query = "交通事故 十级伤残 赔偿 案例"
search_depth = "advanced"
limit = 5
include_domains = ["court.gov.cn", "chinacourt.org"]
```

### Example 3: 查找最新动态
**User:** "最近律师法有什么新修订吗？"

**Assistant:** 调用 tavily-web-search
```python
query = "律师法 修订 2024 最新"
search_depth = "basic"
limit = 5
```

### Example 4: 查询新闻
**User:** "帮我看看最近有什么法律热点新闻"

**Assistant:** 调用 tavily-web-search
```python
query = "法律 热点 新闻 2024"
search_depth = "basic"
limit = 5
exclude_domains = ["zhihu.com", "baike.baidu.com"]
```

## Response Format

搜索结果应包含：

1. **AI 摘要** (如果有)
   - Tavily 生成的智能摘要
   - 概括搜索主题

2. **搜索结果列表**
   ```
   [1] 标题
       来源：域名
       URL: 完整链接
       相关性：评分
       摘要：内容摘要 (300 字以内)
   ```

3. **综合回答**
   - 基于搜索结果回答问题
   - 引用来源
   - 提醒用户核实重要信息

## Error Handling

### API Key 无效
```
错误：Tavily API Key 未配置或无效
解决：请设置环境变量 TAVILY_API_KEY
```

### 搜索失败
```
错误：搜索失败 [错误信息]
解决：尝试简化查询词或使用 basic 模式
```

### 无结果
```
提示：未找到相关结果
建议：尝试不同的关键词或扩大搜索范围
```

## Best Practices

1. **自动判断搜索深度**
   - 简单问题 → `basic`
   - 复杂研究 → `advanced`

2. **智能域名过滤**
   - 法律查询 → 限定政府官网
   - 新闻查询 → 排除低质媒体

3. **结果数量控制**
   - 默认 5 条
   - 复杂问题可到 10 条
   - 简单问题 3 条即可

4. **缓存利用**
   - 相同查询 30 分钟内自动使用缓存
   - 避免重复 API 调用

5. **来源标注**
   - 始终标注信息来源
   - 提醒用户核实重要信息

## Integration

### Python 调用
```python
from app.tools.tavily_search import TavilySearchTool

tool = TavilySearchTool()
result = await tool.execute(
    query="查询关键词",
    search_depth="basic",
    limit=5
)

if result.success:
    print(result.content)  # 格式化的搜索结果
else:
    print(f"搜索失败：{result.error}")
```

### 意图识别
在对话中识别以下关键词触发搜索：
- 查询、搜索、查找、帮我看看
- 最新、最近、现在、当前
- 2024、2025（年份）
- 新闻、案例、法规、标准

## Cost

- **Free Plan:** 1000 次/月
- **Starter Plan:** $25/月 (10000 次)
- **缓存:** 30 分钟内相同查询不消耗额度

## Security

- ✅ API Key 通过环境变量管理
- ✅ 不记录用户查询内容
- ✅ 域名过滤防止低质内容
- ✅ 速率限制防止滥用

## Troubleshooting

### Q: 搜索结果为空？
A: 尝试简化查询词，或使用更通用的关键词

### Q: 搜索结果不相关？
A: 使用 `include_domains` 限定权威来源

### Q: API 调用失败？
A: 检查 `TAVILY_API_KEY` 是否有效

## Related Skills

- `legal-research` - 法律专业检索
- `file-reader` - 读取本地文件
- `document-parser` - 解析文档

## Version

- **Current:** 1.0.0
- **Last Updated:** 2024-04-15
- **SDK:** tavily-python>=0.3.0
