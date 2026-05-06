/**
 * Settings Store Module
 * 管理全局设置（字体大小、主题、自定义模型配置等）
 */
import { getProviders, createProvider, updateProvider, deleteProvider, activateProvider, testConnection } from '@/api/providers'

const state = {
  fontSize: localStorage.getItem('lawyerclaw-fontSize') || 'medium', // small, medium, large, xlarge
  theme: localStorage.getItem('lawyerclaw-theme') || 'light',
  maxTokens: parseInt(localStorage.getItem('lawyerclaw-maxTokens')) || 8000,
  temperature: parseFloat(localStorage.getItem('lawyerclaw-temperature')) || 0.7,
  jurisdiction: localStorage.getItem('lawyerclaw-jurisdiction') || 'cn',
  
  // ⭐ 自动润色设置
  autoPolish: localStorage.getItem('lawyerclaw-autoPolish') === 'true',
  autoPolishStyle: localStorage.getItem('lawyerclaw-autoPolishStyle') || '',
  autoPolishIntensity: localStorage.getItem('lawyerclaw-autoPolishIntensity') || 'medium',
  
  // ⭐ 自定义模型配置
  customProviders: [],      // 模型配置列表
  activeProviderId: parseInt(localStorage.getItem('lawyerclaw-activeProviderId')) || null,  // 当前活跃配置 ID
}

const getters = {
  // ⭐ 获取字体大小级别（由 font-size.css 以 12px 为基准按倍率处理）
  fontSizeLevel: (state) => state.fontSize,
  
  // 获取完整设置对象
  allSettings: (state) => ({ ...state }),
  
  // 确保 temperature 是数字
  temperatureNum: (state) => parseFloat(state.temperature) || 0.7,
  
  // 确保 maxTokens 是数字
  maxTokensNum: (state) => parseInt(state.maxTokens) || 8000,
  
  // ⭐ 获取当前活跃提供商配置
  activeProvider: (state) => {
    if (!state.activeProviderId) return null
    return state.customProviders.find(p => p.id === state.activeProviderId)
  },
  
  // ⭐ 获取活跃提供商的 provider name（用于创建会话）
  activeProviderName: (state, getters) => {
    return getters.activeProvider ? getters.activeProvider.name : null
  },
  
  // ⭐ 获取活跃提供商的模型名称
  activeModelName: (state, getters) => {
    return getters.activeProvider ? getters.activeProvider.default_model : null
  }
}

const mutations = {
  SET_FONT_SIZE(state, size) {
    state.fontSize = size
    localStorage.setItem('lawyerclaw-fontSize', size)
  },
  
  SET_THEME(state, theme) {
    state.theme = theme
    localStorage.setItem('lawyerclaw-theme', theme)
  },
  
  SET_MAX_TOKENS(state, tokens) {
    state.maxTokens = parseInt(tokens) || 8000
    localStorage.setItem('lawyerclaw-maxTokens', state.maxTokens)
  },
  
  SET_TEMPERATURE(state, temp) {
    state.temperature = parseFloat(temp) || 0.7
    localStorage.setItem('lawyerclaw-temperature', state.temperature)
  },
  
  SET_JURISDICTION(state, jurisdiction) {
    state.jurisdiction = jurisdiction
    localStorage.setItem('lawyerclaw-jurisdiction', jurisdiction)
  },
  
  // ⭐ 自动润色设置
  SET_AUTO_POLISH(state, val) {
    state.autoPolish = val
    localStorage.setItem('lawyerclaw-autoPolish', val)
  },
  SET_AUTO_POLISH_STYLE(state, val) {
    state.autoPolishStyle = val
    localStorage.setItem('lawyerclaw-autoPolishStyle', val)
  },
  SET_AUTO_POLISH_INTENSITY(state, val) {
    state.autoPolishIntensity = val
    localStorage.setItem('lawyerclaw-autoPolishIntensity', val)
  },
  
  // ⭐ 自定义提供商相关 mutations
  SET_CUSTOM_PROVIDERS(state, providers) {
    state.customProviders = providers
  },
  
  SET_ACTIVE_PROVIDER(state, id) {
    state.activeProviderId = id
    localStorage.setItem('lawyerclaw-activeProviderId', id)
  },
  
  ADD_PROVIDER(state, provider) {
    state.customProviders.push(provider)
  },
  
  UPDATE_PROVIDER(state, provider) {
    const index = state.customProviders.findIndex(p => p.id === provider.id)
    if (index !== -1) {
      state.customProviders.splice(index, 1, provider)
    }
  },
  
  DELETE_PROVIDER(state, id) {
    state.customProviders = state.customProviders.filter(p => p.id !== id)
    // 如果删除的是活跃配置，清除活跃状态
    if (state.activeProviderId === id) {
      state.activeProviderId = null
      localStorage.removeItem('lawyerclaw-activeProviderId')
    }
  },
  
  // 批量加载设置
  LOAD_SETTINGS(state, settings) {
    Object.keys(settings).forEach(key => {
      if (state.hasOwnProperty(key)) {
        state[key] = settings[key]
        // 同步到 localStorage
        localStorage.setItem(`lawyerclaw-${key}`, settings[key])
      }
    })
  }
}

