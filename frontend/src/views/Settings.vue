<template>
  <div class="settings-view">
    <div class="settings-layout">
      <!-- 左侧：设置内容-->
      <div class="settings-content">
        <h2 class="settings-title">设置</h2>

        <!-- 显示设置 -->
        <div class="settings-section">
          <h3 class="section-title">显示设置</h3>
          <div class="setting-row">
            <span class="setting-label">字体大小</span>
            <select :value="fontSize" @change="setFontSize($event.target.value)" class="setting-select">
              <option value="small">小</option>
              <option value="medium">中 - 默认</option>
              <option value="large">大</option>
              <option value="xlarge">超大</option>
            </select>
          </div>
          <div class="setting-row">
            <span class="setting-label">主题</span>
            <select :value="theme" @change="setTheme($event.target.value)" class="setting-select">
              <option value="light">浅色模式</option>
              <option value="dark">深色模式</option>
            </select>
          </div>
        </div>

        <!-- 模型配置 -->
        <div class="settings-section">
          <h3 class="section-title">模型配置</h3>
          
          <!-- 表单 -->
          <div class="provider-form">
            <div class="setting-row">
              <span class="setting-label">配置名称</span>
              <input v-model="form.name" class="setting-input" placeholder="请输入配置名称" />
            </div>
            <div class="setting-row">
              <span class="setting-label">协议类型</span>
              <select v-model="form.protocol" class="setting-select">
                <option value="openai">OpenAI 兼容协议</option>
                <option value="anthropic">Anthropic 协议</option>
              </select>
            </div>
            <div class="setting-row">
              <span class="setting-label">Base URL</span>
              <input v-model="form.base_url" class="setting-input" />
            </div>
            <div class="setting-row">
              <span class="setting-label">API Key</span>
              <input v-model="form.api_key" class="setting-input" />
            </div>
            <div class="setting-row">
              <span class="setting-label">模型名称</span>
              <input v-model="form.default_model" class="setting-input"
                     placeholder="请输入模型名称" />
            </div>
            <div class="form-actions">
              <button class="btn-test" @click="handleTestConnection">测试连接</button>
              <button class="btn-save-provider" @click="handleSaveProvider">保存</button>
              <button v-if="editingId" class="btn-cancel" @click="cancelEdit">取消</button>
            </div>
          </div>
          
          <!-- 已保存的配置列表 -->
          <div class="provider-list" v-if="customProviders.length > 0">
            <div v-for="p in customProviders" :key="p.id" 
                 :class="['provider-item', { active: p.id === activeProviderId }]">
              <div class="provider-info">
                <span class="provider-name">{{ p.name }}</span>
                <span class="provider-protocol">{{ p.protocol === 'openai' ? 'OpenAI' : 'Anthropic' }}</span>
                <span class="provider-model">{{ p.default_model }}</span>
              </div>
              <div class="provider-actions">
                <el-tag v-if="p.id === activeProviderId" type="success" size="mini">活跃</el-tag>
                <el-button size="mini" @click="setActive(p.id)">设为活跃</el-button>
                <el-button size="mini" @click="editProvider(p)">编辑</el-button>
                <el-button size="mini" type="danger" @click="handleDeleteProvider(p.id)">删除</el-button>
              </div>
            </div>
          </div>
        </div>

        <!-- 技能列表 -->
        <div class="settings-section">
          <h3 class="section-title">技能列表</h3>
          <div v-if="skillsLoading" class="skills-loading">
            <i class="el-icon-loading"></i> 加载中...
          </div>
          <div v-else-if="skills.length === 0" class="skills-empty">
            暂无已安装的技能
          </div>
          <div v-else class="skills-grid">
            <div v-for="(skill, index) in skills" :key="skill.name + '-' + index" class="skill-card">
              <div class="skill-header">
                <span class="skill-name">{{ skill.name }}</span>
                <el-tag v-if="skill.category" size="mini" type="info">{{ skill.category }}</el-tag>
              </div>
              <p class="skill-desc">{{ skill.description || '暂无描述' }}</p>
              <div class="skill-footer">
                <span class="skill-status" :class="{ active: skill.is_active }">
                  {{ skill.is_active ? '已启用' : '已禁用' }}
                </span>
              </div>
            </div>
          </div>
          <p class="setting-hint">技能为智能体提供专业领域的能力扩展。</p>
        </div>

        <!-- 法律专业 -->
        <div class="settings-section">
          <h3 class="section-title">法律专业</h3>
          <div class="setting-row">
            <span class="setting-label">默认法域</span>
            <select :value="jurisdiction" @change="setJurisdiction" class="setting-select">
              <option value="cn">🇨🇳 中国大陆</option>
            </select>
          </div>
        </div>
        
        <!-- ⭐ 自动润色 -->
        <div class="settings-section">
          <h3 class="section-title">自动润色</h3>
          <div class="setting-row">
            <span class="setting-label">启用自动润色</span>
            <label class="setting-switch">
              <input type="checkbox" :checked="autoPolish" @change="setAutoPolish($event.target.checked)">
              <span class="switch-slider"></span>
            </label>
          </div>
          <div v-if="autoPolish" class="setting-sub">
            <div class="setting-row">
              <span class="setting-label">风格名称</span>
              <input
                :value="autoPolishStyle"
                @input="setAutoPolishStyle($event.target.value)"
                class="setting-input"
                placeholder="如 doctor-li"
              />
            </div>
            <div class="setting-row">
              <span class="setting-label">润色强度</span>
              <select :value="autoPolishIntensity" @change="setAutoPolishIntensity($event.target.value)" class="setting-select">
                <option value="light">轻微调整</option>
                <option value="medium">适度改写</option>
                <option value="strong">彻底重写</option>
              </select>
            </div>
            <p v-if="!autoPolishStyle" class="setting-hint" style="color: #e6a23c;">
              ⚠️ 请先在右侧工作空间选择文件，再点击"存入风格库"按钮创建风格文件
            </p>
          </div>
        </div>
        
        <!-- 保存按钮 -->
        <div class="settings-actions">
          <button class="btn-save" @click="save">保存设置</button>
          <button class="btn-reset" @click="reset">恢复默认</button>
        </div>
      </div>

      <!-- 右侧：用户信息-->
      <div class="user-sidebar">
        <div class="user-card">
          <div class="user-logged-section">
            <div class="user-avatar">{{ userAvatar }}</div>
            <h3 class="user-name">{{ displayName }}</h3>
            <p class="user-hint">点击编辑昵称</p>
            <div class="user-actions">
              <el-button 
                type="primary" 
                size="small" 
                @click="editNickname"
                style="width: 100%;"
              >编辑昵称</el-button>
            </div>
          </div>
        </div>
        
        <!-- RAG 知识库管理卡片 -->
        <div class="rag-card">
          <div class="rag-card-header">
            <h3 class="rag-card-title">RAG 知识库</h3>
            <el-tag size="small" :type="ragEnabled ? 'success' : 'info'">
              {{ ragEnabled ? '已启用' : '未启用' }}
            </el-tag>
          </div>
          
          <div class="rag-card-content">
            <div class="rag-stat">
              <div class="rag-stat-item">
                <span class="rag-stat-value">{{ ragStats.docCount || 0 }}</span>
                <span class="rag-stat-label">文档</span>
              </div>
              <div class="rag-stat-item">
                <span class="rag-stat-value">{{ ragStats.chunkCount || 0 }}</span>
                <span class="rag-stat-label">片段</span>
              </div>
            </div>
            
            <p class="rag-card-hint">管理您的法律知识库，提升回答准确性</p>
            
            <div class="rag-card-actions">
              <el-button 
                size="small" 
                @click="openRagManagement"
                style="flex: 1; background: linear-gradient(135deg, var(--primary), var(--primary-container)); border: none; color: white;"
              >
                管理知识库
              </el-button>
              <el-button 
                size="small" 
                @click="toggleRagEnabled"
                style="flex: 1;"
              >
                {{ ragEnabled ? '禁用' : '启用' }}
              </el-button>
            </div>
          </div>
        </div>

        <!-- 退出应用卡片 -->
        <div class="exit-card">
          <div class="exit-card-header">
            <h3 class="exit-card-title">应用程序</h3>
          </div>
          <div class="exit-card-content">
            <p class="exit-card-hint">关闭后端服务并退出百佑 LawyerClaw</p>
            <p class="exit-card-hint">所有数据将自动保存</p>
            <button class="btn-exit-app" @click="confirmExitApp">退出应用程序</button>
          </div>
        </div>
      </div>

      <!-- RAG 知识库管理弹窗 -->
      <el-dialog
        :visible.sync="showRagDialog"
        title="📚 RAG 知识库管理"
        width="680px"
        :close-on-click-modal="false"
        top="5vh"
      >
        <!-- Collection 选择 -->
        <div class="rag-dialog-section">
          <h4 class="rag-dialog-subtitle">已有知识库</h4>
          <div v-if="ragCollections.length === 0 && !ragDialogLoading" class="rag-empty">
            暂无知识库，请上传文档创建
          </div>
          <div v-loading="ragDialogLoading" class="rag-collection-list">
            <div
              v-for="col in ragCollections"
              :key="col.name"
              :class="['rag-collection-item', { active: selectedCollection === col.name }]"
              @click="selectCollection(col.name)"
            >
              <div class="rag-col-info">
                <span class="rag-col-name">{{ col.name }}</span>
                <span class="rag-col-count">{{ col.entity_count }} 条向量</span>
              </div>
              <el-button
                type="text"
                size="mini"
                icon="el-icon-delete"
                class="rag-col-delete"
                @click.stop="deleteCollection(col.name)"
              />
            </div>
          </div>
        </div>

        <!-- 上传文档 -->
        <div class="rag-dialog-section">
          <h4 class="rag-dialog-subtitle">上传文档到知识库</h4>

          <div class="rag-upload-form">
            <div class="rag-upload-row">
              <span class="rag-upload-label">目标知识库</span>
              <el-select
                v-model="uploadTargetCollection"
                size="small"
                placeholder="选择或新建"
                filterable
                allow-create
                style="flex: 1;"
              >
                <el-option
                  v-for="col in ragCollections"
                  :key="col.name"
                  :label="col.name"
                  :value="col.name"
                />
              </el-select>
            </div>

            <div class="rag-upload-area">
              <el-upload
                ref="ragUpload"
                :action="uploadUrl"
                :before-upload="beforeRagUpload"
                :on-success="onRagUploadSuccess"
                :on-error="onRagUploadError"
                :on-progress="onRagUploadProgress"
                :data="uploadExtraData"
                :headers="uploadHeaders"
                :show-file-list="true"
                :file-list="uploadFileList"
                :on-remove="onFileRemove"
                :on-change="onFileChange"
                :auto-upload="false"
                accept=".pdf,.docx,.doc,.txt"
                drag
                multiple
              >
                <i class="el-icon-upload"></i>
                <div class="el-upload__text">将文件拖到此处，或<em>点击上传</em></div>
                <div class="el-upload__tip" slot="tip">
                  支持 PDF、Word、TXT 文件，单文件最大 50MB
                </div>
              </el-upload>
            </div>

            <div v-if="uploadProgress.active || uploadProgress.status" class="rag-upload-progress">
              <!-- 阶段指示器 -->
              <div class="upload-stages">
                <div class="upload-stage" :class="{ active: uploadProgress.stage === 'upload', done: uploadProgress.stage === 'ingest' || uploadProgress.status === 'success' }">
                  <div class="stage-dot">
                    <i :class="uploadProgress.stage === 'upload' ? 'el-icon-loading' : 'el-icon-circle-check'"></i>
                  </div>
                  <span>上传文件</span>
                </div>
                <div class="upload-stage-line" :class="{ done: uploadProgress.stage === 'ingest' || uploadProgress.status === 'success' }"></div>
                <div class="upload-stage" :class="{ active: uploadProgress.stage === 'ingest', done: uploadProgress.status === 'success' }">
                  <div class="stage-dot">
                    <i :class="uploadProgress.stage === 'ingest' ? 'el-icon-loading' : (uploadProgress.status === 'success' ? 'el-icon-circle-check' : 'el-icon-document')"></i>
                  </div>
                  <span>解析入库</span>
                </div>
              </div>

              <!-- 总进度条 -->
              <el-progress
                class="upload-progress-custom"
                :percentage="uploadProgress.percent"
                :status="uploadProgress.status || undefined"
                :stroke-width="20"
              />
              <p class="upload-progress-msg">{{ uploadProgress.message }}</p>

              <!-- 逐文件状态列表 -->
              <div class="upload-file-status-list" v-if="uploadFileStatus.length > 0">
                <div
                  v-for="item in uploadFileStatus"
                  :key="item.uid"
                  class="upload-file-status-item"
                  :class="item.state"
                >
                  <i :class="fileStatusIcon(item.state)"></i>
                  <span class="file-name" :title="item.name">{{ item.name }}</span>
                  <span class="file-state-text">{{ fileStateText(item.state) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <span slot="footer" class="dialog-footer">
          <el-button size="small" @click="showRagDialog = false">关闭</el-button>
          <el-button
            size="small"
            type="primary"
            :loading="uploadProgress.active"
            :disabled="!uploadTargetCollection || uploadFileList.length === 0"
            @click="startUploadAndIngest"
          >
            开始上传并入库
          </el-button>
        </span>
      </el-dialog>


    </div>
  </div>
</template>

<script>
import { mapState, mapActions } from 'vuex'
import { skillAPI } from '@/api/hermes'

export default {
  name: 'SettingsView',
  data() {
    return {
      loading: false,
      stats: {
        sessionCount: 0,
        messageCount: 0
      },
      // RAG 知识库状态
      ragEnabled: true,
      ragStats: {
        docCount: 0,
        chunkCount: 0
      },
      ragLoading: false,
      // RAG 管理弹窗
      showRagDialog: false,
      ragDialogLoading: false,
      ragCollections: [],
      selectedCollection: '',
      uploadTargetCollection: '',
      uploadFileList: [],
      uploadFileStatus: [],
      uploadProgress: {
        active: false,
        percent: 0,
        message: '',
        status: '',
        stage: '',
      },
      // ⭐ 自定义模型配置
      form: {
        id: null,
        name: '',
        protocol: 'openai',
        base_url: '',
        api_key: '',
        default_model: ''
      },
      editingId: null,
      // ⭐ 技能列表
      skills: [],
      skillsLoading: false
    }
  },
  computed: {
    ...mapState('settings', [
      'fontSize',
      'theme',
      'maxTokens',
      'temperature',
      'jurisdiction',
      'customProviders',
      'activeProviderId',
      'autoPolish',
      'autoPolishStyle',
      'autoPolishIntensity'
    ]),
    
    displayName() {
      return localStorage.getItem('nickname') || '新用户'
    },
    userAvatar() {
      const name = this.displayName
      return name ? name.charAt(0).toUpperCase() : '用'
    },
    temperatureNum() {
      return parseFloat(this.temperature) || 0.7
    },
    maxTokensNum() {
      return parseInt(this.maxTokens) || 8000
    },
    uploadUrl() {
      return '/api/rag/upload'
    },
    uploadHeaders() {
      return {}
    },
    uploadExtraData() {
      return { collection_name: this.uploadTargetCollection }
    }
  },
  mounted() {
    this.loadStats()
    this.loadRagStats()
    this.loadProviders()  // ⭐ 加载提供商列表
    this.loadSkills()  // ⭐ 加载技能列表
  },
  methods: {
    ...mapActions('settings', [
      'updateFontSize',
      'saveToBackend',
      'resetSettings',
      'loadProviders',
      'saveProvider',
      'deleteProvider',
      'setActiveProvider',
      'testConnection'
    ]),
    
    setFontSize(size) {
      this.$store.commit('settings/SET_FONT_SIZE', size)
      this.updateFontSize()
    },
    
    setTheme(theme) {
      this.$store.dispatch('settings/setTheme', theme)
    },
    
    setMaxTokens(event) {
      const value = parseInt(event.target.value)
      this.$store.commit('settings/SET_MAX_TOKENS', value)
    },
    
    setTemperature(event) {
      const value = parseFloat(event.target.value)
      this.$store.commit('settings/SET_TEMPERATURE', value)
    },
    
    setJurisdiction(event) {
      this.$store.commit('settings/SET_JURISDICTION', event.target.value)
    },
    
    // ⭐ 自动润色设置
    setAutoPolish(val) {
      this.$store.dispatch('settings/setAutoPolish', val)
    },
    setAutoPolishStyle(event) {
      this.$store.dispatch('settings/setAutoPolishStyle', event.target.value)
    },
    setAutoPolishIntensity(event) {
      this.$store.dispatch('settings/setAutoPolishIntensity', event.target.value)
    },
    
    async save() {
      this.loading = true
      try {
        await this.saveToBackend()
        this.$message?.success?.('设置已保存')
      } catch (e) {
        this.$message?.error?.('保存失败')
      } finally {
        this.loading = false
      }
    },
    
    async reset() {
      await this.resetSettings()
      await this.save()
    },
    
    // ⭐ 自定义模型配置方法
    async handleTestConnection() {
      if (!this.form.base_url || !this.form.api_key) {
        this.$message.warning('请填写 Base URL 和 API Key')
        return
      }
      try {
        const result = await this.testConnection(this.form)
        if (result.success) {
          this.$message.success('连接成功！')
        } else {
          this.$message.error(result.error || '连接失败')
        }
      } catch (e) {
        this.$message.error('测试连接失败')
      }
    },
    
    async handleSaveProvider() {
      if (!this.form.name || !this.form.base_url || !this.form.api_key || !this.form.default_model) {
        this.$message.warning('请填写所有必填字段')
        return
      }
      try {
        const result = await this.saveProvider(this.form)
        if (result.success) {
          this.$message.success('配置已保存')
          this.cancelEdit()
          await this.loadProviders()
        } else {
          this.$message.error(result.error || '保存失败')
        }
      } catch (e) {
        this.$message.error('保存失败')
      }
    },
    
    async editProvider(provider) {
      this.form = { ...provider }
      this.editingId = provider.id
      // 获取原始 API Key（脱敏值不能用于测试/保存）
      try {
        const res = await this.$axios.get(`/api/providers/${provider.id}/raw-key`)
        if (res.data && res.data.success) {
          this.form.api_key = res.data.api_key
        }
      } catch (e) {
        // 静默失败，使用脱敏值
      }
    },
    
    cancelEdit() {
      this.form = {
        id: null,
        name: '',
        protocol: 'openai',
        base_url: '',
        api_key: '',
        default_model: ''
      }
      this.editingId = null
    },
    
    async setActive(id) {
      try {
        const result = await this.setActiveProvider(id)
        if (result.success) {
          this.$message.success('已设为活跃配置')
        } else {
          this.$message.error(result.error || '设置失败')
        }
      } catch (e) {
        this.$message.error('设置失败')
      }
    },
    
    async handleDeleteProvider(id) {
      try {
        await this.$confirm('确定删除此配置？', '确认删除', {
          confirmButtonText: '删除',
          cancelButtonText: '取消',
          type: 'warning'
        })
        const result = await this.deleteProvider(id)
        if (result.success) {
          this.$message.success('配置已删除')
          if (this.editingId === id) {
            this.cancelEdit()
          }
        } else {
          this.$message.error(result.error || '删除失败')
        }
      } catch (e) {
        // 用户取消
      }
    },
    
    async loadStats() {
      try {
        const response = await this.$axios.get('/api/sessions')
        if (response.data.success) {
          this.stats.sessionCount = response.data.sessions.length

          let messageCount = 0
          for (const session of response.data.sessions) {
            const messagesResponse = await this.$axios.get(`/api/sessions/${session.id}/messages`)
            if (messagesResponse.data.success) {
              messageCount += messagesResponse.data.messages.length
            }
          }
          this.stats.messageCount = messageCount
        }
      } catch (error) {
      }
    },

    // ⭐ 加载技能列表
    async loadSkills() {
      try {
        this.skillsLoading = true
        const response = await skillAPI.getSkills()
        if (response.data && response.data.success) {
          this.skills = response.data.skills || []
        }
      } catch (error) {
        console.error('加载技能列表失败:', error)
        this.skills = []
      } finally {
        this.skillsLoading = false
      }
    },

    // 加载 RAG 知识库状态
    async loadRagStats() {
      try {
        this.ragLoading = true
        const response = await this.$axios.get('/api/rag/stats')
        if (response.data.success) {
          this.ragStats = {
            docCount: response.data.stats?.doc_count || 0,
            chunkCount: response.data.stats?.chunk_count || 0
          }
          this.ragEnabled = response.data.stats?.enabled || false
        }
      } catch (error) {
        // 如果 API 不存在，使用模拟数据用于开发
        this.ragStats = {
          docCount: 0,
          chunkCount: 0
        }
        this.ragEnabled = false
      } finally {
        this.ragLoading = false
      }
    },
    
    // 打开 RAG 管理界面
    async openRagManagement() {
      this.showRagDialog = true
      await this.loadCollections()
    },

    // 加载 Collection 列表
    async loadCollections() {
      this.ragDialogLoading = true
      try {
        const response = await this.$axios.get('/api/rag/collections')
        if (response.data.success) {
          this.ragCollections = response.data.collections || []
          // 默认选中第一个
          if (this.ragCollections.length > 0 && !this.uploadTargetCollection) {
            this.uploadTargetCollection = this.ragCollections[0].name
          }
        }
      } catch (error) {
        this.ragCollections = []
      } finally {
        this.ragDialogLoading = false
      }
    },

    // 选中 Collection
    selectCollection(name) {
      this.selectedCollection = this.selectedCollection === name ? '' : name
      this.uploadTargetCollection = name
    },

    // 删除 Collection
    async deleteCollection(name) {
      try {
        await this.$confirm(`确定删除知识库「${name}」？此操作不可恢复。`, '确认删除', {
          confirmButtonText: '删除',
          cancelButtonText: '取消',
          type: 'warning'
        })
      } catch {
        return // 用户取消
      }

      try {
        const response = await this.$axios.delete(`/api/rag/collections/${name}`)
        if (response.data.success) {
          this.$message.success(`已删除「${name}」`)
          await this.loadCollections()
          await this.loadRagStats()
          if (this.uploadTargetCollection === name) {
            this.uploadTargetCollection = this.ragCollections.length > 0 ? this.ragCollections[0].name : ''
          }
        }
      } catch (error) {
        this.$message.error('删除失败: ' + (error.response?.data?.message || error.message))
      }
    },

    fileStatusIcon(state) {
      const map = {
        pending: 'el-icon-time',
        uploading: 'el-icon-loading',
        ingesting: 'el-icon-loading',
        success: 'el-icon-circle-check',
        fail: 'el-icon-circle-close',
      }
      return map[state] || 'el-icon-time'
    },
    fileStateText(state) {
      const map = {
        pending: '等待中',
        uploading: '上传中',
        ingesting: '入库中',
        success: '完成',
        fail: '失败',
      }
      return map[state] || ''
    },

    // 上传前校验
    beforeRagUpload(file) {
      const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()
      const allowed = ['.pdf', '.docx', '.doc', '.txt']
      if (!allowed.includes(ext)) {
        this.$message.error(`不支持的文件格式: ${ext}`)
        return false
      }
      if (file.size > 50 * 1024 * 1024) {
        this.$message.error('文件大小不能超过 50MB')
        return false
      }
      return true
    },

    onRagUploadSuccess() {},
    onRagUploadError() {},
    onRagUploadProgress() {},
    onFileChange(file, fileList) {
      this.uploadFileList = fileList
    },
    onFileRemove(file) {
      this.uploadFileList = this.uploadFileList.filter(f => f.uid !== file.uid)
    },

    // 开始上传并入库
    async startUploadAndIngest() {
      if (!this.uploadTargetCollection) {
        this.$message.warning('请选择或输入目标知识库名称')
        return
      }

      // 确保 collection 名称以 legal_ 开头
      let collectionName = this.uploadTargetCollection
      if (!collectionName.startsWith('legal_')) {
        collectionName = 'legal_' + collectionName
        this.uploadTargetCollection = collectionName
      }

      const uploadRef = this.$refs.ragUpload
      const files = uploadRef?.uploadFiles?.filter(f => f.status === 'ready') || []

      if (files.length === 0) {
        this.$message.warning('请先选择要上传的文件')
        return
      }

      // 初始化逐文件状态
      this.uploadFileStatus = files.map(f => ({
        uid: f.uid,
        name: f.name,
        state: 'pending',
        taskId: null,
      }))

      this.uploadProgress = {
        active: true,
        percent: 0,
        message: '准备上传...',
        status: '',
        stage: 'upload',
      }

      let successCount = 0
      let failCount = 0

      for (let i = 0; i < files.length; i++) {
        const file = files[i]
        const statusItem = this.uploadFileStatus[i]

        statusItem.state = 'uploading'
        this.uploadProgress.stage = 'upload'
        this.uploadProgress.message = `正在上传 (${i + 1}/${files.length}): ${file.name}`

        try {
          const formData = new FormData()
          formData.append('file', file.raw)
          formData.append('collection_name', collectionName)

          // 提交文件，拿到 task_id
          const response = await this.$axios.post('/api/rag/upload', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
            timeout: 60000,
          })

          if (!response.data.success || !response.data.task_id) {
            failCount++
            statusItem.state = 'fail'
            this.$message.warning(`${file.name}: ${response.data.message || '提交失败'}`)
            continue
          }

          // 轮询进度
          statusItem.state = 'ingesting'
          statusItem.taskId = response.data.task_id
          this.uploadProgress.stage = 'ingest'

          const result = await this._pollTaskProgress(response.data.task_id, statusItem, i, files.length)

          if (result.success) {
            successCount++
            file.status = 'success'
            statusItem.state = 'success'
          } else {
            failCount++
            file.status = 'fail'
            statusItem.state = 'fail'
            this.$message.warning(`${file.name}: ${result.message}`)
          }
        } catch (error) {
          failCount++
          file.status = 'fail'
          statusItem.state = 'fail'
        }
      }

      this.uploadProgress.active = false
      this.uploadProgress.status = failCount === 0 ? 'success' : 'warning'
      this.uploadProgress.message = `完成: ${successCount} 个成功, ${failCount} 个失败`

      if (successCount > 0) {
        this.$message.success(`${successCount} 个文件已成功入库`)
        await this.loadCollections()
        await this.loadRagStats()
        this.$refs.ragUpload?.clearFiles()
        this.uploadFileList = []
      }
    },

    // 轮询任务进度
    _pollTaskProgress(taskId, statusItem, fileIndex, totalFiles) {
      return new Promise((resolve) => {
        const poll = setInterval(async () => {
          try {
            const res = await this.$axios.get(`/api/rag/upload/progress/${taskId}`)
            const data = res.data

            if (!data.success) {
              clearInterval(poll)
              resolve({ success: false, message: data.message || '查询进度失败' })
              return
            }

            // 更新进度 UI
            const stageMap = { parsing: 'upload', chunking: 'ingest', embedding: 'ingest', storing: 'ingest', done: 'ingest' }
            this.uploadProgress.stage = stageMap[data.stage] || 'ingest'
            this.uploadProgress.message = data.message || ''

            // 计算总进度：当前文件的进度映射到整体
            const fileBase = Math.round((fileIndex / totalFiles) * 100)
            const fileShare = Math.round((1 / totalFiles) * 100)
            this.uploadProgress.percent = Math.min(fileBase + Math.round((data.progress / 100) * fileShare), 99)

            if (data.status === 'done') {
              clearInterval(poll)
              this.uploadProgress.percent = Math.round(((fileIndex + 1) / totalFiles) * 100)
              resolve({ success: true, result: data.result })
            } else if (data.status === 'failed') {
              clearInterval(poll)
              resolve({ success: false, message: data.message })
            }
          } catch (err) {
            clearInterval(poll)
            resolve({ success: false, message: '网络错误' })
          }
        }, 1500)
      })
    },
    
    // 切换 RAG 启用状态
    async toggleRagEnabled() {
      const newStatus = !this.ragEnabled
      
      try {
        this.ragLoading = true
        const response = await this.$axios.post('/api/rag/toggle', {
          enabled: newStatus
        })
        
        if (response.data.success) {
          this.ragEnabled = newStatus
          this.$message.success(newStatus ? 'RAG 已启用' : 'RAG 已禁用')
        }
      } catch (error) {
        // 开发环境模拟成功
        this.ragEnabled = newStatus
        this.$message.success(newStatus ? 'RAG 已启用（模拟）' : 'RAG 已禁用（模拟）')
      } finally {
        this.ragLoading = false
      }
    },
    
    async confirmExitApp() {
      try {
        await this.$confirm(
          '确定要退出百佑 LawyerClaw 吗？服务器将停止运行。',
          '退出应用',
          {
            confirmButtonText: '确定退出',
            cancelButtonText: '取消',
            type: 'warning'
          }
        )
        try {
          await this.$axios.post('/api/shutdown')
          this.$message.success('应用正在关闭...')
          setTimeout(() => {
            document.body.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100vh;background:#f7f5f2;font-family:sans-serif;"><h2 style="color:#031635;">百佑 LawyerClaw 已关闭，您可以关闭此窗口。</h2></div>'
          }, 800)
        } catch (err) {
          this.$message.error('退出失败: ' + (err.message || '网络错误'))
        }
      } catch {
        // 用户取消
      }
    },

    async editNickname() {
      try {
        const { value } = await this.$prompt('请输入昵称', '编辑昵称', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          inputValue: localStorage.getItem('nickname') || '',
          inputPattern: /^.{1,20}$/,
          inputErrorMessage: '昵称长度应在 1-20 个字符之间'
        })
        if (value !== undefined) {
          const trimmed = value.trim()
          localStorage.setItem('nickname', trimmed)
          this.$message.success('昵称已更新')
          window.dispatchEvent(new CustomEvent('lawyerclaw:nickname-change', {
            detail: { nickname: trimmed }
          }))
        }
      } catch {
        // 用户取消
      }
    }
  },
}
</script>

