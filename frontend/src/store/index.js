import Vue from 'vue'
import Vuex from 'vuex'
import sessions from './modules/sessions'
import chat from './modules/chat'
import workspace from './modules/workspace'
import settings from './modules/settings'

Vue.use(Vuex)

export default new Vuex.Store({
  state: {
    ingestTask: null
  },
  mutations: {
    SET_INGEST_TASK(state, task) {
      state.ingestTask = task
    },
    UPDATE_INGEST_TASK(state, updates) {
      if (state.ingestTask) {
        Object.assign(state.ingestTask, updates)
      }
    },
    CLEAR_INGEST_TASK(state) {
      state.ingestTask = null
    }
  },
  modules: {
    sessions,
    chat,
    workspace,
    settings
  }
})
