<template>
  <div id="app">
    <div class="layout">
      <!-- 第 1 列：导航列 (surface_container_low) -->
      <aside class="col-nav" :style="{ width: navWidth + 'px' }">
        <div class="nav-actions">
          <button class="btn-new-session" @click="createSession">
            <span class="icon">＋</span>
            <span>新会话</span>
          </button>
          <button class="btn-edit-sessions" @click="toggleEditMode" :class="{ active: editMode }">
            <span class="icon">{{ editMode ? '✓' : '✏️' }}</span>
            <span>{{ editMode ? '完成' : '编辑' }}</span>
          </button>
        </div>

        <div class="session-list">
          <!-- 临时会话显示 -->
          <div
            v-if="tempSession"
            :class="['session-item', { active: currentSessionId === tempSession.id, 'selected': selectedSessions.includes(tempSession.id) }]"
            @click="editMode ? toggleSessionSelection(tempSession.id) : switchSession(tempSession.id)"
          >
            <div class="session-info">
              <span class="session-title">新会话</span>
              <span class="session-meta">未保存</span>
            </div>
            <span class="session-time">刚刚</span>
          </div>
          
          <!-- 真实会话列表 -->
          <div
            v-for="session in sessions"
            :key="session.id"
            :class="['session-item', { active: currentSessionId === session.id, 'selected': selectedSessions.includes(session.id) }]"
            @click="editMode ? toggleSessionSelection(session.id) : switchSession(session.id)"
          >
            <div class="session-info">
              <span class="session-title">{{ session.title || '新会话' }}</span>
              <span class="session-meta">{{ session.model || 'qwen3.5-plus' }}</span>
            </div>
            <span class="session-time">{{ formatDate(session.updated_at) }}</span>
          </div>
          
          <div v-if="sessions.length === 0 && !tempSession" class="empty-hint">暂无会话</div>
        </div>

        <div v-if="editMode && selectedSessions.length > 0" class="batch-actions">
          <button class="btn-delete-batch" @click="handleDelete">
            <span class="icon">🗑️</span>
            <span>删除 ({{ selectedSessions.length }})</span>
          </button>
          <button class="btn-cancel-edit" @click="cancelEdit">
            <span>取消</span>
          </button>
        </div>

        <div class="user-center" @click="handleUserCardClick" style="cursor: pointer">
          <div class="user-left">
            <div class="user-avatar">{{ avatarInitial }}</div>
            <div class="user-info">
              <span class="user-name">{{ displayName }}</span>
              <span class="user-plan">在线</span>
            </div>
          </div>
        </div>
      </aside>

      <!-- ⭐ 左侧拖拽手柄 -->
      <div class="resize-handle" @mousedown="startResize($event, 'left')"></div>

      <!-- 第 2 列：主工作区 (surface) -->
      <main class="col-main">
        <router-view />
      </main>

      <!-- ⭐ 右侧拖拽手柄 -->
      <div class="resize-handle" @mousedown="startResize($event, 'right')"></div>

      <!-- 第 3 列：文件资源管理器 (surface_container_low) -->
      <aside class="col-files" :style="{ width: filesWidth + 'px' }">
        <file-explorer ref="fileExplorer" @selection-change="selectedFileCount = $event.count" />
      </aside>
    </div>


  </div>
</template>

<script>
import FileTreeNode from './components/FileTreeNode.vue'
import FileExplorer from './components/FileExplorer.vue'

// 确保 axios 可用
const axios = window.axios || require('axios')

