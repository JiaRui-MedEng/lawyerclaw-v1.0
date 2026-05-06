/**
 * 百佑 LawyerClaw Hermes 核心功能 API 客户端
 * 
 * 功能:
 * 1. 记忆管理 (加载/添加/删除)
 * 2. 技能管理 (加载/创建/修补/搜索)
 * 3. 会话搜索 (FTS5 全文检索)
 */

import axios from 'axios'

const API_BASE = '/api/hermes'

/**
 * 记忆管理 API
 */
export const memoryAPI = {
  /**
   * 获取所有记忆
   */
  async getMemories() {
    return axios.get(`${API_BASE}/memories`)
  },
  
  /**
   * 添加记忆
   */
  async addMemory(data) {
    return axios.post(`${API_BASE}/memories`, data)
  },
  
  /**
   * 删除记忆
   */
  async removeMemory(memoryId) {
    return axios.delete(`${API_BASE}/memories/${memoryId}`)
  }
}

/**
 * 技能管理 API
 */
export const skillAPI = {
  /**
   * 获取所有技能
   */
  async getSkills() {
    return axios.get(`${API_BASE}/skills`)
  },
  
  /**
   * 搜索技能
   */
  async searchSkills(query) {
    return axios.get(`${API_BASE}/skills/search`, { params: { query } })
  },
  
  /**
   * 创建技能
   */
  async createSkill(data) {
    return axios.post(`${API_BASE}/skills`, data)
  },
  
  /**
   * 修补技能
   */
  async patchSkill(name, oldString, newString) {
    return axios.patch(`${API_BASE}/skills/${name}`, {
      old_string: oldString,
      new_string: newString
    })
  },
  
  /**
   * 删除技能
   */
  async deleteSkill(name) {
    return axios.delete(`${API_BASE}/skills/${name}`)
  }
}

/**
 * 会话搜索 API
 */
export const sessionSearchAPI = {
  /**
   * 搜索会话
   */
  async searchSessions(query, options = {}) {
    return axios.get(`${API_BASE}/sessions/search`, {
      params: {
        query,
        limit: options.limit || 5,
        role_filter: options.roleFilter
      }
    })
  },
  
  /**
   * 获取最近会话
   */
  async getRecentSessions(limit = 5) {
    return axios.get(`${API_BASE}/sessions/recent`, { params: { limit } })
  }
}

/**
 * 统一导出
 */
export const hermesAPI = {
  ...memoryAPI,
  ...skillAPI,
  ...sessionSearchAPI
}

export default hermesAPI