<style scoped>
.settings-view {
  display: flex;
  padding: 32px;
  width: 100%;
  background: #F7F5F2;
  min-height: 100%;
  height: 100%;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}

.settings-layout {
  display: grid;
  grid-template-columns: 1.8fr 0.9fr;  /* 缩窄卡片 */
  gap: 60px;  /* 进一步增大左右间距 */
  width: 100%;
  max-width: 1600px;
  margin: 0 auto;
}

.settings-content {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

/* 设置标题样式 */
.settings-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--primary);
  margin-bottom: 24px;
}

/* 用户侧边栏 - 与左侧第一个卡片顶部对齐 */
.user-sidebar {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 32px;  /* 增加上下卡片间距 */
  /* 计算偏移量：设置标题高度 + 标题下边距 ≈ 50px */
  margin-top: 50px;  /* 关键：下移以对齐左侧第一个卡片 */
}

.settings-section {
  background: #FFFFFF;
  border-radius: 12px;
  padding: 40px 35px;  /* 增加上下内边距 */
  margin-bottom: 20px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  transition: transform 0.3s, box-shadow 0.3s;
  min-height: 220px;  /* 增加最小高度 */
  min-width: 0;
  width: 100%;
  box-sizing: border-box;
  overflow: hidden;
}

.settings-section:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
}

