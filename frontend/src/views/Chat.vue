<template>
  <div class="chat-view">
    <!-- 空状态 -->
    <div v-if="messages.length === 0 && !isLoading" class="empty-state">
      <div class="empty-content">
        <div class="empty-header">
          <img :src="`${publicPath}logo.png`" class="empty-logo" alt="百佑 LawyerClaw">
          <h1 class="empty-title">百佑 LawyerClaw</h1>
        </div>
        <p class="empty-subtitle">您的智能法律助手</p>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="isLoading && !isSwitchingSession" class="loading-state">
      <div class="loading-spinner"></div>
      <p class="loading-text">正在加载...</p>
    </div>

    <!-- 消息列表 -->
    <div v-if="messages.length > 0 || (isSwitchingSession && previousMessages.length > 0)" class="messages" ref="messageArea">
      <!-- ✅ 切换期间显示之前的消息 -->
      <template v-if="isSwitchingSession && previousMessages.length > 0">
        <div v-for="(msg, index) in previousMessages" :key="'prev-' + index" :class="['msg', msg.role]">
          <div v-if="msg.role === 'assistant'" class="msg ai">
            <div class="bubble-ai">
              <div class="ai-label"><span>百佑 LawyerClaw</span></div>
              <div v-if="msg.content" v-html="renderMarkdown(msg.content)"></div>
            </div>
          </div>
          <div v-else class="msg user">
            <div class="message-content">
              <div class="message-bubble">
                <div v-if="msg.content" v-html="renderMarkdown(msg.content)"></div>
                <div v-if="msg.attachments && msg.attachments.length > 0" class="attachments-list">
                  <div v-for="(file, fIdx) in msg.attachments" :key="fIdx" class="attachment-item">
                    <span class="attachment-name">{{ getFileName(file) }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>
      
      <!-- ✅ 正常显示当前消息 -->
      <template v-else>
        <div v-for="(msg, index) in messages" :key="index" :class="['msg', msg.role]">
        
        <!-- AI 消息 -->
        <div v-if="msg.role === 'assistant'" class="msg ai">
          <div class="bubble-ai">
            <div class="ai-label">
              <span>百佑 LawyerClaw</span>
            </div>
            
            <!-- 加载状态 -->
            <div v-if="msg.loading" class="loading-dots">
              <span></span><span></span><span></span>
            </div>
            
            <!-- 错误状态 -->
            <div v-else-if="msg.error" class="error-text">{{ msg.error }}</div>
            
            <!-- 消息内容 -->
            <div v-else-if="msg.content" v-html="renderMarkdown(msg.content)"></div>
            
            <!-- ✅ 新增：工具调用状态显示 -->
            <div v-if="msg.toolStatus && msg.toolStatus.length > 0" class="tool-status">
              <div 
                v-for="(tool, index) in msg.toolStatus" 
                :key="index" 
                :class="['tool-item', tool.status]"
              >
                <span class="tool-icon">
                  <span v-if="tool.status === 'running'">⚙️</span>
                  <span v-else-if="tool.status === 'success'">✅</span>
                  <span v-else-if="tool.status === 'error'">❌</span>
                </span>
                <span class="tool-name">{{ tool.tool_name }}</span>
                <span v-if="tool.status === 'running'" class="tool-running">正在执行...</span>
                <span v-else-if="tool.status === 'success'" class="tool-success">{{ tool.elapsed_ms }}ms</span>
                <span v-else-if="tool.status === 'error'" class="tool-error">{{ tool.error }}</span>
              </div>
            </div>
            
            <!-- ✅ 新增：技能使用卡片 -->
            <div v-if="msg.skills_used && msg.skills_used.length > 0" class="skills-card">
              <div class="skills-card-header">
                <span class="skills-icon">🎯</span>
                <span class="skills-title">使用的技能</span>
              </div>
              <div class="skills-list">
                <div 
                  v-for="(skill, index) in msg.skills_used" 
                  :key="index" 
                  class="skill-tag"
                  :title="getSkillDescription(skill)"
                >
                  <span class="skill-icon">📚</span>
                  <span class="skill-name">{{ formatSkillName(skill) }}</span>
                </div>
              </div>
            </div>
            
            <!-- 操作按钮 -->
            <div v-if="!msg.loading && !msg.error && msg.content" class="actions">
              <button @click="copyMessage(msg.content)">
                <i class="icon-copy"></i>复制
              </button>
              <button>
                <i class="icon-bookmark"></i>收藏
              </button>
              <span
                v-if="msg.rag_status"
                class="rag-tag"
                :class="[
                  msg.rag_status.success && msg.rag_status.results && msg.rag_status.results.length ? 'rag-tag-on rag-tag-clickable' :
                  msg.rag_status.triggered ? 'rag-tag-triggered' : 'rag-tag-off'
                ]"
                @click="msg.rag_status.success && msg.rag_status.results && msg.rag_status.results.length ? showRagDetail(msg.rag_status) : null"
              >RAG {{ msg.rag_status.success && msg.rag_status.results_count ? '· ' + msg.rag_status.results_count + '条' : '' }}</span>
            </div>
          </div>
          <span class="time">{{ formatMsgTime(msg.created_at) }}</span>
        </div>

        <!-- 用户消息 -->
        <div v-else class="msg user">
          <div class="message-content">
            <div class="message-bubble">
              <div v-if="msg.content" v-html="renderMarkdown(msg.content)"></div>
              <div v-if="msg.attachments && msg.attachments.length > 0" class="attachments-list">
                <div v-for="(file, fIdx) in msg.attachments" :key="fIdx" class="attachment-item">
                  <span class="attachment-name">{{ getFileName(file) }}</span>
                </div>
              </div>
            </div>
            <div class="message-time">{{ formatMsgTime(msg.created_at) }}</div>
          </div>
        </div>
        
        </div>
      </template>
    </div>

    <!-- 输入区域 -->
    <div class="input-area">
      <div v-if="showSaveToKbButton" class="save-to-kb-bar">
        <span class="save-to-kb-info">已选择 {{ selectedFileCount }} 个文件</span>
        <div class="save-to-kb-actions">
          <button class="save-to-kb-btn" @click="openSaveToStyleDialog">💡 存入风格库</button>
          <button class="save-to-kb-btn" @click="openSaveToKbDialog">📚 存入知识库</button>
        </div>
      </div>
      <div class="input-row">
        <!-- ⭐ 灯泡按钮：控制自动润色（在白框外面） -->
        <el-popover
          placement="top"
          width="220"
          trigger="manual"
          v-model="stylePopoverVisible"
          popper-class="style-popover"
        >
          <div class="style-popover-content">
            <div class="style-popover-header">
              <span>选择润色风格</span>
              <button class="style-popover-close" @click="stylePopoverVisible = false"><i class="el-icon-close"></i></button>
            </div>
            <div v-if="styleProfiles.length === 0" class="style-popover-empty">
              暂无风格，请先存入风格库
            </div>
            <div v-else class="style-popover-list">
              <div
                v-for="p in styleProfiles"
                :key="p.name"
                class="style-popover-item"
                :class="{ active: autoPolishStyle === p.name }"
                @click="selectPolishStyle(p.name)"
              >
                <span class="style-popover-name">{{ p.name }}</span>
                <i v-if="autoPolishStyle === p.name" class="el-icon-check"></i>
              </div>
              <div v-if="autoPolish" class="style-popover-divider"></div>
              <div v-if="autoPolish" class="style-popover-item style-popover-off" @click="turnOffPolish">
                <span>关闭润色</span>
              </div>
            </div>
          </div>
          <button
            slot="reference"
            class="polish-toggle-btn"
            :class="{ active: autoPolish }"
            @click="handlePolishBtnClick"
            :title="autoPolish ? '点击关闭润色或切换风格' : '点击选择润色风格'"
          >
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M9 18h6"/>
              <path d="M10 22h4"/>
              <path d="M12 2a7 7 0 0 1 4 12.9V17a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1v-2.1A7 7 0 0 1 12 2z"/>
            </svg>
          </button>
        </el-popover>
        <!-- 输入框白框 -->
        <div class="input-box">
          <textarea
            v-model="inputText"
            @keydown="handleKeydown"
            :placeholder="currentSessionTitle ? '描述您的问题' : '请先选择或创建会话'"
            :disabled="!currentSessionTitle"
            class="input-field"
            rows="1"
          ></textarea>
        </div>
        <!-- ⭐ 发送按钮 -->
        <button 
          @click="send" 
          :disabled="!inputText.trim() || !currentSessionTitle || isLoading"
          class="send-btn"
        >
          <i class="icon-send"></i>
        </button>
      </div>
    </div>

    <!-- RAG 法条详情弹窗 -->
    <div v-if="ragModalVisible" class="rag-modal-overlay" @click.self="ragModalVisible = false">
      <div class="rag-modal">
        <div class="rag-modal-header">
          <span class="rag-modal-icon">📚</span>
          <span class="rag-modal-title">RAG 检索结果</span>
          <span class="rag-modal-count">{{ ragModalData.results_count || 0 }} 条命中</span>
          <button class="rag-modal-close" @click="ragModalVisible = false">&times;</button>
        </div>
        <div class="rag-modal-body">
          <div
            v-for="(item, idx) in (ragModalData.results || [])"
            :key="idx"
            class="rag-result-card"
          >
            <div class="rag-result-header">
              <span class="rag-result-title">{{ item.title || '未知法条' }}</span>
              <span class="rag-result-score">{{ (item.score * 100).toFixed(1) }}%</span>
            </div>
            <div class="rag-result-score-bar">
              <div class="rag-result-score-fill" :style="{ width: (item.score * 100) + '%' }"></div>
            </div>
            <div class="rag-result-meta">
              <span v-if="item.category" class="rag-result-category">{{ item.category }}</span>
              <span v-if="item.collection" class="rag-result-collection">{{ item.collection }}</span>
            </div>
            <div class="rag-result-content">{{ item.content }}</div>
          </div>
          <div v-if="!ragModalData.results || ragModalData.results.length === 0" class="rag-empty">
            暂无检索结果详情
          </div>
        </div>
      </div>
    </div>

    <!-- 存入知识库弹窗 -->
    <el-dialog :visible.sync="saveToKbDialogVisible" :show-close="false" width="520px" :close-on-click-modal="false">
      <div slot="title" class="dialog-custom-header">
        <span>📚 存入知识库</span>
        <div class="dialog-header-actions">
          <button
            v-if="saveToKbProgress.active || saveToKbProgress.status"
            class="dialog-header-btn"
            @click="minimizeSaveToKb"
            title="最小化"
          ><i class="el-icon-minus"></i></button>
          <button class="dialog-header-btn" @click="closeSaveToKbDialog" title="关闭"><i class="el-icon-close"></i></button>
        </div>
      </div>

      <!-- 初始确认界面 -->
      <div v-if="!saveToKbProgress.active && !saveToKbProgress.status" style="padding: 8px 0;">
        <p style="margin: 0 0 12px 0; font-size: 14px; color: #3A3530;">
          将选中的 <strong>{{ selectedFileCount }}</strong> 个文件存入知识库
        </p>
        <div>
          <label style="font-size: 13px; color: #6B6156; display: block; margin-bottom: 6px;">目标知识库</label>
          <el-input :value="saveToKbCollection" @input="v => $store.commit('UPDATE_INGEST_TASK', { collection: v })" placeholder="输入 collection 名称（默认 legal_default）" size="small" />
          <p style="margin: 6px 0 0 0; font-size: 12px; color: #A09888;">支持格式：PDF、Word、TXT</p>
        </div>
      </div>

      <!-- 进度面板 -->
      <div v-else class="save-to-kb-progress-panel">
        <!-- 阶段指示器 -->
        <div class="upload-stages">
          <div class="upload-stage" :class="{ active: saveToKbProgress.stage === 'upload', done: saveToKbProgress.stage === 'ingest' || saveToKbProgress.status === 'success' }">
            <div class="stage-dot">
              <i :class="saveToKbProgress.stage === 'upload' ? 'el-icon-loading' : 'el-icon-circle-check'"></i>
            </div>
            <span>提交文件</span>
          </div>
          <div class="upload-stage-line" :class="{ done: saveToKbProgress.stage === 'ingest' || saveToKbProgress.status === 'success' }"></div>
          <div class="upload-stage" :class="{ active: saveToKbProgress.stage === 'ingest', done: saveToKbProgress.status === 'success' }">
            <div class="stage-dot">
              <i :class="saveToKbProgress.stage === 'ingest' ? 'el-icon-loading' : (saveToKbProgress.status === 'success' ? 'el-icon-circle-check' : 'el-icon-document')"></i>
            </div>
            <span>解析入库</span>
          </div>
        </div>

        <!-- 总进度条 -->
        <el-progress
          class="upload-progress-custom"
          :percentage="saveToKbProgress.percent"
          :status="saveToKbProgress.status || undefined"
          :stroke-width="20"
        />
        <p class="upload-progress-msg">{{ saveToKbProgress.message }}</p>

        <!-- 逐文件状态列表 -->
        <div class="upload-file-status-list" v-if="saveToKbFileStatus.length > 0">
          <div
            v-for="item in saveToKbFileStatus"
            :key="item.taskId"
            class="upload-file-status-item"
            :class="item.state"
          >
            <i :class="fileStatusIcon(item.state)"></i>
            <span class="file-name" :title="item.name">{{ item.name }}</span>
            <span class="file-state-text">{{ fileStateText(item.state) }}</span>
          </div>
        </div>
      </div>

      <span slot="footer">
        <el-button v-if="!saveToKbProgress.active && !saveToKbProgress.status" @click="saveToKbDialogVisible = false" size="small">取消</el-button>
        <el-button v-if="!saveToKbProgress.active && !saveToKbProgress.status" type="primary" @click="confirmSaveToKb" :loading="saveToKbLoading" size="small">确认存入</el-button>
        <el-button v-else-if="saveToKbProgress.status" @click="closeSaveToKbDialog" size="small">关闭</el-button>
      </span>
    </el-dialog>

    <!-- ⭐ 存入风格库弹窗 -->
    <el-dialog :visible.sync="saveToStyleDialogVisible" :show-close="false" width="520px" :close-on-click-modal="false">
      <div slot="title" class="dialog-custom-header">
        <span>💡 存入风格库</span>
        <div class="dialog-header-actions">
          <button
            v-if="saveToStyleProgress.active || saveToStyleProgress.status"
            class="dialog-header-btn"
            @click="minimizeSaveToStyle"
            title="最小化"
          ><i class="el-icon-minus"></i></button>
          <button class="dialog-header-btn" @click="closeSaveToStyleDialog" title="关闭"><i class="el-icon-close"></i></button>
        </div>
      </div>

      <!-- 初始确认界面 -->
      <div v-if="!saveToStyleProgress.active && !saveToStyleProgress.status" style="padding: 8px 0;">
        <p style="margin: 0 0 12px 0; font-size: 14px; color: #3A3530;">
          将选中的 <strong>{{ selectedFileCount }}</strong> 个文件分析并生成个人写作风格
        </p>
        
        <!-- 风格选择 -->
        <div style="margin-bottom: 12px;">
          <label style="font-size: 13px; color: #6B6156; display: block; margin-bottom: 6px;">选择风格</label>
          <el-select v-model="saveToStyleMode" style="width: 100%;" size="small" @change="onStyleModeChange">
            <el-option label="新建风格" value="new"></el-option>
            <el-option
              v-for="p in styleProfiles"
              :key="p.name"
              :label="p.name + (p.favorite_words && p.favorite_words.length ? '（' + p.favorite_words.slice(0, 3).join(', ') + '）' : '')"
              :value="p.name"
            ></el-option>
          </el-select>
        </div>
        
        <!-- 风格名称输入（新建时显示） -->
        <div v-if="saveToStyleMode === 'new'" style="margin-bottom: 8px;">
          <label style="font-size: 13px; color: #6B6156; display: block; margin-bottom: 6px;">风格名称</label>
          <el-input v-model="saveToStyleName" placeholder="输入风格名称" size="small" />
        </div>

        <!-- 合并提示（选择已有风格时显示） -->
        <div v-else style="margin-bottom: 8px;">
          <p style="margin: 0; font-size: 12px; color: #67c23a;">
            ✓ 将分析结果合并到「{{ saveToStyleMode }}」，保留原有风格特征
          </p>
        </div>
        
        <p style="margin: 6px 0 0 0; font-size: 12px; color: #A09888;">支持格式：PDF、Word、TXT（纯文本分析）</p>
      </div>

      <!-- 进度面板 -->
      <div v-else class="save-to-kb-progress-panel">
        <!-- 阶段指示器 -->
        <div class="upload-stages">
          <div class="upload-stage" :class="{ active: saveToStyleProgress.stage === 'parse', done: saveToStyleProgress.stage === 'analyze' || saveToStyleProgress.status === 'success' }">
            <div class="stage-dot">
              <i :class="saveToStyleProgress.stage === 'parse' ? 'el-icon-loading' : 'el-icon-circle-check'"></i>
            </div>
            <span>解析文件</span>
          </div>
          <div class="upload-stage-line" :class="{ done: saveToStyleProgress.stage === 'analyze' || saveToStyleProgress.status === 'success' }"></div>
          <div class="upload-stage" :class="{ active: saveToStyleProgress.stage === 'analyze', done: saveToStyleProgress.status === 'success' }">
            <div class="stage-dot">
              <i :class="saveToStyleProgress.stage === 'analyze' ? 'el-icon-loading' : (saveToStyleProgress.status === 'success' ? 'el-icon-circle-check' : 'el-icon-document')"></i>
            </div>
            <span>分析风格</span>
          </div>
        </div>

        <!-- 总进度条 -->
        <el-progress
          class="upload-progress-custom"
          :percentage="saveToStyleProgress.percent"
          :status="saveToStyleProgress.status || undefined"
          :stroke-width="20"
        />
        <p class="upload-progress-msg">{{ saveToStyleProgress.message }}</p>

        <!-- 逐文件状态列表 -->
        <div class="upload-file-status-list" v-if="saveToStyleFileStatus.length > 0">
          <div
            v-for="item in saveToStyleFileStatus"
            :key="item.name"
            class="upload-file-status-item"
            :class="item.state"
          >
            <i :class="fileStatusIcon(item.state)"></i>
            <span class="file-name" :title="item.name">{{ item.name }}</span>
            <span class="file-state-text">{{ fileStateText(item.state) }}</span>
          </div>
        </div>
      </div>

      <span slot="footer">
        <el-button v-if="!saveToStyleProgress.active && !saveToStyleProgress.status" @click="closeSaveToStyleDialog" size="small">取消</el-button>
        <el-button v-if="!saveToStyleProgress.active && !saveToStyleProgress.status" type="primary" @click="confirmSaveToStyle" :loading="saveToStyleLoading" size="small">确认存入</el-button>
        <el-button v-else-if="saveToStyleProgress.status" @click="closeSaveToStyleDialog" size="small">关闭</el-button>
      </span>
    </el-dialog>

  </div>
