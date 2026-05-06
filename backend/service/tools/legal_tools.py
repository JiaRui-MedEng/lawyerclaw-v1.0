"""
法律工具系统
提供法律检索、文档生成、案例分析等专业工具
"""
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    content: str
    data: Optional[Any] = None
    error: Optional[str] = None


class BaseTool(ABC):
    """工具抽象基类"""
    
    name: str = ""
    description: str = ""
    parameters: Dict = {}
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        pass
    
    def to_openai_schema(self) -> dict:
        """转换为 OpenAI 工具格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }
    
    def to_claude_schema(self) -> dict:
        """转换为 Claude 工具格式"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters
        }


class LegalSearchTool(BaseTool):
    """法律条文检索工具"""
    
    name = "legal_search"
    description = "检索中国法律条文、司法解释和典型案例。支持按关键词、法条编号、案由搜索。"
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词或法条编号"
            },
            "category": {
                "type": "string",
                "enum": ["law", "regulation", "judicial_interpretation", "case"],
                "description": "搜索类别：法律/法规/司法解释/案例"
            },
            "limit": {
                "type": "integer",
                "description": "返回结果数量",
                "default": 5
            }
        },
        "required": ["query"]
    }
    
    async def execute(self, query: str, category: str = "law", limit: int = 5) -> ToolResult:
        """
        执行法律检索
        实际应连接法律数据库（如北大法宝、法信等）
        当前返回模拟结果
        """
        # TODO: 接入真实法律数据库 API
        mock_results = [
            {
                "title": "《中华人民共和国民法典》",
                "type": "law",
                "content": f"搜索结果：关于'{query}'的相关规定...",
                "article": "相关法条"
            },
            {
                "title": "最高人民法院关于适用《民法典》若干问题的解释",
                "type": "judicial_interpretation",
                "content": "司法解释相关内容...",
                "article": "第X条"
            },
            {
                "title": f"典型案例：涉及{query}的纠纷案",
                "type": "case",
                "content": "案例摘要：本案涉及...",
                "court": "最高人民法院"
            }
        ]
        
        return ToolResult(
            success=True,
            content=f"检索到 {len(mock_results)} 条关于 '{query}' 的结果：\n\n" + 
                    "\n".join(f"**{r['title']}**\n{r.get('content', '')}\n" for r in mock_results[:limit]),
            data=mock_results[:limit]
        )


class ContractDraftTool(BaseTool):
    """合同起草工具"""
    
    name = "contract_draft"
    description = "根据用户需求和合同类型，起草标准合同文本。支持劳动合同、买卖合同、租赁合同等常见合同类型。"
    parameters = {
        "type": "object",
        "properties": {
            "contract_type": {
                "type": "string",
                "enum": ["labor", "sales", "lease", "service", "partnership", "nda", "custom"],
                "description": "合同类型"
            },
            "parties": {
                "type": "array",
                "items": {"type": "string"},
                "description": "合同各方当事人"
            },
            "key_terms": {
                "type": "string",
                "description": "关键条款描述"
            },
            "special_requirements": {
                "type": "string",
                "description": "特殊要求"
            }
        },
        "required": ["contract_type", "key_terms"]
    }
    
    async def execute(self, contract_type: str, key_terms: str, 
                      parties: List[str] = None, special_requirements: str = "") -> ToolResult:
        """起草合同"""
        type_names = {
            "labor": "劳动合同",
            "sales": "买卖合同",
            "lease": "租赁合同",
            "service": "服务合同",
            "partnership": "合伙协议",
            "nda": "保密协议",
            "custom": "自定义合同"
        }
        
        contract_name = type_names.get(contract_type, "合同")
        
        # 生成合同框架
        draft = f"""# {contract_name}

## 合同编号：[自动生成]
## 签订日期：[填写日期]
## 签订地点：[填写地点]

---

### 甲方：{parties[0] if parties else '[甲方名称]'}
### 乙方：{parties[1] if parties and len(parties) > 1 else '[乙方名称]'}

---

## 第一条 合同目的
根据《中华人民共和国民法典》及相关法律法规，甲乙双方本着平等自愿、诚实信用的原则，就以下事项达成协议。

## 第二条 核心条款
{key_terms}

## 第三条 权利与义务
### 甲方权利义务
1. [根据具体合同类型填写]
2. [根据具体合同类型填写]

### 乙方权利义务
1. [根据具体合同类型填写]
2. [根据具体合同类型填写]

## 第四条 违约责任
任何一方违反本合同约定，应承担违约责任，赔偿守约方因此遭受的直接损失。

## 第五条 争议解决
因本合同引起的争议，双方应协商解决；协商不成的，任何一方均可向合同签订地人民法院提起诉讼。

## 第六条 附则
1. 本合同自双方签字盖章之日起生效。
2. 本合同一式两份，甲乙双方各执一份，具有同等法律效力。

---

**甲方（签字/盖章）：**                    **乙方（签字/盖章）：**

日期：____年____月____日                   日期：____年____月____日
"""
        
        if special_requirements:
            draft += f"\n\n## 附加条款\n{special_requirements}\n"
        
        return ToolResult(
            success=True,
            content=draft,
            data={"contract_type": contract_type, "parties": parties}
        )