/* 第一个设置卡片与右侧用户信息卡片顶部对齐 */
.settings-section:first-child {
  margin-top: 0;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--primary);
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 2px solid var(--surface-container-high);
}

.setting-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 0;
  min-width: 0;
}

.setting-row + .setting-row {
  border-top: 1px solid var(--surface-container-low);
}

.setting-label {
  width: 120px;
  flex-shrink: 0;
  font-size: 14px;
  color: var(--on-surface-variant);
  font-weight: 500;
}

.setting-value {
  font-size: 14px;
  color: var(--on-surface);
}

.setting-value.mono {
  font-family: 'SF Mono', 'Cascadia Code', monospace;
  font-size: 12px;
}

.setting-hint {
  font-size: 12px;
  color: var(--on-surface-variant);
  margin-top: 12px;
  padding: 8px 12px;
  background: var(--surface-container-low);
  border-radius: var(--radius);
}

/* ⭐ 开关切换 */
.setting-switch {
  position: relative;
  display: inline-block;
  width: 44px;
  height: 24px;
  flex-shrink: 0;
}

.setting-switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.switch-slider {
  position: absolute;
  cursor: pointer;
  top: 0; left: 0; right: 0; bottom: 0;
  background: #D5CEC4;
  border-radius: 12px;
  transition: 0.3s;
}