export default {
  name: 'App',
  components: { FileTreeNode, FileExplorer },
  computed: {
    displayName() {
      return this.nickname || '新用户'
    },
    avatarInitial() {
      const name = this.displayName
      return name ? name.charAt(0).toUpperCase() : '用'
    },
    sessions() {
      return this.$store.state.sessions.list
    },
    currentSessionId() {
      return this.$store.state.sessions.currentId
    },
    tempSession() {
      return this.$store.state.sessions.tempSession
    },
    allSessions() {
      const all = [...this.$store.state.sessions.list]
      if (this.$store.state.sessions.tempSession) {
        all.unshift(this.$store.state.sessions.tempSession)
      }
      return all
    },
    workspaceTree() {
      return this.$store.state.workspace.tree
    },
    workspaceRoot() {
      return this.$store.state.workspace.root
    },
    workspaceLoading() {
      return this.$store.state.workspace.loading
    }
  },
  data() {
    return {
      editMode: false,
      selectedSessions: [],
      nickname: localStorage.getItem('nickname') || '',
      selectedFileCount: 0,
      // ⭐ 可拖拽调整列宽
      navWidth: parseInt(localStorage.getItem('lawyerclaw-navWidth')) || 220,
      filesWidth: parseInt(localStorage.getItem('lawyerclaw-filesWidth')) || 220,
      isResizing: false,
      resizeSide: null,  // 'left' or 'right'
      startX: 0,
      startWidth: 0
    }
  },
  methods: {
    // ⭐ 拖拽调整列宽
    startResize(event, side) {
      event.preventDefault()
      this.isResizing = true
      this.resizeSide = side
      this.startX = event.clientX
      this.startWidth = side === 'left' ? this.navWidth : this.filesWidth
      
      // 添加全局鼠标事件监听
      document.addEventListener('mousemove', this.onMouseMove)
      document.addEventListener('mouseup', this.onMouseUp)
      
      // 防止拖拽期间选中文字
      document.body.style.userSelect = 'none'
      document.body.style.cursor = 'col-resize'
    },
    
    onMouseMove(event) {
      if (!this.isResizing) return
      
      const delta = event.clientX - this.startX
      
      if (this.resizeSide === 'left') {
        // 左侧栏：向右拖增大，向左拖减小
        const newWidth = this.startWidth + delta
        this.navWidth = Math.max(160, Math.min(500, newWidth))
      } else {
        // 右侧栏：向左拖增大，向右拖减小
        const newWidth = this.startWidth - delta
        this.filesWidth = Math.max(160, Math.min(500, newWidth))
      }
    },
    
    onMouseUp() {
      if (!this.isResizing) return
      
      this.isResizing = false
      this.resizeSide = null
      
      // 移除全局事件监听
      document.removeEventListener('mousemove', this.onMouseMove)
      document.removeEventListener('mouseup', this.onMouseUp)
      
      // 恢复默认样式
      document.body.style.userSelect = ''
      document.body.style.cursor = ''
      
      // 持久化到 localStorage
      localStorage.setItem('lawyerclaw-navWidth', this.navWidth)
      localStorage.setItem('lawyerclaw-filesWidth', this.filesWidth)
    },
    
    toggleEditMode() {
      this.editMode = !this.editMode
      if (!this.editMode) {
        this.selectedSessions = []
      }
    },
    
    toggleSessionSelection(sessionId) {
      const index = this.selectedSessions.indexOf(sessionId)
      if (index > -1) {
        this.selectedSessions.splice(index, 1)
      } else {
        this.selectedSessions.push(sessionId)
      }
    },
    
    cancelEdit() {
      this.editMode = false
      this.selectedSessions = []
    },
    
    handleDelete() {
      this.batchDeleteSessions()
    },
    
    async batchDeleteSessions() {
      if (this.selectedSessions.length === 0) {
        return
      }
      
      
      try {
        const { MessageBox } = require('element-ui')
        
        await MessageBox.confirm(
          `确定要删除选中的 ${this.selectedSessions.length} 个会话吗？此操作不可恢复。`,
          '批量删除',
          {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            type: 'warning'
          }
        )
        
        
        // 过滤掉 undefined 和 null 值
        const validSessionIds = this.selectedSessions.filter(id => id)
        
        const tempSessionIds = validSessionIds.filter(id => id && id.startsWith('temp_'))
        const realSessionIds = validSessionIds.filter(id => id && !id.startsWith('temp_'))
        
        
        const willDeleteCurrent = this.selectedSessions.includes(this.currentSessionId)
        
        
        let result = null
        if (realSessionIds.length > 0) {
          result = await this.$store.dispatch('sessions/batchDeleteSessions', realSessionIds)
        }
        
        if (tempSessionIds.length > 0) {
          this.$store.dispatch('sessions/clearTempSession')
        }
        
        
        if (result === null || (result && result.success)) {
          this.$message.success(tempSessionIds.length > 0 ? '会话已删除' : result.message)
          this.editMode = false
          this.selectedSessions = []
          
          await this.$nextTick()
          
          if (willDeleteCurrent && this.sessions.length > 0) {
            this.$store.commit('sessions/setCurrentSession', this.sessions[0].id)
          } else if (willDeleteCurrent) {
            this.$store.commit('sessions/setCurrentSession', null)
          }
        } else {
          this.$message.error(result?.message || '删除失败')
        }
      } catch (error) {
        if (error === 'cancel' || error.message === 'cancel') {
          return
        }
        this.$message.error('删除失败：' + error.message)
      }
    },
    
    async loadFontSize() {
      await this.$store.dispatch('settings/loadSettings')
      
      const loadedFromBackend = await this.$store.dispatch('settings/loadFromBackend')
      if (!loadedFromBackend) {
        await this.$store.dispatch('settings/loadSettings')
      }
      
      await this.$store.dispatch('settings/updateFontSize')
    },
    
    applyFontSizeDataAttribute() {
      const fontSize = this.$store.state.settings.fontSize
      document.documentElement.setAttribute('data-font-size', fontSize)
    },
    
    applyTheme() {
      this.$store.dispatch('settings/applyTheme')
    },
    async createSession() {
      if (this.$store.state.sessions.tempSession) {
        this.$store.dispatch('sessions/clearTempSession')
      }
      
      const session = this.$store.dispatch('sessions/createTempSession')
      if (session) {
        if (this.$route.path !== '/chat') {
          this.$router.push('/chat')
        }
      }
    },
    switchSession(id) {
      if (this.currentSessionId && this.currentSessionId.startsWith('temp_') && id !== this.currentSessionId) {
        this.$store.dispatch('sessions/clearTempSession')
      }
      
      // 使用命名空间调用
      this.$store.commit('sessions/setCurrentSession', id)
      if (this.$route.path !== '/chat') {
        this.$router.push('/chat')
      }
    },
    formatDate(dateStr) {
      if (!dateStr) return ''

      // 后端存储的是 UTC 时间，需要转换为东八区
      const d = new Date(dateStr)
      const utcTime = d.getTime()
      const cstTime = new Date(utcTime + (8 * 3600000))

      const now = new Date()
      const nowCst = new Date(now.getTime() + (8 * 3600000))

      const diff = nowCst - cstTime

      if (diff < 86400000) {
        // 今天：显示 HH:MM（用 getUTCHours 避免浏览器时区二次偏移）
        return `${cstTime.getUTCHours().toString().padStart(2, '0')}:${cstTime.getUTCMinutes().toString().padStart(2, '0')}`
      }
      // 其他日期：显示 MM/DD
      return `${cstTime.getUTCMonth() + 1}/${cstTime.getUTCDate()}`
    },
    shortPath(p) {
      const parts = p.replace(/\\/g, '/').split('/')
      if (parts.length <= 3) return p
      return '…/' + parts.slice(-2).join('/')
    },
    
    handleUserCardClick() {
      this.$router.push('/settings').catch(err => {
        if (err.name !== 'NavigationDuplicated') {
        }
      })
    },
    
    onNicknameChange(event) {
      this.nickname = event.detail?.nickname || localStorage.getItem('nickname') || ''
    },
    
    async refreshFiles() {
      await this.$store.dispatch('fetchTree')
    },
    async changeWorkspace() {
      try {
        const { value } = await this.$prompt('请输入工作空间目录路径：', '设置工作空间', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          inputValue: this.workspaceRoot || '',
          inputPlaceholder: '例如：D:\\\\Projects'
        })
        if (value) {
          const ok = await this.$store.dispatch('setWorkspaceRoot', value)
          if (ok) {
            await this.$store.dispatch('fetchTree')
            this.$message.success('工作空间已更新')
          } else {
            this.$message.error('目录不存在或无法访问')
          }
        }
      } catch {
        // 用户取消
      }
    }
  },
  async mounted() {
    // 使用命名空间调用 modules 中的 actions
    await this.$store.dispatch('sessions/fetchSessions')
    this.$store.dispatch('workspace/fetchTree')
    
    // 如果没有会话，自动创建一个新会话
    if (this.sessions.length === 0 && !this.tempSession) {
      this.createSession()
    }
    await this.loadFontSize()
    
    this.applyFontSizeDataAttribute()
    
    // 初始化主题
    this.applyTheme()
    
    // 监听昵称变化事件（从 Settings / UserCenter 同步）
    window.addEventListener('lawyerclaw:nickname-change', this.onNicknameChange)
  },
  beforeDestroy() {
    window.removeEventListener('lawyerclaw:nickname-change', this.onNicknameChange)
    // ⭐ 清理拖拽事件监听
    document.removeEventListener('mousemove', this.onMouseMove)
    document.removeEventListener('mouseup', this.onMouseUp)
  },
}
</script>

