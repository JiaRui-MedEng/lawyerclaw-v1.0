#!/usr/bin/env python3
"""
专利检索技能主逻辑
"""

import sys
import json
from typing import Dict, List, Optional

class PatentSkill:
    """专利检索技能"""
    
    def __init__(self, api):
        """初始化技能"""
        self.api = api
        
        # 命令映射
        self.commands = {
            'search': self.handle_search,
            'detail': self.handle_patent,
            'claims': self.handle_claims,
            'description': self.handle_desc,
            'legal': self.handle_law,
            'citing': self.handle_citing,
            'similar': self.handle_similar,
            'company': self.handle_company,
            'copyright': self.handle_copyright,
            'trademark': self.handle_trademark,
            'analysis': self.handle_analysis,
            'help': self.handle_help,
        }
    
    def handle_search(self, args) -> str:
        """处理搜索命令"""
        if not args.query:
            return "❌ 请输入查询条件"
        
        try:
            result = self.api.search(
                query=args.query,
                page=args.page or 1,
                page_size=args.page_size or 10,
                data_scope=args.scope or 'cn',
                sort=args.sort or 'relation'
            )
            
            if not result.get('success'):
                return f"❌ 搜索失败: {result.get('message', '未知错误')}"
            
            return self.api.format_search_result(result, detailed=args.details)
            
        except Exception as e:
            return f"❌ 搜索失败: {e}"
    
    def handle_patent(self, args) -> str:
        """处理专利详情命令"""
        if not args.patent_id:
            return "❌ 请输入专利ID"
        
        try:
            result = self.api.get_patent_base(args.patent_id)
            
            if not result.get('success'):
                return f"❌ 获取专利详情失败: {result.get('message', '未知错误')}"
            
            patent = result.get('patent', {})
            
            output = []
            output.append(f"📄 专利详情: {args.patent_id}")
            output.append("=" * 50)
            
            # 基本信息
            output.append(f"📝 标题: {patent.get('title', '未知')}")
            output.append(f"👤 申请人: {patent.get('applicant', '未知')}")
            output.append(f"👨‍🔬 发明人: {patent.get('inventor', '未知')}")
            output.append(f"🏢 代理机构: {patent.get('agency', '未知')}")
            
            # 日期信息
            output.append(f"📅 申请日: {patent.get('applicationDate', '未知')}")
            output.append(f"📅 公开日: {patent.get('documentDate', '未知')}")
            
            # 分类信息
            output.append(f"🏷️ IPC分类: {patent.get('ipc', '未知')}")
            output.append(f"🏷️ 主分类: {patent.get('mainIpc', '未知')}")
            
            # 法律状态
            output.append(f"⚖️ 法律状态: {patent.get('legalStatus', '未知')}")
            output.append(f"📋 当前状态: {patent.get('currentStatus', '未知')}")
            output.append(f"📄 专利类型: {patent.get('type', '未知')}")
            
            # 摘要
            summary = patent.get('summary', '')
            if summary:
                if len(summary) > 200:
                    summary = summary[:200] + "..."
                output.append(f"📖 摘要: {summary}")
            
            return "\n".join(output)
            
        except Exception as e:
            return f"❌ 获取专利详情失败: {e}"
    
    def handle_claims(self, args) -> str:
        """处理权利要求命令"""
        if not args.patent_id:
            return "❌ 请输入专利ID"
        
        try:
            result = self.api.get_patent_claims(args.patent_id)
            
            if not result.get('success'):
                return f"❌ 获取权利要求失败: {result.get('message', '未知错误')}"
            
            claims = result.get('claims', '')
            
            output = []
            output.append(f"📜 权利要求: {args.patent_id}")
            output.append("=" * 50)
            
            if claims:
                # 限制输出长度
                if len(claims) > 1000:
                    claims = claims[:1000] + "...\n(内容已截断，完整内容请查看原始文件)"
                output.append(claims)
            else:
                output.append("无权利要求信息")
            
            return "\n".join(output)
            
        except Exception as e:
            return f"❌ 获取权利要求失败: {e}"
    
    def handle_desc(self, args) -> str:
        """处理说明书命令"""
        if not args.patent_id:
            return "❌ 请输入专利ID"
        
        try:
            result = self.api.get_patent_desc(args.patent_id)
            
            if not result.get('success'):
                return f"❌ 获取说明书失败: {result.get('message', '未知错误')}"
            
            description = result.get('description', '')
            
            output = []
            output.append(f"📖 说明书: {args.patent_id}")
            output.append("=" * 50)
            
            if description:
                # 限制输出长度
                if len(description) > 1500:
                    description = description[:1500] + "...\n(内容已截断，完整内容请查看原始文件)"
                output.append(description)
            else:
                output.append("无说明书信息")
            
            return "\n".join(output)
            
        except Exception as e:
            return f"❌ 获取说明书失败: {e}"
    
    def handle_law(self, args) -> str:
        """处理法律信息命令"""
        if not args.patent_id:
            return "❌ 请输入专利ID"
        
        try:
            result = self.api.get_patent_tx(args.patent_id)
            
            if not result.get('success'):
                return f"❌ 获取法律信息失败: {result.get('message', '未知错误')}"
            
            legal_info = result.get('legalInfo', {})
            legal_events = legal_info.get('legalEvent', [])
            
            output = []
            output.append(f"⚖️ 法律信息: {args.patent_id}")
            output.append("=" * 50)
            
            if legal_info:
                output.append(f"📋 法律状态: {legal_info.get('legalStatus', '未知')}")
                output.append(f"📅 状态日期: {legal_info.get('statusDate', '未知')}")
                output.append(f"💰 年费状态: {legal_info.get('annualFeeStatus', '未知')}")
                
                if legal_events:
                    output.append("\n📅 法律事件:")
                    for event in legal_events[:5]:  # 只显示前5个事件
                        output.append(f"  • {event.get('date', '未知')}: {event.get('type', '未知')}")
                    if len(legal_events) > 5:
                        output.append(f"  还有 {len(legal_events)-5} 个事件未显示")
            else:
                output.append("无法律信息")
            
            return "\n".join(output)
            
        except Exception as e:
            return f"❌ 获取法律信息失败: {e}"
    
    def handle_citing(self, args) -> str:
        """处理引用分析命令"""
        if not args.patent_id:
            return "❌ 请输入专利ID"
        
        try:
            result = self.api.get_patent_citing(args.patent_id)
            
            if not result.get('success'):
                return f"❌ 获取引用分析失败: {result.get('message', '未知错误')}"
            
            citing_patents = result.get('citingPatents', [])
            cited_patents = result.get('citedPatents', [])
            
            output = []
            output.append(f"🔗 引用分析: {args.patent_id}")
            output.append("=" * 50)
            
            # 被引用情况
            output.append(f"📊 被引用次数: {len(cited_patents)}")
            if cited_patents:
                output.append("📄 引用本专利的专利:")
                for i, patent in enumerate(cited_patents[:5], 1):
                    output.append(f"  {i}. {patent.get('id', '未知')} - {patent.get('title', '未知')[:50]}...")
                if len(cited_patents) > 5:
                    output.append(f"  还有 {len(cited_patents)-5} 条未显示")
            
            # 引用他人情况
            output.append(f"\n📊 引用他人次数: {len(citing_patents)}")
            if citing_patents:
                output.append("📄 本专利引用的专利:")
                for i, patent in enumerate(citing_patents[:5], 1):
                    output.append(f"  {i}. {patent.get('id', '未知')} - {patent.get('title', '未知')[:50]}...")
                if len(citing_patents) > 5:
                    output.append(f"  还有 {len(citing_patents)-5} 条未显示")
            
            return "\n".join(output)
            
        except Exception as e:
            return f"❌ 获取引用分析失败: {e}"
    
    def handle_similar(self, args) -> str:
        """处理相似专利命令"""
        if not args.patent_id:
            return "❌ 请输入专利ID"
        
        try:
            result = self.api.get_patent_like(args.patent_id)
            
            if not result.get('success'):
                return f"❌ 获取相似专利失败: {result.get('message', '未知错误')}"
            
            similar_patents = result.get('similarPatents', [])
            
            output = []
            output.append(f"🔍 相似专利: {args.patent_id}")
            output.append("=" * 50)
            
            output.append(f"📊 找到相似专利: {len(similar_patents)} 条")
            
            if similar_patents:
                for i, patent in enumerate(similar_patents[:5], 1):
                    similarity = patent.get('similarity', 0)
                    title = patent.get('title', '未知标题')
                    if len(title) > 60:
                        title = title[:60] + "..."
                    
                    output.append(f"\n{i}. 相似度: {similarity}%")
                    output.append(f"   🆔 {patent.get('id', '未知')}")
                    output.append(f"   📝 {title}")
                    output.append(f"   👤 {patent.get('applicant', '未知')}")
                
                if len(similar_patents) > 5:
                    output.append(f"\n📄 还有 {len(similar_patents)-5} 条相似专利未显示")
            
            return "\n".join(output)
            
        except Exception as e:
            return f"❌ 获取相似专利失败: {e}"
    
    def handle_company(self, args) -> str:
        """处理企业画像命令"""
        if not args.company_name:
            return "❌ 请输入企业名称"
        
        try:
            result = self.api.get_company_portrait(args.company_name)
            
            if not result.get('success'):
                return f"❌ 获取企业画像失败: {result.get('message', '未知错误')}"
            
            company_data = result.get('company', {})
            analysis = result.get('analysis', {})
            
            output = []
            output.append(f"🏢 企业画像: {args.company_name}")
            output.append("=" * 50)
            
            # 基本信息
            if company_data:
                output.append(f"📊 专利总数: {company_data.get('totalPatents', 0)}")
                output.append(f"📅 最早申请: {company_data.get('earliestApplication', '未知')}")
                output.append(f"📅 最新申请: {company_data.get('latestApplication', '未知')}")
                output.append(f"🏷️ 主要IPC: {company_data.get('mainIpc', '未知')}")
            
            # 分析数据
            if analysis:
                output.append("\n📈 分析数据:")
                
                # 法律状态分布
                legal_status = analysis.get('legalStatus', {})
                if legal_status:
                    output.append("⚖️ 法律状态分布:")
                    for status, count in list(legal_status.items())[:5]:
                        output.append(f"  • {status}: {count}件")
                
                # 专利类型分布
                patent_types = analysis.get('patentType', {})
                if patent_types:
                    output.append("\n📄 专利类型分布:")
                    for ptype, count in list(patent_types.items())[:5]:
                        output.append(f"  • {ptype}: {count}件")
                
                # 申请趋势
                trend = analysis.get('applicationTrend', {})
                if trend:
                    output.append("\n📅 申请趋势:")
                    for year, count in list(trend.items())[-5:]:  # 最近5年
                        output.append(f"  • {year}: {count}件")
            
            return "\n".join(output)
            
        except Exception as e:
            return f"❌ 获取企业画像失败: {e}"
    
    def handle_copyright(self, args) -> str:
        """处理著作权搜索命令"""
        if not args.query:
            return "❌ 请输入查询条件"
        
        try:
            result = self.api.search_copyright(
                query=args.query,
                copyright_type=args.type,
                field=args.field,
                page=args.page or 1,
                page_size=args.page_size or 10
            )
            
            if not result.get('success'):
                return f"❌ 搜索著作权失败: {result.get('message', '未知错误')}"
            
            copyrights = result.get('copyrights', [])
            total = result.get('total', 0)
            
            output = []
            output.append(f"📚 著作权搜索结果")
            output.append(f"📊 总数: {total} 条")
            output.append(f"🔍 查询条件: {args.query}")
            output.append(f"📄 类型: {args.type}")
            output.append("=" * 50)
            
            if not copyrights:
                output.append("未找到相关著作权")
                return "\n".join(output)
            
            for i, copyright in enumerate(copyrights[:10], 1):
                output.append(f"{i}. 登记号: {copyright.get('registrationNumber', '未知')}")
                output.append(f"   作品名称: {copyright.get('workName', '未知')}")
                output.append(f"   著作权人: {copyright.get('copyrightOwner', '未知')}")
                output.append(f"   登记日期: {copyright.get('registrationDate', '未知')}")
                output.append(f"   作品类别: {copyright.get('workCategory', '未知')}")
                output.append("")  # 空行分隔
            
            return "\n".join(output)
            
        except Exception as e:
            return f"❌ 搜索著作权失败: {e}"
    
    def handle_trademark(self, args) -> str:
        """处理商标搜索命令"""
        if args.detail and args.trademark_id:
            # 查看商标详情
            try:
                result = self.api.get_trademark_detail(args.trademark_id)
                
                if not result.get('success'):
                    return f"❌ 获取商标详情失败: {result.get('message', '未知错误')}"
                
                trademark = result.get('trademark', {})
                
                output = []
                output.append(f"🏷️ 商标详情: {args.trademark_id}")
                output.append("=" * 50)
                
                output.append(f"📝 商标名称: {trademark.get('trademarkName', '未知')}")
                output.append(f"🔢 申请号: {trademark.get('applicationNumber', '未知')}")
                output.append(f"👤 申请人: {trademark.get('applicantLabel', '未知')}")
                output.append(f"📅 申请日: {trademark.get('applicationDate', '未知')}")
                output.append(f"🏷️ 国际分类: {', '.join(trademark.get('ncl', []))}")
                output.append(f"⚖️ 法律状态: {trademark.get('lawStatus', '未知')}")
                output.append(f"🏢 代理机构: {trademark.get('agentLabel', '未知')}")
                
                return "\n".join(output)
                
            except Exception as e:
                return f"❌ 获取商标详情失败: {e}"
        else:
            # 搜索商标
            if not args.query:
                return "❌ 请输入查询条件"
            
            try:
                result = self.api.search_trademark(
                    query=args.query,
                    page=args.page or 1,
                    page_size=args.page_size or 10,
                    sort=args.sort
                )
                
                if not result.get('success'):
                    return f"❌ 搜索商标失败: {result.get('message', '未知错误')}"
                
                trademarks = result.get('trademarks', [])
                total = result.get('total', 0)
                
                output = []
                output.append(f"🏷️ 商标搜索结果")
                output.append(f"📊 总数: {total} 条")
                output.append(f"🔍 查询条件: {args.query}")
                output.append("=" * 50)
                
                if not trademarks:
                    output.append("未找到相关商标")
                    return "\n".join(output)
                
                for i, trademark in enumerate(trademarks[:10], 1):
                    output.append(f"{i}. 商标名称: {trademark.get('trademarkName', '未知')}")
                    output.append(f"   申请号: {trademark.get('applicationNumber', '未知')}")
                    output.append(f"   申请人: {trademark.get('applicantLabel', '未知')}")
                    output.append(f"   申请日: {trademark.get('applicationDate', '未知')}")
                    output.append("")  # 空行分隔
                
                return "\n".join(output)
                
            except Exception as e:
                return f"❌ 搜索商标失败: {e}"
    
    def handle_analysis(self, args) -> str:
        """处理统计分析命令"""
        if not args.query:
            return "❌ 请输入查询条件"
        
        try:
            result = self.api.get_analysis(
                query=args.query,
                dimension=args.dimension,
                data_scope=args.scope or 'cn'
            )
            
            if not result.get('success'):
                return f"❌ 统计分析失败: {result.get('message', '未知错误')}"
            
            import json
            analysis_data = result.get('analysis_total', '[]')
            
            try:
                items = json.loads(analysis_data)
            except:
                items = []
            
            output = []
            output.append(f"📊 统计分析 - {args.dimension}")
            output.append(f"🔍 查询条件: {args.query}")
            output.append("=" * 50)
            
            if not items:
                output.append("无分析数据")
                return "\n".join(output)
            
            limit = getattr(args, 'limit', 20)
            output.append(f"📈 分布情况 (前{limit}项):")
            for i, item in enumerate(items[:limit], 1):
                key = item.get('key', '未知')
                count = item.get('count', 0)
                output.append(f"{i:2d}. {key}: {count}件")
            
            return "\n".join(output)
            
        except Exception as e:
            return f"❌ 统计分析失败: {e}"
    
    def handle_help(self, args) -> str:
        """处理帮助命令"""
        help_text = """
🏢 专利检索技能 - 使用指南
==================================================

🔍 基本命令:
  patent search <查询条件>      - 搜索专利
  patent detail <专利ID>       - 查看专利详情
  patent claims <专利ID>       - 获取权利要求
  patent description <专利ID>  - 获取说明书
  patent legal <专利ID>        - 查看法律信息

📊 分析命令:
  patent analysis <查询条件> --dimension <维度>  - 统计分析
  patent company <企业名称>                     - 企业画像

📚 扩展命令:
  patent copyright <查询条件>    - 搜索著作权
  patent trademark <查询条件>    - 搜索商标
  patent citing <专利ID>        - 引用分析
  patent similar <专利ID>       - 相似专利

🛠️ 常用参数:
  --page, -p <页码>            - 指定页码
  --page-size, -ps <条数>      - 每页显示条数
  --scope, -s <cn/all>         - 数据范围
  --sort, -st <relation/date>  - 排序方式
  --details, -d               - 显示详细信息

📖 示例:
  patent search "锂电池" --page-size 5 --details
  patent detail CN112968234A
  patent analysis "锂电池" --dimension applicant
  patent company "比亚迪股份有限公司"

🔧 配置说明:
  1. 申请API Token: https://www.9235.net/api/open
  2. 配置Token:
     openclaw config set skills.entries.patent-search.apiKey '您的Token'
  3. 重启服务: openclaw gateway restart

📞 支持:
  • 文档: https://docs.openclaw.ai
  • 社区: https://discord.com/invite/clawd
  • GitHub: https://github.com/openclaw/openclaw
    """
        return help_text