class CaseAnalysisTool(BaseTool):
    """案例分析工具"""
    
    name = "case_analysis"
    description = "对提供的案件事实进行法律分析，包括：法律关系识别、争议焦点归纳、法律适用建议、风险评估。"
    parameters = {
        "type": "object",
        "properties": {
            "case_facts": {
                "type": "string",
                "description": "案件事实描述"
            },
            "analysis_type": {
                "type": "string",
                "enum": ["full", "risk", "strategy", "legal_basis"],
                "description": "分析类型：全面/风险/策略/法律依据"
            }
        },
        "required": ["case_facts"]
    }
    
    async def execute(self, case_facts: str, analysis_type: str = "full") -> ToolResult:
        """分析案件"""
        analysis = f"""# 案件法律分析报告

## 一、案件概述
{case_facts[:200]}...

## 二、法律关系识别
"""
        
        if analysis_type in ["full", "legal_basis"]:
            analysis += """
根据案件事实，本案涉及以下法律关系：
1. **主要法律关系**：[待识别]
2. **次要法律关系**：[待识别]
3. **可能的竞合关系**：[待分析]

## 三、争议焦点归纳
1. 焦点一：[待归纳]
2. 焦点二：[待归纳]
3. 焦点三：[待归纳]

## 四、法律适用
"""
        
        if analysis_type in ["full", "strategy"]:
            analysis += """
### 适用法律
1. 《中华人民共和国民法典》相关规定
2. 相关司法解释
3. 地方性法规（如适用）

### 诉讼策略建议
1. **证据收集**：[建议收集的证据清单]
2. **诉讼请求**：[建议的诉讼请求]
3. **管辖选择**：[管辖法院建议]
"""
        
        if analysis_type in ["full", "risk"]:
            analysis += """
## 五、风险评估

### 有利因素
- [列出对当事人有利的事实和法律依据]

### 不利因素
- [列出对当事人不利的事实和法律风险]

### 胜诉概率评估
- **高**：[条件]
- **中**：[条件]
- **低**：[条件]
"""
        
        analysis += """
---
*注：本分析基于提供的案件事实，仅供参考，具体案件需结合完整证据材料进行详细分析。*
"""
        
        return ToolResult(
            success=True,
            content=analysis,
            data={"analysis_type": analysis_type}
        )


