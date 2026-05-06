#!/usr/bin/env python3
"""
分析锂电池专利的年度申请趋势
"""

import json
import requests
import sys
from datetime import datetime

from patent_token import get_patent_api_token


def get_analysis(query, dimension, token):
    """获取统计分析数据"""
    # 构建API请求
    params = {
        "ds": "cn",  # 中国专利
        "t": token,
        "q": query,
        "dimension": dimension,
        "v": 1
    }
    
    try:
        print(f"📊 正在分析: {query} - 维度: {dimension}")
        response = requests.get("https://www.9235.net/api/analysis", params=params, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            
            # 检查API返回状态
            success = result.get("success", False)
            error_code = result.get("errorCode")
            error_msg = result.get("message", "")
            
            if not success:
                print(f"❌ API返回错误:")
                print(f"   错误代码: {error_code}")
                print(f"   错误信息: {error_msg}")
                return None
            
            return result
            
        else:
            print(f"❌ HTTP错误: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ 分析失败: {str(e)}")
        return None

def format_application_year_trend(analysis_data):
    """格式化申请年度趋势分析"""
    if not analysis_data:
        return "无分析数据"
    
    # 提取分析数据
    analysis_total = analysis_data.get("analysis_total", "[]")
    
    try:
        items = json.loads(analysis_total)
    except:
        items = []
    
    if not items:
        return "无年度申请数据"
    
    # 按年份排序
    items.sort(key=lambda x: x.get("key", "0"))
    
    output = []
    output.append("📈 锂电池专利年度申请趋势分析")
    output.append("=" * 60)
    
    # 计算总数和趋势
    total_patents = sum(item.get("count", 0) for item in items)
    output.append(f"📊 分析专利总数: {total_patents:,} 件")
    output.append(f"📅 时间跨度: {items[0].get('key')} - {items[-1].get('key')} 年")
    output.append("=" * 60)
    
    # 显示年度数据
    output.append("📅 年度申请分布:")
    output.append("-" * 50)
    
    # 按年份分组显示
    year_groups = []
    current_decade = []
    
    for item in items:
        year = item.get("key", "0")
        count = item.get("count", 0)
        
        if year.isdigit() and len(year) == 4:
            year_int = int(year)
            
            # 按年代分组
            if not current_decade or year_int // 10 != current_decade[0][0] // 10:
                if current_decade:
                    year_groups.append(current_decade)
                current_decade = []
            
            current_decade.append((year_int, count))
    
    if current_decade:
        year_groups.append(current_decade)
    
    # 显示每个年代的数据
    for decade_group in year_groups:
        if not decade_group:
            continue
            
        start_year = decade_group[0][0]
        end_year = decade_group[-1][0]
        
        # 计算年代总数
        decade_total = sum(count for _, count in decade_group)
        
        output.append(f"\n📅 {start_year//10}0年代 ({start_year}-{end_year}):")
        output.append(f"   年代总数: {decade_total:,} 件")
        
        # 显示该年代每年的数据
        for year, count in decade_group:
            bar_length = int(count / max(1, max(count for _, count in decade_group)) * 30)
            bar = "█" * bar_length + "░" * (30 - bar_length)
            output.append(f"   {year}: {count:6,} 件 {bar}")
    
    # 计算增长趋势
    if len(items) >= 5:
        recent_years = items[-5:]  # 最近5年
        growth_rates = []
        
        for i in range(1, len(recent_years)):
            prev_count = recent_years[i-1].get("count", 0)
            curr_count = recent_years[i].get("count", 0)
            
            if prev_count > 0:
                growth_rate = (curr_count - prev_count) / prev_count * 100
                growth_rates.append(growth_rate)
        
        if growth_rates:
            avg_growth = sum(growth_rates) / len(growth_rates)
            output.append("\n📈 增长趋势分析:")
            output.append(f"   最近5年平均增长率: {avg_growth:+.1f}%")
            
            if avg_growth > 10:
                output.append("   📈 趋势: 快速增长期")
            elif avg_growth > 0:
                output.append("   ↗️  趋势: 稳步增长")
            elif avg_growth > -10:
                output.append("   ↘️  趋势: 略有下降")
            else:
                output.append("   📉 趋势: 明显下降")
    
    # 找出峰值年份
    if items:
        peak_year = max(items, key=lambda x: x.get("count", 0))
        output.append(f"\n🏆 申请峰值年份: {peak_year.get('key')}年")
        output.append(f"   峰值申请量: {peak_year.get('count'):,} 件")
    
    # 技术生命周期分析
    if len(items) >= 10:
        first_half = items[:len(items)//2]
        second_half = items[len(items)//2:]
        
        first_avg = sum(item.get("count", 0) for item in first_half) / len(first_half)
        second_avg = sum(item.get("count", 0) for item in second_half) / len(second_half)
        
        output.append("\n🔬 技术生命周期分析:")
        if second_avg > first_avg * 1.5:
            output.append("   🚀 阶段: 成长期 (申请量快速增长)")
        elif second_avg > first_avg:
            output.append("   📈 阶段: 发展期 (申请量稳步增长)")
        elif second_avg > first_avg * 0.8:
            output.append("   ⚖️  阶段: 成熟期 (申请量趋于稳定)")
        else:
            output.append("   📉 阶段: 衰退期 (申请量开始下降)")
    
    output.append("\n" + "=" * 60)
    output.append("🎯 后续分析建议:")
    output.append("• 分析 锂电池 的技术领域分布 --dimension ipc")
    output.append("• 分析 锂电池 的申请人分布 --dimension applicant")
    output.append("• 分析 锂电池 的法律状态分布 --dimension legalStatus")
    output.append("• 对比分析: 锂电池 vs 钠电池 vs 氢燃料电池")
    
    return "\n".join(output)

def main():
    """主函数"""
    print("📈 锂电池专利年度申请趋势分析")
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
    print(f"📊 分析维度: 申请年份 (applicationYear)")
    print("-" * 50)
    
    # 获取分析数据
    analysis_data = get_analysis("锂电池", "applicationYear", token)
    
    if analysis_data:
        # 格式化显示结果
        formatted_result = format_application_year_trend(analysis_data)
        print(formatted_result)
    else:
        print("❌ 分析失败，请检查网络连接或API权限")
        
        print("\n🔧 备选方案:")
        print("1. 使用其他分析维度:")
        print("   • 技术领域: --dimension ipc")
        print("   • 申请人: --dimension applicant")
        print("   • 法律状态: --dimension legalStatus")
        print("2. 缩小搜索范围:")
        print("   • 搜索 锂电池 AND 申请年:[2020 TO 2024]")
        print("   • 搜索 锂电池 AND applicant:\"宁德时代\"")

if __name__ == "__main__":
    main()