const actions = {
  // 设置主题并应用
  setTheme({ commit, dispatch }, theme) {
    commit('SET_THEME', theme)
    dispatch('applyTheme')
    dispatch('saveToBackend')

    // 触发全局事件
    window.dispatchEvent(new CustomEvent('lawyerclaw:settings-change', {
      detail: { key: 'theme', value: theme }
    }))
  },

  // ⭐ 自动润色设置（同步到后端）
  setAutoPolish({ commit, dispatch }, val) {
    commit('SET_AUTO_POLISH', val)
    dispatch('saveToBackend')
  },
  setAutoPolishStyle({ commit, dispatch }, val) {
    commit('SET_AUTO_POLISH_STYLE', val)
    dispatch('saveToBackend')
  },
  setAutoPolishIntensity({ commit, dispatch }, val) {
    commit('SET_AUTO_POLISH_INTENSITY', val)
    dispatch('saveToBackend')
  },
  
  // 更新字体大小并应用到 DOM
  updateFontSize({ commit, state, getters }) {
    commit('SET_FONT_SIZE', state.fontSize)
    
    // ⭐ 现在字体大小完全由 CSS clamp() 处理，只需设置 data-font-size 属性
    const root = document.documentElement
    root.setAttribute('data-font-size', state.fontSize)
    
    // 触发全局事件（供其他组件监听）
    window.dispatchEvent(new CustomEvent('lawyerclaw:settings-change', {
      detail: { key: 'fontSize', value: state.fontSize }
    }))
  },
  
  // 应用主题到 DOM
  applyTheme({ commit, state }) {
    const root = document.documentElement
    if (state.theme === 'dark') {
      root.setAttribute('data-theme', 'dark')
    } else {
      root.removeAttribute('data-theme')
    }
    
    // 触发全局事件
    window.dispatchEvent(new CustomEvent('lawyerclaw:settings-change', {
      detail: { key: 'theme', value: state.theme }
    }))
  },
  
  // 加载并应用所有设置
  loadSettings({ commit, dispatch }) {
    const saved = {
      fontSize: localStorage.getItem('lawyerclaw-fontSize'),
      theme: localStorage.getItem('lawyerclaw-theme'),
      maxTokens: localStorage.getItem('lawyerclaw-maxTokens'),
      temperature: localStorage.getItem('lawyerclaw-temperature'),
      jurisdiction: localStorage.getItem('lawyerclaw-jurisdiction'),
      activeProviderId: localStorage.getItem('lawyerclaw-activeProviderId'),
      autoPolish: localStorage.getItem('lawyerclaw-autoPolish'),
      autoPolishStyle: localStorage.getItem('lawyerclaw-autoPolishStyle'),
      autoPolishIntensity: localStorage.getItem('lawyerclaw-autoPolishIntensity'),
    }
    
    // 过滤掉 null 的
    const validSettings = {}
    Object.keys(saved).forEach(key => {
      if (saved[key] !== null) {
        validSettings[key] = saved[key]
      }
    })
    
    if (Object.keys(validSettings).length > 0) {
      commit('LOAD_SETTINGS', validSettings)
      dispatch('updateFontSize')
      // 加载完成后应用主题
      dispatch('applyTheme')
    }
  },
  
  // 保存设置到后端（camelCase → snake_case 转换）
  async saveToBackend({ state }) {
    try {
      const api = (await import('@/api/index')).default
      // 后端 UserSettings 使用 snake_case key
      const backendSettings = {
        font_size: state.fontSize,
        theme: state.theme,
        max_tokens: state.maxTokens,
        temperature: state.temperature,
        jurisdiction: state.jurisdiction,
        auto_polish: String(state.autoPolish),
        auto_polish_style: state.autoPolishStyle,
        auto_polish_intensity: state.autoPolishIntensity,
      }
      await api.post('/settings', { settings: backendSettings })
    } catch (e) {
      // 静默失败
    }
  },
  
  // 从后端加载设置（snake_case → camelCase 转换）
  async loadFromBackend({ commit }) {
    try {
      const api = (await import('@/api/index')).default
      const response = await api.get('/settings')
      if (response.data && response.data.settings) {
        const raw = response.data.settings
        // snake_case → camelCase 映射
        const keyMap = {
          font_size: 'fontSize',
          max_tokens: 'maxTokens',
          auto_polish: 'autoPolish',
          auto_polish_style: 'autoPolishStyle',
          auto_polish_intensity: 'autoPolishIntensity',
        }
        const mapped = {}
        Object.keys(raw).forEach(k => {
          const camelKey = keyMap[k] || k
          mapped[camelKey] = raw[k]
        })
        // auto_polish 存的是字符串 "true"/"false"，转为布尔
        if (typeof mapped.autoPolish === 'string') {
          mapped.autoPolish = mapped.autoPolish === 'true'
        }
        commit('LOAD_SETTINGS', mapped)
        return true
      }
    } catch (e) {
      // 静默失败
    }
    return false
  },
  
  // 重置为默认设置
  resetSettings({ commit, dispatch }) {
    const defaults = {
      fontSize: 'medium',
      theme: 'light',
      maxTokens: 8000,
      temperature: 0.7,
      jurisdiction: 'cn',
      activeProviderId: null,
      autoPolish: false,
      autoPolishStyle: '',
      autoPolishIntensity: 'medium',
    }
    
    commit('LOAD_SETTINGS', defaults)
    dispatch('updateFontSize')
  },
  
  // ⭐ 加载自定义提供商列表
  async loadProviders({ commit }) {
    try {
      const response = await getProviders()
      if (response.success) {
        const providers = response.providers || []
        commit('SET_CUSTOM_PROVIDERS', providers)
        // ⭐ 从后端同步活跃状态（修复刷新后丢失）
        const active = providers.find(p => p.is_active)
        if (active) {
          commit('SET_ACTIVE_PROVIDER', active.id)
        }
      }
    } catch (e) {
      console.error('加载提供商列表失败:', e)
    }
  },
  
  // ⭐ 保存提供商配置（新增或更新）
  async saveProvider({ commit }, providerData) {
    try {
      let response
      if (providerData.id) {
        response = await updateProvider(providerData.id, providerData)
        if (response.success) {
          commit('UPDATE_PROVIDER', response.provider)
        }
      } else {
        response = await createProvider(providerData)
        if (response.success) {
          commit('ADD_PROVIDER', response.provider)
        }
      }
      return response
    } catch (e) {
      console.error('保存提供商配置失败:', e)
      return { success: false, error: e.message }
    }
  },
  
  // ⭐ 删除提供商配置
  async deleteProvider({ commit }, id) {
    try {
      const response = await deleteProvider(id)
      if (response.success) {
        commit('DELETE_PROVIDER', id)
      }
      return response
    } catch (e) {
      console.error('删除提供商配置失败:', e)
      return { success: false, error: e.message }
    }
  },
  
  // ⭐ 设为活跃配置
  async setActiveProvider({ commit, dispatch }, id) {
    try {
      const response = await activateProvider(id)
      if (response.success) {
        commit('SET_ACTIVE_PROVIDER', id)
        // 更新提供商列表状态（其他配置的 is_active 会被后端取消）
        dispatch('loadProviders')
      }
      return response
    } catch (e) {
      console.error('设置活跃配置失败:', e)
      return { success: false, error: e.message }
    }
  },
  
  // ⭐ 测试连接
  async testConnection(_, providerData) {
    try {
      return await testConnection(providerData)
    } catch (e) {
      console.error('测试连接失败:', e)
      return { success: false, error: e.message }
    }
  }
}

export default {
  namespaced: true,
  state,
  getters,
  mutations,
  actions
}
