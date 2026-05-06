#!/usr/bin/env python3
"""
锂电池专利年度申请趋势分析 - 替代方案
通过搜索接口获取数据并分析趋势
"""

import json
import requests
import sys
from collections import Counter
from datetime import datetime

from patent_token import get_patent_api_token


def search_patents(query, token, page=1, page_size=100):
    """搜索专利"""
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
            return response.json()
        else:
            print(f"❌ HTTP错误: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ 搜索失败: {str(e)}")
        return None

def extract_years_from_patents(patents):
    """从专利数据中提取申请年份"""
    year_counter = Counter()
    
    for patent in patents:
        # 尝试从不同字段提取年份
        application_date = patent.get('ad', '')  # 申请日
        publication_date = patent.get('pd', '')  # 公开日
        
        # 从日期字符串中提取年份
        for date_str in [application_date, publication_date]:
            if date_str and len(date_str) >= 4:
                year_str = date_str[:4]
                if year_str.isdigit():
                    year = int(year_str)
                    if 1980 <= year <= datetime.now().year:
                        year_counter[year] += 1
                        break
    
    return year_counter

def analyze_trend_from_samples(query, token, sample_size=500):
    """通过样本分析趋势"""
    print(f"🔍 正在采集样本数据...")
    print(f"📊 计划采集 {sample_size} 条专利样本")
    
    all_years = Counter()
    total_patents = 0
    page = 1
    page_size = min(100, sample_size)
    
    while total_patents < sample_size:
        print(f"⏳ 采集第 {page} 页数据...")
        
        result = search_patents(query, token, page, page_size)
        
        if not result or not result.get("success"):
            print(f"❌ 第 {page} 页数据获取失败")
            break
        
        patents = result.get("patents", [])
        if not patents:
            break
        
        # 提取年份
        year_counter = extract_years_from_patents(patents)
        all_years.update(year_counter)
        
        total_patents += len(patents)
        page += 1
        
        # 检查是否还有更多数据
        total_in_result = result.get("total", 0)
        if total_patents >= min(sample_size, total_in_result):
            break
    
    return all_years, total_patents

