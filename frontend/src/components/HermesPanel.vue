<!--
百佑 LawyerClaw Hermes 核心功能集成组件

功能:
1. 记忆管理 (添加/搜索/显示)
2. 技能管理 (创建/修补/搜索)
3. 会话搜索 (FTS5 全文检索)
-->
<template>
  <div class="hermes-panel">
    <!-- 标签页切换 -->
    <div class="tabs">
      <button 
        :class="['tab', { active: activeTab === 'memory' }]"
        @click="activeTab = 'memory'"
      >
        🧠 记忆
      </button>
      <button 
        :class="['tab', { active: activeTab === 'skills' }]"
        @click="activeTab = 'skills'"
      >
        🔧 技能
      </button>
      <button 
        :class="['tab', { active: activeTab === 'search' }]"
        @click="activeTab = 'search'"
      >
        🔍 会话搜索
      </button>
    </div>
    
    <!-- 记忆面板 -->
    <div v-show="activeTab === 'memory'" class="panel-content">
      <div class="panel-header">
        <h3>持久化记忆</h3>
        <button class="btn-primary" @click="showAddMemory = !showAddMemory">
          {{ showAddMemory ? '取消' : '+ 添加记忆' }}
        </button>
      </div>
      
      <!-- 添加记忆表单 -->
      <div v-if="showAddMemory" class="add-form">
        <div class="form-group">
          <label>类型</label>
          <select v-model="newMemory.target">
            <option value="memory">个人笔记</option>
            <option value="user">用户画像</option>
          </select>
        </div>
        <div class="form-group">
          <label>内容</label>
          <textarea 
            v-model="newMemory.content"
            placeholder="输入要记忆的内容..."
            rows="4"
          ></textarea>
        </div>
        <div class="form-actions">
          <button class="btn-secondary" @click="cancelAddMemory">取消</button>
          <button class="btn-primary" @click="addMemory" :disabled="addingMemory">
            {{ addingMemory ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
      
      <!-- 记忆列表 -->
      <div class="memory-list">
        <div v-for="memory in memories" :key="memory.id" class="memory-item">
          <span class="memory-target" :class="memory.target">
            {{ memory.target === 'memory' ? '📝' : '👤' }}
          </span>
          <div class="memory-content">
            <p>{{ memory.content }}</p>
            <span class="memory-time">{{ formatDate(memory.created_at) }}</span>
          </div>
          <button class="btn-icon" @click="removeMemory(memory.id)" title="删除">
            🗑️
          </button>
        </div>
        <div v-if="memories.length === 0" class="empty-hint">
          暂无记忆
        </div>
      </div>
    </div>
    
    <!-- 技能面板 -->
    <div v-show="activeTab === 'skills'" class="panel-content">
      <div class="panel-header">
        <h3>技能管理</h3>
        <button class="btn-primary" @click="showCreateSkill = !showCreateSkill">
          {{ showCreateSkill ? '取消' : '+ 创建技能' }}
        </button>
      </div>
      
      <!-- 创建技能表单 -->
      <div v-if="showCreateSkill" class="add-form">
        <div class="form-group">
          <label>技能名称</label>
          <input 
            v-model="newSkill.name"
            placeholder="例如：legal-document-analyzer"
          />
        </div>
        <div class="form-group">
          <label>描述</label>
          <input 
            v-model="newSkill.description"
            placeholder="简短描述技能功能"
          />
        </div>
        <div class="form-group">
          <label>分类</label>
          <input 
            v-model="newSkill.category"
            placeholder="例如：legal"
          />
        </div>
        <div class="form-group">
          <label>SKILL.md 内容</label>
          <textarea 
            v-model="newSkill.content"
            placeholder="---&#10;name: skill-name&#10;description: 技能描述&#10;---&#10;&#10;# 技能内容..."
            rows="8"
          ></textarea>
        </div>
        <div class="form-actions">
          <button class="btn-secondary" @click="cancelCreateSkill">取消</button>
          <button class="btn-primary" @click="createSkill" :disabled="creatingSkill">
            {{ creatingSkill ? '创建中...' : '创建' }}
          </button>
        </div>
      </div>
      
      <!-- 技能搜索 -->
      <div class="search-bar">
        <input 
          v-model="skillQuery"
          placeholder="搜索技能..."
          @keyup.enter="searchSkills"
        />
        <button class="btn-icon" @click="searchSkills">🔍</button>
      </div>
      
      <!-- 技能列表 -->
      <div class="skill-list">
        <div v-for="skill in skills" :key="skill.id" class="skill-item">
          <div class="skill-header">
            <span class="skill-name">{{ skill.name }}</span>
            <span class="skill-category">{{ skill.category }}</span>
          </div>
          <p class="skill-description">{{ skill.description }}</p>
          <div class="skill-actions">
            <button class="btn-small" @click="viewSkill(skill)">查看</button>
            <button class="btn-small" @click="patchSkill(skill)">修补</button>
          </div>
        </div>
        <div v-if="skills.length === 0" class="empty-hint">
          {{ skillQuery ? '未找到匹配的技能' : '暂无技能' }}
        </div>
      </div>
    </div>
    
    <!-- 会话搜索面板 -->
    <div v-show="activeTab === 'search'" class="panel-content">
      <div class="panel-header">
        <h3>会话搜索</h3>
      </div>
      
      <!-- 搜索栏 -->
      <div class="search-bar">
        <input 
          v-model="searchQuery"
          placeholder="搜索历史会话..."
          @keyup.enter="searchSessions"
        />
        <button class="btn-icon" @click="searchSessions">🔍</button>
      </div>
      
      <!-- 搜索结果 -->
      <div class="search-results">
        <div v-for="result in searchResults" :key="result.session_id" class="result-item">
          <div class="result-header">
            <span class="result-title">{{ result.session_title || '无标题' }}</span>
            <span class="result-time">{{ formatDate(result.when) }}</span>
          </div>
          <p class="result-snippet" v-html="highlightMatch(result.snippet)"></p>
          <div class="result-meta">
            <span>{{ result.session_provider }}</span>
            <span>{{ result.session_model }}</span>
          </div>
          <button class="btn-small" @click="loadSession(result.session_id)">
            加载会话
          </button>
        </div>
        <div v-if="searchResults.length === 0 && searched" class="empty-hint">
          未找到匹配的会话
        </div>
        <div v-if="!searched" class="search-hint">
          <p>💡 搜索提示:</p>
          <ul>
            <li>关键词搜索：<code>docker deployment</code></li>
            <li>短语搜索：<code>"exact phrase"</code></li>
            <li>布尔搜索：<code>python NOT java</code></li>
            <li>前缀搜索：<code>deploy*</code></li>
          </ul>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { hermesAPI } from '@/api/hermes'

export default {
  name: 'HermesPanel',
  data() {
    return {
      activeTab: 'memory',
      
      // 记忆相关
      showAddMemory: false,
      addingMemory: false,
      memories: [],
      newMemory: {
        target: 'memory',
        content: ''
      },
      
      // 技能相关
      showCreateSkill: false,
      creatingSkill: false,
      skills: [],
      skillQuery: '',
      newSkill: {
        name: '',
        description: '',
        category: 'general',
        content: ''
      },
      
      // 会话搜索
      searchQuery: '',
      searchResults: [],
      searched: false
    }
  },
  mounted() {
    this.loadMemories()
    this.loadSkills()
  },
  methods: {
    // 记忆方法
    async loadMemories() {
      try {
        const response = await hermesAPI.getMemories()
        this.memories = response.data
      } catch (error) {
      }
    },
    
    async addMemory() {
      if (!this.newMemory.content.trim()) {
        alert('内容不能为空')
        return
      }
      
      this.addingMemory = true
      try {
        await hermesAPI.addMemory(this.newMemory)
        this.newMemory.content = ''
        this.showAddMemory = false
        this.loadMemories()
      } catch (error) {
        alert(error.response?.data?.error || '添加失败')
      } finally {
        this.addingMemory = false
      }
    },
    
    cancelAddMemory() {
      this.showAddMemory = false
      this.newMemory.content = ''
    },
    
    async removeMemory(memoryId) {
      if (!confirm('确定要删除这条记忆吗？')) return
      
      try {
        await hermesAPI.removeMemory(memoryId)
        this.loadMemories()
      } catch (error) {
      }
    },
    
    // 技能方法
    async loadSkills() {
      try {
        const response = await hermesAPI.getSkills()
        this.skills = response.data
      } catch (error) {
      }
    },
    
    async searchSkills() {
      if (!this.skillQuery.trim()) {
        this.loadSkills()
        return
      }
      
      try {
        const response = await hermesAPI.searchSkills(this.skillQuery)
        this.skills = response.data
      } catch (error) {
      }
    },
    
    async createSkill() {
      if (!this.newSkill.name.trim()) {
        alert('技能名称不能为空')
        return
      }
      
      this.creatingSkill = true
      try {
        await hermesAPI.createSkill(this.newSkill)
        this.newSkill = { name: '', description: '', category: 'general', content: '' }
        this.showCreateSkill = false
        this.loadSkills()
      } catch (error) {
        alert(error.response?.data?.error || '创建失败')
      } finally {
        this.creatingSkill = false
      }
    },
    
    cancelCreateSkill() {
      this.showCreateSkill = false
      this.newSkill = { name: '', description: '', category: 'general', content: '' }
    },
    
    viewSkill(skill) {
      // 查看技能详情
      this.$emit('view-skill', skill)
    },
    
    async patchSkill(skill) {
      // 修补技能 (简化版)
      const oldString = prompt('输入要查找的文本:')
      if (!oldString) return
      
      const newString = prompt('输入替换文本:')
      if (!newString) return
      
      try {
        await hermesAPI.patchSkill(skill.name, oldString, newString)
        alert('技能已修补')
      } catch (error) {
        alert(error.response?.data?.error || '修补失败')
      }
    },
    
    // 会话搜索方法
    async searchSessions() {
      if (!this.searchQuery.trim()) {
        this.searchResults = []
        this.searched = false
        return
      }
      
      this.searched = true
      try {
        const response = await hermesAPI.searchSessions(this.searchQuery)
        this.searchResults = response.data.results || []
      } catch (error) {
      }
    },
    
    highlightMatch(snippet) {
      if (!snippet) return ''
      // 高亮 >>> 和 <<< 之间的内容
      return snippet
        .replace(/>>>/g, '<mark>')
        .replace(/<</g, '</mark>')
    },
    
    loadSession(sessionId) {
      this.$emit('load-session', sessionId)
    },
    
    formatDate(dateString) {
      if (!dateString) return ''
      const date = new Date(dateString)
      return date.toLocaleString('zh-CN')
    }
  }
}
</script>

<style scoped>
.hermes-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--md-sys-color-surface);
  border-radius: 12px;
  overflow: hidden;
}

