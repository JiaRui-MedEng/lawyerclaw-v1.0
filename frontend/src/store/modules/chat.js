import { sendMessageStream } from '../../api/chat'
import { getSessionMessages } from '../../api/sessions'

const state = {
  messages: [],
  streaming: false,
  currentResponse: ''
}

const mutations = {
  ADD_MESSAGE(state, message) {
    state.messages.push(message)
  },
  SET_STREAMING(state, streaming) {
    state.streaming = streaming
  },
  SET_CURRENT_RESPONSE(state, text) {
    state.currentResponse = text
  },
  SET_MESSAGES(state, messages) {
    // 兼容旧格式：从 content 中提取附件文件列表
    state.messages = messages.map(msg => {
      if (msg.role === 'user' && msg.content && msg.content.includes('\n\n📎 附件文件:\n')) {
        const parts = msg.content.split('\n\n📎 附件文件:\n')
        const cleanContent = parts[0]
        const attachments = parts[1] ? parts[1].split('\n').filter(f => f.trim()) : []
        return { ...msg, content: cleanContent, attachments }
      }
      return msg
    })
  },
  CLEAR_MESSAGES(state) {
    state.messages = []
  }
}

const actions = {
  /**
   * 加载会话历史消息
   */
  async loadSessionMessages({ commit, state }, sessionId) {
    if (!sessionId) {
      return []
    }
    try {
      const res = await getSessionMessages(sessionId)
      if (res.success) {
        commit('SET_MESSAGES', res.messages)
        return res.messages
      }
    } catch (e) {
    }
    return []
  },

  async sendMessage({ commit, state, rootState }, payload) {
    const sessionId = payload.sessionId || rootState.sessions.currentId
    const content = payload.content

    if (!sessionId) {
      return
    }

    const now = new Date()
    const nowISO = now.toISOString()

    commit('ADD_MESSAGE', {
      role: 'user',
      content,
      created_at: nowISO
    })

    commit('SET_STREAMING', true)
    commit('ADD_MESSAGE', {
      role: 'assistant',
      content: '',
      loading: true,
      created_at: nowISO
    })

    try {
      let fullContent = ''
      await sendMessageStream(
        sessionId,
        content,
        (chunk) => {
          fullContent += chunk
          const lastMsg = state.messages[state.messages.length - 1]
          lastMsg.content = fullContent
          lastMsg.loading = false
        },
        () => {
          commit('SET_STREAMING', false)
        },
        (err) => {
          const lastMsg = state.messages[state.messages.length - 1]
          lastMsg.content = '❌ 请求失败，请重试'
          lastMsg.loading = false
          commit('SET_STREAMING', false)
        }
      )
    } catch (e) {
      const lastMsg = state.messages[state.messages.length - 1]
      lastMsg.content = '❌ 请求失败，请重试'
      lastMsg.loading = false
      commit('SET_STREAMING', false)
    }
  }
}

export default {
  namespaced: true,
  state,
  mutations,
  actions
}
