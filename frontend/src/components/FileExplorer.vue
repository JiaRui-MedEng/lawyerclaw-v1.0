<!--
百佑 LawyerClaw 文件选择器 - 参照 lawyerclaw.html 设计
功能:
1. 多选文件
2. 文件浏览
3. 选中文件自动附加到对话
-->
<template>
  <aside class="sidebar-right">
    <!-- 头部 -->
    <div class="sidebar-right-header">
      <span class="title">工作空间</span>
      <button class="btn-refresh" @click="refreshFiles" title="刷新文件列表" :disabled="loading">
        <i class="icon-refresh" :class="{ rotating: loading }"></i>
      </button>
    </div>

    <!-- 进行中任务指示器 -->
    <div v-if="ingestTask && ingestTask.minimized" class="ingest-task-indicator" @click="restoreIngestTask">
      <div class="ingest-task-info">
        <i :class="ingestTask.progress.active ? 'el-icon-loading' : 'el-icon-circle-check'"></i>
        <span class="ingest-task-title">存入知识库</span>
        <span class="ingest-task-count">{{ completedFileCount }}/{{ ingestTask.fileStatus.length }}</span>
      </div>
      <el-progress
        :percentage="ingestTask.progress.percent"
        :status="ingestTask.progress.status || undefined"
        :stroke-width="4"
        :show-text="false"
        class="ingest-task-progress"
      />
    </div>

    <!-- 路径选择器 -->
    <div class="path-selector" style="padding-left: 12px;">
      <button class="btn-parent" @click="goToParentDirectory" title="返回上级目录" :disabled="!currentPath || currentPath === getRootPath()">
        <i class="icon-arrow-up"></i>
      </button>
      <input 
        v-model="currentPathInput"
        @keyup.enter="navigateToPath"
        class="path-input"
        placeholder="输入路径..."
      />
      <button class="btn-navigate" @click="selectFolderDialog" title="选择文件夹">
        <i class="icon-folder"></i>
      </button>
    </div>

    <!-- 文件统计 -->
    <div class="file-count">
      共 {{ files.length }} 个文件
    </div>

    <!-- 文件列表 -->
    <div class="file-list">
      <div v-if="files.length === 0" class="empty-hint">暂无文件</div>
      
      <div 
        v-for="file in files" 
        :key="file.path"
        :class="['file-item', { selected: selectedFiles.includes(file.path) }]"
        @click="handleFileClick(file)"
        @dblclick="handleFileDoubleClick(file)"
      >
        <!-- 复选框 -->
        <div 
          :class="['checkbox', { checked: selectedFiles.includes(file.path) }]"
          @click.stop="toggleFileSelection(file.path)"
        >
          <i v-if="selectedFiles.includes(file.path)" class="icon-check"></i>
        </div>
        
        <!-- 文件类型徽章 -->
        <span v-if="!file.is_dir" :class="['file-badge', getFileBadgeClass(file.name)]">
          {{ getFileExtension(file.name) }}
        </span>
        <span v-else class="file-badge folder">📁</span>
        
        <!-- 文件信息 -->
        <div class="file-info">
          <div class="name">{{ file.name }}</div>
          <div v-if="!file.is_dir" class="meta">
            {{ formatFileSize(file.size) }} · {{ formatDate(file.modified) }}
          </div>
        </div>
      </div>
    </div>

    <!-- 底部选中状态 -->
    <div v-if="selectedFiles.length > 0" class="sidebar-right-footer">
      <span class="selected-count">
        已选 <strong>{{ selectedFiles.length }}</strong> 个文件
      </span>
      <button class="btn-clear" @click="clearSelection">
        <i class="icon-trash-2"></i>清空
      </button>
    </div>
    <div v-else class="sidebar-right-footer empty">
      <span class="hint">勾选文件后将在对话中自动附加</span>
    </div>
  </aside>
</template>

<script>
import { workspaceAPI } from '@/api/workspace'

