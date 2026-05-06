"""
Tavily AI 搜索工具
专为百佑 LawyerClaw 设计的互联网搜索能力

特性:
- AI 优化的搜索结果（结构化摘要）
- 法律专业搜索模式
- 来源可信度过滤
- 自动内容提取

API: https://app.tavily.com
价格：Free 1000 次/月，Starter $25/10000 次
"""
import os
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from service.tools.legal_tools import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class TavilySearchTool(BaseTool):
    """Tavily AI 搜索工具"""
    
    name = "tavily_search"
    description = "使用 Tavily AI 搜索引擎检索互联网最新信息。适用于查询最新法律法规、司法案例、社会热点、新闻动态等。返回结构化摘要和可信来源。"
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词或问题"
            },
            "search_depth": {
                "type": "string",
                "enum": ["basic", "advanced"],
                "description": "搜索深度：basic(快速)/advanced(深度)",
                "default": "basic"
            },
            "limit": {
                "type": "integer",
                "description": "返回结果数量",
                "default": 5,
                "minimum": 1,
                "maximum": 10
            },
            "include_domains": {
                "type": "array",
                "items": {"type": "string"},
                "description": "限定搜索的域名（如 ['gov.cn', 'court.gov.cn']）",
                "default": []
            },
            "exclude_domains": {
                "type": "array",
                "items": {"type": "string"},
                "description": "排除的域名（如 ['zhihu.com', 'baike.baidu.com']）",
                "default": []
            }
        },
        "required": ["query"]
    }
    
    def __init__(self, api_key: str = None):
        """
        初始化 Tavily 搜索工具
        
        Args:
            api_key: Tavily API Key，默认从环境变量读取
        """
        self.api_key = api_key or os.getenv('TAVILY_API_KEY')
        self.client = None
        self._cache = {}  # 简单缓存
        self._cache_ttl = timedelta(minutes=30)
        
        if not self.api_key:
            logger.warning("TAVILY_API_KEY 未设置，Tavily 搜索将不可用")
        else:
            self._init_client()
    
    def _init_client(self):
        """初始化 Tavily 客户端"""
        try:
            from tavily import TavilyClient
            # TavilyClient 直接传 API Key 字符串，不是 api_key=参数
            self.client = TavilyClient(self.api_key)
            logger.info("Tavily 客户端初始化成功")
        except ImportError:
            logger.error("未安装 tavily-python，请运行：pip install tavily-python")
            self.client = None
        except Exception as e:
            logger.error(f"Tavily 客户端初始化失败：{e}")
            self.client = None
    
    def _get_cache_key(self, query: str, **kwargs) -> str:
        """生成缓存键"""
        return f"{query}:{kwargs.get('search_depth', 'basic')}:{kwargs.get('limit', 5)}"
    
    def _get_from_cache(self, key: str) -> Optional[Dict]:
        """从缓存获取结果"""
        if key in self._cache:
            cached = self._cache[key]
            if datetime.now() - cached['timestamp'] < self._cache_ttl:
                logger.info(f"使用缓存的搜索结果：{key}")
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
    
    async def execute(
        self,
        query: str,
        search_depth: str = "basic",  # 改为 basic 加快速度
        limit: int = 3,  # 减少默认结果数量，加快速度
        include_domains: List[str] = None,
        exclude_domains: List[str] = None,
        **kwargs
    ) -> ToolResult:
        """
        执行 Tavily 搜索
        
        Args:
            query: 搜索关键词
            search_depth: basic 或 advanced
            limit: 返回结果数量 (1-10)
            include_domains: 限定搜索的域名列表
            exclude_domains: 排除的域名列表
            
        Returns:
            ToolResult: 搜索结果
        """
        if not self.client:
            return ToolResult(
                success=False,
                content='',
                error='Tavily 搜索未初始化（检查 TAVILY_API_KEY 是否配置）'
            )
        
        # 检查缓存
        cache_key = self._get_cache_key(query, search_depth=search_depth, limit=limit)
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            return ToolResult(
                success=True,
                content=self._format_results(cached_result),
                data=cached_result
            )
        
        try:
            import time
            start_time = time.time()
            logger.info(f"[Tavily] 🔍 开始搜索：{query} (depth={search_depth}, limit={limit})")
            logger.info(f"[Tavily] 📡 API Key: {self.api_key[:15] if self.api_key else 'None'}...")
            logger.info(f"[Tavily] 📡 客户端状态：{'已初始化' if self.client else '未初始化'}")
            
            # 构建搜索参数 - 优化速度
            search_params = {
                "query": query,
                "search_depth": search_depth,
                "include_answer": True,  # 获取 AI 摘要
                "include_raw_content": False,  # 不需要原始 HTML
                "max_results": limit,
                # 优化：限制搜索结果天数（最近 1 年），加快搜索速度
                "days": 365,
            }
            
            # 添加域名过滤（法律专业搜索限定政府官网）
            if include_domains:
                search_params["include_domains"] = include_domains
            if exclude_domains:
                search_params["exclude_domains"] = exclude_domains
            
            # 执行搜索（带超时）
            logger.info(f"[Tavily] 📡 调用 Tavily API (timeout=30s)...")
            logger.info(f"[Tavily] 📡 搜索参数：{search_params}")
            
            try:
                response = self.client.search(**search_params, timeout=30)  # 30 秒超时
                elapsed = time.time() - start_time
                logger.info(f"[Tavily] ✅ API 调用完成，耗时：{elapsed:.2f}秒")
            except Exception as api_error:
                logger.error(f"[Tavily] ❌ API 调用失败：{api_error}")
                logger.error(f"[Tavily] ❌ 错误类型：{type(api_error).__name__}")
                raise
            
            # 保存缓存
            self._save_to_cache(cache_key, response)
            
            # 格式化结果
            formatted = self._format_results(response)
            
            logger.info(f"[Tavily] ✅ 搜索完成，返回 {len(response.get('results', []))} 条结果，总耗时：{elapsed:.2f}秒")
            
            return ToolResult(
                success=True,
                content=formatted,
                data=response
            )
            
        except Exception as e:
            elapsed = time.time() - start_time if 'start_time' in locals() else 0
            logger.error(f"[Tavily] ❌ 搜索失败（耗时 {elapsed:.2f}秒）: {e}")
            logger.error(f"[Tavily] 错误类型：{type(e).__name__}")
            
            # 区分超时和其他错误
            error_msg = str(e)
            if 'timeout' in error_msg.lower() or 'timed out' in error_msg.lower():
                return ToolResult(
                    success=False,
                    content='',
                    error=f'Tavily 搜索超时（{elapsed:.1f}秒），请重试或检查网络连接'
                )
            else:
                return ToolResult(
                    success=False,
                    content='',
                    error=f'Tavily 搜索失败：{error_msg}'
                )
    
    def _format_results(self, response: Dict) -> str:
        """
        格式化 Tavily 搜索结果
        
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
                lines.append(f"    摘要：{content[:300]}")  # 限制长度
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
# 法律专业搜索预设
# ═══════════════════════════════════════════════════════════

class LegalSearchPreset:
    """法律专业搜索预设配置"""
    
    # 政府/法院官网白名单
    GOVERNMENT_DOMAINS = [
        "gov.cn",
        "court.gov.cn",
        "npc.gov.cn",
        "pkulaw.com",  # 北大法宝
        "lawinfochina.com"
    ]
    
    # 低质量内容黑名单
    LOW_QUALITY_DOMAINS = [
        "zhihu.com",  # 知乎（个人观点）
        "baike.baidu.com",  # 百度百科（可能过时）
        "sohu.com",  # 搜狐（自媒体）
        "163.com",  # 网易（自媒体）
    ]
    
    @classmethod
    def search_law(cls, query: str) -> dict:
        """搜索法律法规"""
        return {
            "query": query,
            "search_depth": "advanced",
            "limit": 5,
            "include_domains": cls.GOVERNMENT_DOMAINS,
            "exclude_domains": cls.LOW_QUALITY_DOMAINS
        }
    
    @classmethod
    def search_case(cls, query: str) -> dict:
        """搜索司法案例"""
        return {
            "query": f"司法案例 {query}",
            "search_depth": "advanced",
            "limit": 5,
            "include_domains": ["court.gov.cn", "chinacourt.org", "pkulaw.com"]
        }
    
    @classmethod
    def search_news(cls, query: str) -> dict:
        """搜索法律新闻"""
        return {
            "query": f"最新 {query}",
            "search_depth": "basic",
            "limit": 5,
            "exclude_domains": cls.LOW_QUALITY_DOMAINS
        }


# ═══════════════════════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import asyncio
    
    async def test():
        tool = TavilySearchTool()
        
        if not tool.is_available():
            print("❌ Tavily 搜索不可用（检查 API Key）")
            return
        
        # 测试 1: 基础搜索
        print("\n=== 测试 1: 基础搜索 ===")
        result = await tool.execute("2024 年民法典最新司法解释")
        print(result.content[:500])
        
        # 测试 2: 法律专业搜索
        print("\n=== 测试 2: 法律专业搜索 ===")
        preset = LegalSearchPreset.search_law("工伤保险条例")
        result = await tool.execute(**preset)
        print(result.content[:500])
        
        # 测试 3: 案例搜索
        print("\n=== 测试 3: 案例搜索 ===")
        preset = LegalSearchPreset.search_case("交通事故 伤残等级")
        result = await tool.execute(**preset)
        print(result.content[:500])
    
    asyncio.run(test())
