<template>
  <div class="tools-view">
    <h2>🛠️ 工具箱</h2>
    <p class="view-desc">专业法律工具，辅助您的日常工作</p>
    
    <!-- 工具卡片网格 -->
    <div class="tools-grid">
      <div
        v-for="tool in tools"
        :key="tool.name"
        class="tool-card"
        @click="openTool(tool)"
      >
        <div class="tool-icon">{{ getToolIcon(tool.name) }}</div>
        <h3 class="tool-name">{{ getToolDisplayName(tool.name) }}</h3>
        <p class="tool-desc">{{ tool.description }}</p>
        <div class="tool-tag">{{ getToolCategory(tool.name) }}</div>
      </div>
    </div>
    
    <!-- 工具执行面板 -->
    <el-dialog
      :title="currentTool ? getToolDisplayName(currentTool.name) : '执行工具'"
      :visible.sync="dialogVisible"
      width="700px"
      top="5vh"
    >
      <div v-if="currentTool" class="tool-exec-panel">
        <!-- 法律检索 -->
        <template v-if="currentTool.name === 'legal_search'">
          <el-form label-width="80px">
            <el-form-item label="搜索内容">
              <el-input v-model="form.query" placeholder="输入关键词或法条编号" />
            </el-form-item>
            <el-form-item label="搜索类别">
              <el-select v-model="form.category" style="width: 100%">
                <el-option label="法律" value="law" />
                <el-option label="法规" value="regulation" />
                <el-option label="司法解释" value="judicial_interpretation" />
                <el-option label="案例" value="case" />
              </el-select>
            </el-form-item>
            <el-form-item label="结果数量">
              <el-slider v-model="form.limit" :min="1" :max="20" show-stops />
            </el-form-item>
          </el-form>
        </template>
        
        <!-- 合同起草 -->
        <template v-if="currentTool.name === 'contract_draft'">
          <el-form label-width="80px">
            <el-form-item label="合同类型">
              <el-select v-model="form.contract_type" style="width: 100%">
                <el-option label="劳动合同" value="labor" />
                <el-option label="买卖合同" value="sales" />
                <el-option label="租赁合同" value="lease" />
                <el-option label="服务合同" value="service" />
                <el-option label="合伙协议" value="partnership" />
                <el-option label="保密协议" value="nda" />
                <el-option label="自定义" value="custom" />
              </el-select>
            </el-form-item>
            <el-form-item label="当事人">
              <el-input v-model="form.partiesInput" placeholder="甲方, 乙方（逗号分隔）" />
            </el-form-item>
            <el-form-item label="核心条款">
              <el-input
                v-model="form.key_terms"
                type="textarea"
                :rows="4"
                placeholder="描述合同的核心内容和条款"
              />
            </el-form-item>
            <el-form-item label="特殊要求">
              <el-input
                v-model="form.special_requirements"
                type="textarea"
                :rows="2"
                placeholder="可选：特殊条款或要求"
              />
            </el-form-item>
          </el-form>
        </template>
        
        <!-- 案件分析 -->
        <template v-if="currentTool.name === 'case_analysis'">
          <el-form label-width="80px">
            <el-form-item label="案件事实">
              <el-input
                v-model="form.case_facts"
                type="textarea"
                :rows="6"
                placeholder="详细描述案件事实..."
              />
            </el-form-item>
            <el-form-item label="分析类型">
              <el-select v-model="form.analysis_type" style="width: 100%">
                <el-option label="全面分析" value="full" />
                <el-option label="风险评估" value="risk" />
                <el-option label="诉讼策略" value="strategy" />
                <el-option label="法律依据" value="legal_basis" />
              </el-select>
            </el-form-item>
          </el-form>
        </template>
        
        <!-- 文书审查 -->
        <template v-if="currentTool.name === 'document_review'">
          <el-form label-width="80px">
            <el-form-item label="文书内容">
              <el-input
                v-model="form.document_content"
                type="textarea"
                :rows="10"
                placeholder="粘贴待审查的文书内容..."
              />
            </el-form-item>
            <el-form-item label="审查重点">
              <el-select v-model="form.review_focus" style="width: 100%">
                <el-option label="合规性" value="compliance" />
                <el-option label="风险识别" value="risk" />
                <el-option label="完整性" value="completeness" />
                <el-option label="公平性" value="fairness" />
              </el-select>
            </el-form-item>
          </el-form>
        </template>
        
        <!-- 法律计算 -->
        <template v-if="currentTool.name === 'legal_calc'">
          <el-form label-width="80px">
            <el-form-item label="计算类型">
              <el-select v-model="form.calc_type" style="width: 100%">
                <el-option label="利息计算" value="interest" />
                <el-option label="诉讼费" value="court_fee" />
                <el-option label="经济补偿金" value="labor_compensation" />
              </el-select>
            </el-form-item>
            <el-form-item label="基数金额">
              <el-input-number v-model="form.base_amount" :min="0" :precision="2" />
            </el-form-item>
            
            <template v-if="form.calc_type === 'interest'">
              <el-form-item label="年利率(%)">
                <el-input-number v-model="form.rate" :min="0" :max="100" :precision="2" :step="0.1" />
              </el-form-item>
              <el-form-item label="天数">
                <el-input-number v-model="form.days" :min="1" :max="3650" />
              </el-form-item>
            </template>
            
            <template v-if="form.calc_type === 'labor_compensation'">
              <el-form-item label="工作年限">
                <el-input-number v-model="form.years" :min="0" :max="50" :precision="1" />
              </el-form-item>
              <el-form-item label="月工资">
                <el-input-number v-model="form.monthly_salary" :min="0" :precision="2" />
              </el-form-item>
            </template>
          </el-form>
        </template>
        
        <!-- 执行按钮 -->
        <div class="exec-actions">
          <el-button type="primary" @click="execute" :loading="executing" icon="el-icon-caret-right">
            执行
          </el-button>
        </div>
        
        <!-- 执行结果 -->
        <div v-if="execResult" class="exec-result">
          <el-divider content-position="left">执行结果</el-divider>
          <div v-html="renderMarkdown(execResult)" class="result-content"></div>
          <el-button size="small" @click="copyResult" icon="el-icon-document-copy">复制结果</el-button>
          <el-button size="small" @click="sendToChat" type="primary" icon="el-icon-s-promotion">
            发送到对话
          </el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { getTools, executeTool } from '../api/tools'