.switch-slider:before {
  position: absolute;
  content: "";
  height: 18px;
  width: 18px;
  left: 3px;
  bottom: 3px;
  background: white;
  border-radius: 50%;
  transition: 0.3s;
  box-shadow: 0 1px 3px rgba(0,0,0,0.15);
}

.setting-switch input:checked + .switch-slider {
  background: #52c41a;
}

.setting-switch input:checked + .switch-slider:before {
  transform: translateX(20px);
}

/* ⭐ 润色子区域 */
.setting-sub {
  margin-top: 12px;
  padding: 12px;
  background: var(--surface-container-low);
  border-radius: var(--radius);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.setting-input {
  flex: 1;
  min-width: 0;
  max-width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--outline-variant);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--on-surface);
  font-size: 14px;
  font-family: inherit;
  outline: none;
  transition: border-color 0.2s;
}

.setting-input:focus {
  border-color: var(--primary);
}

.setting-slider {
  flex: 1;
  accent-color: var(--primary);
  height: 4px;
}

.setting-select {
  flex: 1;
  min-width: 0;
  max-width: 100%;
  padding: 8px 12px;
  background: var(--surface);
  border: none;
  border-radius: var(--radius);
  font-family: var(--font-family);
  font-size: 14px;
  color: var(--on-surface);
}

