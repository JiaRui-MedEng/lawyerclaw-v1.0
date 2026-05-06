#!/usr/bin/env python3
"""
专利检索API客户端 - 修复版
封装9235.net专利检索API
"""

import os
import json
import requests
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

class PatentAPI:
    """专利API客户端"""
    
    def __init__(self, token: Optional[str] = None, base_url: str = "https://www.9235.net/api"):
        """
        初始化API客户端
        
        Args:
            token: API Token，如果为None则尝试从环境变量或配置文件读取
            base_url: API基础URL
        """
        self.base_url = base_url.rstrip('/')
        
        # 获取token的优先级: 参数 > 环境变量 > 配置文件
        self.token = token
        if not self.token:
            self.token = os.environ.get('PATENT_API_TOKEN')
        
        if not self.token:
            # 尝试从配置文件读取
            config_path = Path(__file__).parent / 'config.json'
            if config_path.exists():
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        self.token = config.get('token')
                except:
                    pass
        
        if not self.token:
            raise ValueError("未找到API Token，请设置环境变量 PATENT_API_TOKEN 或创建配置文件")
    
    def _make_request(self, endpoint: str, params: Dict[str, Any] = None, method: str = 'GET') -> Dict[str, Any]:
        """
        发送API请求
        
        Args:
            endpoint: API端点
            params: 请求参数
            method: 请求方法
            
        Returns:
            API响应数据
        """
        if params is None:
            params = {}
        
        # 添加token和版本号
        params['t'] = self.token
        params['v'] = 1
        
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, params=params, timeout=30)
            else:
                response = requests.post(url, json=params, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "success": False,
                    "errorCode": response.status_code,
                    "message": f"HTTP {response.status_code}: {response.text[:200]}"
                }
                
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "errorCode": 408,
                "message": "请求超时"
            }
        except requests.exceptions.ConnectionError:
            return {
                "success": False,
                "errorCode": 503,
                "message": "连接失败"
            }
        except Exception as e:
            return {
                "success": False,
                "errorCode": 500,
                "message": f"请求异常: {str(e)}"
            }
    
    def search(self, query: str, page: int = 1, page_size: int = 10, 
               data_scope: str = "cn", sort: str = "relation") -> Dict[str, Any]:
        """
        搜索专利
        
        Args:
            query: 检索式
            page: 页码
            page_size: 每页条数
            data_scope: 数据范围 (cn/all)
            sort: 排序字段
            
        Returns:
            搜索结果
        """
        params = {
            "ds": data_scope,
            "q": query,
            "p": page,
            "ps": page_size,
            "sort": sort
        }
        
        return self._make_request("/s", params)
    
    def format_search_result(self, result: Dict[str, Any], detailed: bool = False) -> str:
        """
        格式化搜索结果
        
        Args:
            result: 搜索结果
            detailed: 是否显示详细信息
            
        Returns:
            格式化后的字符串
        """
        if not result.get("success"):
            return f"❌ 搜索失败: {result.get('message', '未知错误')}"
        
        patents = result.get("patents", [])
        total = result.get("total", 0)
        ids = result.get("ids", [])
        
        output = []
        output.append(f"🔍 搜索完成")
        output.append(f"📊 找到 {total:,} 条专利")
        
        if ids:
            output.append(f"📋 专利ID: {', '.join(ids[:5])}{'...' if len(ids) > 5 else ''}")
        
        output.append("=" * 50)
        
        if not patents:
            output.append("未找到相关专利")
            return "\n".join(output)
        
        # 显示专利列表
        for i, patent in enumerate(patents[:10], 1):
            # 使用正确的字段名
            title = patent.get('title', '未知标题')
            if len(title) > 60:
                title = title[:60] + "..."
            
            output.append(f"{i}. 📄 {title}")
            output.append(f"   🆔 {patent.get('id', '未知')}")
            output.append(f"   👤 {patent.get('applicant', '未知申请人')}")
            
            if detailed:
                # 显示详细信息
                if patent.get('applicationDate'):
                    output.append(f"   📅 申请: {patent.get('applicationDate')}")
                if patent.get('documentDate'):
                    output.append(f"   📅 公开: {patent.get('documentDate')}")
                if patent.get('ipc'):
                    output.append(f"   🏷️ IPC: {patent.get('ipc')}")
                
                summary = patent.get('summary', '')
                if summary:
                    if len(summary) > 100:
                        summary = summary[:100] + "..."
                    output.append(f"   📖 {summary}")
            else:
                # 简要信息
                summary = patent.get('summary', '')
                if summary:
                    if len(summary) > 80:
                        summary = summary[:80] + "..."
                    output.append(f"   📖 {summary}")
            
            output.append("")
        
        if total > 10:
            output.append(f"📄 还有 {total-10} 条专利未显示")
            output.append("💡 使用 --page 2 查看下一页，或 --details 显示详细信息")
        
        return "\n".join(output)
    
    def get_patent_base(self, patent_id: str) -> Dict[str, Any]:
        """
        获取专利基本信息
        
        Args:
            patent_id: 专利ID
            
        Returns:
            专利基本信息
        """
        params = {
            "id": patent_id
        }
        
        return self._make_request("/patent/base", params)
    
    def get_patent_claims(self, patent_id: str) -> Dict[str, Any]:
        """
        获取专利权利要求
        
        Args:
            patent_id: 专利ID
            
        Returns:
            专利权利要求
        """
        params = {
            "id": patent_id
        }
        
        return self._make_request("/patent/claims", params)
    
    def get_patent_desc(self, patent_id: str) -> Dict[str, Any]:
        """
        获取专利说明书
        
        Args:
            patent_id: 专利ID
            
        Returns:
            专利说明书
        """
        params = {
            "id": patent_id
        }
        
        return self._make_request("/patent/desc", params)
    
    def get_patent_tx(self, patent_id: str) -> Dict[str, Any]:
        """
        获取专利法律信息
        
        Args:
            patent_id: 专利ID
            
        Returns:
            专利法律信息
        """
        params = {
            "id": patent_id
        }
        
        return self._make_request("/patent/tx", params)
    
    def get_patent_citing(self, patent_id: str) -> Dict[str, Any]:
        """
        获取专利引用分析
        
        Args:
            patent_id: 专利ID
            
        Returns:
            专利引用分析
        """
        params = {
            "id": patent_id
        }
        
        return self._make_request("/patent/citing", params)
    
    def get_patent_like(self, patent_id: str) -> Dict[str, Any]:
        """
        获取相似专利
        
        Args:
            patent_id: 专利ID
            
        Returns:
            相似专利列表
        """
        params = {
            "id": patent_id
        }
        
        return self._make_request("/patent/like", params)
    
    def get_analysis(self, query: str, dimension: str, data_scope: str = "cn") -> Dict[str, Any]:
        """
        获取统计分析
        
        Args:
            query: 检索式
            dimension: 分析维度
            data_scope: 数据范围
            
        Returns:
            统计分析结果
        """
        params = {
            "ds": data_scope,
            "q": query,
            "dimension": dimension
        }
        
        return self._make_request("/analysis", params)
    
    def get_company_portrait(self, company_name: str) -> Dict[str, Any]:
        """
        获取企业画像
        
        Args:
            company_name: 企业名称
            
        Returns:
            企业画像数据
        """
        params = {
            "company": company_name
        }
        
        return self._make_request("/company/portrait", params)
    
    def search_copyright(self, query: str, copyright_type: str = "software", 
                        field: str = None, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """
        搜索著作权
        
        Args:
            query: 检索式
            copyright_type: 著作权类型 (software/works)
            field: 查询字段
            page: 页码
            page_size: 每页条数
            
        Returns:
            著作权搜索结果
        """
        params = {
            "type": copyright_type,
            "q": query,
            "p": page,
            "ps": page_size
        }
        
        if field:
            params["field"] = field
        
        return self._make_request("/copyright/search", params)
    
    def search_trademark(self, query: str, page: int = 1, page_size: int = 10, 
                        sort: str = None) -> Dict[str, Any]:
        """
        搜索商标
        
        Args:
            query: 检索式
            page: 页码
            page_size: 每页条数
            sort: 排序字段
            
        Returns:
            商标搜索结果
        """
        params = {
            "q": query,
            "p": page,
            "ps": page_size
        }
        
        if sort:
            params["sort"] = sort
        
        return self._make_request("/trademark/search", params)
    
    def get_trademark_detail(self, trademark_id: str) -> Dict[str, Any]:
        """
        获取商标详情
        
        Args:
            trademark_id: 商标ID
            
        Returns:
            商标详情
        """
        params = {
            "id": trademark_id
        }
        
        return self._make_request("/trademark/detail", params)
    
    def download_pdf(self, pdf_path: str, output_dir: str = "./downloads") -> bool:
        """
        下载PDF文件
        
        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录
            
        Returns:
            是否下载成功
        """
        try:
            # 创建输出目录
            os.makedirs(output_dir, exist_ok=True)
            
            # 构建完整URL
            pdf_url = f"{self.base_url}/pdf?path={pdf_path}&t={self.token}"
            
            # 下载文件
            response = requests.get(pdf_url, timeout=60)
            
            if response.status_code == 200:
                # 提取文件名
                filename = os.path.basename(pdf_path)
                if not filename.endswith('.pdf'):
                    filename += '.pdf'
                
                # 保存文件
                output_path = os.path.join(output_dir, filename)
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                
                return True
            else:
                return False
                
        except Exception as e:
            print(f"下载失败: {str(e)}")
            return False
    
    def download_image(self, image_path: str, output_dir: str = "./downloads") -> bool:
        """
        下载图片文件
        
        Args:
            image_path: 图片文件路径
            output_dir: 输出目录
            
        Returns:
            是否下载成功
        """
        try:
            # 创建输出目录
            os.makedirs(output_dir, exist_ok=True)
            
            # 构建完整URL
            image_url = f"{self.base_url}/img?path={image_path}&t={self.token}"
            
            # 下载文件
            response = requests.get(image_url, timeout=60)
            
            if response.status_code == 200:
                # 提取文件名
                filename = os.path.basename(image_path)
                if not any(filename.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                    filename += '.jpg'
                
                # 保存文件
                output_path = os.path.join(output_dir, filename)
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                
                return True
            else:
                return False
                
        except Exception as e:
            print(f"下载失败: {str(e)}")
            return False

# 单例模式支持
_patent_api = None

def get_patent_api() -> PatentAPI:
    """
    获取PatentAPI单例实例
    
    Returns:
        PatentAPI实例
    """
    global _patent_api
    
    if _patent_api is None:
        # 尝试从配置文件读取token
        config_path = Path(__file__).parent / 'config.json'
        token = None
        
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    token = config.get('token')
            except:
                pass
        
        _patent_api = PatentAPI(token=token)
    
    return _patent_api

if __name__ == '__main__':
    # 测试代码
    try:
        api = get_patent_api()
        
        # 测试搜索
        print("🔍 测试搜索功能...")
        result = api.search("无人机", page_size=3)
        
        if result.get('success'):
            print("✅ 搜索测试成功")
            print(f"📊 找到 {result.get('total', 0)} 条专利")
            
            # 测试格式化输出
            formatted = api.format_search_result(result)
            print("\n📄 搜索结果示例:")
            print(formatted[:500] + "..." if len(formatted) > 500 else formatted)
            
            # 测试获取详情（如果有专利）
            patents = result.get('patents', [])
            if patents:
                patent_id = patents[0]['id']
                print(f"\n🔍 测试获取专利详情: {patent_id}")
                detail = api.get_patent_base(patent_id)
                
                if detail.get('success'):
                    print("✅ 专利详情获取成功")
                    patent = detail.get('patent', {})
                    print(f"📝 标题: {patent.get('title', '未知')[:50]}...")
                    print(f"👤 申请人: {patent.get('applicant', '未知')}")
                else:
                    print(f"❌ 专利详情获取失败: {detail.get('message', '未知错误')}")
        else:
            print(f"❌ 搜索测试失败: {result.get('message', '未知错误')}")
            
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {str(e)}")
        print("\n💡 可能的原因:")
        print("1. 未配置API Token")
        print("2. 网络连接问题")
        print("3. API服务不可用")
        
        print("\n🔧 解决方案:")
        print("1. 设置环境变量: export PATENT_API_TOKEN='您的Token'")
        print("2. 创建配置文件: config.json")
        print("3. 检查网络连接")