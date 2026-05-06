/**
 * 百佑 LawyerClaw 安全 API 客户端
 * 基于 Hermes 安全架构
 */

import axios from 'axios'

const API_BASE = '/api/security'

/**
 * 检查命令审批状态
 * @param {string} command - 要检查的命令
 * @param {string} sessionId - 会话 ID
 * @returns {Promise<Object>}
 */
export async function checkCommandApproval(command, sessionId) {
  const response = await axios.post(`${API_BASE}/command/check`, {
    command,
    session_id: sessionId
  })
  return response.data
}

/**
 * 审批危险命令
 * @param {string} sessionId - 会话 ID
 * @param {string} patternKey - 危险模式标识
 * @param {string} approvalType - 审批类型 (session/permanent)
 * @returns {Promise<Object>}
 */
export async function approveCommand(sessionId, patternKey, approvalType = 'session') {
  const response = await axios.post(`${API_BASE}/command/approve`, {
    session_id: sessionId,
    pattern_key: patternKey,
    approval_type: approvalType
  })
  return response.data
}

/**
 * 扫描技能安全性
 * @param {string} skillDir - 技能目录路径
 * @param {string} source - 来源类型 (community/trusted/internal/legal)
 * @returns {Promise<Object>}
 */
export async function scanSkill(skillDir, source = 'community') {
  const response = await axios.post(`${API_BASE}/skill/scan`, {
    skill_dir: skillDir,
    source
  })
  return response.data
}

/**
 * 扫描记忆内容安全性
 * @param {string} content - 记忆内容
 * @param {string} source - 来源类型 (user/agent/system)
 * @returns {Promise<Object>}
 */
export async function scanMemory(content, source = 'user') {
  const response = await axios.post(`${API_BASE}/memory/scan`, {
    content,
    source
  })
  return response.data
}

/**
 * 获取安全审计日志
 * @param {Object} params - 查询参数
 * @param {string} params.sessionId - 会话 ID
 * @param {string} params.auditType - 审计类型
 * @param {number} params.limit - 返回数量限制
 * @returns {Promise<Object>}
 */
export async function getAuditLogs(params = {}) {
  const response = await axios.get(`${API_BASE}/audit/logs`, { params })
  return response.data
}

/**
 * 获取安全审计统计
 * @returns {Promise<Object>}
 */
export async function getAuditStatistics() {
  const response = await axios.get(`${API_BASE}/audit/statistics`)
  return response.data
}

/**
 * 获取审批记录列表
 * @param {Object} params - 查询参数
 * @returns {Promise<Object>}
 */
export async function listApprovals(params = {}) {
  const response = await axios.get(`${API_BASE}/approvals/list`, { params })
  return response.data
}

/**
 * 撤销审批
 * @param {number} recordId - 审批记录 ID
 * @returns {Promise<Object>}
 */
export async function revokeApproval(recordId) {
  const response = await axios.post(`${API_BASE}/approvals/revoke`, {
    record_id: recordId
  })
  return response.data
}

/**
 * 安全工具类
 */
export class SecurityClient {
  constructor(sessionId) {
    this.sessionId = sessionId
  }

  /**
   * 安全执行命令（带审批检查）
   * @param {string} command - 要执行的命令
   * @param {Function} onApprovalRequired - 需要审批时的回调
   * @returns {Promise<Object>}
   */
  async executeCommand(command, onApprovalRequired) {
    // 1. 检查审批状态
    const checkResult = await checkCommandApproval(command, this.sessionId)
    
    // 2. 如果已批准，直接返回
    if (checkResult.approved) {
      return { success: true, ...checkResult }
    }
    
    // 3. 需要审批
    if (checkResult.requires_approval) {
      // 调用回调，显示审批对话框
      const approvalResult = await onApprovalRequired(checkResult)
      
      if (approvalResult.approved) {
        // 用户批准，执行审批
        await approveCommand(
          this.sessionId,
          checkResult.pattern_key,
          approvalResult.approvalType
        )
        return { success: true, approved: true }
      } else {
        // 用户拒绝
        return { success: false, rejected: true }
      }
    }
    
    return checkResult
  }

  /**
   * 安全保存记忆（带内容扫描）
   * @param {string} content - 记忆内容
   * @param {Function} onScanWarning - 扫描警告回调
   * @returns {Promise<Object>}
   */
  async saveMemory(content, onScanWarning) {
    // 1. 扫描内容
    const scanResult = await scanMemory(content)
    
    // 2. 如果安全，直接允许
    if (scanResult.safe) {
      return { allowed: true, ...scanResult }
    }
    
    // 3. 需要用户确认
    if (scanResult.allowed === null) {
      const userDecision = await onScanWarning(scanResult)
      return { allowed: userDecision.allowed, ...scanResult }
    }
    
    // 4. 被阻止
    return scanResult
  }

  /**
   * 安全安装技能（带扫描）
   * @param {string} skillDir - 技能目录
   * @param {Function} onScanWarning - 扫描警告回调
   * @returns {Promise<Object>}
   */
  async installSkill(skillDir, onScanWarning) {
    // 1. 扫描技能
    const scanResult = await scanSkill(skillDir)
    
    // 2. 如果允许，直接返回
    if (scanResult.allowed === true) {
      return { allowed: true, ...scanResult }
    }
    
    // 3. 需要用户确认
    if (scanResult.allowed === null) {
      const userDecision = await onScanWarning(scanResult)
      return { allowed: userDecision.allowed, ...scanResult }
    }
    
    // 4. 被阻止
    return scanResult
  }
}

export default {
  checkCommandApproval,
  approveCommand,
  scanSkill,
  scanMemory,
  getAuditLogs,
  getAuditStatistics,
  listApprovals,
  revokeApproval,
  SecurityClient
}