</template>

<script>
import { mapState, mapActions } from 'vuex'
import { sendMessageStream } from '@/api/chat'
import MarkdownIt from 'markdown-it'

const md = new MarkdownIt({
  breaks: true,
  linkify: true,
  typographer: true
})

export default {
  name: 'ChatView',
  data() {
    return {
      inputText: '',
      isLoading: false,
      loadingSessions: false,
      isSending: false,
      isSwitchingSession: false,  // ✅ 新增：会话切换状态
      previousMessages: [],        // ✅ 新增：保存之前的消息
      ragModalVisible: false,      // RAG 弹窗显示状态
      ragModalData: {},            // RAG 弹窗数据
      saveToKbLoading: false,
      
      // ⭐ 存入风格库相关
      saveToStyleDialogVisible: false,
      saveToStyleLoading: false,
      saveToStyleName: '',
      saveToStyleProgress: { active: false, percent: 0, message: '', status: '', stage: '' },
      saveToStyleFileStatus: [],
      saveToStyleMode: 'new',  // 'new' | 已有风格名
      saveToStyleMergeTarget: '',  // 合并目标风格名
      styleProfiles: [],       // 已存在的风格列表
      styleProfilesLoading: false,
      stylePopoverVisible: false,  // 灯泡按钮风格选择弹窗
    }
  },
  computed: {
    ...mapState('chat', ['messages']),
    ...mapState('sessions', ['currentId', 'sessions']),
    ...mapState('settings', ['autoPolish', 'autoPolishStyle', 'autoPolishIntensity']),
    publicPath() {
      return process.env.BASE_URL || '/'
    },
    currentSessionTitle() {
      if (!this.currentId) return null
      const sessions = this.sessions || []
      const session = sessions.find(s => s.id === this.currentId)
      return session?.title || '新会话'
    },
    selectedFileCount() {
      return this.$parent.selectedFileCount || 0
    },
    showSaveToKbButton() {
      // 只在非用户中心页面且选中了文件时显示
      return this.selectedFileCount > 0 && this.$route.path !== '/user'
    },
    ingestTask() {
      return this.$store.state.ingestTask
    },
    saveToKbDialogVisible: {
      get() {
        const task = this.$store.state.ingestTask
        return task ? (task.visible && !task.minimized) : false
      },
      set(val) {
        this.$store.commit('UPDATE_INGEST_TASK', { visible: val })
      }
    },
    saveToKbCollection() {
      const task = this.$store.state.ingestTask
      return task ? task.collection : 'legal_default'
    },
    saveToKbProgress() {
      const task = this.$store.state.ingestTask
      return task ? task.progress : { active: false, percent: 0, message: '', status: '', stage: '' }
    },
    saveToKbFileStatus() {
      const task = this.$store.state.ingestTask
      return task ? task.fileStatus : []
    }
  },
  watch: {
    currentId: {
      handler(newId, oldId) {
        if (this.isSending || this.$store.state.chat.streaming) {
          return
        }
        if (newId && newId !== oldId) {
          this.switchSession(newId, oldId)
        }
      },
      immediate: true
    }
  },
  mounted() {
    if (this.currentId) {
      this.loadMessages(this.currentId)
    }
    // ⭐ 加载已存在的风格列表
    this.loadStyleProfiles()
  },
  methods: {
    /**
     * ✅ 优化：会话切换 - 保持原页面直到新会话加载完成
     */
    async switchSession(newId, oldId) {
      
      // 保存当前消息（用于保持显示）
      this.previousMessages = [...this.$store.state.chat.messages]
      this.isSwitchingSession = true
      
      try {
        await this.loadMessages(newId, false)  // 不显示加载状态
      } finally {
        this.isSwitchingSession = false
        this.previousMessages = []  // 清空临时保存
      }
    },
    
    async loadMessages(sessionId, showLoading = true) {
      if (!sessionId) return

      if (sessionId.startsWith('temp_')) {
        this.$store.commit('chat/CLEAR_MESSAGES')
        this.isLoading = false
        return
      }

      // 正在发送消息时，不要从后端加载消息（会覆盖正在流式输出的内容）
      if (this.isSending || this.$store.state.chat.streaming) {
        return
      }
      
      // ✅ 优化：只在非切换状态时显示加载
      if (showLoading) {
        this.isLoading = true
      }
      
      
      try {
        const messages = await this.$store.dispatch('chat/loadSessionMessages', sessionId)
        
        // ✅ 优化：切换到新会话后，滚动到最后一条消息的顶部
        this.$nextTick(() => {
          this.scrollToTopOfLastMessage()
        })
      } finally {
        if (showLoading) {
          this.isLoading = false
        }
      }
    },
    
    /**
     * ⭐ 切换自动润色开关
     */
    toggleAutoPolish() {
      const newVal = !this.autoPolish
      this.$store.dispatch('settings/setAutoPolish', newVal)
    },
    
    async send() {
      if (!this.inputText.trim() || !this.currentId) return
      
      if (this.isSending) {
        return
      }
      
      this.isSending = true
      
      let sessionId = this.currentId
      let content = this.inputText.trim()
      
      const app = this.$parent
      let selectedFiles = []
      if (app && app.$refs && app.$refs.fileExplorer) {
        selectedFiles = app.$refs.fileExplorer.selectedFiles || []
      }
      
      // 构建发送给后端的完整内容（包含文件路径供 LLM 使用）
      let apiContent = content
      if (selectedFiles.length > 0) {
        const filesText = '\n\n📎 附件文件:\n' + selectedFiles.join('\n')
        apiContent = content + filesText
      }

      if (sessionId.startsWith('temp_')) {
        try {
          const realSession = await this.$store.dispatch('sessions/convertTempSession', content)
          if (realSession) {
            sessionId = realSession.id
          }
        } catch (error) {
          this.$message && this.$message.error('创建会话失败')
          this.isSending = false
          return
        }
      }
      
      this.inputText = ''
      
      this.$store.commit('chat/ADD_MESSAGE', {
        role: 'user',
        content,
        attachments: selectedFiles.length > 0 ? [...selectedFiles] : null,
        created_at: new Date().toISOString()
      })
      
      this.$store.commit('chat/ADD_MESSAGE', {
        role: 'assistant',
        content: '',
        loading: true,
        created_at: new Date().toISOString()
      })
      
      this.$store.commit('chat/SET_STREAMING', true)
      this.$nextTick(() => this.scrollToBottom())
      
      let accumulatedContent = ''
      let hasReceivedFullContent = false
      let toolStatus = []  // 工具调用状态
      let renderTimer = null  // 批量渲染定时器
      
      await sendMessageStream(
        sessionId,
        apiContent,
        // onChunk - 内容块回调
        (chunk) => {
          if (chunk.startsWith('[FULL_CONTENT_START]') && chunk.endsWith('[FULL_CONTENT_END]')) {
            const fullContent = chunk.slice(19, -17)
            accumulatedContent = fullContent
            hasReceivedFullContent = true
            
            const msgs = this.$store.state.chat.messages
            const lastMsg = msgs[msgs.length - 1]
            if (lastMsg && lastMsg.role === 'assistant') {
              lastMsg.content = fullContent
              this.$forceUpdate()
              this.$nextTick(() => this.scrollToBottom())
            }
            return
          }
          
          // ✅ 优化：实时追加内容，不使用 hasReceivedFullContent 判断
          accumulatedContent += chunk
          const msgs = this.$store.state.chat.messages
          const lastMsg = msgs[msgs.length - 1]
          if (lastMsg && lastMsg.role === 'assistant') {
            lastMsg.content += chunk
            
            // ✅ 优化：批量渲染（每 50ms 更新一次，避免频繁重绘）
            if (!renderTimer) {
              renderTimer = setTimeout(() => {
                this.$forceUpdate()
                this.$nextTick(() => this.scrollToBottom())
                renderTimer = null
              }, 50)
            }
          }
        },
        // onDone - 完成回调
        () => {
          const msgs = this.$store.state.chat.messages
          const lastMsg = msgs[msgs.length - 1]

          if (!lastMsg) {
            this.$store.commit('chat/SET_STREAMING', false)
            this.isSending = false
            return
          }

          // ⭐ 修复：增加安全兜底 - 如果 content 为空但 accumulatedContent 有内容，直接使用
          if (!lastMsg.content && accumulatedContent) {
            lastMsg.content = accumulatedContent
            this.$forceUpdate()
          }

          if (!lastMsg.content && hasReceivedFullContent) {
            // hasReceivedFullContent 为 true 但 content 为空，强制刷新
            this.$forceUpdate()
          } else if (!lastMsg.content && !hasReceivedFullContent) {
            lastMsg.error = '未收到有效回复，请重试'
          }
          
          if (lastMsg) {
            lastMsg.loading = false
            lastMsg.toolStatus = toolStatus  // 保存工具调用状态
            // ⭐ RAG 状态会在 done 事件的 eventData 中通过 onEvent 回调设置
          }
          
          this.$store.commit('chat/SET_STREAMING', false)
          
          // ✅ 新增：更新会话标题（如果是第一条消息）
          // 注意：使用 this.$store.state.sessions.list 而不是 this.sessions
          const sessionsList = this.$store.state.sessions.list
          const currentSession = sessionsList.find(s => s.id === sessionId)
          if (currentSession && (currentSession.message_count === 1 || currentSession.message_count === 0)) {
            // 提取用户消息的前 50 个字符作为标题
            const title = content.length > 50 ? content.substring(0, 50) + '...' : content
            this.$store.dispatch('sessions/updateSessionTitle', {
              sessionId,
              title
            }).then(() => {
            })
          }
          
          if (selectedFiles.length > 0) {
            this.clearFileSelection()
          }

          // ⭐ 文件工具执行后自动刷新工作空间
          const fileTools = ['write_file', 'python_executor', 'create_directory', 'delete_file', 'patch_file']
          const usedFileTool = toolStatus.some(t => fileTools.includes(t.tool_name) && t.status === 'success')
          if (usedFileTool) {
            const app = this.$parent
            if (app && app.$refs && app.$refs.fileExplorer) {
              app.$refs.fileExplorer.refreshFiles()
            }
          }

          this.isSending = false
        },
        // onError - 错误回调
        (error) => {
          const msgs = this.$store.state.chat.messages
          const lastMsg = msgs[msgs.length - 1]
          if (lastMsg) {
            lastMsg.content = ''
            lastMsg.error = '请求失败：' + error.message
            lastMsg.loading = false
          }
          this.$store.commit('chat/SET_STREAMING', false)
          this.isSending = false
        },
        // ✅ onEvent - 通用事件回调
        (eventType, eventData) => {
          switch (eventType) {
            case 'tool_start':
              toolStatus.push({
                tool_name: eventData.tool_name,
                status: 'running',
                start_time: Date.now()
              })
              this.$forceUpdate()
              break
            
            case 'tool_end':
              const runningTool = toolStatus.find(t => t.tool_name === eventData.tool_name && t.status === 'running')
              if (runningTool) {
                runningTool.status = eventData.success ? 'success' : 'error'
                runningTool.end_time = Date.now()
                runningTool.elapsed_ms = eventData.elapsed_ms
                runningTool.error = eventData.error
              }
              this.$forceUpdate()
              break
            
            case 'file_start':
              break
            
            case 'file_read_end':
              break
            
            // ⭐ 新增：处理 done 事件中的 rag_status
            case 'done':
              const msgsDone = this.$store.state.chat.messages
              const lastMsgDone = msgsDone[msgsDone.length - 1]
              if (lastMsgDone) {
                // ⭐ 总是设置 rag_status，即使为 null（用于显示灰色徽章）
                lastMsgDone.rag_status = eventData.rag_status || {
                  enabled: false,
                  triggered: false,
                  success: false,
                  results_count: 0
                }
                this.$forceUpdate()
              }
              break
          }
        }
      )
      
      this.isSending = false
    },

    clearFileSelection() {
      const app = this.$parent
      if (app && app.$refs && app.$refs.fileExplorer) {
        app.$refs.fileExplorer.clearSelection()
      }
    },
    
    sendQuick(text) {
      this.inputText = text
      this.send()
    },

    handleKeydown(e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        this.send()
      }
    },

    scrollToBottom() {
      const area = this.$refs.messageArea
      if (area) {
        area.scrollTop = area.scrollHeight
      }
    },
    
    /**
     * ✅ 新增：滚动到最后一条消息的顶部
     */
    scrollToTopOfLastMessage() {
      const area = this.$refs.messageArea
      if (!area || !this.messages || this.messages.length === 0) return
      
      this.$nextTick(() => {
        // 获取最后一条消息的元素
        const messageElements = area.querySelectorAll('.msg')
        if (messageElements.length > 0) {
          const lastMsg = messageElements[messageElements.length - 1]
          // 滚动到最后一条消息的顶部位置
          area.scrollTop = lastMsg.offsetTop - area.offsetTop
        }
      })
    },

    renderMarkdown(text) {
      return md.render(text || '')
    },

    formatMsgTime(dateStr) {
      if (!dateStr) return ''
      
      try {
        const d = new Date(dateStr)
        
        // 检查是否是有效日期
        if (isNaN(d.getTime())) {
          return dateStr
        }
        
        // ✅ 修复：统一使用 UTC 时间转换为东八区
        // 无论输入格式如何，都假设存储的是 UTC 时间
        let utcHours, utcMinutes
        
        // 如果是 ISO 格式（包含 T），使用 UTC 方法
        if (dateStr.includes('T')) {
          // ISO 8601 格式：2026-04-20T03:20:00.000Z 或 2026-04-20T03:20:00.000
          utcHours = d.getUTCHours()
          utcMinutes = d.getUTCMinutes()
        } else {
          // 其他格式也使用 UTC 时间
          utcHours = d.getUTCHours()
          utcMinutes = d.getUTCMinutes()
        }
        
        // 转换为东八区时间
        let cstHours = utcHours + 8
        if (cstHours >= 24) cstHours -= 24
        if (cstHours < 0) cstHours += 24
        
        return `${String(cstHours).padStart(2, '0')}:${String(utcMinutes).padStart(2, '0')}`
        
      } catch (e) {
        return dateStr
      }
    },

    getFileName(filePath) {
      if (!filePath) return ''
      const parts = filePath.split(/[\\/]/)
      return parts[parts.length - 1]
    },

    copyMessage(content) {
      navigator.clipboard.writeText(content || '').then(() => {
        this.$message && this.$message.success('已复制')
      }).catch(() => {})
    },

    showRagDetail(ragStatus) {
      if (ragStatus && ragStatus.success && ragStatus.results) {
        this.ragModalData = ragStatus
        this.ragModalVisible = true
      }
    },

    openSaveToKbDialog() {
      this.$store.commit('SET_INGEST_TASK', {
        visible: true,
        minimized: false,
        collection: 'legal_default',
        progress: { active: false, percent: 0, message: '', status: '', stage: '' },
        fileStatus: []
      })
    },

    minimizeSaveToKb() {
      this.$store.commit('UPDATE_INGEST_TASK', { minimized: true, visible: false })
    },

    async closeSaveToKbDialog() {
      const task = this.$store.state.ingestTask
      if (task && task.progress && task.progress.active) {
        try {
          await this.$confirm('任务正在进行中，关闭后将不再显示进度，但任务仍会在后台运行。确定关闭？', '提示', {
            confirmButtonText: '确定关闭',
            cancelButtonText: '取消',
            type: 'warning'
          })
        } catch {
          return
        }
      }
      this.$store.commit('CLEAR_INGEST_TASK')
    },

    async confirmSaveToKb() {
      const app = this.$parent
      let selectedFiles = []
      if (app && app.$refs && app.$refs.fileExplorer) {
        selectedFiles = app.$refs.fileExplorer.selectedFiles || []
      }

      if (selectedFiles.length === 0) {
        this.$message.warning('请先选择文件')
        return
      }

      const collection = this.saveToKbCollection
      this.saveToKbLoading = true

      // 初始化进度状态到 Vuex
      this.$store.commit('UPDATE_INGEST_TASK', {
        progress: {
          active: true,
          percent: 0,
          message: '正在提交文件...',
          status: '',
          stage: 'upload',
        },
        fileStatus: []
      })

      try {
        const response = await this.$axios.post('/api/rag/ingest-local', {
          file_paths: selectedFiles,
          collection_name: collection
        })

        if (!response.data.success) {
          this.$store.commit('UPDATE_INGEST_TASK', {
            progress: { active: false, percent: 0, message: response.data.message || '提交失败', status: 'exception', stage: '' }
          })
          this.$message.error(response.data.message || '入库失败')
          return
        }

        const tasks = response.data.tasks || []
        if (tasks.length === 0) {
          this.$store.commit('UPDATE_INGEST_TASK', {
            progress: { active: false, percent: 0, message: '没有可处理的文件', status: 'exception', stage: '' }
          })
          return
        }

        // 初始化逐文件状态
        this.$store.commit('UPDATE_INGEST_TASK', {
          fileStatus: tasks.map(t => ({
            taskId: t.task_id,
            name: t.file_name,
            state: 'pending',
          })),
          progress: {
            active: true,
            percent: 0,
            message: `正在解析入库 (0/${tasks.length})...`,
            status: '',
            stage: 'ingest',
          }
        })

        // 并行轮询所有任务进度
        let successCount = 0
        let failCount = 0

        const pollPromises = tasks.map((task, index) =>
          this._pollSaveToKbProgress(task.task_id, index, tasks.length).then(result => {
            const fileStatus = this.$store.state.ingestTask?.fileStatus || []
            const statusItem = fileStatus[index]
            if (statusItem) {
              if (result.success) {
                statusItem.state = 'success'
                successCount++
              } else {
                statusItem.state = 'fail'
                failCount++
              }
            }
          })
        )

        await Promise.all(pollPromises)

        this.$store.commit('UPDATE_INGEST_TASK', {
          progress: {
            active: false,
            percent: 100,
            message: `完成: ${successCount} 个成功, ${failCount} 个失败`,
            status: failCount === 0 ? 'success' : 'warning',
            stage: 'ingest',
          }
        })

        if (successCount > 0) {
          this.$message.success(`${successCount} 个文件已成功入库`)
          // 清空选择
          if (app && app.$refs && app.$refs.fileExplorer) {
            app.$refs.fileExplorer.clearSelection()
          }
        }
      } catch (error) {
        this.$store.commit('UPDATE_INGEST_TASK', {
          progress: {
            active: false,
            percent: 0,
            message: '入库请求失败: ' + (error.response?.data?.message || error.message),
            status: 'exception',
            stage: '',
          }
        })
        this.$message.error('入库请求失败: ' + (error.response?.data?.message || error.message))
      } finally {
        this.saveToKbLoading = false
      }
    },

    _pollSaveToKbProgress(taskId, fileIndex, totalFiles) {
      return new Promise((resolve) => {
        const poll = setInterval(async () => {
          // 检查任务是否已被清除
          if (!this.$store.state.ingestTask) {
            clearInterval(poll)
            resolve({ success: false, message: '任务已取消' })
            return
          }

          try {
            const res = await this.$axios.get(`/api/rag/upload/progress/${taskId}`)
            const data = res.data

            if (!data.success) {
              clearInterval(poll)
              resolve({ success: false, message: data.message || '查询进度失败' })
              return
            }

            // 更新进度 UI
            const stageMap = { parsing: 'ingest', chunking: 'ingest', embedding: 'ingest', storing: 'ingest', done: 'ingest' }
            const task = this.$store.state.ingestTask
            if (task) {
              const progress = { ...task.progress }
              progress.stage = stageMap[data.stage] || 'ingest'
              progress.message = data.message || ''

              // 计算总进度：当前文件的进度映射到整体
              const fileBase = Math.round((fileIndex / totalFiles) * 100)
              const fileShare = Math.round((1 / totalFiles) * 100)
              const currentPercent = Math.min(fileBase + Math.round((data.progress / 100) * fileShare), 99)
              // 取所有文件中的最大进度作为总进度
              progress.percent = Math.max(progress.percent, currentPercent)

              this.$store.commit('UPDATE_INGEST_TASK', { progress })
            }

            if (data.status === 'done') {
              clearInterval(poll)
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
    
    // ⭐ 存入风格库相关方法
    async loadStyleProfiles() {
      this.styleProfilesLoading = true
      try {
        const api = (await import('@/api/index')).default
        const response = await api.get('/style/profiles')
        if (response.data && response.data.success) {
          this.styleProfiles = response.data.profiles || []
        }
      } catch (e) {
        console.warn('[Chat] 加载风格列表失败:', e.message)
      } finally {
        this.styleProfilesLoading = false
      }
    },

    onStyleModeChange(val) {
      if (val === 'new') {
        this.saveToStyleMergeTarget = ''
        this.saveToStyleName = ''
      } else {
        this.saveToStyleMergeTarget = val
        this.saveToStyleName = val
      }
    },

    openSaveToStyleDialog() {
      this.saveToStyleDialogVisible = true
      this.saveToStyleProgress = { active: false, percent: 0, message: '', status: '', stage: '' }
      this.saveToStyleFileStatus = []
      this.saveToStyleName = ''
      this.saveToStyleMode = 'new'
      this.saveToStyleMergeTarget = ''
      this.loadStyleProfiles()
    },

    closeSaveToStyleDialog() {
      this.saveToStyleDialogVisible = false
      this.saveToStyleProgress = { active: false, percent: 0, message: '', status: '', stage: '' }
      this.saveToStyleFileStatus = []
    },

    minimizeSaveToStyle() {
      this.saveToStyleDialogVisible = false
    },

    async confirmSaveToStyle() {
      const app = this.$parent
      let selectedFiles = []
      if (app && app.$refs && app.$refs.fileExplorer) {
        selectedFiles = app.$refs.fileExplorer.selectedFiles || []
      }

      if (selectedFiles.length === 0) {
        this.$message.warning('请先选择文件')
        return
      }

      const isMerge = this.saveToStyleMode !== 'new'
      const styleName = isMerge ? this.saveToStyleMergeTarget : this.saveToStyleName.trim()

      if (!styleName) {
        this.$message.warning(isMerge ? '请选择目标风格' : '请输入风格名称')
        return
      }

      this.saveToStyleLoading = true

      // selectedFiles 是路径字符串数组，提取文件名用于显示
      const fileNames = selectedFiles.map(fp => {
        const parts = fp.split(/[\\/]/)
        return parts[parts.length - 1]
      })

      // 初始化进度状态
      this.saveToStyleProgress = { active: true, percent: 0, message: '开始分析...', stage: 'parse' }
      this.saveToStyleFileStatus = fileNames.map(name => ({ name, state: 'pending' }))

      try {
        // 阶段 1：解析文件
        this.saveToStyleProgress.message = `正在解析 ${selectedFiles.length} 个文件...`

        for (let i = 0; i < this.saveToStyleFileStatus.length; i++) {
          this.saveToStyleFileStatus[i].state = 'uploading'
          this.saveToStyleProgress.percent = Math.round((i / selectedFiles.length) * 50)
          this.saveToStyleProgress.message = `正在解析: ${fileNames[i]}`
        }

        // 调用后端 API 分析风格
        const api = (await import('@/api/index')).default
        const response = await api.post('/style/analyze', {
          file_paths: selectedFiles,
          style_name: styleName,
          merge: isMerge,
        })

        if (response.data && response.data.success) {
          // 阶段 2：分析完成
          this.saveToStyleProgress.stage = 'analyze'
          this.saveToStyleProgress.percent = 100
          const action = isMerge ? '合并更新' : '生成'
          this.saveToStyleProgress.message = `风格 "${styleName}" 已${action}`
          this.saveToStyleProgress.status = 'success'

          for (let i = 0; i < this.saveToStyleFileStatus.length; i++) {
            this.saveToStyleFileStatus[i].state = 'success'
          }

          this.$message.success(`风格 "${styleName}" 已成功${isMerge ? '合并更新' : '存入风格库'}`)

          // 同步更新自动润色设置
          this.$store.dispatch('settings/setAutoPolishStyle', styleName)
          // 刷新风格列表
          this.loadStyleProfiles()
        } else {
          throw new Error(response.data?.error || '分析失败')
        }
      } catch (e) {
        this.saveToStyleProgress.status = 'exception'
        this.saveToStyleProgress.message = `分析失败: ${e.message}`

        for (let i = 0; i < this.saveToStyleFileStatus.length; i++) {
          if (this.saveToStyleFileStatus[i].state === 'pending' || this.saveToStyleFileStatus[i].state === 'uploading') {
            this.saveToStyleFileStatus[i].state = 'fail'
          }
        }

        this.$message.error(`分析失败: ${e.message}`)
      } finally {
        this.saveToStyleLoading = false
      }
    },

    // ⭐ 灯泡按钮交互
    handlePolishBtnClick() {
      // 正在显示弹窗时，点击关闭
      if (this.stylePopoverVisible) {
        this.stylePopoverVisible = false
        return
      }
      // 已开启润色 → 再次点击弹出列表（可切换风格或关闭）
      if (this.autoPolish) {
        this.loadStyleProfiles()
        this.stylePopoverVisible = true
        return
      }
      // 未开启润色 → 没有风格，提示去存入
      if (this.styleProfiles.length === 0) {
        this.$message.warning('暂无风格，请先选择文件并存入风格库')
        return
      }
      // 未开启润色 → 有风格但未选择，弹出列表
      if (!this.autoPolishStyle) {
        this.stylePopoverVisible = true
        return
      }
      // 未开启润色 → 已有选中风格，直接开启
      this.toggleAutoPolish()
    },

    selectPolishStyle(name) {
      this.$store.dispatch('settings/setAutoPolishStyle', name)
      if (!this.autoPolish) {
        this.$store.dispatch('settings/setAutoPolish', true)
      }
      this.stylePopoverVisible = false
      this.$message.success(`已切换润色风格: ${name}`)
    },

    turnOffPolish() {
      this.$store.dispatch('settings/setAutoPolish', false)
      this.stylePopoverVisible = false
    },
    
    /**
     * ✅ 新增：格式化技能名称
     */
    formatSkillName(skillName) {
      // 将 snake_case 转换为可读格式
      return skillName
        .replace(/_/g, ' ')
        .replace(/\b\w/g, l => l.toUpperCase())
    },
    
    /**
     * ✅ 新增：获取技能描述（用于 tooltip）
     */
    getSkillDescription(skillName) {
      const skillDescriptions = {
        'china_legal_query': '中国法律法规查询',
        'contract_generator': '合同生成',
        'contract_review_pro': '合同审查专业版',
        'lawsuit_fee_calc': '诉讼费计算',
        'legal_doc_writer': '法律文书撰写',
        'litigation_jurisdiction': '诉讼管辖判断',
        'litigation_response': '诉讼应对策略',
        'patent_search': '专利检索',
        'patent_writer': '专利撰写',
        'patent_fto': '专利 FTO 分析',
        'patent_invalid_search': '专利无效检索',
        'patent_assistant': '专利助手',
        'content_writer': '内容撰写',
        'marketing_strategy_pmm': '营销策略',
        'news_writing': '新闻稿撰写',
        'wechat_mp_writer': '微信公众号撰写',
      }
      
      return skillDescriptions[skillName] || skillName
    }
  },
}
</script>

<style scoped>
/* ✅ 新增：工具调用状态样式 */
.tool-status {
  margin-top: 12px;
  padding: 12px;
  background: #f5f5f5;
  border-radius: 8px;
  border-left: 3px solid var(--primary);
}

.tool-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  font-size: 13px;
}

.tool-item.running {
  color: #1890ff;
}

.tool-item.success {
  color: #52c41a;
}

.tool-item.error {
  color: #ff4d4f;
}

.tool-icon {
  font-size: 16px;
}

.tool-name {
  font-weight: 500;
  flex: 1;
}

.tool-running,
.tool-success,
.tool-error {
  font-size: 12px;
  opacity: 0.8;
}

/* ✅ 新增：技能使用卡片样式 */
.skills-card {
  margin-top: 12px;
  padding: 12px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 8px;
  color: white;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
}

.skills-card-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
  font-size: 13px;
  font-weight: 600;
  opacity: 0.9;
}

.skills-icon {
  font-size: 16px;
}

.skills-title {
  flex: 1;
}

.skills-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.skill-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 16px;
  font-size: 12px;
  backdrop-filter: blur(10px);
  transition: all 0.3s ease;
  cursor: default;
}

.skill-tag:hover {
  background: rgba(255, 255, 255, 0.3);
  transform: translateY(-1px);
}

.skill-icon {
  font-size: 14px;
  opacity: 0.9;
}

.skill-name {
  font-weight: 500;
  letter-spacing: 0.3px;
}

/* 加载动画 */
.loading-dots {
  display: flex;
  gap: 4px;
  padding: 8px 0;
}

.loading-dots span {
  width: 8px;
  height: 8px;
  background: var(--primary);
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}

.loading-dots span:nth-child(1) {
  animation-delay: -0.32s;
}

.loading-dots span:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes bounce {
  0%, 80%, 100% {
    transform: scale(0);
  }
  40% {
    transform: scale(1);
  }
}

  /* RAG 小标签 - 与 .actions button 等高 */
  .rag-tag {
    display: inline-flex;
    align-items: center;
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
    font-family: 'Geist Mono', monospace;
    letter-spacing: 0.5px;
    margin-left: auto;
    line-height: 1;
    box-sizing: border-box;
  }

  .rag-tag-on {
    background: #52c41a;
    color: #fff;
  }

  .rag-tag-triggered {
    background: #faad14;
    color: #fff;
  }

  .rag-tag-off {
    background: #e0e0e0;
    color: #999;
  }

  .rag-tag-clickable {
    cursor: pointer;
    transition: filter 0.15s;
  }

  .rag-tag-clickable:hover {
    filter: brightness(1.1);
  }

  /* RAG 弹窗 */
  .rag-modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.45);
    z-index: 1000;
    display: flex;
    align-items: center;
    justify-content: center;
    animation: fadeIn 0.15s ease;
  }

  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }

  .rag-modal {
    background: #fff;
    border-radius: 16px;
    width: 600px;
    max-width: 90vw;
    max-height: 75vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
    animation: slideUp 0.2s ease;
  }

  @keyframes slideUp {
    from { transform: translateY(20px); opacity: 0; }
    to { transform: translateY(0); opacity: 1; }
  }

  .rag-modal-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 18px 24px;
    border-bottom: 1px solid #E0D9D0;
    flex-shrink: 0;
  }

  .rag-modal-icon {
    font-size: 20px;
  }

  .rag-modal-title {
    font-size: 16px;
    font-weight: 600;
    color: #1C1C1C;
  }

  .rag-modal-count {
    font-size: 12px;
    font-family: 'Geist Mono', monospace;
    color: #52c41a;
    background: #f0fce8;
    padding: 2px 8px;
    border-radius: 10px;
  }

  .rag-modal-close {
    margin-left: auto;
    background: none;
    border: none;
    font-size: 22px;
    color: #999;
    cursor: pointer;
    padding: 0 4px;
    line-height: 1;
  }

  .rag-modal-close:hover {
    color: #333;
  }

  .rag-modal-body {
    padding: 16px 24px 24px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .rag-result-card {
    border: 1px solid #E0D9D0;
    border-radius: 10px;
    padding: 14px 16px;
    background: #FAFAF8;
  }

  .rag-result-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
  }

  .rag-result-title {
    font-size: 14px;
    font-weight: 600;
    color: #1C1C1C;
  }

  .rag-result-score {
    font-size: 12px;
    font-family: 'Geist Mono', monospace;
    font-weight: 600;
    color: #52c41a;
  }

  .rag-result-score-bar {
    height: 4px;
    background: #E0D9D0;
    border-radius: 2px;
    margin-bottom: 8px;
    overflow: hidden;
  }

  .rag-result-score-fill {
    height: 100%;
    background: #52c41a;
    border-radius: 2px;
    transition: width 0.3s ease;
  }

  .rag-result-meta {
    display: flex;
    gap: 8px;
    margin-bottom: 8px;
  }

  .rag-result-category,
  .rag-result-collection {
    font-size: 11px;
    font-family: 'Geist Mono', monospace;
    padding: 2px 6px;
    border-radius: 4px;
    background: #f0ede8;
    color: #6B6156;
  }

  .rag-result-content {
    font-size: 13px;
    line-height: 1.7;
    color: #3A3530;
    white-space: pre-wrap;
    word-break: break-word;
    max-height: 200px;
    overflow-y: auto;
  }

  .rag-empty {
    text-align: center;
    color: #999;
    padding: 32px 0;
    font-size: 14px;
  }

