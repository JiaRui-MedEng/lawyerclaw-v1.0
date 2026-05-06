# 🔌 Tavily Search Skill 集成指南

> 如何将搜索技能集成到 AI 对话系统中

---

## 📋 集成步骤

### Step 1: 复制 Skill 文件

将 `tavily-web-search` 文件夹复制到 OpenClaw skills 目录：

```bash
# 源目录
D:\Projects\Pycharm\lawyerclaw\skills-zip\tavily-web-search

# 目标目录（示例）
~/.openclaw/workspace/skills/tavily-web-search
```

### Step 2: 确保依赖已安装

```bash
pip install tavily-python
```

### Step 3: 配置 API Key

编辑 `.env` 文件：
```bash
TAVILY_API_KEY=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
```

### Step 4: 在对话中自动触发

AI 会自动识别搜索意图并调用 Tavily 搜索。

---

## 🤖 AI 对话流程

### 完整流程

```
用户输入
    ↓
意图识别 (search_intent.py)
    ↓
┌─────────────────────────────┐
│  是否需要搜索？             │
│  - 是 → 调用 Tavily         │
│  - 否 → 使用本地知识        │
└─────────────────────────────┘
    ↓
生成回答
    ↓
返回给用户
```

### 代码示例

```python
from app.tools.search_intent import SearchIntentClassifier
from app.tools.tavily_search import TavilySearchTool

async def handle_user_query(query: str) -> str:
    """处理用户查询"""
    
    # 1. 判断是否需要搜索
    should_search, reason = SearchIntentClassifier.should_search(query)
    
    if should_search:
        print(f"🔍 触发搜索：{reason}")
        
        # 2. 获取搜索参数
        params = SearchIntentClassifier.get_search_params(query)
        
        # 3. 执行搜索
        tool = TavilySearchTool()
        result = await tool.execute(**params)
        
        if result.success:
            # 4. 基于搜索结果生成回答
            search_content = result.content
            answer = generate_answer_from_search(query, search_content)
            return answer
        else:
            return f"搜索失败：{result.error}"
    
    else:
        # 5. 使用本地知识回答
        return answer_with_local_knowledge(query)
```

---

## 🎯 意图识别规则

### 触发搜索的模式

```python
SEARCH_PATTERNS = [
    # 明确查询
    '帮我查询', '帮我搜索', '搜索一下', '查找一下',
    
    # 最新信息
    '最新的', '最近', '近期', '新出台', '新发布',
    
    # 年份
    '2024 年', '2025 年', '今年', '明年', '当前', '现在',
    
    # 新闻
    '新闻', '动态', '热点', '进展',
    
    # 法律
    '类似案例', '赔偿标准', '量刑标准', '司法解释',
]
```

### 不触发搜索的模式

```python
NON_SEARCH_PATTERNS = [
    '什么是', '定义', '含义', '意思',
    '怎么理解', '解释一下', '介绍一下',
    '历史', '什么时候颁布', '哪一年',
]
```

---

## 📊 智能参数优化

### 自动选择搜索深度

```python
if '研究' in query or '分析' in query:
    search_depth = "advanced"  # 深度搜索
else:
    search_depth = "basic"     # 快速搜索
```

### 自动限定域名

```python
if '法律' in query or '法规' in query:
    include_domains = ["gov.cn", "court.gov.cn", "npc.gov.cn"]

if '案例' in query or '判决' in query:
    include_domains = ["court.gov.cn", "chinacourt.org"]
```

### 自动排除低质内容

```python
if '新闻' in query or '热点' in query:
    exclude_domains = ["zhihu.com", "baike.baidu.com", "sohu.com"]
```

---

## 💬 对话示例

### 示例 1: 查询最新法律

