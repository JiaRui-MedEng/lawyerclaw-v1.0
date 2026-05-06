"""
搜索意图识别模块

识别用户是否需要调用 Tavily 互联网搜索

触发模式：
1. 明确查询请求："帮我查询..."、"搜索一下..."
2. 最新信息请求："最新的..."、"2024 年..."
3. 实时信息请求："现在的..."、"最近的..."
4. 法律专业查询："最新法规"、"类似案例"
"""
import re
from typing import Tuple, Optional


class SearchIntentClassifier:
    """搜索意图分类器"""
    
    # 触发搜索的关键词模式
    SEARCH_PATTERNS = [
        # 明确查询请求
        r'帮我查询',
        r'帮我搜索',
        r'帮我查找',
        r'帮我看看',
        r'查询一下',
        r'搜索一下',
        r'查找一下',
        r'看一下',
        
        # 最新信息请求
        r'最新的',
        r'最新版',
        r'最新修订',
        r'最新规定',
        r'最新标准',
        r'最近',
        r'近期',
        r'新出台',
        r'新发布',
        
        # 年份相关（暗示需要最新信息）
        r'202[4-9]年',
        r'203[0-9]年',
        r'今年',
        r'明年',
        r'当前',
        r'现在',
        r'目前',
        
        # 新闻动态
        r'新闻',
        r'动态',
        r'热点',
        r'进展',
        r'情况',
        
        # 法律专业查询
        r'类似案例',
        r'相关案例',
        r'判例',
        r'赔偿标准',
        r'量刑标准',
        r'司法解释',
        r'指导意见',
    ]
    
    # 不触发搜索的模式（使用本地知识即可）
    NON_SEARCH_PATTERNS = [
        r'什么是',
        r'定义',
        r'含义',
        r'意思',
        r'怎么理解',
        r'解释一下',
        r'介绍一下',
        r'历史',
        r'什么时候颁布',
        r'什么时候实施',
        r'哪一年',
    ]
    
    # 法律专业搜索的域名预设
    LEGAL_DOMAINS = [
        "gov.cn",
        "court.gov.cn",
        "npc.gov.cn",
        "pkulaw.com",
        "chinacourt.org",
    ]
    
    # 低质量内容域名（排除）
    LOW_QUALITY_DOMAINS = [
        "zhihu.com",
        "baike.baidu.com",
        "sohu.com",
        "163.com",
        "sina.com",
    ]
    
    @classmethod
    def should_search(cls, query: str) -> Tuple[bool, Optional[str]]:
        """
        判断是否需要调用搜索
        
        Args:
            query: 用户查询
            
        Returns:
            (是否需要搜索，触发原因)
        """
        # 1. 检查是否明确不需要搜索
        for pattern in cls.NON_SEARCH_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                return False, None
        
        # 2. 检查是否需要搜索
        for pattern in cls.SEARCH_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                return True, f"匹配模式：{pattern}"
        
        # 3. 检查是否是问题形式（可能需要搜索）
        if query.endswith('?') or query.endswith('？'):
            # 判断是否是事实性问题
            if any(kw in query for kw in ['什么', '谁', '哪里', '何时']):
                return False, None  # 事实性问题用本地知识
            else:
                return True, "疑问句可能需要最新信息"
        
        return False, None
    
    @classmethod
    def get_search_params(cls, query: str) -> dict:
        """
        根据查询内容生成搜索参数
        
        Args:
            query: 用户查询
            
        Returns:
            搜索参数字典
        """
        params = {
            "query": query,
            "search_depth": "basic",
            "limit": 5,
        }
        
        # 判断搜索深度
        if any(kw in query for kw in ['研究', '分析', '详细', '深入', '全面']):
            params["search_depth"] = "advanced"
        
        # 法律相关查询 - 限定政府官网
        if any(kw in query for kw in ['法律', '法规', '法条', '司法', '法院', '赔偿', '伤残']):
            params["include_domains"] = cls.LEGAL_DOMAINS
            params["exclude_domains"] = cls.LOW_QUALITY_DOMAINS
        
        # 新闻查询 - 排除低质媒体
        if any(kw in query for kw in ['新闻', '热点', '动态']):
            params["exclude_domains"] = cls.LOW_QUALITY_DOMAINS
        
        # 案例查询 - 限定法院网站
        if any(kw in query for kw in ['案例', '判例', '判决']):
            params["include_domains"] = ["court.gov.cn", "chinacourt.org", "pkulaw.com"]
        
        # 判断结果数量
        if "详细" in query or "全面" in query:
            params["limit"] = 10
        elif "简单" in query or "大概" in query:
            params["limit"] = 3
        
        return params
    
    @classmethod
    def extract_keywords(cls, query: str) -> str:
        """
        从查询中提取关键词（优化搜索）
        
        Args:
            query: 用户查询
            
        Returns:
            优化后的搜索关键词
        """
        # 移除语气词
        query = re.sub(r'帮我 | 一下 | 看看 | 查询 | 搜索', '', query)
        
        # 移除疑问词
        query = re.sub(r'什么 | 怎么 | 如何 | 哪些', '', query)
        
        # 移除标点
        query = re.sub(r'[，。？！,.!?]', ' ', query)
        
        # 清理空格
        query = ' '.join(query.split())
        
        return query.strip()


# ═══════════════════════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    test_queries = [
        # 应该触发搜索
        ("帮我查询 2024 年最新的工伤保险赔偿标准", True),
        ("搜索一下交通事故十级伤残的案例", True),
        ("最近律师法有什么新修订吗", True),
        ("帮我看看最新的法律热点新闻", True),
        ("2024 年民法典有什么新司法解释", True),
        
        # 不应该触发搜索
        ("什么是民法典", False),
        ("刑法的定义是什么", False),
        ("民法典什么时候颁布的", False),
        ("介绍一下合同法的历史", False),
    ]
    
    print("="*60)
    print("搜索意图识别测试")
    print("="*60)
    
    for query, expected in test_queries:
        should_search, reason = SearchIntentClassifier.should_search(query)
        status = "✅" if should_search == expected else "❌"
        
        print(f"\n{status} 查询：{query}")
        print(f"   预期：{'搜索' if expected else '不搜索'}")
        print(f"   实际：{'搜索' if should_search else '不搜索'}")
        if reason:
            print(f"   原因：{reason}")
        
        if should_search:
            params = SearchIntentClassifier.get_search_params(query)
            print(f"   搜索参数：")
            print(f"     query: {params['query']}")
            print(f"     depth: {params['search_depth']}")
            print(f"     limit: {params['limit']}")
            if 'include_domains' in params:
                print(f"     include: {params['include_domains']}")