</style>

<style>
@import url('https://unpkg.com/lucide-static@latest/font/lucide.css');
</style>

<style scoped>
.chat-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #F7F5F2;
}

.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.empty-content {
  text-align: center;
  padding: 40px;
}

.empty-header {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  margin-bottom: 12px;
}

.empty-logo {
  width: 56px;
  height: 56px;
  object-fit: contain;
}

.empty-title {
  font-family: 'Playfair Display', serif;
  font-size: 32px !important;
  font-weight: 600;
  color: #1C1C1C;
  margin: 0;
}

.empty-subtitle {
  font-size: 20px !important;
  color: #8A7D6B;
  margin-bottom: 40px;
}

.loading-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #E0D9D0;
  border-top-color: #C8A96E;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.loading-text {
  font-size: 14px !important;
  color: #8A7D6B;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.messages::-webkit-scrollbar {
  width: 6px;
}

.messages::-webkit-scrollbar-thumb {
  background: #D5CEC4;
  border-radius: 3px;
}

.msg {
  display: flex;
  flex-direction: column;
}

.msg.user {
  align-self: flex-end;
  align-items: flex-end;
  max-width: 100%;
}

.msg.ai {
  align-self: flex-start;
  align-items: flex-start;
}

.message-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-width: 100%;
}

