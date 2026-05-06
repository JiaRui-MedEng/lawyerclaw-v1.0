import { getSessions, createSession, deleteSession } from '../../api/sessions'

const state = {
  list: [],
  currentId: null,
  loading: false,
  tempSession: null
}

const mutations = {
  SET_SESSIONS(state, sessions) {
    state.list = sessions
  },
  ADD_SESSION(state, session) {
    state.list.unshift(session)
  },
  REMOVE_SESSION(state, sessionId) {
    state.list = state.list.filter(s => s.id !== sessionId)
  },
  setCurrentSession(state, id) {
    state.currentId = id
  },
  setLoading(state, loading) {
    state.loading = loading
  },
  SET_TEMP_SESSION(state, session) {
    state.tempSession = session
  },
  CLEAR_TEMP_SESSION(state) {
    state.tempSession = null
  },
  CONVERT_TEMP_TO_REAL(state, realSession) {
    state.tempSession = null
    state.list.unshift(realSession)
    state.currentId = realSession.id
  },
  
  /**
   * ✅ 新增：更新会话标题
   */
  UPDATE_SESSION_TITLE(state, { sessionId, title }) {
    const session = state.list.find(s => s.id === sessionId)
    if (session) {
      session.title = title
    }
  }
}

const actions = {
  async fetchSessions({ commit }) {
    commit('setLoading', true)
    try {
      const res = await getSessions()
      if (res.success) {
        commit('SET_SESSIONS', res.sessions)
        if (res.sessions.length > 0 && !state.currentId) {
          commit('setCurrentSession', res.sessions[0].id)
        }
      }
    } catch (error) {
    } finally {
      commit('setLoading', false)
    }
  },
  
  async createSession({ commit, rootState }, { model } = {}) {
    try {
      const response = await createSession({ model })
      
      // 🚨 后端返回 {success: true, session: {...}}
      const session = response.session || response
      
      commit('ADD_SESSION', session)
      // 自动选中创建的会话
      commit('setCurrentSession', session.id)
      return session
    } catch (error) {
      throw error
    }
  },
  
  async deleteSession({ commit }, sessionId) {
    try {
      await deleteSession(sessionId)
      commit('REMOVE_SESSION', sessionId)
    } catch (error) {
      throw error
    }
  },
  
  async batchDeleteSessions({ commit }, sessionIds) {
    try {
      for (const id of sessionIds) {
        await deleteSession(id)
        commit('REMOVE_SESSION', id)
      }
      return { success: true, message: '批量删除成功' }
    } catch (error) {
      return { success: false, message: error.message }
    }
  },
  
  async createTempSession({ commit, rootState }) {
    const activeProvider = rootState.settings.activeProvider
    const tempSession = {
      id: 'temp_' + Date.now(),
      title: '新会话',
      provider: 'custom',
      model: activeProvider && activeProvider.default_model,
      created_at: new Date().toISOString(),
      is_temp: true
    }
    commit('SET_TEMP_SESSION', tempSession)
    commit('setCurrentSession', tempSession.id)
    return tempSession
  },
  
  clearTempSession({ commit }) {
    commit('CLEAR_TEMP_SESSION')
  },
  
  async convertTempSession({ commit, state, rootState }, messageContent) {
    if (!state.tempSession) {
      return null
    }

    // 将临时会话保存为真实会话
    try {
      const activeProvider = rootState.settings.activeProvider
      const response = await createSession({
        model: activeProvider && activeProvider.default_model
      })
      
      
      // 🚨 后端返回 {success: true, session: {...}}
      const realSession = response.session || response
      
      commit('CLEAR_TEMP_SESSION')
      commit('ADD_SESSION', realSession)
      commit('setCurrentSession', realSession.id)
      
      
      return realSession
    } catch (error) {
      throw error
    }
  },
  
  /**
   * ✅ 新增：更新会话标题
   */
  async updateSessionTitle({ commit, state }, { sessionId, title }) {
    const session = state.list.find(s => s.id === sessionId)
    if (session) {
      commit('UPDATE_SESSION_TITLE', { sessionId, title })
      
      // TODO: 调用后端 API 持久化标题
      // await api.patch(`/sessions/${sessionId}`, { title })
    }
  }
}

export default {
  namespaced: true,
  state,
  mutations,
  actions
}
