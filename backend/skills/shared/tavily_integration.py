"""
Tavily 搜索集成模块 - Skills 共享版

为所有 Skills 提供统一的互联网搜索能力

使用方式:
    from skills.shared.tavily_integration import search_web
    
    result = await search_web("查询关键词")
"""
import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class TavilySearchClient:
    """Tavily 搜索客户端 - Skills 共享版"""
    
    def __init__(self, api_key: str = None):
        """
        初始化 Tavily 客户端
        
        Args:
            api_key: Tavily API Key，默认从环境变量读取
        """
        self.api_key = api_key or os.getenv('TAVILY_API_KEY')
        self.client = None
        self._cache = {}
        self._cache_ttl = timedelta(minutes=30)
        
        if self.api_key:
            self._init_client()
    
    def _init_client(self):
        """初始化 Tavily 客户端"""
        try:
            from tavily import TavilyClient
            # TavilyClient 直接传 API Key 字符串
            # API 格式：client = TavilyClient("tvly-dev-xxx")
            self.client = TavilyClient(self.api_key)
            logger.info(f"✅ Tavily 客户端初始化成功 (API Key: {self.api_key[:15]}...)")
            
            # 测试连接
            try:
                test_response = self.client.search(query="test", search_depth="basic")
                logger.info("✅ Tavily API 连接测试成功")
            except Exception as test_error:
                logger.warning(f"⚠️ Tavily API 连接测试失败：{test_error}")
                
        except ImportError:
            logger.error("❌ 未安装 tavily-python，请运行：pip install tavily-python")
            self.client = None
        except Exception as e:
            logger.error(f"❌ Tavily 客户端初始化失败：{e}")
            self.client = None
    
    def _get_cache_key(self, query: str, **kwargs) -> str:
        """生成缓存键"""
        return f"{query}:{kwargs.get('search_depth', 'basic')}:{kwargs.get('limit', 5)}"
    
    def _get_from_cache(self, key: str) -> Optional[Dict]:
        """从缓存获取结果"""
        if key in self._cache:
            cached = self._cache[key]
            if datetime.now() - cached['timestamp'] < self._cache_ttl:
                logger.info(f"📦 使用缓存的搜索结果：{key}")
                return cached['data']
            else:
                del self._cache[key]
        return None
    
    def _save_to_cache(self, key: str, data: Dict):
        """保存结果到缓存"""
        self._cache[key] = {
            'data': data,
            'timestamp': datetime.now()
        }
    
    async def search(
        self,
        query: str,
        search_depth: str = "basic",
        limit: int = 5,
        include_domains: List[str] = None,
        exclude_domains: List[str] = None,
    ) -> Dict[str, Any]:
        """
        执行 Tavily 搜索
        
        Args:
            query: 搜索关键词
            search_depth: basic 或 advanced
            limit: 返回结果数量 (1-10)
            include_domains: 限定搜索的域名列表
            exclude_domains: 排除的域名列表
            
        Returns:
            Dict: 搜索结果
        """
        if not self.client:
            return {
                'success': False,
                'error': 'Tavily 搜索未初始化（检查 TAVILY_API_KEY 是否配置）',
                'results': []
            }
        
        # 检查缓存
        cache_key = self._get_cache_key(query, search_depth=search_depth, limit=limit)
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            return cached_result
        
        try:
            logger.info(f"🔍 Tavily 搜索：{query} (depth={search_depth}, limit={limit})")
            
            # 构建搜索参数
            search_params = {
                "query": query,
                "search_depth": search_depth,
                "include_answer": True,
                "include_raw_content": False,
                "max_results": limit,
            }
            
            # 添加域名过滤
            if include_domains:
                search_params["include_domains"] = include_domains
            if exclude_domains:
                search_params["exclude_domains"] = exclude_domains
            
            # 执行搜索
            response = self.client.search(**search_params)
            
            # 保存缓存
            self._save_to_cache(cache_key, response)
            
            logger.info(f"✅ Tavily 搜索完成，返回 {len(response.get('results', []))} 条结果")
            
            return {
                'success': True,
                'query': response.get('query', query),
                'answer': response.get('answer', ''),
                'results': response.get('results', []),
                'total_results': len(response.get('results', []))
            }
            
        except Exception as e:
            logger.error(f"❌ Tavily 搜索失败：{e}")
            return {
                'success': False,
                'error': f'Tavily 搜索失败：{str(e)}',
                'results': []
            }
    
    def format_results(self, response: Dict) -> str:
        """
        格式化搜索结果
        
        Args:
            response: Tavily API 响应
            
        Returns:
            str: 格式化的搜索结果
        """
        lines = []
        
        # 1. AI 生成的摘要（如果有）
        if response.get('answer'):
            lines.append("🤖 AI 摘要：")
            lines.append(response['answer'])
            lines.append("")
        
        # 2. 搜索结果列表
        results = response.get('results', [])
        if results:
            lines.append(f"📊 搜索结果（共 {len(results)} 条）：")
            lines.append("")
            
            for i, result in enumerate(results, 1):
                title = result.get('title', '无标题')
                url = result.get('url', '')
                content = result.get('content', '')
                score = result.get('score', 0)
                published_date = result.get('published_date', '')
                
                lines.append(f"[{i}] {title}")
                lines.append(f"    来源：{self._extract_domain(url)}")
                lines.append(f"    URL: {url}")
                if published_date:
                    lines.append(f"    日期：{published_date}")
                lines.append(f"    相关性：{score:.2f}")
                lines.append(f"    摘要：{content[:300]}")
                lines.append("")
        else:
            lines.append("未找到相关结果。")
        
        return "\n".join(lines)
    
    def _extract_domain(self, url: str) -> str:
        """从 URL 提取域名"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc or url
        except:
            return url
    
    def is_available(self) -> bool:
        """检查 Tavily 搜索是否可用"""
        return self.client is not None and self.api_key is not None


# ═══════════════════════════════════════════════════════════
# 便捷函数 - Skills 直接使用
# ═══════════════════════════════════════════════════════════

# 全局客户端实例
_global_client = None


def _get_client() -> TavilySearchClient:
    """获取全局 Tavily 客户端实例"""
    global _global_client
    if _global_client is None:
        _global_client = TavilySearchClient()
    return _global_client


async def search_web(
    query: str,
    search_depth: str = "basic",
    limit: int = 5,
    include_domains: List[str] = None,
    exclude_domains: List[str] = None,
) -> Dict[str, Any]:
    """
    互联网搜索（便捷函数）
    
    Args:
        query: 搜索关键词
        search_depth: basic 或 advanced
        limit: 返回结果数量
        include_domains: 限定域名
        exclude_domains: 排除域名
        
    Returns:
        Dict: 搜索结果
    """
    client = _get_client()
    return await client.search(
        query=query,
        search_depth=search_depth,
        limit=limit,
        include_domains=include_domains,
        exclude_domains=exclude_domains
    )


async def search_legal(
    query: str,
    search_depth: str = "advanced",
    limit: int = 5,
) -> Dict[str, Any]:
    """
    法律专业搜索（自动限定政府官网）
    
    Args:
        query: 搜索关键词
        search_depth: basic 或 advanced
        limit: 返回结果数量
        
    Returns:
        Dict: 搜索结果
    """
    client = _get_client()
    
    # 法律专业域名白名单
    legal_domains = [
        "gov.cn",
        "court.gov.cn",
        "npc.gov.cn",
        "pkulaw.com",
        "chinacourt.org",
    ]
    
    # 低质内容黑名单
    low_quality = [
        "zhihu.com",
        "baike.baidu.com",
        "sohu.com",
        "163.com",
    ]
    
    return await client.search(
        query=query,
        search_depth=search_depth,
        limit=limit,
        include_domains=legal_domains,
        exclude_domains=low_quality
    )


async def search_news(
    query: str,
    search_depth: str = "basic",
    limit: int = 5,
) -> Dict[str, Any]:
    """
    新闻搜索（自动排除低质媒体）
    
    Args:
        query: 搜索关键词
        search_depth: basic 或 advanced
        limit: 返回结果数量
        
    Returns:
        Dict: 搜索结果
    """
    client = _get_client()
    
    # 排除低质媒体
    exclude_media = [
        "zhihu.com",
        "baike.baidu.com",
        "sohu.com",
        "163.com",
        "sina.com",
    ]
    
    return await client.search(
        query=query,
        search_depth=search_depth,
        limit=limit,
        exclude_domains=exclude_media
    )


async def search_cases(
    query: str,
    search_depth: str = "advanced",
    limit: int = 5,
) -> Dict[str, Any]:
    """
    司法案例搜索（自动限定法院网站）
    
    Args:
        query: 搜索关键词
        search_depth: basic 或 advanced
        limit: 返回结果数量
        
    Returns:
        Dict: 搜索结果
    """
    client = _get_client()
    
    # 法院相关域名
    court_domains = [
        "court.gov.cn",
        "chinacourt.org",
        "pkulaw.com",
    ]
    
    return await client.search(
        query=query,
        search_depth=search_depth,
        limit=limit,
        include_domains=court_domains
    )


# ═══════════════════════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import asyncio
    
    async def test():
        print("="*60)
        print("Tavily Skills 集成测试")
        print("="*60)
        
        # 测试 1: 基础搜索
        print("\n测试 1: 基础搜索")
        result = await search_web("2024 年最新民法典")
        print(f"成功：{result['success']}")
        print(f"结果数：{result.get('total_results', 0)}")
        
        # 测试 2: 法律搜索
        print("\n测试 2: 法律专业搜索")
        result = await search_legal("工伤保险条例 2024")
        print(f"成功：{result['success']}")
        if result['success']:
            print(f"AI 摘要：{result.get('answer', '')[:100]}")
        
        # 测试 3: 新闻搜索
        print("\n测试 3: 新闻搜索")
        result = await search_news("科技新闻 2024")
        print(f"成功：{result['success']}")
        print(f"结果数：{result.get('total_results', 0)}")
        
        # 测试 4: 案例搜索
        print("\n测试 4: 司法案例搜索")
        result = await search_cases("交通事故 伤残等级")
        print(f"成功：{result['success']}")
        if result['success']:
            print(f"结果数：{result.get('total_results', 0)}")
        
        print("\n" + "="*60)
        print("测试完成")
        print("="*60)
    
    asyncio.run(test())
