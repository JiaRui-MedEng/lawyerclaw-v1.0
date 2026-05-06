import workspaceAPI from '../../api/workspace'

const state = {
  tree: [],
  root: null,
  loading: false
}

const mutations = {
  SET_TREE(state, tree) {
    state.tree = tree
  },
  SET_ROOT(state, root) {
    state.root = root
  },
  SET_LOADING(state, loading) {
    state.loading = loading
  }
}

const actions = {
  async fetchTree({ commit }) {
    commit('SET_LOADING', true)
    try {
      const tree = await workspaceAPI.getTree()
      commit('SET_TREE', tree)
    } catch (error) {
    } finally {
      commit('SET_LOADING', false)
    }
  },
  
  async setWorkspaceRoot({ commit }, root) {
    try {
      await workspaceAPI.setConfig(root)
      commit('SET_ROOT', root)
      return true
    } catch (error) {
      return false
    }
  }
}

export default {
  namespaced: true,
  state,
  mutations,
  actions
}