export default {
  name: 'FileExplorer',
  data() {
    return {
      loading: false,
      currentPath: '',
      currentPathInput: '',
      files: [],
      selectedFiles: []
    }
  },
  computed: {
    ingestTask() {
      return this.$store.state.ingestTask
    },
    completedFileCount() {
      const task = this.$store.state.ingestTask
      if (!task || !task.fileStatus) return 0
      return task.fileStatus.filter(f => f.state === 'success' || f.state === 'fail').length
    }
  },
  async mounted() {
    // 优先从 localStorage 恢复上次选择的路径
    const savedPath = localStorage.getItem('lawyerclaw-workspacePath')
    if (savedPath) {
      this.currentPath = savedPath
      this.currentPathInput = savedPath
      // 同步到后端环境变量，确保重启后 LLM 也能获取工作空间路径
      workspaceAPI.setConfig(savedPath).catch(() => {})
    } else {
      // 从后端获取工作空间根目录
      try {
        const config = await workspaceAPI.getConfig()
        if (config.success && config.root) {
          this.currentPath = config.root
          this.currentPathInput = config.root
        }
      } catch (e) {
      }
    }
    if (this.currentPath) {
      this.refreshFiles()
    }
  },
  methods: {
    async refreshFiles() {
      if (!this.currentPath) return
      
      this.loading = true
      try {
        const res = await workspaceAPI.listFiles(this.currentPath, 2)
        if (res.success) {
          // API 返回 items 数组
          this.files = res.items || res.files || []
        } else {
          this.files = []
        }
      } catch (error) {
        this.files = []
      } finally {
        this.loading = false
      }
    },
    
    navigateToPath() {
      const path = this.currentPathInput.trim()
      if (path) {
        this.currentPath = path
        this.saveWorkspacePath(path)
        this.refreshFiles()
      }
    },

    getRootPath() {
      // 获取路径的根目录（Windows: C:\, Linux: /）
      if (!this.currentPath) return ''
      // Windows 路径: D:\Projects\Class -> D:\
      const winMatch = this.currentPath.match(/^([A-Za-z]:\\)/)
      if (winMatch) return winMatch[1]
      // Linux/Unix 路径: /home/user -> /
      if (this.currentPath === '/') return '/'
      return '/'
    },

    goToParentDirectory() {
      if (!this.currentPath) return
      const root = this.getRootPath()
      if (this.currentPath === root) return

      // 移除末尾斜杠
      let path = this.currentPath.replace(/[\\\/]+$/, '')
      // 获取父目录
      const lastSep = path.lastIndexOf('\\')
      const lastSlash = path.lastIndexOf('/')
      const lastSepIndex = Math.max(lastSep, lastSlash)

      if (lastSepIndex <= 0) {
        // 已经是根目录
        this.currentPath = root
      } else {
        this.currentPath = path.substring(0, lastSepIndex)
      }

      // 确保路径以斜杠结尾（Windows）
      if (this.currentPath.match(/^[A-Za-z]:$/) && !this.currentPath.endsWith('\\')) {
        this.currentPath += '\\'
      }

      this.currentPathInput = this.currentPath
      this.saveWorkspacePath(this.currentPath)
      this.refreshFiles()
    },

    async selectFolderDialog() {
      console.log('[FileExplorer] selectFolderDialog called')
      console.log('this.$axios =', this.$axios)
      console.log('this.$axios.defaults.baseURL =', this.$axios?.defaults?.baseURL)
      try {
        console.log('即将发送请求...')
        const response = await this.$axios.post('/api/workspace/select-folder')
        console.log('请求成功:', response.data)
        if (response.data.success) {
          // 同步模式：直接返回路径
          if (response.data.path) {
            this.currentPath = response.data.path
            this.currentPathInput = response.data.path
            this.saveWorkspacePath(response.data.path)
            this.refreshFiles()
          }
          // 异步模式：对话框已在后台弹出，提示用户
          else if (response.data.async) {
            this.$message.info(response.data.message || '文件夹选择器已弹出，请选择文件夹')
            // 轮询检查结果文件
            const resultFile = response.data.result_file
            if (resultFile) {
              this._pollFolderResult(resultFile)
            } else {
              // 兼容旧版：回退到 config 轮询
              this._pollFolderSelection()
            }
          }
        }
      } catch (error) {
        const msg = error.response?.data?.message || error.message
        if (msg !== '未选择文件夹') {
          this.$message.error('选择文件夹失败: ' + msg)
        }
      }
    },

    async _pollFolderResult(resultFile) {
      // 轮询后端结果文件，检测用户是否选择了文件夹
      let attempts = 0
      const maxAttempts = 120  // 最多等待 120 秒
      const pollInterval = setInterval(async () => {
        attempts++
        if (attempts > maxAttempts) {
          clearInterval(pollInterval)
          this.$message.warning('文件夹选择超时')
          return
        }
        try {
          const res = await this.$axios.post('/api/workspace/select-folder/result', {
            result_file: resultFile
          })
          const data = res.data

          if (!data.ready) {
            // 结果尚未就绪，继续轮询
            return
          }

          clearInterval(pollInterval)

          if (data.success && data.path) {
            this.currentPath = data.path
            this.currentPathInput = data.path
            this.saveWorkspacePath(data.path)
            this.refreshFiles()
            this.$message.success('工作空间已更新: ' + data.path)
          } else {
            // 用户取消或出错
            if (data.message && data.message !== '用户取消了选择') {
              this.$message.warning(data.message)
            }
          }
        } catch (e) {
          // 忽略轮询错误
        }
      }, 1000)
    },

    async _pollFolderSelection() {
      // 轮询后端配置，检测用户是否选择了新文件夹
      let attempts = 0
      const maxAttempts = 60  // 最多等待 60 秒
      const pollInterval = setInterval(async () => {
        attempts++
        if (attempts > maxAttempts) {
          clearInterval(pollInterval)
          return
        }
        try {
          const config = await workspaceAPI.getConfig()
          if (config.success && config.root) {
            // 检查路径是否变化
            if (config.root !== this.currentPath) {
              clearInterval(pollInterval)
              this.currentPath = config.root
              this.currentPathInput = config.root
              this.saveWorkspacePath(config.root)
              this.refreshFiles()
              this.$message.success('工作空间已更新: ' + config.root)
            }
          }
        } catch (e) {
          // 忽略轮询错误
        }
      }, 1000)
    },

    restoreIngestTask() {
      this.$store.commit('UPDATE_INGEST_TASK', { minimized: false, visible: true })
      // 如果当前不在聊天页面，导航到聊天页面
      if (this.$route.path !== '/chat') {
        this.$router.push('/chat')
      }
    },
    
    handleFileClick(file) {
      // 单击切换选中状态
      this.toggleFileSelection(file.path)
    },
    
    handleFileDoubleClick(file) {
      if (file.is_dir) {
        // 双击进入文件夹
        this.currentPath = file.path
        this.currentPathInput = file.path
        this.saveWorkspacePath(file.path)
        this.refreshFiles()
      } else {
        // 双击文件 - 用系统默认程序打开
        workspaceAPI.openFile(file.path).catch(err => {
          const msg = err.response?.data?.message || err.message
          this.$message.error('打开文件失败: ' + msg)
        })
      }
    },
    
    saveWorkspacePath(path) {
      localStorage.setItem('lawyerclaw-workspacePath', path)
      // 同步到后端配置
      workspaceAPI.setConfig(path).catch(e => {
      })
    },
    
    toggleFileSelection(filePath) {
      const index = this.selectedFiles.indexOf(filePath)
      if (index === -1) {
        this.selectedFiles.push(filePath)
      } else {
        this.selectedFiles.splice(index, 1)
      }
      this.$emit('selection-change', { count: this.selectedFiles.length, files: [...this.selectedFiles] })
    },
    
    clearSelection() {
      this.selectedFiles = []
      this.$emit('selection-change', { count: 0, files: [] })
    },
    
    getFileName(path) {
      const parts = path.split(/[\\/]/)
      return parts[parts.length - 1]
    },
    
    getFileExtension(filename) {
      const ext = filename.split('.').pop().toLowerCase()
      const extMap = {
        'pdf': 'PDF',
        'doc': 'DOC',
        'docx': 'DOC',
        'xls': 'XLS',
        'xlsx': 'XLS',
        'png': 'IMG',
        'jpg': 'IMG',
        'jpeg': 'IMG',
        'gif': 'IMG',
        'bmp': 'IMG',
        'webp': 'IMG',
        'txt': 'TXT',
        'md': 'TXT',
        'py': 'PY',
        'js': 'JS',
        'ts': 'TS',
        'vue': 'VUE',
        'json': 'JSON',
        'yaml': 'YAML',
        'yml': 'YAML'
      }
      return extMap[ext] || ext.toUpperCase().slice(0, 3)
    },
    
    getFileBadgeClass(filename) {
      const ext = filename.split('.').pop().toLowerCase()
      if (['pdf'].includes(ext)) return 'pdf'
      if (['doc', 'docx'].includes(ext)) return 'doc'
      if (['xls', 'xlsx'].includes(ext)) return 'xls'
      if (['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'].includes(ext)) return 'img'
      if (['txt', 'md'].includes(ext)) return 'txt'
      return 'txt'
    },
    
    formatFileSize(size) {
      if (size === undefined || size === null) return ''
      const kb = size / 1024
      if (kb < 1024) return `${kb.toFixed(1)} KB`
      return `${(kb / 1024).toFixed(1)} MB`
    },
    
    formatDate(dateStr) {
      if (!dateStr) return ''
      const d = new Date(dateStr)
      return `${d.getMonth() + 1}/${d.getDate()}`
    }
  }
}
</script>