.msg.user .message-content {
  align-items: flex-end;
}

.message-bubble {
  padding: 12px 18px;
  border-radius: 16px 16px 4px 16px;
  background: #C8A96E;
  color: #fff;
  font-size: 14px;
  line-height: 1.6;
  min-width: 80px;
  max-width: 450px;
  width: 100%;
  word-break: break-word;
  white-space: normal;
}

/* 附件文件列表 */
.attachments-list {
  margin-top: 8px;
  padding: 8px 12px;
  background: #EDE8DF;
  border-radius: 8px;
}

.attachment-item {
  display: flex;
  align-items: center;
  padding: 3px 0;
  font-size: 12px;
  color: #6B6156;
  line-height: 1.4;
}

.attachment-item .attachment-name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.message-time {
  font-size: 11px;
  font-family: 'Geist Mono', monospace;
  color: #A09888;
  padding: 0 4px;
}

.bubble-ai {
  padding: 20px 24px;
  border-radius: 16px 16px 16px 4px;
  background: #FFFFFF;
  border: 1px solid #E0D9D0;
  color: #3A3530;
  font-size: 14px;
  line-height: 1.7;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  min-width: 300px;
  max-width: 650px;
  width: auto;
}

.ai-label {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
  font-family: 'Geist Mono', monospace;
  font-size: 11px;
  color: #A09888;
  letter-spacing: 0.5px;
}

