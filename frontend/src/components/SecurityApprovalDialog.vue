<!--
百佑 LawyerClaw 安全审批对话框组件
基于 Hermes 安全架构的前端实现

功能:
- 危险命令审批提示
- 安全扫描报告展示
- 用户确认/拒绝操作
-->
<template>
  <div v-if="visible" class="security-dialog-overlay" @click.self="handleCancel">
    <div class="security-dialog">
      <!-- 头部 -->
      <div class="dialog-header" :class="severityClass">
        <span class="dialog-icon">{{ severityIcon }}</span>
        <span class="dialog-title">{{ dialogTitle }}</span>
      </div>
      
      <!-- 内容 -->
      <div class="dialog-content">
        <!-- 危险命令提示 -->
        <div v-if="type === 'command_approval'" class="approval-section">
          <div class="warning-banner">
            <span class="warning-icon">⚠️</span>
            <span class="warning-text">检测到危险命令</span>
          </div>
          
          <div class="command-preview">
            <code>{{ command }}</code>
          </div>
          
          <div class="risk-info">
            <p><strong>风险类型:</strong> {{ patternKey }}</p>
            <p><strong>风险等级:</strong> <span :class="severityClass">{{ severity }}</span></p>
            <p><strong>描述:</strong> {{ description }}</p>
          </div>
          
          <div class="approval-options">
            <label class="option-item">
              <input type="radio" v-model="approvalType" value="session" />
              <span class="option-label">
                <strong>仅本次会话</strong>
                <small>仅允许当前会话执行此命令</small>
              </span>
            </label>
            
            <label class="option-item">
              <input type="radio" v-model="approvalType" value="permanent" />
              <span class="option-label">
                <strong>永久允许</strong>
                <small>所有会话都允许执行此类命令</small>
              </span>
            </label>
          </div>
        </div>
        
        <!-- 安全扫描报告 -->
        <div v-else-if="type === 'skill_scan'" class="scan-section">
          <div class="scan-header">
            <span class="scan-verdict" :class="scanResult.verdict">
              {{ scanResult.verdict.toUpperCase() }}
            </span>
            <span class="scan-count">{{ scanResult.findings_count }} 个问题</span>
          </div>
          
          <div class="findings-list">
            <div v-for="(finding, index) in scanResult.findings" :key="index" 
                 class="finding-item" :class="finding.severity">
              <span class="finding-severity">
                {{ finding.severity === 'critical' ? '🔴' : finding.severity === 'high' ? '🟠' : '🟡' }}
              </span>
              <div class="finding-details">
                <p class="finding-pattern">{{ finding.pattern_id }}</p>
                <p class="finding-file">{{ finding.file }}:{{ finding.line }}</p>
                <p class="finding-match">{{ finding.match }}</p>
              </div>
            </div>
          </div>
        </div>
        
        <!-- 记忆扫描报告 -->
        <div v-else-if="type === 'memory_scan'" class="memory-section">
          <div class="memory-preview">
            <pre>{{ memoryContent }}</pre>
          </div>
          
          <div class="memory-findings">
            <div v-for="(finding, index) in memoryFindings" :key="index" 
                 class="finding-item" :class="finding.severity">
              <span class="finding-severity">
                {{ finding.severity === 'critical' ? '🔴' : finding.severity === 'high' ? '🟠' : '🟡' }}
              </span>
              <span class="finding-desc">{{ finding.description }}</span>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 底部按钮 -->
      <div class="dialog-footer">
        <button class="btn-cancel" @click="handleCancel">取消</button>
        
        <template v-if="type === 'command_approval'">
          <button class="btn-allow-session" @click="handleApprove('session')">
            允许本次
          </button>
          <button class="btn-allow-permanent" @click="handleApprove('permanent')">
            永久允许
          </button>
        </template>
        
        <template v-else-if="type === 'skill_scan' || type === 'memory_scan'">
          <button class="btn-reject" @click="handleReject">拒绝</button>
          <button class="btn-approve" @click="handleApprove('manual')">
            允许
          </button>
        </template>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'SecurityApprovalDialog',
  props: {
    visible: {
      type: Boolean,
      default: false
    },
    type: {
      type: String,
      default: 'command_approval',
      validator: (value) => ['command_approval', 'skill_scan', 'memory_scan'].includes(value)
    },
    // 命令审批相关
    command: {
      type: String,
      default: ''
    },
    patternKey: {
      type: String,
      default: ''
    },
    severity: {
      type: String,
      default: 'high',
      validator: (value) => ['critical', 'high', 'medium', 'low'].includes(value)
    },
    description: {
      type: String,
      default: ''
    },
    // 技能扫描相关
    scanResult: {
      type: Object,
      default: () => ({
        verdict: 'caution',
        findings_count: 0,
        findings: []
      })
    },
    // 记忆扫描相关
    memoryContent: {
      type: String,
      default: ''
    },
    memoryFindings: {
      type: Array,
      default: () => []
    }
  },
  data() {
    return {
      approvalType: 'session'
    }
  },
  computed: {
    severityClass() {
      const map = {
        critical: 'severity-critical',
        high: 'severity-high',
        medium: 'severity-medium',
        low: 'severity-low',
        safe: 'severity-safe',
        caution: 'severity-caution',
        dangerous: 'severity-dangerous'
      }
      return map[this.severity] || map[this.scanResult.verdict] || ''
    },
    severityIcon() {
      const map = {
        critical: '🔴',
        high: '🟠',
        medium: '🟡',
        low: '🟢',
        safe: '✅',
        caution: '⚠️',
        dangerous: '🚫'
      }
      return map[this.severity] || map[this.scanResult.verdict] || '❓'
    },
    dialogTitle() {
      const titles = {
        command_approval: '安全审批',
        skill_scan: '技能安全扫描',
        memory_scan: '记忆内容检查'
      }
      return titles[this.type] || '安全提示'
    }
  },
  methods: {
    handleCancel() {
      this.$emit('cancel')
    },
    handleApprove(type) {
      this.$emit('approve', {
        type: this.type,
        approvalType: type || this.approvalType
      })
    },
    handleReject() {
      this.$emit('reject', {
        type: this.type
      })
    }
  }
}
</script>