def format_trend_analysis(years_counter, total_samples):
    """格式化趋势分析结果"""
    if not years_counter:
        return "❌ 无法提取有效的年份数据"
    
    # 按年份排序
    sorted_years = sorted(years_counter.items())
    
    output = []
    output.append("📈 锂电池专利年度申请趋势分析 (基于样本数据)")
    output.append("=" * 60)
    
    # 基本信息
    start_year = min(years_counter.keys())
    end_year = max(years_counter.keys())
    total_patents_in_sample = sum(years_counter.values())
    
    output.append(f"📊 分析样本: {total_samples:,} 条专利")
    output.append(f"📅 时间跨度: {start_year} - {end_year} 年")
    output.append(f"📈 覆盖年份: {len(years_counter)} 年")
    output.append("=" * 60)
    
    # 年度分布
    output.append("📅 年度申请分布 (基于样本):")
    output.append("-" * 50)
    
    # 按年代分组
    decades = {}
    for year, count in sorted_years:
        decade = (year // 10) * 10
        if decade not in decades:
            decades[decade] = []
        decades[decade].append((year, count))
    
    # 显示每个年代的数据
    for decade in sorted(decades.keys()):
        decade_data = decades[decade]
        decade_years = [year for year, _ in decade_data]
        decade_total = sum(count for _, count in decade_data)
        
        output.append(f"\n📅 {decade}年代 ({min(decade_years)}-{max(decade_years)}):")
        output.append(f"   年代样本数: {decade_total:,} 件")
        
        # 显示该年代每年的数据
        for year, count in sorted(decade_data):
            # 计算相对比例（基于该年代最大值）
            max_in_decade = max(count for _, count in decade_data)
            if max_in_decade > 0:
                bar_length = int(count / max_in_decade * 30)
                bar = "█" * bar_length + "░" * (30 - bar_length)
                output.append(f"   {year}: {count:4,} 件 {bar}")
    
    # 趋势分析
    if len(sorted_years) >= 5:
        # 计算最近5年的趋势
        recent_years = sorted_years[-5:]
        years = [year for year, _ in recent_years]
        counts = [count for _, count in recent_years]
        
        # 计算增长率
        growth_rates = []
        for i in range(1, len(counts)):
            if counts[i-1] > 0:
                growth = (counts[i] - counts[i-1]) / counts[i-1] * 100
                growth_rates.append(growth)
        
        if growth_rates:
            avg_growth = sum(growth_rates) / len(growth_rates)
            
            output.append("\n📈 最近5年趋势分析:")
            output.append(f"   平均年增长率: {avg_growth:+.1f}%")
            
            if avg_growth > 15:
                output.append("   🚀 趋势: 爆发式增长")
            elif avg_growth > 5:
                output.append("   📈 趋势: 快速增长")
            elif avg_growth > 0:
                output.append("   ↗️  趋势: 稳步增长")
            elif avg_growth > -5:
                output.append("   ↘️  趋势: 略有下降")
            else:
                output.append("   📉 趋势: 明显下滑")
    
    # 找出峰值年份
    if years_counter:
        peak_year, peak_count = max(years_counter.items(), key=lambda x: x[1])
        output.append(f"\n🏆 申请峰值年份: {peak_year}年")
        output.append(f"   峰值样本数: {peak_count:,} 件")
        
        # 计算峰值占比
        if total_patents_in_sample > 0:
            peak_percentage = peak_count / total_patents_in_sample * 100
            output.append(f"   峰值占比: {peak_percentage:.1f}%")
    
    # 技术发展阶段判断
    if len(sorted_years) >= 10:
        first_half = sorted_years[:len(sorted_years)//2]
        second_half = sorted_years[len(sorted_years)//2:]
        
        first_avg = sum(count for _, count in first_half) / len(first_half)
        second_avg = sum(count for _, count in second_half) / len(second_half)
        
        output.append("\n🔬 技术发展阶段判断:")
        if second_avg > first_avg * 2:
            output.append("   🚀 阶段: 技术爆发期")
        elif second_avg > first_avg * 1.2:
            output.append("   📈 阶段: 快速发展期")
        elif second_avg > first_avg:
            output.append("   ⚖️  阶段: 稳步发展期")
        elif second_avg > first_avg * 0.8:
            output.append("   📊 阶段: 成熟稳定期")
        else:
            output.append("   📉 阶段: 技术衰退期")
    
    output.append("\n" + "=" * 60)
    output.append("💡 分析说明:")
    output.append("• 本分析基于500条专利样本数据")
    output.append("• 实际专利总数: 262,995件 (基于之前搜索)")
    output.append("• 样本代表性: 约0.2%的专利数据")
    output.append("• 趋势方向具有参考价值，具体数值仅供参考")
    
    output.append("\n🎯 后续深度分析建议:")
    output.append("• 分析技术领域分布: --dimension ipc")
    output.append("• 分析主要申请人: --dimension applicant")
    output.append("• 分析专利类型: --dimension type")
    output.append("• 分析法律状态: --dimension legalStatus")
    
    return "\n".join(output)

def main():
    """主函数"""
    print("📈 锂电池专利年度申请趋势分析")
    print("=" * 60)
    
    # 加载Token
    token = get_patent_api_token()
    
    if not token:
        print("❌ 未找到有效的Token配置")
        return
    
    print("✅ 已获取 API Token（不在此输出具体内容）")
    print(f"🔍 分析对象: 锂电池")
    print(f"📊 分析方法: 样本统计分析")
    print(f"📈 样本大小: 500条专利")
    print("-" * 50)
    
    # 通过样本分析趋势
    years_counter, total_samples = analyze_trend_from_samples("锂电池", token, 500)
    
    if years_counter:
        # 格式化显示结果
        formatted_result = format_trend_analysis(years_counter, total_samples)
        print(formatted_result)
    else:
        print("❌ 无法获取分析数据")
        
        print("\n🔧 可能的原因:")
        print("1. API权限限制")
        print("2. 网络连接问题")
        print("3. Token权限不足")
        
        print("\n💡 解决方案:")
        print("1. 检查网络连接")
        print("2. 确认Token有效性")
        print("3. 联系API服务商")

if __name__ == "__main__":
    main()