.time {
  margin-top: 6px;
  font-family: 'Geist Mono', monospace;
  font-size: 11px;
  color: #A09888;
}

.loading-dots {
  display: flex;
  gap: 4px;
  padding: 4px 0;
}

.loading-dots span {
  width: 8px;
  height: 8px;
  background: #C8A96E;
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}

.loading-dots span:nth-child(1) { animation-delay: -0.32s; }
.loading-dots span:nth-child(2) { animation-delay: -0.16s; }
.loading-dots span:nth-child(3) { animation-delay: 0s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

.error-text {
  color: #C0392B;
  font-size: 13px;
}

.bubble-ai :deep(p) {
  margin: 8px 0;
}

.bubble-ai :deep(p:first-child) {
  margin-top: 0;
}

.bubble-ai :deep(p:last-child) {
  margin-bottom: 0;
}

.bubble-ai :deep(strong) {
  font-weight: 600;
  color: #1C1C1C;
}

.bubble-ai :deep(pre) {
  background: #F0EBE3;
  padding: 12px 16px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 10px 0;
  font-family: 'Geist Mono', monospace;
  font-size: 13px;
}

.bubble-ai :deep(code) {
  font-family: 'Geist Mono', monospace;
  font-size: 13px;
  background: #F0EBE3;
  padding: 2px 8px;
  border-radius: 4px;
  color: #8A7D6B;
}

.bubble-ai :deep(ol),
.bubble-ai :deep(ul) {
  padding-left: 20px;
  margin: 10px 0;
}

.bubble-ai :deep(li) {
  margin-bottom: 10px;
  line-height: 1.6;
}

.bubble-ai :deep(blockquote) {
  border-left: 3px solid #C8A96E;
  padding-left: 12px;
  margin: 10px 0;
  color: #6B6156;
  background: #FDFCFA;
  padding: 8px 12px;
  border-radius: 0 4px 4px 0;
}

.actions {
  display: flex;
  gap: 8px;
  margin-top: 16px;
  flex-wrap: wrap;
}

.actions button {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  border: 1px solid #E0D9D0;
  border-radius: 6px;
  background: #FDFCFA;
  font-size: 12px;
  color: #6B6156;
  cursor: pointer;
  transition: all 0.15s;
}

.actions button:hover {
  background: #F0EBE3;
  border-color: #C8A96E;
}

.actions button i {
  font-size: 13px;
  color: #C8A96E;
}

.input-area {
  position: relative;
  padding: 0 24px;
  border-top: 1px solid #E0D9D0;
  flex-shrink: 0;
  background: #F7F5F2;
  height: 68px;
  display: flex;
  align-items: center;
}

.save-to-kb-bar {
  position: absolute;
  bottom: 100%;
  left: 0;
  right: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 24px;
  background: #EDE8DF;
  border: none;
  animation: fadeIn 0.2s ease;
}

.save-to-kb-info {
  font-size: 13px;
  color: #6B6156;
}

.save-to-kb-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 5px 12px;
  border: none;
  border-radius: 6px;
  background: #C8A96E;
  color: #fff;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;
  font-family: var(--font-family);
}