<style scoped>
.security-dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  backdrop-filter: blur(4px);
}

.security-dialog {
  background: var(--md-sys-color-surface);
  border-radius: 12px;
  max-width: 600px;
  width: 90%;
  max-height: 80vh;
  overflow: hidden;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

.dialog-header {
  padding: 20px 24px;
  display: flex;
  align-items: center;
  gap: 12px;
  border-bottom: 1px solid var(--md-sys-color-outline-variant);
}

.dialog-header.severity-critical,
.dialog-header.severity-dangerous {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
  color: white;
}

.dialog-header.severity-high,
.dialog-header.severity-caution {
  background: linear-gradient(135deg, #f97316 0%, #ea580c 100%);
  color: white;
}

.dialog-header.severity-medium {
  background: linear-gradient(135deg, #eab308 0%, #ca8a04 100%);
  color: white;
}

.dialog-header.severity-low,
.dialog-header.severity-safe {
  background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
  color: white;
}

.dialog-icon {
  font-size: 24px;
}

.dialog-title {
  font-size: 18px;
  font-weight: 600;
}

.dialog-content {
  padding: 24px;
  max-height: calc(80vh - 140px);
  overflow-y: auto;
}

/* 危险命令提示 */
.warning-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: var(--md-sys-color-error-container);
  border-radius: 8px;
  margin-bottom: 16px;
}

.warning-icon {
  font-size: 20px;
}

.warning-text {
  font-weight: 600;
  color: var(--md-sys-color-on-error-container);
}

.command-preview {
  background: var(--md-sys-color-surface-container-highest);
  padding: 12px 16px;
  border-radius: 8px;
  margin-bottom: 16px;
}

.command-preview code {
  font-family: 'Courier New', monospace;
  font-size: 13px;
  word-break: break-all;
}

.risk-info {
  background: var(--md-sys-color-surface-container);
  padding: 16px;
  border-radius: 8px;
  margin-bottom: 16px;
}

.risk-info p {
  margin: 8px 0;
  font-size: 14px;
}

.approval-options {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.option-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  border: 2px solid var(--md-sys-color-outline-variant);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.option-item:hover {
  border-color: var(--md-sys-color-primary);
  background: var(--md-sys-color-primary-container);
}

.option-item input[type="radio"] {
  margin-top: 4px;
}

.option-label {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.option-label small {
  color: var(--md-sys-color-on-surface-variant);
  font-size: 12px;
}

/* 扫描报告 */
.scan-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.scan-verdict {
  padding: 6px 12px;
  border-radius: 6px;
  font-weight: 600;
  font-size: 14px;
}

.scan-verdict.safe {
  background: #22c55e;
  color: white;
}

.scan-verdict.caution {
  background: #f97316;
  color: white;
}

.scan-verdict.dangerous {
  background: #ef4444;
  color: white;
}

.scan-count {
  color: var(--md-sys-color-on-surface-variant);
  font-size: 14px;
}

.findings-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.finding-item {
  display: flex;
  gap: 12px;
  padding: 12px;
  border-radius: 8px;
  background: var(--md-sys-color-surface-container);
}

.finding-item.critical {
  border-left: 4px solid #ef4444;
}

.finding-item.high {
  border-left: 4px solid #f97316;
}

.finding-item.medium,
.finding-item.low {
  border-left: 4px solid #eab308;
}

.finding-severity {
  font-size: 16px;
}

.finding-details {
  flex: 1;
}

.finding-pattern {
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 4px;
}

.finding-file {
  font-size: 12px;
  color: var(--md-sys-color-on-surface-variant);
  margin-bottom: 4px;
}

.finding-match {
  font-family: 'Courier New', monospace;
  font-size: 12px;
  background: var(--md-sys-color-surface-container-highest);
  padding: 4px 8px;
  border-radius: 4px;
  word-break: break-all;
}

.memory-preview {
  background: var(--md-sys-color-surface-container-highest);
  padding: 12px;
  border-radius: 8px;
  margin-bottom: 16px;
  max-height: 200px;
  overflow-y: auto;
}

.memory-preview pre {
  font-family: 'Courier New', monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
}

/* 底部按钮 */
.dialog-footer {
  padding: 16px 24px;
  border-top: 1px solid var(--md-sys-color-outline-variant);
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.dialog-footer button {
  padding: 10px 20px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.btn-cancel {
  background: var(--md-sys-color-surface-container-high);
  color: var(--md-sys-color-on-surface);
}

.btn-cancel:hover {
  background: var(--md-sys-color-surface-container-highest);
}

.btn-allow-session {
  background: var(--md-sys-color-primary);
  color: var(--md-sys-color-on-primary);
}

.btn-allow-session:hover {
  background: var(--md-sys-color-primary-container);
}

.btn-allow-permanent {
  background: var(--md-sys-color-secondary);
  color: var(--md-sys-color-on-secondary);
}

.btn-allow-permanent:hover {
  background: var(--md-sys-color-secondary-container);
}

.btn-reject {
  background: var(--md-sys-color-error);
  color: var(--md-sys-color-on-error);
}

.btn-reject:hover {
  background: #dc2626;
}

.btn-approve {
  background: var(--md-sys-color-tertiary);
  color: var(--md-sys-color-on-tertiary);
}

.btn-approve:hover {
  background: var(--md-sys-color-tertiary-container);
}
</style>
