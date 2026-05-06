import api from './index'

export function getWorkspaceConfig() {
  return api.get('/workspace/config').then(r => r.data)
}

export function setWorkspaceConfig(root) {
  return api.post('/workspace/config', { root }).then(r => r.data)
}

export function listFiles(path = '', maxDepth = 2) {
  return api.get('/workspace/files', { params: { path, max_depth: maxDepth } }).then(r => r.data)
}

export function getFileTree() {
  return api.get('/workspace/tree').then(r => r.data)
}

// 兼容 FileExplorer.vue 的 workspaceAPI 对象
export const workspaceAPI = {
  getRoot() {
    return api.get('/workspace/config').then(r => {
      // API 返回 {root: '...', success: true}
      return r.data
    })
  },
  listFiles(path, maxDepth = 2) {
    return api.get('/workspace/files', { params: { path, max_depth: maxDepth } }).then(r => {
      // API 返回 {success: true, path: '...', items: [...]}
      return r.data
    })
  },
  getTree() {
    return api.get('/workspace/tree').then(r => r.data)
  },
  getConfig() {
    return api.get('/workspace/config').then(r => r.data)
  },
  setConfig(root) {
    return api.post('/workspace/config', { root }).then(r => r.data)
  },
  openFile(path) {
    return api.post('/workspace/open-file', { path }).then(r => r.data)
  }
}

export default workspaceAPI
