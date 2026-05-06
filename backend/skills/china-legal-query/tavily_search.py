"""
中国法律法规查询 - Tavily 搜索集成

为 china-legal-query Skill 提供互联网搜索能力
查询最新法律法规、司法解释、典型案例
"""
import sys
from pathlib import Path

# 添加共享模块路径
sys.path.insert(0, str(Path(__file__).parent.parent / 'shared'))

from tavily_integration import search_legal, search_cases


async def search_laws(query: str) -> dict:
    """
    搜索法律法规
    
    Args:
        query: 查询关键词，如"工伤保险条例 2024"
        
    Returns:
        dict: 搜索结果
    """
    # 使用法律专业搜索（自动限定政府官网）
    result = await search_legal(query)
    
    if result['success']:
        return {
            'type': 'laws',
            'query': result['query'],
            'answer': result.get('answer', ''),
            'results': result['results'],
            'total': result['total_results']
        }
    else:
        return {
            'type': 'laws',
            'query': query,
            'error': result.get('error', '搜索失败'),
            'results': []
        }


async def search_judicial_interpretations(query: str) -> dict:
    """
    搜索司法解释
    
    Args:
        query: 查询关键词，如"民法典 司法解释"
        
    Returns:
        dict: 搜索结果
    """
    full_query = f"{query} 司法解释 最高人民法院"
    result = await search_legal(full_query)
    
    if result['success']:
        return {
            'type': 'judicial_interpretations',
            'query': result['query'],
            'answer': result.get('answer', ''),
            'results': result['results'],
            'total': result['total_results']
        }
    else:
        return {
            'type': 'judicial_interpretations',
            'query': full_query,
            'error': result.get('error', '搜索失败'),
            'results': []
        }


async def search_legal_cases(query: str) -> dict:
    """
    搜索司法案例
    
    Args:
        query: 查询关键词，如"交通事故 十级伤残"
        
    Returns:
        dict: 搜索结果
    """
    # 使用案例搜索（自动限定法院网站）
    result = await search_cases(query)
    
    if result['success']:
        return {
            'type': 'cases',
            'query': result['query'],
            'answer': result.get('answer', ''),
            'results': result['results'],
            'total': result['total_results']
        }
    else:
        return {
            'type': 'cases',
            'query': query,
            'error': result.get('error', '搜索失败'),
            'results': []
        }


def format_search_results(results: dict) -> str:
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
            lines.append(f"    来源：{_extract_domain(url)}")
            lines.append(f"    URL: {url}")
            lines.append(f"    摘要：{content[:200]}")
            lines.append("")
    
    return "\n".join(lines)


def _extract_domain(url: str) -> str:
    """从 URL 提取域名"""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc
    except:
        return url


# ═══════════════════════════════════════════════════════════
# 使用示例
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import asyncio
    
    async def demo():
        print("="*60)
        print("中国法律法规查询 - Tavily 集成演示")
        print("="*60)
        
        # 示例 1: 搜索法律法规
        print("\n示例 1: 搜索法律法规")
        print("-"*60)
        result = await search_laws("2024 年工伤保险条例")
        print(f"类型：{result['type']}")
        print(f"查询：{result['query']}")
        print(f"成功：{result.get('success', True)}")
        if result.get('answer'):
            print(f"AI 摘要：{result['answer'][:100]}")
        print(f"结果数：{result['total']}")
        
        # 示例 2: 搜索司法解释
        print("\n示例 2: 搜索司法解释")
        print("-"*60)
        result = await search_judicial_interpretations("民法典 合同编")
        print(f"类型：{result['type']}")
        print(f"查询：{result['query']}")
        print(f"成功：{result.get('success', True)}")
        print(f"结果数：{result['total']}")
        
        # 示例 3: 搜索案例
        print("\n示例 3: 搜索司法案例")
        print("-"*60)
        result = await search_legal_cases("交通事故 十级伤残 赔偿")
        print(f"类型：{result['type']}")
        print(f"查询：{result['query']}")
        print(f"成功：{result.get('success', True)}")
        print(f"结果数：{result['total']}")
        
        print("\n" + "="*60)
        print("演示完成")
        print("="*60)
    
    asyncio.run(demo())