class DocumentReviewTool(BaseTool):
    """文书审查工具"""
    
    name = "document_review"
    description = "审查法律文书的合规性，识别风险条款，提出修改建议。适用于合同、协议、声明等文书。"
    parameters = {
        "type": "object",
        "properties": {
            "document_content": {
                "type": "string",
                "description": "待审查的文书内容"
            },
            "review_focus": {
                "type": "string",
                "enum": ["compliance", "risk", "completeness", "fairness"],
                "description": "审查重点：合规/风险/完整性/公平性"
            }
        },
        "required": ["document_content"]
    }
    
    async def execute(self, document_content: str, review_focus: str = "compliance") -> ToolResult:
        """审查文书"""
        review_result = f"""# 文书审查报告

## 审查信息
- **审查类型**：{review_focus}
- **文书长度**：{len(document_content)} 字符

## 审查发现

### ⚠️ 风险条款
1. [待识别]

### ✅ 合规条款
1. [待确认]

### 📝 修改建议
1. [待提出]

## 总体评价
[待评估]

---
*注：审查结果仅供参考，建议结合具体业务场景进行最终判断。*
"""
        
        return ToolResult(
            success=True,
            content=review_result,
            data={"review_focus": review_focus, "doc_length": len(document_content)}
        )


class LegalCalcTool(BaseTool):
    """法律计算工具（赔偿金、利息等）"""
    
    name = "legal_calc"
    description = "计算法律相关的金额，包括：赔偿金、违约金、利息、诉讼费等。"
    parameters = {
        "type": "object",
        "properties": {
            "calc_type": {
                "type": "string",
                "enum": ["compensation", "penalty", "interest", "court_fee", "labor_compensation"],
                "description": "计算类型"
            },
            "base_amount": {
                "type": "number",
                "description": "基数金额"
            },
            "parameters": {
                "type": "object",
                "description": "计算参数"
            }
        },
        "required": ["calc_type", "base_amount"]
    }
    
    async def execute(self, calc_type: str, base_amount: float, parameters: dict = None) -> ToolResult:
        """执行法律计算"""
        params = parameters or {}
        result = {}
        
        if calc_type == "interest":
            rate = params.get("annual_rate", 0.0365)  # 默认年利率 3.65%
            days = params.get("days", 365)
            interest = base_amount * rate * days / 365
            result = {
                "principal": base_amount,
                "annual_rate": rate,
                "days": days,
                "interest": round(interest, 2),
                "total": round(base_amount + interest, 2)
            }
        elif calc_type == "court_fee":
            #  simplified 诉讼费计算
            if base_amount <= 10000:
                fee = 50
            elif base_amount <= 100000:
                fee = base_amount * 0.025 - 200
            elif base_amount <= 200000:
                fee = base_amount * 0.02 + 300
            elif base_amount <= 500000:
                fee = base_amount * 0.015 + 1300
            elif base_amount <= 1000000:
                fee = base_amount * 0.01 + 3800
            else:
                fee = base_amount * 0.005 + 8800
            result = {
                "claim_amount": base_amount,
                "court_fee": round(fee, 2)
            }
        elif calc_type == "labor_compensation":
            years = params.get("years", 1)
            monthly_salary = params.get("monthly_salary", base_amount)
            compensation = monthly_salary * years
            result = {
                "monthly_salary": monthly_salary,
                "years_of_service": years,
                "severance_pay": round(compensation, 2)
            }
        else:
            result = {"base_amount": base_amount, "result": "待实现"}
        
        content = f"""# 计算结果

## 计算类型：{calc_type}

"""
        for k, v in result.items():
            content += f"- **{k}**：{v}\n"
        
        return ToolResult(success=True, content=content, data=result)


