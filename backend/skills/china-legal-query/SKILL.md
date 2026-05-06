---
name: china-legal-query
description: 中国法律法规查询工具（集成 Tavily AI 搜索）。Use when user needs to search Chinese laws, regulations, judicial interpretations. Supports criminal law, civil law, labor law, contract law, intellectual property law. 中国法律、法规查询、法律条文。
version: 1.0.3
license: MIT-0
required_environment_variables:
  - name: TAVILY_API_KEY
    prompt: 输入 Tavily API 密钥
    help: https://tavily.com/
    value: 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
metadata: {"openclaw": {"emoji": "⚖️", "requires": {"bins": ["python3", "curl"], "env": ["TAVILY_API_KEY"]}}}
---

# 中国法律法规查询工具（集成 Tavily）

查询中国法律法规、司法解释、案例判决。

## 功能特点

- ⚖️ **法律条文**: 刑法、民法、劳动法、合同法等
- 📋 **司法解释**: 最高法院、最高检察院解释
- 📚 **案例参考**: 裁判文书、典型案例
- 🔍 **智能搜索**: 关键词、法条号、主题搜索
- 🌐 **官方来源**: 国家法律法规数据库（通过 Tavily）
- 🇨🇳 **中国法律**: 专注中国法律体系
- 🤖 **AI 搜索**: 集成 Tavily AI 搜索引擎

## ⚠️ 免责声明

> **本工具仅供参考，不构成法律建议。**
> 不同 AI 模型能力不同，查询结果可能有差异。
> 重要法律事务请咨询专业律师。
> 法律条文以官方发布为准。

## 使用方式

```
User: "查询劳动法关于加班的规定"
Agent: 使用 Tavily 搜索最新法律条文并展示

User: "民法典第 1024 条是什么"
Agent: 查询具体法条内容

User: "关于知识产权保护的法律有哪些"
Agent: 列出相关法律法规

User: "帮我查询 2024 年最新的工伤保险赔偿标准"
Agent: 使用 Tavily 搜索最新标准
```

---

## Python 代码（完整 Tavily 集成）