.settings-actions {
  display: flex;
  gap: 12px;
  padding: 8px 0;
}

.btn-save {
  padding: 10px 24px;
  background: linear-gradient(135deg, var(--primary), var(--primary-container));
  color: var(--on-primary);
  border: none;
  border-radius: var(--radius);
  font-family: var(--font-family);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: opacity 0.2s;
}

.btn-save:hover {
  opacity: 0.9;
}

.btn-reset {
  padding: 10px 24px;
  background: var(--surface-container-high);
  color: var(--on-surface);
  border: none;
  border-radius: var(--radius);
  font-family: var(--font-family);
  font-size: 14px;
  cursor: pointer;
  transition: background 0.15s;
}

.btn-reset:hover {
  background: var(--surface-container-highest);
}

/* 用户信息侧边栏*/
.user-sidebar {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 24px;
  align-self: start;  /* 顶部对齐 */
}

.user-card {
  background: #FFFFFF;
  border-radius: 12px;
  padding: 45px 30px;  /* 增加上下内边距 */
  box-shadow: 0 2px 12px rgba(0,0,0,0.08);
  text-align: center;
  transition: transform 0.3s, box-shadow 0.3s;
  min-height: 300px;  /* 增加最小高度 */
}

.user-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0,0,0,0.12);
}