.save-to-kb-btn:hover {
  background: #B8994E;
}

.save-to-kb-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.input-area {
  position: relative;
  padding: 0 24px;
  border-top: 1px solid #E0D9D0;
  flex-shrink: 0;
  background: #F7F5F2;
}

/* ⭐ 输入行容器：灯泡 + 输入框 + 发送按钮 */
.input-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 0;
  width: 100%;
}

/* ⭐ 输入白框（仅含输入框） */
.input-box {
  display: flex;
  align-items: center;
  padding: 6px 12px;
  border: 1px solid #D5CEC4;
  border-radius: 12px;
  background: #FFFFFF;
  flex: 1;
  min-width: 0;
  min-height: 44px;
  height: 44px;
}

/* ⭐ 灯泡按钮：自动润色开关（在白框外面） */
.polish-toggle-btn {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  border: 1px solid #D5CEC4;
  background: #FFFFFF;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.25s ease;
  flex-shrink: 0;
  color: #A09888;
  padding: 0;
}

.polish-toggle-btn:hover {
  background: #F5F2EE;
  color: #6B6156;
}

.polish-toggle-btn.active {
  background: #F0FFF0;
  border-color: #67c23a;
  color: #52c41a;
  box-shadow: 0 0 0 3px rgba(103, 194, 58, 0.12);
}

