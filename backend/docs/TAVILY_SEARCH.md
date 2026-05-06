# Tavily AI 搜索使用指南

## 📦 快速开始

### 1. 安装依赖

```bash
cd D:\Projects\Pycharm\lawyerclaw\backend

pip install tavily-python
```

### 2. 获取 API Key

1. 访问 https://app.tavily.com
2. 注册账号（支持 Google/GitHub 登录）
3. 进入 Dashboard → API Keys
4. 创建新的 API Key
5. 复制到 `.env` 文件：

```bash
# .env
TAVILY_API_KEY=tvly-xxxxxxxxxxxxxxxxxxxxxxxx
```

### 3. 测试搜索

```bash
python -m app.tools.tavily_search
```

---

## 🔧 Python 代码使用

### 基础用法

```python
from app.tools.tavily_search import TavilySearchTool
import asyncio

async def main():
    tool = TavilySearchTool()
    
    # 执行搜索
    result = await tool.execute(
        query="2024 年最新民法典司法解释",
        search_depth="basic",
        limit=5
    )
    
    if result.success:
        print(result.content)  # 格式化的搜索结果
        print(result.data)     # 原始数据（dict）
    else:
        print(f"搜索失败：{result.error}")

asyncio.run(main())
```

### 法律专业搜索

```python
from app.tools.tavily_search import TavilySearchTool, LegalSearchPreset
import asyncio

async def main():
    tool = TavilySearchTool()
    
    # 搜索法律法规（限定政府官网）
    law_preset = LegalSearchPreset.search_law("工伤保险条例 2024")
    result = await tool.execute(**law_preset)
    print("法律法规搜索结果：", result.content)
    
    # 搜索司法案例
    case_preset = LegalSearchPreset.search_case("交通事故 十级伤残")
    result = await tool.execute(**case_preset)
    print("案例搜索结果：", result.content)
    
    # 搜索法律新闻
    news_preset = LegalSearchPreset.search_news("律师法 修订")
    result = await tool.execute(**news_preset)
    print("新闻搜索结果：", result.content)

asyncio.run(main())
```

### 限定搜索范围

```python
# 只搜索政府网站
result = await tool.execute(
    query="个人所得税法",
    include_domains=["gov.cn", "court.gov.cn", "npc.gov.cn"],
    search_depth="advanced"
)

# 排除低质量网站
result = await tool.execute(
    query="婚姻法司法解释",
    exclude_domains=["zhihu.com", "baike.baidu.com", "sohu.com"]
)
```

---

## 🤖 在对话中自动使用

Tavily 搜索已集成到百佑 LawyerClaw 工具系统，AI 会自动判断何时使用互联网搜索。

### 示例对话

**用户：** "2024 年最新的工伤赔偿标准是什么？"

**AI 思考过程：**
1. 检测到"2024 年最新" → 需要实时信息
2. 自动调用 `tavily_search` 工具
3. 搜索"2024 年工伤赔偿标准 最新"
4. 返回搜索结果 + AI 摘要

**AI 回复：**
```
根据最新搜索结果，2024 年工伤赔偿标准如下：

🤖 AI 摘要：
2024 年全国一次性工亡补助金标准为 52,920 元×20=1,058,400 元，
较 2023 年上涨约 5%...

📊 搜索结果（共 5 条）：
[1] 人力资源社会保障部关于 2024 年工伤保险待遇标准的通知
    来源：gov.cn
    URL: https://www.gov.cn/...
    日期：2024-01-15
    摘要：各省、自治区、直辖市及新疆生产建设兵团人力资源社会保障厅（局）...
```

---

## 📊 API 限制与优化

### 免费额度

- **1000 次/月** ≈ 33 次/天
- 适合开发测试和小规模使用

### 缓存机制

TavilySearchTool 内置 30 分钟缓存，相同查询不会重复调用 API。

```python
# 第一次调用 → 调用 API
result1 = await tool.execute("民法典 诉讼时效")

# 30 分钟内相同查询 → 使用缓存
result2 = await tool.execute("民法典 诉讼时效")  # 不消耗额度
```

### 优化建议

1. **使用 `basic` 深度**（除非需要深度搜索）
   ```python
   search_depth="basic"  # 更快，更便宜
   ```

2. **限制结果数量**
   ```python
   limit=3  # 默认 5，最多 10
   ```

3. **使用缓存**
   - 相同查询 30 分钟内自动缓存
   - 可手动扩展缓存时间

4. **批量查询**
   ```python
   # 一次查询多个相关问题
   query="2024 年 工伤 赔偿 标准 最新"
   ```

---

## 🔍 搜索参数详解

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `query` | string | - | 搜索关键词（必填） |
| `search_depth` | string | "basic" | "basic" 或 "advanced" |
| `limit` | int | 5 | 返回结果数（1-10） |
| `include_domains` | list | [] | 限定搜索的域名 |
| `exclude_domains` | list | [] | 排除的域名 |

### search_depth 对比

| 深度 | 速度 | 质量 | 成本 | 适用场景 |
|------|------|------|------|---------|
| **basic** | ~300ms | ⭐⭐⭐ | 1x | 日常查询 |
| **advanced** | ~2-3s | ⭐⭐⭐⭐⭐ | 2x | 深度研究 |

---

## 💰 升级到付费计划

当免费额度不够用时：

### Starter 计划（$25/月）
- 10,000 次/月搜索
- 适合小型应用
- 约 0.0025 美元/次

### Pro 计划（$250/月）
- 100,000 次/月搜索
- 适合商业应用
- 约 0.0025 美元/次

### 计费示例

假设百佑 LawyerClaw 每天有 100 个用户，每人搜索 2 次：
- 每天：200 次
- 每月：6,000 次
- **费用：$15/月**（在 Starter 计划内）

---

## ⚠️ 注意事项

### 1. API Key 安全

```bash
# ✅ 正确：使用环境变量
TAVILY_API_KEY=tvly-xxx

# ❌ 错误：硬编码到代码
api_key = "tvly-xxx"  # 不要提交到 Git
```

### 2. 内容准确性

Tavily 返回的是互联网公开信息，**不保证法律准确性**：
- ✅ 适合查询最新法规、案例
- ⚠️ 需要人工核实重要信息
- ❌ 不能作为法律意见直接使用

### 3. 速率限制

- Free: 3 次/秒
- Starter: 10 次/秒
- Pro: 50 次/秒

如果超过限制，API 会返回 429 错误。

---

## 🆚 Tavily vs 其他搜索方案

| 特性 | Tavily | Brave Search | Google Custom Search |
|------|--------|-------------|---------------------|
| **免费额度** | 1000/月 | 2500/月 | 100/天 |
| **AI 摘要** | ✅ | ❌ | ❌ |
| **内容提取** | ✅ | ❌ | ❌ |
| **价格** | $25/10k | $3/1k | $5/1k |
| **中文支持** | ✅ | ⚠️ | ✅ |
| **法律专业** | ✅ | ⚠️ | ✅ |

**结论：** Tavily 最适合 AI Agent，性价比最高。

---

## 📞 技术支持

- **官方文档：** https://docs.tavily.com
- **Discord 社区：** https://discord.gg/tavily
- **Email：** support@tavily.com

---

## 📝 更新日志

### v1.0.0 (2024-04-15)
- ✅ 初始版本
- ✅ Tavily API 集成
- ✅ 法律专业搜索预设
- ✅ 30 分钟缓存
- ✅ 域名过滤功能