.user-logged-section {
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.user-avatar {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--primary), var(--primary-container));
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 36px;
  font-weight: bold;
  margin: 0 auto 20px;
}

.user-name {
  font-size: 20px;
  font-weight: 700;
  color: var(--on-surface);
  margin: 0 0 8px;
}

.user-email {
  font-size: 14px;
  color: var(--on-surface-variant);
  margin: 0 0 24px;
  word-break: break-all;
}

.user-hint {
  font-size: 13px;
  color: var(--on-surface-variant);
  margin-bottom: 16px;
}

.user-stats {
  display: flex;
  justify-content: space-around;
  margin-bottom: 24px;
  padding: 20px;
  background: var(--surface-container-low);
  border-radius: var(--radius);
}

.stat-item {
  text-align: center;
}

.stat-value {
  display: block;
  font-size: 24px;
  font-weight: bold;
  color: var(--primary);
  margin-bottom: 4px;
}

.stat-label {
  font-size: 12px;
  color: var(--on-surface-variant);
}

.user-status {
  margin-bottom: 20px;
}

.user-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}

/* 覆盖 Element UI 按钮默认颜色 */
.user-sidebar .el-button.el-button--primary {
  background: linear-gradient(135deg, var(--primary), var(--primary-container)) !important;
  border: none !important;
  color: var(--on-primary) !important;
}