```
用户：帮我查询 2024 年最新的工伤保险赔偿标准

AI（思考）：
- 检测到"帮我查询" → 触发搜索
- 检测到"2024 年最新" → 需要实时信息
- 检测到"工伤保险" → 法律相关，限定政府官网

AI（调用 Tavily）：
{
  "query": "2024 年 工伤保险 赔偿标准 最新",
  "search_depth": "basic",
  "limit": 5,
  "include_domains": ["gov.cn", "court.gov.cn"]
}

AI（回答）：
根据最新搜索结果，2024 年工伤保险赔偿标准如下：

🤖 AI 摘要：
2024 年全国一次性工亡补助金标准为 1,058,400 元，
较 2023 年上涨约 5%...

📊 主要调整：
1. 一次性工亡补助金：1,058,400 元
2. 伤残津贴：每月 XXX-XXX 元
3. 生活护理费：每月 XXX 元

信息来源：
- 人力资源社会保障部官网
- 各省市人社厅通知

⚠️ 提示：具体标准可能因地区而异，请咨询当地社保部门。
```

### 示例 2: 搜索类似案例

```
用户：搜索一下交通事故十级伤残的赔偿案例

AI（思考）：
- 检测到"搜索一下" → 触发搜索
- 检测到"案例" → 限定法院网站

AI（调用 Tavily）：
{
  "query": "交通事故 十级伤残 赔偿 案例",
  "search_depth": "advanced",
  "limit": 5,
  "include_domains": ["court.gov.cn", "chinacourt.org"]
}

AI（回答）：
找到以下类似案例：

📊 案例 1: 王某交通事故损害赔偿案
- 法院：北京市朝阳区人民法院
- 伤残等级：十级伤残
- 赔偿金额：医疗费 + 误工费 + 护理费 + 残疾赔偿金 = 约 15 万元
- 来源：最高人民法院公报

📊 案例 2: 李某交通事故案
- 法院：上海市浦东新区人民法院
- 伤残等级：十级伤残
- 赔偿金额：约 18 万元
- 来源：中国裁判文书网

💡 赔偿项目通常包括：
1. 医疗费
2. 误工费
3. 护理费
4. 残疾赔偿金
5. 精神损害抚慰金

注：具体金额因地区、年龄、收入等因素而异。
```

### 示例 3: 事实性问题（不触发搜索）

```
用户：什么是民法典？

AI（思考）：
- 检测到"什么是" → 事实性问题
- 不触发搜索，使用本地知识

AI（回答）：
《中华人民共和国民法典》是中华人民共和国的基本法律之一，
于 2020 年 5 月 28 日通过，2021 年 1 月 1 日起施行...

（使用本地知识库回答，不消耗 API 额度）
```

---

## 🔧 高级配置

### 自定义触发模式

编辑 `search_intent.py`：

```python
# 添加自定义触发词
SEARCH_PATTERNS.extend([
    '帮我找找', '查一查', '搜一下',
])

# 添加自定义排除词
NON_SEARCH_PATTERNS.extend([
    '原理', '机制', '背景',
])
```

### 自定义域名过滤

```python
# 添加专业法律数据库
LEGAL_DOMAINS = [
    "gov.cn",
    "court.gov.cn",
    "pkulaw.com",      # 北大法宝
    "lawinfochina.com" # 法律信息网
]
```

### 调整缓存时间

```python
# tavily_search.py
class TavilySearchTool:
    def __init__(self):
        self._cache_ttl = timedelta(minutes=60)  # 改为 60 分钟
```

---

## 📈 监控与优化

### 监控指标

```python
# 记录搜索统计
stats = {
    "total_searches": 0,
    "successful_searches": 0,
    "cached_searches": 0,
    "api_cost": 0.0,
}
```

### 优化建议

1. **缓存命中率**
   - 目标：>30%
   - 方法：延长缓存时间

2. **搜索成功率**
   - 目标：>95%
   - 方法：优化查询词

3. **用户满意度**
   - 收集反馈
   - 调整搜索策略

---

## ⚠️ 错误处理

### API Key 无效

```python
if not tool.is_available():
    return "搜索功能暂时不可用，请稍后再试。"
```

### 搜索失败

```python
if not result.success:
    logger.error(f"搜索失败：{result.error}")
    return "抱歉，搜索遇到问题，请尝试其他关键词。"
```

### 无结果

```python
if not result.data.get('results'):
    return "未找到相关结果，请尝试其他关键词。"
```

---

## 📚 相关文档

- **Skill 定义：** `SKILL.md`
- **使用手册：** `README.md`
- **API 文档：** `docs/TAVILY_SEARCH.md`
- **意图识别：** `app/tools/search_intent.py`

---

**最后更新：** 2024-04-15