# 工具注册表
class ToolRegistry:
    """工具注册和管理"""
    
    def __init__(self):
        self._tools = {}
        self._register_builtins()
        self._register_file_tools()  # ⭐ 新增：注册文件工具
    
    def _register_builtins(self):
        """注册内置法律工具"""
        tools = [
            LegalSearchTool(),
            ContractDraftTool(),
            CaseAnalysisTool(),
            DocumentReviewTool(),
            LegalCalcTool()
        ]
        for tool in tools:
            self.register(tool)
        
        # ⭐ 注册 Vision 工具（图片分析和 OCR）
        try:
            from service.tools.vision_tools import VisionAnalyzeTool, OCRTool
            self.register(VisionAnalyzeTool())
            self.register(OCRTool())
            logger.info("✅ Vision 工具已注册（vision_analyze, ocr_extract）")
        except Exception as e:
            logger.warning(f"⚠️ Vision 工具注册失败：{e}")
        
        # ⭐ 注册 Style Forge 工具（风格分析与润色）
        try:
            from service.tools.style_tools import (
                StyleAnalyzeTool,
                StylePolishTool,
                StyleListTool,
                StyleExportTool,
            )
            self.register(StyleAnalyzeTool())
            self.register(StylePolishTool())
            self.register(StyleListTool())
            self.register(StyleExportTool())
            logger.info("✅ Style Forge 工具已注册（style_analyze, style_polish, style_list, style_export）")
        except Exception as e:
            logger.warning(f"⚠️ Style Forge 工具注册失败：{e}")
        
        # ⭐ 注册 Tavily 互联网搜索工具
        try:
            from service.tools.tavily_search import TavilySearchTool
            tavily_tool = TavilySearchTool()
            if tavily_tool.is_available():
                self.register(tavily_tool)
                logger.info("✅ Tavily 搜索工具已注册")
            else:
                logger.warning("⚠️ Tavily 搜索工具不可用（检查 TAVILY_API_KEY）")
        except ImportError as e:
            logger.warning(f"⚠️ Tavily 搜索工具未安装：{e}")
        
        # ⭐ 注册 Skills 工具（skills_list, check_skill_readiness, get_skill_info）
        try:
            from service.tools.skills_tools import SKILLS_TOOLS
            for tool in SKILLS_TOOLS:
                self.register(tool)
            logger.info("✅ Skills 工具已注册（skills_list, check_skill_readiness, get_skill_info）")
        except Exception as e:
            logger.warning(f"⚠️ Skills 工具注册失败：{e}")

        # ⭐ 注册 Python 代码执行工具（python_executor）
        try:
            from service.tools.python_executor import python_executor_tool
            self.register(python_executor_tool)
            logger.info("✅ Python 执行工具已注册（python_executor）")
        except Exception as e:
            logger.warning(f"⚠️ Python 执行工具注册失败：{e}")
    
    def _register_file_tools(self):
        """注册文件操作工具"""
        # 延迟到 __init__ 完成后注册
        pass
    
    def register(self, tool: BaseTool):
        """注册工具"""
        self._tools[tool.name] = tool
    
    def get(self, name: str) -> Optional[BaseTool]:
        """获取工具"""
        return self._tools.get(name)
    
    def list_tools(self) -> List[dict]:
        """列出所有工具"""
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters
            }
            for t in self._tools.values()
        ]
    
    def get_openai_tools(self) -> List[dict]:
        """获取 OpenAI 格式的工具列表"""
        return [t.to_openai_schema() for t in self._tools.values()]
    
    def get_claude_tools(self) -> List[dict]:
        """获取 Claude 格式的工具列表"""
        return [t.to_claude_schema() for t in self._tools.values()]
    
    async def execute(self, name: str, **kwargs) -> ToolResult:
        """执行工具"""
        tool = self.get(name)
        if not tool:
            return ToolResult(success=False, content="", error=f"工具 '{name}' 不存在")
        return await tool.execute(**kwargs)


# 全局实例
registry = ToolRegistry()

# 注册文件工具（延迟注册，避免循环依赖）
try:
    from service.tools.file_tool_registry import register_all
    register_all()
    logger.info("文件工具已注册")
except Exception as e:
    logger.warning(f"文件工具注册失败：{e}")