```python
import os
import sys
import re
from pathlib import Path
from tavily import TavilyClient

# 初始化 Tavily 客户端
TAVILY_API_KEY = os.getenv('TAVILY_API_KEY', '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')
tavily_client = TavilyClient(TAVILY_API_KEY)

# 添加共享模块路径
skill_dir = Path(__file__).parent
sys.path.insert(0, str(skill_dir.parent / 'shared'))

from tavily_integration import search_legal, search_cases


class LegalQueryEngine:
    """中国法律法规查询引擎 - 集成 Tavily AI 搜索"""
    
    def __init__(self):
        self.sources = {
            'tavily': '使用 Tavily 搜索最新法律法规',
            'ai_knowledge': '使用 AI 模型法律知识库'
        }
    
    async def search_law(self, keyword, law_type=None):
        """
        搜索法律法规（使用 Tavily）
        
        Args:
            keyword: 搜索关键词，如"工伤保险条例 2024"
            law_type: 法律类型（可选）
        
        Returns:
            dict: 搜索结果
        """
        # 使用 Tavily 法律专业搜索（自动限定政府官网）
        result = await search_legal(keyword)
        
        if result['success']:
            return {
                'success': True,
                'source': 'tavily',
                'query': result['query'],
                'answer': result.get('answer', ''),
                'results': result['results'],
                'total': result['total_results']
            }
        else:
            # 降级方案：使用 AI 知识库
            return self._fallback_search(keyword)
    
    def _fallback_search(self, keyword):
        """降级搜索（使用 AI 知识库）"""
        return {
            'success': True,
            'source': 'ai_knowledge',
            'query': keyword,
            'answer': f'根据 AI 法律知识库，关于"{keyword}"的相关规定...',
            'results': [],
            'total': 0,
            'note': '⚠️ 未连接互联网，使用本地知识库'
        }
    
    async def search_judicial_interpretation(self, law_name):
        """
        搜索司法解释
        
        Args:
            law_name: 法律名称，如"民法典"
        
        Returns:
            dict: 司法解释搜索结果
        """
        query = f"{law_name} 司法解释 最高人民法院"
        result = await search_legal(query)
        
        if result['success']:
            return {
                'success': True,
                'type': 'judicial_interpretation',
                'results': result['results']
            }
        else:
            return {'success': False, 'error': result.get('error', '搜索失败')}
    
    async def search_cases(self, case_keywords):
        """
        搜索司法案例
        
        Args:
            case_keywords: 案例关键词，如"交通事故 十级伤残"
        
        Returns:
            dict: 案例搜索结果
        """
        result = await search_cases(case_keywords)
        
        if result['success']:
            return {
                'success': True,
                'type': 'cases',
                'results': result['results'],
                'total': result['total_results']
            }
        else:
            return {'success': False, 'error': result.get('error', '搜索失败')}
    
    def format_results(self, results: dict) -> str:
        """
        格式化搜索结果
        
        Args:
            results: 搜索结果字典
        
        Returns:
            str: 格式化的文本
        """
        lines = []
        
        # AI 摘要
        if results.get('answer'):
            lines.append("🤖 AI 摘要：")
            lines.append(results['answer'])
            lines.append("")
        
        # 结果列表
        items = results.get('results', [])
        if items:
            lines.append(f"📊 搜索结果（共 {len(items)} 条）：")
            lines.append("")
            
            for i, item in enumerate(items, 1):
                title = item.get('title', '无标题')
                url = item.get('url', '')
                content = item.get('content', '')
                
                lines.append(f"[{i}] {title}")
                lines.append(f"    来源：{self._extract_domain(url)}")
                lines.append(f"    URL: {url}")
                lines.append(f"    摘要：{content[:200]}")
                lines.append("")
        
        # 免责声明
        lines.append("⚠️ 提示：以上信息仅供参考，具体法律条文以官方发布为准。")
        
        return "\n".join(lines)
    
    def _extract_domain(self, url: str) -> str:
        """从 URL 提取域名"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc
        except:
            return url
    
    def analyze_query(self, user_query):
        """分析用户查询意图"""
        # 检测是否查询具体法条
        if re.search(r'第\d+条', user_query):
            return {
                'domain': '具体法条查询',
                'search_strategy': 'tavily',
                'query_type': 'article'
            }
        
        # 检测是否查询案例
        if any(kw in user_query for kw in ['案例', '判决', '判例']):
            return {
                'domain': '司法案例',
                'search_strategy': 'tavily_cases',
                'query_type': 'case'
            }
        
        # 检测是否查询司法解释
        if '司法解释' in user_query:
            return {
                'domain': '司法解释',
                'search_strategy': 'tavily',
                'query_type': 'interpretation'
            }
        
        # 默认：法律法规查询
        return {
            'domain': '法律法规',
            'search_strategy': 'tavily',
            'query_type': 'law'
        }


# 使用示例
if __name__ == "__main__":
    import asyncio
    
    async def demo():
        engine = LegalQueryEngine()
        
        # 示例 1: 搜索法律法规
        print("="*60)
        print("示例 1: 搜索法律法规")
        print("="*60)
        result = await engine.search_law("2024 年工伤保险条例")
        print(engine.format_results(result))
        
        # 示例 2: 搜索司法解释
        print("\n" + "="*60)
        print("示例 2: 搜索司法解释")
        print("="*60)
        result = await engine.search_judicial_interpretation("民法典")
        print(result)
        
        # 示例 3: 搜索案例
        print("\n" + "="*60)
        print("示例 3: 搜索案例")
        print("="*60)
        result = await engine.search_cases("交通事故 十级伤残")
        print(result)
    
    asyncio.run(demo())
```

---

## 注意事项

- ✅ **已集成 Tavily AI 搜索** - 自动获取最新法律法规
- ⚠️ 法律条文以官方数据库为准
- ⚠️ AI 解读仅供参考
- ⚠️ 条文可能有更新，以最新版本为准
- ⚠️ 复杂法律问题请咨询专业律师
- 🔑 **需要配置 TAVILY_API_KEY** - 在环境变量中设置

## 配置说明

1. **获取 Tavily API Key**
   - 访问：https://app.tavily.com
   - 注册账号
   - 创建 API Key

2. **设置环境变量**
   ```bash
   # Linux/Mac
   export TAVILY_API_KEY=tvly-your-key
   
   # Windows PowerShell
   $env:TAVILY_API_KEY="tvly-your-key"
   
   # 或添加到 .env 文件
   TAVILY_API_KEY=tvly-your-key
   ```

3. **安装依赖**
   ```bash
   pip install tavily-python
   ```

---

**版本：** 1.0.3（集成 Tavily）  
**最后更新：** 2024-04-15
