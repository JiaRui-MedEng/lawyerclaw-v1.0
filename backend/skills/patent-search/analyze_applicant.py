#!/usr/bin/env python3
"""
分析锂电池专利的申请人分布
"""

import json
import requests
import sys
from collections import Counter

from patent_token import get_patent_api_token


def analyze_applicant_distribution(query, token, sample_size=200):
    """分析申请人分布"""
    print(f"🔍 正在分析 '{query}' 的申请人分布...")
    print("=" * 60)
    
    # 获取专利样本
    all_patents = []
    page = 1
    page_size = 50
    
    while len(all_patents) < sample_size:
        print(f"⏳ 获取第 {page} 页数据...")
        
        params = {
            "ds": "cn",
            "t": token,
            "q": query,
            "p": page,
            "ps": page_size,
            "v": 1
        }
        
        try:
            response = requests.get("https://www.9235.net/api/s", params=params, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                
                if not result.get("success"):
                    print(f"❌ API返回错误: {result.get('message', '未知错误')}")
                    break
                
                patents = result.get("patents", [])
                if not patents:
                    print("✅ 已获取所有可用数据")
                    break
                
                all_patents.extend(patents)
                print(f"✅ 已获取 {len(patents)} 条，累计 {len(all_patents)} 条")
                
                # 检查是否还有更多页
                total_pages = result.get("totalPages", 0)
                if page >= total_pages:
                    print("✅ 已到达最后一页")
                    break
                
                page += 1
                
            else:
                print(f"❌ HTTP错误: {response.status_code}")
                break
                
        except Exception as e:
            print(f"❌ 获取数据失败: {str(e)}")
            break
    
    if not all_patents:
        print("❌ 无法获取专利数据")
        return None
    
    # 分析申请人分布
    applicant_counter = Counter()
    
    for patent in all_patents[:sample_size]:
        applicant = patent.get('applicant', '')
        if applicant:
            applicant_counter[applicant] += 1
    
    return applicant_counter, len(all_patents[:sample_size])

def format_applicant_analysis(applicant_counter, total_patents, query):
    """格式化申请人分析结果"""
    if not applicant_counter:
        return "❌ 无法提取申请人数据"
    
    # 按申请数量排序
    sorted_applicants = sorted(applicant_counter.items(), key=lambda x: x[1], reverse=True)
    
    output = []
    output.append(f"🏢 {query}专利申请人分布分析")
    output.append("=" * 60)
    
    # 基本信息
    total_applicants = len(applicant_counter)
    total_patents_with_applicant = sum(applicant_counter.values())
    
    output.append(f"📊 分析样本: {total_patents} 条专利")
    output.append(f"👥 涉及申请人: {total_applicants} 个")
    output.append(f"📄 有效专利: {total_patents_with_applicant} 条 (含申请人信息)")
    output.append("=" * 60)
    
    # 申请人排名
    output.append("🥇 申请人排名 (前20名):")
    output.append("-" * 50)
    
    for i, (applicant, count) in enumerate(sorted_applicants[:20], 1):
        percentage = count / total_patents_with_applicant * 100
        
        # 创建进度条
        max_count = sorted_applicants[0][1] if sorted_applicants else 1
        bar_length = int(count / max_count * 40)
        bar = "█" * bar_length + "░" * (40 - bar_length)
        
        rank_symbol = ""
        if i == 1:
            rank_symbol = "🥇"
        elif i == 2:
            rank_symbol = "🥈"
        elif i == 3:
            rank_symbol = "🥉"
        
        output.append(f"{i:2d}. {rank_symbol} {applicant[:40]}{'...' if len(applicant) > 40 else ''}")
        output.append(f"    专利数: {count:3d} 件 ({percentage:5.1f}%) {bar}")
    
    # 集中度分析
    output.append("\n📊 市场集中度分析:")
    output.append("-" * 50)
    
    # 前5名集中度
    top5_count = sum(count for _, count in sorted_applicants[:5])
    top5_percentage = top5_count / total_patents_with_applicant * 100
    output.append(f"🏆 前5名申请人集中度: {top5_percentage:.1f}%")
    
    # 前10名集中度
    top10_count = sum(count for _, count in sorted_applicants[:10])
    top10_percentage = top10_count / total_patents_with_applicant * 100
    output.append(f"🏆 前10名申请人集中度: {top10_percentage:.1f}%")
    
    # 前20名集中度
    top20_count = sum(count for _, count in sorted_applicants[:20])
    top20_percentage = top20_count / total_patents_with_applicant * 100
    output.append(f"🏆 前20名申请人集中度: {top20_percentage:.1f}%")
    
    # 竞争格局判断
    output.append("\n🔬 竞争格局判断:")
    if top5_percentage > 50:
        output.append("   🏢 格局: 高度集中 (寡头垄断)")
    elif top5_percentage > 30:
        output.append("   🏢 格局: 相对集中 (主导企业)")
    elif top5_percentage > 15:
        output.append("   🏢 格局: 适度集中 (竞争激烈)")
    else:
        output.append("   🏢 格局: 分散竞争 (完全竞争)")
    
    # 申请人类型分析
    output.append("\n👥 申请人类型分析:")
    
    # 识别申请人类型关键词
    company_keywords = ['公司', '有限', '集团', '科技', '股份', '厂', '企业']
    university_keywords = ['大学', '学院', '学校', '研究所', '研究院', '实验室']
    personal_keywords = ['个人', '独立', '个体']
    
    company_count = 0
    university_count = 0
    personal_count = 0
    other_count = 0
    
    for applicant, count in sorted_applicants:
        applicant_lower = applicant.lower()
        
        if any(keyword in applicant_lower for keyword in company_keywords):
            company_count += count
        elif any(keyword in applicant_lower for keyword in university_keywords):
            university_count += count
        elif any(keyword in applicant_lower for keyword in personal_keywords):
            personal_count += count
        else:
            other_count += count
    
    total_typed = company_count + university_count + personal_count + other_count
    if total_typed > 0:
        output.append(f"   🏢 企业申请人: {company_count} 件 ({company_count/total_typed*100:.1f}%)")
        output.append(f"   🎓 高校科研机构: {university_count} 件 ({university_count/total_typed*100:.1f}%)")
        output.append(f"   👤 个人申请人: {personal_count} 件 ({personal_count/total_typed*100:.1f}%)")
        output.append(f"   ❓ 其他类型: {other_count} 件 ({other_count/total_typed*100:.1f}%)")
    
    # 创新活跃度分析
    output.append("\n🚀 创新活跃度分析:")
    
    # 计算HHI指数（赫芬达尔-赫希曼指数）
    hhi = 0
    for _, count in sorted_applicants:
        share = count / total_patents_with_applicant
        hhi += share * share * 10000
    
    output.append(f"   📊 HHI指数: {hhi:.0f}")
    
    if hhi > 2500:
        output.append("   ⚠️  市场集中度: 高 (垄断风险)")
    elif hhi > 1500:
        output.append("   ⚠️  市场集中度: 较高")
    elif hhi > 1000:
        output.append("   ✅ 市场集中度: 适中")
    else:
        output.append("   ✅ 市场集中度: 低 (竞争充分)")
    
    output.append("\n" + "=" * 60)
    output.append("💡 数据说明:")
    output.append(f"• 基于 {total_patents} 条专利样本分析")
    output.append(f"• 样本代表性: 约{total_patents/262995*100:.2f}% (基于262,995条总数)")
    output.append("• 分析结果具有统计参考价值")
    
    output.append("\n🎯 深度分析建议:")
    output.append("• 分析头部企业的技术布局")
    output.append("• 对比高校与企业的创新差异")
    output.append("• 跟踪新兴申请人的技术动向")
    output.append("• 分析国际合作申请情况")
    
    return "\n".join(output)

def main():
    """主函数"""
    print("🏢 锂电池专利申请人分布分析")
    print("=" * 60)
    
    # 加载Token
    token = get_patent_api_token()
    
    if not token:
        print("❌ 未找到有效的Token配置")
        print("\n💡 请使用以下命令配置Token:")
        print("   openclaw config set skills.entries.patent-search.apiKey '您的Token'")
        return
    
    print("✅ 已获取 API Token（不在此输出具体内容）")
    print(f"🔍 分析对象: 锂电池")
    print(f"📊 分析维度: 申请人分布")
    print(f"📈 样本目标: 200条专利")
    print("-" * 50)
    
    # 分析申请人分布
    applicant_counter, total_patents = analyze_applicant_distribution("锂电池", token, 200)
    
    if applicant_counter:
        # 生成分析报告
        report = format_applicant_analysis(applicant_counter, total_patents, "锂电池")
        print("\n" + report)
    else:
        print("❌ 分析失败")
        
        print("\n🔧 可能的原因:")
        print("1. API权限限制")
        print("2. 网络连接问题")
        print("3. 数据获取失败")
        
        print("\n💡 解决方案:")
        print("1. 检查网络连接")
        print("2. 确认Token有效性")
        print("3. 稍后重试")

if __name__ == "__main__":
    main()