<style scoped>
/* ========== 右侧边栏整体 ========== */
.sidebar-right {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  background: #FDFCFA;
}

/* ========== 头部 ========== */
.sidebar-right-header {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  border-bottom: 1px solid #E0D9D0;
}

.sidebar-right-header .title {
  font-weight: 600;
  font-size: 14px;
  color: #1C1C1C;
}

.sidebar-right-header .actions {
  display: flex;
  gap: 8px;
}

.sidebar-right-header .actions i {
  color: #A09888;
  font-size: 16px;
  cursor: pointer;
}

.sidebar-right-header .actions i:hover {
  color: #6B6156;
}

/* 刷新按钮 */
.btn-refresh {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  color: #A09888;
  cursor: pointer;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}

.btn-refresh:hover:not(:disabled) {
  background: #F0EBE3;
  color: #6B6156;
}

.btn-refresh:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-refresh .icon-refresh {
  font-size: 16px;
  display: inline-block;
}

.btn-refresh .icon-refresh::before {
  content: '↻';
  font-style: normal;
  font-size: 16px;
  line-height: 1;
}

.btn-refresh .icon-refresh.rotating {
  animation: rotate 1s linear infinite;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* ========== 路径选择器 ========== */
.path-selector {
  margin: 12px 16px 0;
  padding: 8px 12px;
  border-radius: 6px;
  background: #F0EBE3;
  display: flex;
  align-items: center;
  gap: 8px;
}

.path-selector i {
  font-size: 14px;
  color: #A09888;
  flex-shrink: 0;
}

.path-input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-family: 'Geist Mono', monospace;
  font-size: 12px;
  color: #6B6156;
}

