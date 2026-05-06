import api from './index'

export function getTools() {
  return api.get('/tools').then(r => r.data)
}

export function executeTool(toolName, parameters) {
  return api.post('/tools/execute', { tool_name: toolName, parameters }).then(r => r.data)
}

export function getToolSchemas(provider) {
  const endpoint = provider === 'minimax' ? 'claude' : 'openai'
  return api.get(`/tools/schemas/${endpoint}`).then(r => r.data)
}