<style>
/* 导入深色模式主题 */
@import './styles/dark-theme.css';

/* ====== 全局重置 ====== */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

/* ====== CSS 变量（设计系统） ====== */
:root {
  /* ⭐ 字体大小变量 - 与右侧侧边栏保持一致 */
  --font-size-lg: 16px;
  --font-size-md: 14px;
  --font-size-sm: 13px;
  --font-size-xs: 11px;
  
  --primary: #031635;
  --primary-container: #1a2b4b;
  --on-primary: #ffffff;
  --on-primary-fixed-variant: #364768;

  --surface: #f7f9fb;
  --surface-container-low: #f2f4f6;
  --surface-container-lowest: #ffffff;
  --surface-container-high: #e8eaed;
  --surface-container-highest: #e0e3e5;

  --on-surface: #191c1e;
  --on-surface-variant: #44474e;

  --secondary-container: #d0e1fb;
  --error-container: #ffdad6;
  --outline-variant: #c5c6cf;

  --radius: 4px;

  --font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

body {
  font-family: var(--font-family);
  color: var(--on-surface);
  background: var(--surface);
  /* ⭐ 使用 rem 继承 html 根字体大小 */
  font-size: 1rem;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}

#app {
  height: 100vh;
  overflow: hidden;
}

.layout {
  display: flex;
  height: 100vh;
}

