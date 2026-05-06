"""
新闻聚合 - Tavily 搜索集成

为 news-aggregator Skill 提供互联网新闻搜索能力
自动搜索、筛选、整理社会、科技、军事新闻
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

# 添加共享模块路径
sys.path.insert(0, str(Path(__file__).parent.parent / 'shared'))

from tavily_integration import search_news


# 新闻类别配置
NEWS_CATEGORIES = {
    'tech': {
        'query': '科技新闻 最新',
        'keywords': ['人工智能', '芯片', '互联网', '科技创新', '数码'],
    },
    'mil': {
        'query': '军事新闻 最新',
        'keywords': ['国防', '军队', '武器', '军事演习', '国际军事'],
    },
    'society': {
        'query': '社会新闻 最新',
        'keywords': ['民生', '社会热点', '突发事件', '社会治理'],
    },
    'finance': {
        'query': '财经新闻 最新',
        'keywords': ['经济', '金融', '股市', '投资', '企业'],
    },
    'international': {
        'query': '国际新闻 最新',
        'keywords': ['国际关系', '外交', '国际会议', '全球'],
    }
}


async def fetch_category_news(category: str, limit: int = 10) -> dict:
    """
    获取指定类别的新闻
    
    Args:
        category: 新闻类别 (tech/mil/society/finance/international)
        limit: 返回数量
        
    Returns:
        dict: 新闻搜索结果
    """
    if category not in NEWS_CATEGORIES:
        return {
            'success': False,
            'error': f'未知类别：{category}',
            'category': category,
            'news': []
        }
    
    config = NEWS_CATEGORIES[category]
    query = config['query']
    
    # 搜索新闻
    result = await search_news(query, limit=limit)
    
    if result['success']:
        return {
            'success': True,
            'category': category,
            'category_name': _get_category_name(category),
            'query': result['query'],
            'news': result['results'],
            'total': result['total_results'],
            'timestamp': datetime.now().isoformat()
        }
    else:
        return {
            'success': False,
            'category': category,
            'category_name': _get_category_name(category),
            'error': result.get('error', '搜索失败'),
            'news': []
        }


async def fetch_all_news(limit_per_category: int = 5) -> dict:
    """
    获取所有类别的新闻
    
    Args:
        limit_per_category: 每个类别的返回数量
        
    Returns:
        dict: 所有新闻类别的搜索结果
    """
    all_news = {}
    
    for category in NEWS_CATEGORIES:
        result = await fetch_category_news(category, limit_per_category)
        all_news[category] = result
    
    return {
        'success': True,
        'total_categories': len(NEWS_CATEGORIES),
        'news': all_news,
        'timestamp': datetime.now().isoformat()
    }


async def search_specific_news(keywords: str, limit: int = 10) -> dict:
    """
    搜索特定主题的新闻
    
    Args:
        keywords: 关键词
        limit: 返回数量
        
    Returns:
        dict: 新闻搜索结果
    """
    query = f"{keywords} 新闻"
    result = await search_news(query, limit=limit)
    
    if result['success']:
        return {
            'success': True,
            'query': result['query'],
            'keywords': keywords,
            'news': result['results'],
            'total': result['total_results'],
            'timestamp': datetime.now().isoformat()
        }
    else:
        return {
            'success': False,
            'query': query,
            'keywords': keywords,
            'error': result.get('error', '搜索失败'),
            'news': []
        }


def format_news_digest(news_data: dict) -> str:
    """
    格式化新闻摘要
    
    Args:
        news_data: 新闻数据
        
    Returns:
        str: 格式化的新闻摘要
    """
    lines = []
    
    # 标题
    category_name = news_data.get('category_name', '新闻')
    lines.append(f"## {category_name}")
    lines.append("")
    
    # 新闻列表
    news_items = news_data.get('news', [])
    if news_items:
        for i, item in enumerate(news_items, 1):
            title = item.get('title', '无标题')
            url = item.get('url', '')
            content = item.get('content', '')
            
            lines.append(f"{i}. [{title}]({url})")
            lines.append(f"   摘要：{content[:150]}")
            lines.append("")
    else:
        lines.append("暂无新闻")
        lines.append("")
    
    return "\n".join(lines)


def format_all_news_digest(all_news_data: dict) -> str:
    """
    格式化所有类别的新闻摘要
    
    Args:
        all_news_data: 所有新闻数据
        
    Returns:
        str: 格式化的完整新闻摘要
    """
    lines = []
    
    # 总标题
    lines.append("# 📰 新闻摘要")
    lines.append(f"**更新时间：** {all_news_data.get('timestamp', '')}")
    lines.append("")
    
    # 各类别新闻
    news_by_category = all_news_data.get('news', {})
    for category, news_data in news_by_category.items():
        if news_data.get('success'):
            section = format_news_digest(news_data)
            lines.append(section)
    
    return "\n".join(lines)


def _get_category_name(category: str) -> str:
    """获取类别中文名"""
    names = {
        'tech': '科技新闻',
        'mil': '军事新闻',
        'society': '社会新闻',
        'finance': '财经新闻',
        'international': '国际新闻'
    }
    return names.get(category, category)


# ═══════════════════════════════════════════════════════════
# 使用示例
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import asyncio
    
    async def demo():
        print("="*60)
        print("新闻聚合 - Tavily 集成演示")
        print("="*60)
        
        # 示例 1: 获取科技新闻
        print("\n示例 1: 获取科技新闻")
        print("-"*60)
        result = await fetch_category_news('tech', limit=5)
        print(f"类别：{result.get('category_name')}")
        print(f"成功：{result.get('success')}")
        print(f"查询：{result.get('query')}")
        print(f"结果数：{result.get('total', 0)}")
        if result.get('news'):
            print(f"\n第一条新闻：")
            print(f"标题：{result['news'][0]['title']}")
            print(f"URL: {result['news'][0]['url']}")
        
        # 示例 2: 搜索特定主题
        print("\n示例 2: 搜索特定主题新闻")
        print("-"*60)
        result = await search_specific_news('人工智能', limit=5)
        print(f"关键词：{result.get('keywords')}")
        print(f"成功：{result.get('success')}")
        print(f"结果数：{result.get('total', 0)}")
        
        # 示例 3: 获取所有新闻
        print("\n示例 3: 获取所有类别新闻（摘要）")
        print("-"*60)
        result = await fetch_all_news(limit_per_category=2)
        print(f"总类别数：{result.get('total_categories')}")
        print(f"成功：{result.get('success')}")
        print(f"\n格式化输出：")
        print(format_all_news_digest(result))
        
        print("\n" + "="*60)
        print("演示完成")
        print("="*60)
    
    asyncio.run(demo())