.user-sidebar .el-button.el-button--primary:hover {
  opacity: 0.9;
}

.user-sidebar .el-button.el-button--danger {
  background: var(--error-container) !important;
  border: none !important;
  color: #c62828 !important;
}

.user-sidebar .el-button.el-button--danger:hover {
  background: #ffcdd2 !important;
}

[data-theme='dark'] .user-sidebar .el-button.el-button--danger:hover {
  background: #ffcdd2 !important;
}

/* RAG 卡片深色模式 */
[data-theme='dark'] .rag-card {
  background: var(--surface-container-lowest);
  box-shadow: var(--shadow-sm);
}

[data-theme='dark'] .rag-card-header {
  border-bottom-color: var(--divider);
}

[data-theme='dark'] .rag-card-title {
  color: var(--primary);
}

[data-theme='dark'] .rag-stat {
  background: var(--surface-container-high);
}

[data-theme='dark'] .rag-stat-value {
  color: var(--primary);
}

[data-theme='dark'] .rag-stat-label {
  color: var(--on-surface-variant);
}

[data-theme='dark'] .rag-card-hint {
  color: var(--on-surface-variant);
}

/* 响应式布局 */
@media (max-width: 1200px) {
  .settings-layout {
    grid-template-columns: 1fr;
  }
  
  .user-sidebar {
    width: 100%;
  }
}

@media (max-width: 900px) {
  .settings-view {
    flex-direction: column;
    padding: 16px;
  }
  
  .settings-layout {
    grid-template-columns: 1fr;
  }
  
  .settings-content {
    max-width: 100%;
  }
  
  .user-sidebar {
    width: 100%;
  }
}

/* RAG 知识库卡片样式 */
.rag-card {
  background: #FFFFFF;
  border-radius: 12px;
  padding: 40px 30px;  /* 增加上下内边距 */
  box-shadow: 0 2px 12px rgba(0,0,0,0.08);
  animation: fadeIn 0.3s ease;
  transition: transform 0.3s, box-shadow 0.3s;
  min-height: 260px;  /* 增加最小高度 */
}

.rag-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0,0,0,0.12);
}

.rag-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--surface-container-high);
}

.rag-card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--primary);
  margin: 0;
}

.rag-card-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.rag-stat {
  display: flex;
  justify-content: space-around;
  padding: 16px;
  background: var(--surface-container-low);
  border-radius: var(--radius);
}

.rag-stat-item {
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.rag-stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--primary);
}

.rag-stat-label {
  font-size: 12px;
  color: var(--on-surface-variant);
}

.rag-card-hint {
  font-size: 12px;
  color: var(--on-surface-variant);
  text-align: center;
  margin: 0;
}

.rag-card-actions {
  display: flex;
  gap: 8px;
}

.rag-card-actions .el-button {
  flex: 1;
}

/* RAG 管理弹窗 */
.rag-dialog-section {
  margin-bottom: 24px;
}

.rag-dialog-subtitle {
  font-size: 14px;
  font-weight: 600;
  color: var(--on-surface);
  margin: 0 0 12px 0;
}

.rag-empty {
  text-align: center;
  color: var(--on-surface-variant);
  font-size: 13px;
  padding: 20px;
  background: var(--surface-container-low);
  border-radius: var(--radius);
}