.tabs {
  display: flex;
  border-bottom: 1px solid var(--md-sys-color-outline-variant);
}

.tab {
  flex: 1;
  padding: 12px 16px;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  color: var(--md-sys-color-on-surface-variant);
  transition: all 0.2s;
}

.tab:hover {
  background: var(--md-sys-color-surface-container-highest);
}

.tab.active {
  border-bottom-color: var(--md-sys-color-primary);
  color: var(--md-sys-color-primary);
}

.panel-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.panel-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.add-form {
  background: var(--md-sys-color-surface-container);
  padding: 16px;
  border-radius: 8px;
  margin-bottom: 16px;
}

.form-group {
  margin-bottom: 12px;
}

.form-group label {
  display: block;
  margin-bottom: 4px;
  font-size: 13px;
  font-weight: 500;
  color: var(--md-sys-color-on-surface-variant);
}

.form-group input,
.form-group select,
.form-group textarea {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--md-sys-color-outline);
  border-radius: 6px;
  font-size: 14px;
  background: var(--md-sys-color-surface);
  color: var(--md-sys-color-on-surface);
}

.form-group textarea {
  resize: vertical;
  font-family: 'Courier New', monospace;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.search-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.search-bar input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid var(--md-sys-color-outline);
  border-radius: 6px;
  font-size: 14px;
}

