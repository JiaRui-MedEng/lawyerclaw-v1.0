# 🔍 Tavily Web Search Skill

> **版本：** 1.0.0  
> **功能：** 互联网搜索 - 查询最新信息、法律法规、司法案例、新闻动态  
> **触发：** "帮我查询..."、"搜索..."、"最新的..."等

---

## 📋 功能说明

当用户表达以下意图时，自动调用 Tavily 互联网搜索：

### ✅ 触发场景

1. **明确查询请求**
   - "帮我查询 [关键词]"
   - "搜索一下 [关键词]"
   - "查找 [关键词] 的相关信息"
   - "帮我看看 [关键词]"

2. **最新信息请求**
   - "最新的 [主题]"
   - "2024/2025 年 [主题]"
   - "最近 [主题] 有什么变化"
   - "现在 [主题] 的情况"

3. **法律专业查询**
   - "最新法律法规"
   - "最新司法解释"
   - "类似案例"
   - "赔偿标准"
   - "量刑标准"

### ❌ 不触发场景

- 事实性问题："什么是民法典"
- 历史问题："民法典什么时候颁布"
- 定义问题："刑法的定义是什么"
- 介绍问题："介绍一下合同法"

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install tavily-python
```

### 2. 配置 API Key

编辑 `.env` 文件：
```bash
TAVILY_API_KEY=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
```

### 3. 自动触发

在对话中，AI 会自动识别搜索意图并调用此技能。

**示例对话：**

用户：`帮我查询 2024 年最新的工伤保险赔偿标准`

AI：（自动调用 Tavily 搜索）→ 返回最新标准

---

## 💡 使用示例

### 示例 1: 查询最新法律

```
用户：帮我查询 2024 年最新的工伤保险赔偿标准

AI 思考：
- 检测到"帮我查询" → 触发搜索
- 检测到"2024 年最新" → 需要实时信息
- 检测到"工伤保险" → 法律相关，限定政府官网

调用参数：
{
  "query": "2024 年 工伤保险 赔偿标准 最新",
  "search_depth": "basic",
  "limit": 5,
  "include_domains": ["gov.cn", "court.gov.cn"]
}

返回：
🤖 AI 摘要：2024 年全国工伤保险赔偿标准有所调整...

📊 搜索结果（共 5 条）：
[1] 人力资源社会保障部关于 2024 年工伤保险待遇标准的通知
    来源：gov.cn
    URL: https://www.gov.cn/...
    摘要：...
```

### 示例 2: 搜索类似案例

```
用户：搜索一下交通事故十级伤残的赔偿案例

AI 思考：
- 检测到"搜索一下" → 触发搜索
- 检测到"案例" → 限定法院网站

调用参数：
{
  "query": "交通事故 十级伤残 赔偿 案例",
  "search_depth": "advanced",
  "limit": 5,
  "include_domains": ["court.gov.cn", "chinacourt.org"]
}
```

### 示例 3: 查找最新动态

```
用户：最近律师法有什么新修订吗？

AI 思考：
- 检测到"最近" → 触发搜索
- 检测到"新修订" → 需要最新信息

调用参数：
{
  "query": "律师法 修订 2024 最新",
  "search_depth": "basic",
  "limit": 5
}
```

---

## 🔧 技术实现

### 意图识别

使用 `app/tools/search_intent.py` 自动识别搜索意图：

```python
from app.tools.search_intent import SearchIntentClassifier

query = "帮我查询 2024 年最新的工伤保险赔偿标准"

# 判断是否需要搜索
should_search, reason = SearchIntentClassifier.should_search(query)
# 返回：(True, "匹配模式：帮我查询")

# 获取搜索参数
params = SearchIntentClassifier.get_search_params(query)
# 返回：{
#   "query": "...",
#   "search_depth": "basic",
#   "limit": 5,
#   "include_domains": ["gov.cn", ...]
# }
```

### 搜索执行

```python
from app.tools.tavily_search import TavilySearchTool

tool = TavilySearchTool()
result = await tool.execute(**params)

if result.success:
    print(result.content)  # 格式化的搜索结果
```

---

## 📊 搜索参数

### search_depth
- **basic** (默认): 快速搜索 (~300ms)
- **advanced**: 深度搜索 (~2-3s)

### limit
- 默认：5 条
- 范围：1-10 条
- 建议：3-5 条

### include_domains (可选)
限定搜索特定网站：
```python
["gov.cn", "court.gov.cn", "npc.gov.cn"]
```

### exclude_domains (可选)
排除低质量网站：
```python
["zhihu.com", "baike.baidu.com", "sohu.com"]
```

---

## 🎯 自动优化

### 智能域名过滤

| 查询类型 | 自动限定域名 |
|---------|-------------|
| 法律法规 | gov.cn, court.gov.cn, npc.gov.cn |
| 司法案例 | court.gov.cn, chinacourt.org |
| 新闻热点 | 排除 zhihu.com, baike.baidu.com |

### 智能搜索深度

| 关键词 | 自动选择 |
|--------|---------|
| 研究、分析、详细 | advanced |
| 简单、大概、快速 | basic |

### 智能结果数量

| 关键词 | 自动设置 |
|--------|---------|
| 详细、全面 | 10 条 |
| 简单、大概 | 3 条 |
| 默认 | 5 条 |

---

## 💰 成本说明

### 免费计划
- **额度：** 1000 次/月
- **日均：** 33 次/天
- **适合：** 开发测试 + 小范围使用

### Starter 计划
- **价格：** $25/月
- **额度：** 10,000 次/月
- **适合：** 小规模应用

### 优化建议
1. **使用缓存** - 相同查询 30 分钟内不重复调用
2. **basic 模式** - 除非需要深度搜索
3. **限制结果数** - 默认 5 条即可

---

## ⚠️ 注意事项

### 1. 内容准确性
- Tavily 返回互联网公开信息
- ✅ 适合查询最新动态
- ⚠️ 重要信息需人工核实
- ❌ 不能直接作为法律意见

### 2. 来源标注
- 始终标注信息来源
- 优先引用政府官网
- 提醒用户核实重要信息

### 3. 额度管理
- 监控地址：https://app.tavily.com/dashboard
- 缓存机制：30 分钟自动缓存
- 告警设置：接近限额时通知

---

## 🧪 测试

### 测试意图识别
```bash
cd D:\Projects\Pycharm\lawyerclaw\backend
python app\tools\search_intent.py
```

### 测试搜索功能
```bash
python test_fixed_tavily.py
python test_legal_search.py
```

---

## 📚 相关文件

| 文件 | 说明 |
|------|------|
| `SKILL.md` | Skill 定义文件 |
| `README.md` | 本文档 |
| `app/tools/tavily_search.py` | Tavily 搜索工具 |
| `app/tools/search_intent.py` | 意图识别模块 |
| `docs/TAVILY_SEARCH.md` | 完整使用手册 |

---

## 🔗 相关链接

- **Tavily 官网：** https://app.tavily.com
- **官方文档：** https://docs.tavily.com
- **Dashboard:** https://app.tavily.com/dashboard

---

## 📝 更新日志

### v1.0.0 (2024-04-15)
- ✅ 初始版本发布
- ✅ Tavily API 集成
- ✅ 意图识别模块
- ✅ 自动域名过滤
- ✅ 智能参数优化

---

**创建者：** 百佑 LawyerClaw Team  
**最后更新：** 2024-04-15