.col-nav {
  /* ⭐ 使用 width 而非 flex，允许拖拽调整 */
  flex-shrink: 0;
  background: #FDFCFA;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding-top: 16px;
  height: 100vh;
}

.nav-actions {
  display: flex;
  gap: 8px;
  padding: 0 12px 12px;
}

.btn-new-session,
.btn-edit-sessions {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border: none;
  border-radius: var(--radius);
  font-size: var(--font-size-md);
  font-weight: 500;
  cursor: pointer;
  font-family: var(--font-family);
  transition: all 0.2s;
}

.btn-new-session {
  flex: 1;
  background: linear-gradient(135deg, var(--primary), var(--primary-container));
  color: var(--on-primary);
}

.btn-new-session:hover {
  opacity: 0.9;
}

.btn-edit-sessions {
  background: transparent;
  border: 1px solid #D5CEC4;
  color: #6B6156;
}

.btn-edit-sessions:hover {
  background: #F0EBE3;
  border-color: #C8A96E;
}

.btn-edit-sessions.active {
  background: #C8A96E;
  border-color: #C8A96E;
  color: #fff;
}

.btn-new-session .icon {
  font-size: var(--font-size-lg);
  font-weight: 300;
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px;
}

.session-item {
  padding: 9px 12px;
  margin-bottom: 2px;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: background 0.15s;
}

.session-item:hover {
  background: #F0EBE3;
}

.session-item.active {
  background: #EDE8DF;
  border-left: 3px solid #C8A96E;
}

.session-item.selected {
  background: #EDE8DF;
  border-left: 3px solid #C8A96E;
}

.session-checkbox {
  display: none;
}

.session-item.selected .session-checkbox {
  display: block;
}

.session-checkbox input {
  cursor: pointer;
}

.batch-actions {
  display: flex;
  gap: 8px;
  padding: 12px;
  border-top: 1px solid var(--outline-variant);
  background: var(--surface-container-low);
}