/* 记忆列表 */
.memory-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.memory-item {
  display: flex;
  gap: 12px;
  padding: 12px;
  background: var(--md-sys-color-surface-container);
  border-radius: 8px;
}

.memory-target {
  font-size: 20px;
}

.memory-target.memory::after {
  content: '📝';
}

.memory-target.user::after {
  content: '👤';
}

.memory-content {
  flex: 1;
}

.memory-content p {
  margin: 0 0 4px 0;
  font-size: 14px;
  line-height: 1.5;
}

.memory-time {
  font-size: 12px;
  color: var(--md-sys-color-on-surface-variant);
}

/* 技能列表 */
.skill-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.skill-item {
  padding: 12px;
  background: var(--md-sys-color-surface-container);
  border-radius: 8px;
}

.skill-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.skill-name {
  font-weight: 600;
  font-size: 14px;
}

.skill-category {
  padding: 4px 8px;
  background: var(--md-sys-color-primary-container);
  border-radius: 4px;
  font-size: 12px;
  color: var(--md-sys-color-on-primary-container);
}

.skill-description {
  margin: 0 0 8px 0;
  font-size: 13px;
  color: var(--md-sys-color-on-surface-variant);
}

.skill-actions {
  display: flex;
  gap: 8px;
}

/* 搜索结果 */
.search-results {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.result-item {
  padding: 12px;
  background: var(--md-sys-color-surface-container);
  border-radius: 8px;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.result-title {
  font-weight: 600;
  font-size: 14px;
}

.result-time {
  font-size: 12px;
  color: var(--md-sys-color-on-surface-variant);
}

.result-snippet {
  margin: 0 0 8px 0;
  font-size: 13px;
  color: var(--md-sys-color-on-surface-variant);
  line-height: 1.5;
}

.result-snippet :deep(mark) {
  background: var(--md-sys-color-primary-container);
  color: var(--md-sys-color-on-primary-container);
  padding: 2px 4px;
  border-radius: 2px;
}

.result-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--md-sys-color-on-surface-variant);
  margin-bottom: 8px;
}