.polish-toggle-btn.active:hover {
  background: #E8F8E8;
  color: #49b816;
}

.input-field {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 16px;
  color: #1C1C1C;
  resize: none;
  height: 28px;
  max-height: 120px;
  font-family: inherit;
  line-height: 28px;
  padding: 0;
  margin: 0;
}

.input-field::placeholder {
  color: #B0A898;
}

.input-field:focus {
  outline: none;
}

.send-btn {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  border: none;
  background: linear-gradient(135deg, var(--primary), var(--primary-container));
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(3, 22, 53, 0.15);
}

.send-btn:hover:not(:disabled) {
  opacity: 0.9;
  box-shadow: 0 4px 12px rgba(3, 22, 53, 0.25);
  transform: translateY(-1px);
}

.send-btn:disabled {
  background: #D5CEC4;
  cursor: not-allowed;
  box-shadow: none;
  transform: none;
}

.send-btn i {
  color: #fff;
  font-size: 18px;
}

/* 存入知识库进度面板 */
.save-to-kb-progress-panel {
  padding: 8px 0;
}

/* 自定义对话框头部 */
.dialog-custom-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding-right: 20px;
}

.dialog-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.dialog-header-btn {
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: #A09888;
  font-size: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  line-height: 1;
  padding: 0;
}