.btn-delete-batch,
.btn-cancel-edit {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border: none;
  border-radius: var(--radius);
  font-size: var(--font-size-sm);
  cursor: pointer;
  font-family: var(--font-family);
  transition: all 0.2s;
}

.btn-delete-batch {
  background: var(--error-container);
  color: #c62828;
  flex: 1;
}

.btn-delete-batch:hover {
  background: #ffcdd2;
}

.btn-cancel-edit {
  background: var(--surface-container-high);
  color: var(--on-surface);
}

.btn-cancel-edit:hover {
  background: var(--surface-container-highest);
}

.session-info {
  flex: 1;
  min-width: 0;
}

.session-title {
  display: block;
  font-size: var(--font-size-sm);
  color: var(--on-surface);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-meta {
  display: block;
  font-size: var(--font-size-xs);
  color: var(--on-surface-variant);
  margin-top: 2px;
}

.session-time {
  font-size: var(--font-size-xs);
  color: var(--on-surface-variant);
  margin-left: 8px;
  flex-shrink: 0;
}

.user-center {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  border-top: 1px solid #E0D9D0;
  gap: 10px;
  margin-top: 0;
  cursor: pointer;
  transition: background 0.15s;
  height: 68px;
  flex-shrink: 0;
  align-self: flex-end;
  width: 100%;
  box-sizing: border-box;
}

.user-center:hover {
  background: #F0EBE3;
}

.user-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.user-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--primary), var(--primary-container));
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 15px;
  font-weight: 700;
  flex-shrink: 0;
}

.user-info {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.user-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--on-surface);
}

.user-plan {
  font-size: 12px;
  color: var(--on-surface-variant);
}

.btn-settings {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: var(--radius);
  cursor: pointer;
  font-size: 16px;
  transition: background 0.15s;
}

.btn-settings:hover {
  background: var(--surface-container-high);
}

.col-main {
  flex: 1;
  background: var(--surface);
  min-width: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.col-files {
  /* ⭐ 使用 width 而非 flex，允许拖拽调整 */
  flex-shrink: 0;
  background: var(--surface-container-low);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  height: 100vh;
}

/* ⭐ 拖拽手柄 */
.resize-handle {
  width: 4px;
  cursor: col-resize;
  background: transparent;
  transition: background 0.2s;
  flex-shrink: 0;
  position: relative;
  z-index: 10;
}

.resize-handle:hover {
  background: var(--primary, #031635);
  opacity: 0.15;
}

.resize-handle:active {
  background: var(--primary, #031635);
  opacity: 0.25;
}

.files-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 18px 12px;
}

.files-title {
  font-size: var(--font-size-md);
  font-weight: 600;
  color: var(--primary);
}

.btn-icon {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: var(--radius);
  cursor: pointer;
  font-size: var(--font-size-lg);
  color: var(--on-surface-variant);
  transition: background 0.15s;
}

.btn-icon:hover {
  background: var(--surface-container-high);
}

.files-path {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 18px 12px;
}

.path-text {
  font-size: var(--font-size-xs);
  color: var(--on-surface-variant);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.btn-path {
  font-size: var(--font-size-xs);
  color: var(--primary);
  background: none;
  border: none;
  cursor: pointer;
  font-family: var(--font-family);
  padding: 2px 6px;
  border-radius: var(--radius);
  flex-shrink: 0;
}

.btn-path:hover {
  background: var(--secondary-container);
}

.file-tree {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px 12px;
}

.empty-hint {
  text-align: center;
  padding: 32px 16px;
  font-size: var(--font-size-sm);
  color: var(--on-surface-variant);
}

::-webkit-scrollbar {
  width: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: var(--outline-variant);
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: var(--on-surface-variant);
}


/* 覆盖 Element UI 按钮默认颜色 */
.el-button.el-button--primary {
  background: linear-gradient(135deg, var(--primary), var(--primary-container)) !important;
  border: none !important;
  color: var(--on-primary) !important;
}

.el-button.el-button--primary:hover {
  opacity: 0.9;
}

.el-message-box__wrapper .el-message-box {
  border-radius: var(--radius) !important;
  border: none !important;
  box-shadow: 0 20px 40px rgba(3, 22, 53, 0.06) !important;
}
</style>