.empty-hint,
.search-hint {
  text-align: center;
  padding: 32px;
  color: var(--md-sys-color-on-surface-variant);
}

.search-hint ul {
  text-align: left;
  margin-top: 8px;
  padding-left: 20px;
}

.search-hint code {
  background: var(--md-sys-color-surface-container-highest);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'Courier New', monospace;
  font-size: 12px;
}

/* 按钮 */
.btn-primary {
  padding: 8px 16px;
  background: var(--md-sys-color-primary);
  color: var(--md-sys-color-on-primary);
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-primary:hover:not(:disabled) {
  background: var(--md-sys-color-primary-container);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  padding: 8px 16px;
  background: var(--md-sys-color-surface-container-high);
  color: var(--md-sys-color-on-surface);
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-secondary:hover {
  background: var(--md-sys-color-surface-container-highest);
}

.btn-icon {
  width: 32px;
  height: 32px;
  padding: 0;
  background: none;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.btn-icon:hover {
  background: var(--md-sys-color-surface-container-highest);
}

.btn-small {
  padding: 4px 12px;
  background: var(--md-sys-color-secondary-container);
  color: var(--md-sys-color-on-secondary-container);
  border: none;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-small:hover {
  background: var(--md-sys-color-secondary-fixed);
}
</style>