.rag-collection-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 200px;
  overflow-y: auto;
}

.rag-collection-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-radius: var(--radius);
  border: 1px solid var(--outline-variant);
  cursor: pointer;
  transition: all 0.15s;
}

.rag-collection-item:hover {
  background: var(--surface-container-low);
}

.rag-collection-item.active {
  border-color: var(--primary);
  background: color-mix(in srgb, var(--primary) 8%, transparent);
}

.rag-col-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.rag-col-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--on-surface);
}

.rag-col-count {
  font-size: 12px;
  color: var(--on-surface-variant);
}

.rag-col-delete {
  color: var(--error) !important;
  opacity: 0;
  transition: opacity 0.15s;
}

.rag-collection-item:hover .rag-col-delete {
  opacity: 1;
}

.rag-upload-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.rag-upload-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.rag-upload-label {
  font-size: 13px;
  color: var(--on-surface);
  white-space: nowrap;
  min-width: 80px;
}

.rag-upload-area {
  border-radius: var(--radius);
}

.rag-upload-progress {
  padding: 16px;
  background: var(--surface-container-low);
  border-radius: var(--radius);
  margin-top: 8px;
}

.rag-upload-progress p {
  font-size: 13px;
  color: var(--on-surface-variant);
  margin: 0 0 8px 0;
}

/* 退出应用卡片 */
.exit-card {
  background: #FFFFFF;
  border-radius: 12px;
  padding: 30px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.08);
  transition: transform 0.3s, box-shadow 0.3s;
  border-left: 3px solid #c62828;
}

.exit-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0,0,0,0.12);
}

.exit-card-header {
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--surface-container-high);
}

.exit-card-title {
  font-size: 16px;
  font-weight: 600;
  color: #c62828;
  margin: 0;
}

.exit-card-content {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.exit-card-hint {
  font-size: 13px;
  color: var(--on-surface-variant);
  margin: 0;
  line-height: 1.5;
}

.btn-exit-app {
  width: 100%;
  padding: 10px 20px;
  background: #c62828;
  color: white;
  border: none;
  border-radius: var(--radius);
  font-family: var(--font-family);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-exit-app:hover {
  background: #b71c1c;
}

[data-theme='dark'] .exit-card {
  background: var(--surface-container-lowest);
  box-shadow: var(--shadow-sm);
}

[data-theme='dark'] .exit-card-header {
  border-bottom-color: var(--divider);
}

/* ⭐ 自定义模型配置样式 */
.provider-form {
  margin-bottom: 24px;
  padding: 20px;
  background: var(--surface-container-low);
  border-radius: 8px;
  min-width: 0;
  width: 100%;
  box-sizing: border-box;
}

.form-actions {
  display: flex;
  gap: 12px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--surface-container-high);
  flex-wrap: wrap;
}

.btn-test, .btn-save-provider, .btn-cancel {
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-test {
  background: #e3f2fd;
  color: #1976d2;
}
.btn-test:hover { background: #bbdefb; }

.btn-save-provider {
  background: linear-gradient(135deg, var(--primary), var(--primary-container));
  color: white;
}
.btn-save-provider:hover { opacity: 0.9; }

.btn-cancel {
  background: var(--surface-container-high);
  color: var(--on-surface);
}
.btn-cancel:hover { background: var(--surface-container-highest); }

.provider-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.provider-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  background: var(--surface-container-low);
  border-radius: 8px;
  border: 2px solid transparent;
  transition: all 0.2s;
}

.provider-item:hover {
  background: var(--surface-container);
}

.provider-item.active {
  border-color: var(--primary);
  background: var(--surface-container-lowest);
}

.provider-info {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
}

.provider-name {
  font-weight: 600;
  color: var(--on-surface);
  font-size: 14px;
}

.provider-protocol {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--primary-container);
  color: var(--on-primary-container);
}

.provider-model {
  font-size: 12px;
  color: var(--on-surface-variant);
  font-family: 'SF Mono', 'Cascadia Code', monospace;
}

.provider-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.setting-input {
  flex: 1;
  min-width: 0;
  max-width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--outline);
  border-radius: 6px;
  font-size: 14px;
  background: var(--surface);
  color: var(--on-surface);
  transition: border-color 0.2s;
}

.setting-input:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 2px rgba(var(--primary-rgb), 0.1);
}

/* ⭐ 技能列表样式 */
.skills-loading {
  text-align: center;
  padding: 40px;
  color: var(--on-surface-variant);
  font-size: 14px;
}

.skills-empty {
  text-align: center;
  padding: 40px;
  color: var(--on-surface-variant);
  font-size: 14px;
}

.skills-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 520px;
  overflow-y: auto;
  padding-right: 8px;
}

.skills-grid::-webkit-scrollbar {
  width: 6px;
}

.skills-grid::-webkit-scrollbar-thumb {
  background: var(--outline-variant);
  border-radius: 3px;
}

.skills-grid::-webkit-scrollbar-thumb:hover {
  background: var(--on-surface-variant);
}

.skill-card {
  background: var(--surface-container-low);
  border-radius: 10px;
  padding: 14px 18px;
  border: 1px solid var(--surface-container-high);
  transition: all 0.2s;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.skill-card:hover {
  background: var(--surface-container);
  border-color: var(--primary);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.skill-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.skill-name {
  font-weight: 600;
  font-size: 14px;
  color: var(--on-surface);
}

.skill-desc {
  font-size: 13px;
  color: var(--on-surface-variant);
  margin: 0;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.skill-footer {
  display: flex;
  justify-content: flex-end;
}

.skill-status {
  font-size: 12px;
  color: var(--on-surface-variant);
}

.skill-status.active {
  color: #4caf50;
}

</style>

<style>
@import '@/styles/upload-progress.css';
</style>