.path-input::placeholder {
  color: #A09888;
}

.btn-navigate {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: #A09888;
  cursor: pointer;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}

.btn-navigate:hover {
  background: #E0D9D0;
  color: #6B6156;
}

/* 父目录按钮 */
.btn-parent {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: #A09888;
  cursor: pointer;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  flex-shrink: 0;
}

.btn-parent:hover:not(:disabled) {
  background: #E0D9D0;
  color: #6B6156;
}

.btn-parent:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.btn-parent .icon-arrow-up {
  font-size: 14px;
}

/* ========== 文件统计 ========== */
.file-count {
  padding: 8px 16px;
  font-family: 'Geist Mono', monospace;
  font-size: 11px;
  color: #A09888;
  letter-spacing: 0.5px;
}

/* ========== 文件列表 ========== */
.file-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px;
}

.file-list::-webkit-scrollbar {
  width: 4px;
}

.file-list::-webkit-scrollbar-thumb {
  background: #D5CEC4;
  border-radius: 2px;
}

.empty-hint {
  padding: 40px 16px;
  text-align: center;
  color: #A09888;
  font-size: 13px;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
  margin-bottom: 2px;
}

.file-item:hover {
  background: #F0EBE3;
}

.file-item.selected {
  background: #EDE8DF;
}

