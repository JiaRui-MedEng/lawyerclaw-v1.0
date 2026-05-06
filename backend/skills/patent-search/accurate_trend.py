#!/usr/bin/env python3
"""
准确的锂电池专利年度申请趋势分析
基于API返回的实际数据
"""

import json
import requests
import sys
from collections import Counter
from datetime import datetime

from patent_token import get_patent_api_token


def fetch_patent_samples(query, token, sample_size=200):
    """获取专利样本数据"""
    print(f"🔍 正在获取专利样本数据...")
    print(f"📊 目标样本数: {sample_size} 条")
    
    all_patents = []
    page = 1
    page_size = 50  # 每页获取50条
    
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
    
    return all_patents[:sample_size]  # 返回不超过样本大小的数据

def analyze_yearly_trend(patents):
    """分析年度趋势"""
    if not patents:
        return None
    
    # 统计每年的专利数量
    year_counter = Counter()
    
    for patent in patents:
        application_date = patent.get('applicationDate', '')
        if application_date and len(application_date) >= 4:
            year_str = application_date[:4]
            if year_str.isdigit():
                year = int(year_str)
                if 1980 <= year <= datetime.now().year:
                    year_counter[year] += 1
    
    return year_counter

def format_trend_report(year_counter, total_patents, query):
    """格式化趋势分析报告"""
    if not year_counter:
        return "❌ 无法提取年份数据"
    
    # 按年份排序
    sorted_years = sorted(year_counter.items())
    
    output = []
    output.append(f"📈 {query}专利年度申请趋势分析")
    output.append("=" * 60)
    
    # 基本信息
    start_year = min(year_counter.keys())
    end_year = max(year_counter.keys())
    total_years = len(year_counter)
    total_count = sum(year_counter.values())
    
    output.append(f"📊 分析样本: {total_patents:,} 条专利")
    output.append(f"📅 时间跨度: {start_year} - {end_year} 年 ({total_years} 年)")
    output.append(f"📈 有效样本: {total_count:,} 条 (含申请日期)")
    output.append("=" * 60)
    
    # 年度分布表格
    output.append("📅 年度申请分布:")
    output.append("-" * 50)
    
    # 按年代分组显示
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
        output.append(f"   年代总数: {decade_total:,} 件")
        output.append(f"   年代占比: {decade_total/total_count*100:.1f}%")
        
        # 显示该年代每年的数据
        for year, count in sorted(decade_data):
            # 计算年度占比
            year_percentage = count / total_count * 100
            
            # 创建条形图
            max_in_decade = max(count for _, count in decade_data)
            if max_in_decade > 0:
                bar_length = int(count / max_in_decade * 30)
                bar = "█" * bar_length + "░" * (30 - bar_length)
                output.append(f"   {year}: {count:4,} 件 ({year_percentage:4.1f}%) {bar}")
    
    # 趋势分析
    if len(sorted_years) >= 5:
        # 最近5年数据
        recent_years = sorted_years[-5:]
        years = [year for year, _ in recent_years]
        counts = [count for _, count in recent_years]
        
        output.append("\n📈 最近5年趋势分析:")
        output.append("-" * 50)
        
        # 计算每年增长
        for i in range(len(recent_years)):
            year, count = recent_years[i]
            if i == 0:
                output.append(f"   {year}: {count:,} 件 (基准年)")
            else:
                prev_count = recent_years[i-1][1]
                if prev_count > 0:
                    growth = (count - prev_count) / prev_count * 100
                    growth_symbol = "📈" if growth > 0 else "📉" if growth < 0 else "➡️"
                    output.append(f"   {year}: {count:,} 件 ({growth:+.1f}%) {growth_symbol}")
        
        # 计算平均增长率
        growth_rates = []
        for i in range(1, len(counts)):
            if counts[i-1] > 0:
                growth = (counts[i] - counts[i-1]) / counts[i-1] * 100
                growth_rates.append(growth)
        
        if growth_rates:
            avg_growth = sum(growth_rates) / len(growth_rates)
            output.append(f"\n   📊 平均年增长率: {avg_growth:+.1f}%")
            
            # 趋势判断
            if avg_growth > 20:
                output.append("   🚀 趋势判断: 爆发式增长期")
            elif avg_growth > 10:
                output.append("   📈 趋势判断: 快速增长期")
            elif avg_growth > 0:
                output.append("   ↗️  趋势判断: 稳步增长期")
            elif avg_growth > -5:
                output.append("   ↘️  趋势判断: 平稳调整期")
            else:
                output.append("   📉 趋势判断: 技术衰退期")
    
    # 峰值分析
    if year_counter:
        peak_year, peak_count = max(year_counter.items(), key=lambda x: x[1])
        output.append(f"\n🏆 申请峰值分析:")
        output.append(f"   峰值年份: {peak_year}年")
        output.append(f"   峰值数量: {peak_count:,} 件")
        output.append(f"   峰值占比: {peak_count/total_count*100:.1f}%")
        
        # 检查峰值后趋势
        if peak_year < end_year:
            post_peak_years = [count for year, count in sorted_years if year > peak_year]
            if post_peak_years:
                post_peak_avg = sum(post_peak_years) / len(post_peak_years)
                if post_peak_avg < peak_count * 0.7:
                    output.append("   📉 峰值后趋势: 申请量明显下降")
                elif post_peak_avg < peak_count * 0.9:
                    output.append("   ↘️  峰值后趋势: 申请量略有下降")
                else:
                    output.append("   ⚖️  峰值后趋势: 申请量保持高位")
    
    # 技术发展阶段
    if len(sorted_years) >= 8:
        # 分为三个阶段
        stage_size = len(sorted_years) // 3
        stages = [
            ("早期阶段", sorted_years[:stage_size]),
            ("中期阶段", sorted_years[stage_size:stage_size*2]),
            ("近期阶段", sorted_years[stage_size*2:])
        ]
        
        output.append("\n🔬 技术发展阶段分析:")
        for stage_name, stage_data in stages:
            if stage_data:
                stage_years = [year for year, _ in stage_data]
                stage_total = sum(count for _, count in stage_data)
                stage_avg = stage_total / len(stage_data)
                output.append(f"   {stage_name} ({min(stage_years)}-{max(stage_years)}):")
                output.append(f"     年均申请: {stage_avg:.1f} 件")
                output.append(f"     阶段占比: {stage_total/total_count*100:.1f}%")
    
    output.append("\n" + "=" * 60)
    output.append("💡 数据说明:")
    output.append(f"• 基于 {total_patents:,} 条专利样本分析")
    output.append(f"• 其中 {total_count:,} 条包含申请日期信息")
    output.append(f"• 样本代表性: 约{total_patents/262995*100:.2f}% (基于262,995条总数)")
    output.append("• 趋势分析具有统计参考价值")
    
    output.append("\n🎯 深度分析建议:")
    output.append("• 分析技术热点: --dimension ipc")
    output.append("• 分析竞争格局: --dimension applicant")
    output.append("• 分析专利质量: --dimension type")
    output.append("• 分析市场布局: --dimension province")
    
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
    print(f"📊 分析方法: 基于API返回的实际数据")
    print(f"📈 样本目标: 200条专利")
    print("-" * 50)
    
    # 获取专利样本
    patents = fetch_patent_samples("锂电池", token, 200)
    
    if not patents:
        print("❌ 无法获取专利数据")
        return
    
    print(f"\n✅ 成功获取 {len(patents)} 条专利样本")
    
    # 分析年度趋势
    year_counter = analyze_yearly_trend(patents)
    
    if not year_counter:
        print("❌ 无法从样本中提取申请年份信息")
        print("\n🔍 检查发现:")
        print("• 部分专利可能缺少applicationDate字段")
        print("• 或字段格式不符合预期")
        return
    
    # 生成分析报告
    report = format_trend_report(year_counter, len(patents), "锂电池")
    print("\n" + report)

if __name__ == "__main__":
    main()