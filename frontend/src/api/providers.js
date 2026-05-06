import api from './index'

/**
 * 获取所有自定义 LLM 提供商配置
 */
export function getProviders() {
  return api.get('/providers').then(r => r.data)
}

/**
 * 添加新提供商配置
 */
export function createProvider(data) {
  return api.post('/providers', data).then(r => r.data)
}

/**
 * 更新提供商配置
 */
export function updateProvider(id, data) {
  return api.put(`/providers/${id}`, data).then(r => r.data)
}

/**
 * 删除提供商配置
 */
export function deleteProvider(id) {
  return api.delete(`/providers/${id}`).then(r => r.data)
}

/**
 * 设为活跃配置（自动取消其他活跃状态）
 */
export function activateProvider(id) {
  return api.post(`/providers/${id}/activate`).then(r => r.data)
}

/**
 * 测试连接（不保存配置，仅验证 API Key 和 Base URL 是否有效）
 */
export function testConnection(data) {
  return api.post('/providers/test', data).then(r => r.data)
}

/**
 * 获取原始 API Key（用于编辑回填）
 */
export function getRawApiKey(id) {
  return api.get(`/providers/${id}/raw-key`).then(r => r.data)
}