/* 复选框 */
.checkbox {
  width: 16px;
  height: 16px;
  border-radius: 4px;
  border: 1.5px solid #C8C0B4;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.15s;
}

.checkbox.checked {
  background: #C8A96E;
  border-color: #C8A96E;
}

.checkbox i {
  color: #fff;
  font-size: 11px;
}

/* 文件类型徽章 */
.file-badge {
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'Geist Mono', monospace;
  font-size: 10px;
  font-weight: 600;
  flex-shrink: 0;
}

.file-badge.pdf {
  background: #FDECEA;
  color: #C0392B;
}

.file-badge.doc {
  background: #E8F0FE;
  color: #2B6CB0;
}

.file-badge.xls {
  background: #E6F4EA;
  color: #1E7E34;
}

.file-badge.img {
  background: #FFF3E0;
  color: #E67E22;
}

.file-badge.txt {
  background: #F0EBE3;
  color: #8A7D6B;
}

.file-badge.folder {
  background: #F0EBE3;
  color: #8A7D6B;
}

/* 文件信息 */
.file-info {
  flex: 1;
  min-width: 0;
}

.file-info .name {
  font-size: 13px;
  color: #3A3530;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-info .meta {
  font-family: 'Geist Mono', monospace;
  font-size: 11px;
  color: #A09888;
  margin-top: 2px;
}

/* ========== 底部状态栏 ========== */
.sidebar-right-footer {
  height: 68px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  border-top: 1px solid #E0D9D0;
  flex-shrink: 0;
}

.sidebar-right-footer.empty {
  justify-content: center;
}

.selected-count {
  font-size: 14px;
  color: #6B6156;
}

.selected-count strong {
  color: #C8A96E;
  font-weight: 600;
}

.hint {
  font-size: 13px;
  color: #A09888;
  font-style: italic;
}

.btn-clear {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border: 1px solid #D5CEC4;
  border-radius: 6px;
  background: transparent;
  color: #6B6156;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}

.btn-clear:hover {
  background: #F0EBE3;
  border-color: #C8A96E;
}

.btn-clear i {
  font-size: 13px;
}

/* ========== 进行中任务指示器 ========== */
.ingest-task-indicator {
  margin: 8px 16px 0;
  padding: 8px 12px;
  background: #FDFCFA;
  border: 1px solid #E0D9D0;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
}

.ingest-task-indicator:hover {
  background: #F0EBE3;
  border-color: #C8A96E;
}

.ingest-task-info {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #6B6156;
  margin-bottom: 4px;
}

.ingest-task-info i {
  font-size: 13px;
  color: #C8A96E;
}

.ingest-task-title {
  flex: 1;
  font-weight: 500;
}

.ingest-task-count {
  font-family: 'Geist Mono', monospace;
  font-size: 11px;
  color: #A09888;
}

.ingest-task-progress {
  margin: 0;
}

.ingest-task-progress :deep(.el-progress-bar__outer) {
  background-color: #E0D9D0;
}
</style>