.dialog-header-btn:hover {
  background: #F0EBE3;
  color: #6B6156;
}
</style>

<style>
@import '@/styles/upload-progress.css';

/* ⭐ 灯泡按钮风格选择弹窗（unscoped，因为 el-popover 渲染在 body 下） */
.style-popover {
  padding: 0 !important;
  border-radius: 10px !important;
  border: 1px solid #E0D9D0 !important;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08) !important;
}

.style-popover-content {
  padding: 0;
}

.style-popover-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-bottom: 1px solid #E0D9D0;
  font-size: 13px;
  font-weight: 500;
  color: #3A3530;
}

.style-popover-close {
  width: 22px;
  height: 22px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: #A09888;
  font-size: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  padding: 0;
}

.style-popover-close:hover {
  background: #F0EBE3;
  color: #6B6156;
}

.style-popover-empty {
  padding: 16px 14px;
  text-align: center;
  font-size: 12px;
  color: #A09888;
}

.style-popover-list {
  max-height: 200px;
  overflow-y: auto;
  padding: 4px 0;
}

.style-popover-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 14px;
  cursor: pointer;
  transition: background 0.15s;
  font-size: 13px;
  color: #3A3530;
}

.style-popover-item:hover {
  background: #F5F2EE;
}

.style-popover-item.active {
  background: #F0FFF0;
  color: #52c41a;
}

.style-popover-item .el-icon-check {
  color: #52c41a;
  font-size: 14px;
  font-weight: 600;
}

.style-popover-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 160px;
}

.style-popover-divider {
  height: 1px;
  background: #E0D9D0;
  margin: 4px 14px;
}

.style-popover-off {
  color: #A09888;
}

.style-popover-off:hover {
  color: #6B6156;
}
</style>