import MarkdownIt from 'markdown-it'

const md = new MarkdownIt()

export default {
  name: 'ToolsView',
  data() {
    return {
      tools: [],
      dialogVisible: false,
      currentTool: null,
      executing: false,
      execResult: '',
      form: {}
    }
  },
  methods: {
    async loadTools() {
      try {
        const res = await getTools()
        if (res.success) {
          this.tools = res.tools
        }
      } catch (e) {
      }
    },
    
    openTool(tool) {
      this.currentTool = tool
      this.execResult = ''
      this.form = this.getDefaultForm(tool.name)
      this.dialogVisible = true
    },
    
    getDefaultForm(toolName) {
      const defaults = {
        legal_search: { query: '', category: 'law', limit: 5 },
        contract_draft: { contract_type: 'labor', partiesInput: '', key_terms: '', special_requirements: '' },
        case_analysis: { case_facts: '', analysis_type: 'full' },
        document_review: { document_content: '', review_focus: 'compliance' },
        legal_calc: { calc_type: 'interest', base_amount: 10000, rate: 3.65, days: 365, years: 1, monthly_salary: 10000 }
      }
      return defaults[toolName] || {}
    },
    
    async execute() {
      this.executing = true
      this.execResult = ''
      
      try {
        const params = { ...this.form }
        
        // 处理特殊字段
        if (params.partiesInput) {
          params.parties = params.partiesInput.split(/[,，]/).map(s => s.trim()).filter(Boolean)
          delete params.partiesInput
        }
        if (params.calc_type === 'interest') {
          params.parameters = { annual_rate: params.rate / 100, days: params.days }
          delete params.rate
          delete params.days
        }
        if (params.calc_type === 'labor_compensation') {
          params.parameters = { years: params.years, monthly_salary: params.monthly_salary }
          delete params.years
          delete params.monthly_salary
        }
        
        const res = await executeTool(this.currentTool.name, params)
        
        if (res.success) {
          this.execResult = res.content
        } else {
          this.$message.error(res.message || res.error || '执行失败')
        }
      } catch (e) {
        this.$message.error('执行失败：' + e.message)
      } finally {
        this.executing = false
      }
    },
    
    copyResult() {
      navigator.clipboard.writeText(this.execResult).then(() => {
        this.$message.success('已复制到剪贴板')
      })
    },
    
    sendToChat() {
      this.$store.commit('chat/ADD_MESSAGE', {
        role: 'user',
        content: `我使用工具「${this.getToolDisplayName(this.currentTool.name)}」得到以下结果：\n\n${this.execResult}\n\n请帮我分析和解读。`,
        created_at: new Date().toISOString()
      })
      this.dialogVisible = false
      this.$router.push('/chat')
    },
    
    renderMarkdown(text) {
      return md.render(text || '')
    },
    
    getToolIcon(name) {
      const icons = {
        legal_search: '🔍',
        contract_draft: '📝',
        case_analysis: '⚖️',
        document_review: '📋',
        legal_calc: '🧮'
      }
      return icons[name] || '🔧'
    },
    
    getToolDisplayName(name) {
      const names = {
        legal_search: '法律检索',
        contract_draft: '合同起草',
        case_analysis: '案件分析',
        document_review: '文书审查',
        legal_calc: '法律计算'
      }
      return names[name] || name
    },
    
    getToolCategory(name) {
      const categories = {
        legal_search: '检索',
        contract_draft: '生成',
        case_analysis: '分析',
        document_review: '审查',
        legal_calc: '计算'
      }
      return categories[name] || '工具'
    }
  },
  
  mounted() {
    this.loadTools()
  }
}
</script>

<style scoped>
.tools-view {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
}

.view-desc {
  color: #666;
  margin-bottom: 32px;
}

.tools-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
}

.tool-card {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  cursor: pointer;
  transition: all 0.3s;
  border: 1px solid #eee;
}

.tool-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0,0,0,0.1);
  border-color: #409eff;
}

.tool-icon {
  font-size: 40px;
  margin-bottom: 12px;
}

.tool-name {
  font-size: 18px;
  margin-bottom: 8px;
  color: #333;
}

.tool-desc {
  font-size: 14px;
  color: #666;
  line-height: 1.5;
  margin-bottom: 12px;
  min-height: 42px;
}

.tool-tag {
  display: inline-block;
  background: #ecf5ff;
  color: #409eff;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
}

.tool-exec-panel {
  padding: 8px 0;
}

.exec-actions {
  text-align: center;
  margin: 24px 0;
}

.exec-result {
  background: #f9f9f9;
  border-radius: 8px;
  padding: 20px;
  max-height: 500px;
  overflow-y: auto;
}

.result-content {
  line-height: 1.8;
  margin-bottom: 16px;
}

.result-content ::v-deep pre {
  background: #f0f0f0;
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
}

.result-content ::v-deep code {
  background: #f0f0f0;
  padding: 2px 6px;
  border-radius: 4px;
}
</style>
