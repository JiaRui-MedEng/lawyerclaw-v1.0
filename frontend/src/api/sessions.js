import api from './index'

export function getSessions() {
  return api.get('/sessions').then(r => r.data)
}

export function createSession(params = {}) {
  return api.post('/sessions', params).then(r => r.data)
}

export function getSession(id) {
  return api.get(`/sessions/${id}`).then(r => r.data)
}

export function deleteSession(id) {
  return api.delete(`/sessions/${id}`).then(r => r.data)
}

export function updateSessionTitle(id, title) {
  return api.patch(`/sessions/${id}/title`, { title }).then(r => r.data)
}

export function getSessionMessages(id) {
  return api.get(`/sessions/${id}/messages`).then(r => r.data)
}
