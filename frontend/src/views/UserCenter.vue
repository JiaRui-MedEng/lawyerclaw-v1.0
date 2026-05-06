<template>
  <div class="user-center">
    <div class="profile-card">
      <div class="avatar">{{ avatarInitial }}</div>
      <h3 class="user-name">{{ displayName }}</h3>
      <p class="user-hint">点击编辑您的昵称</p>
      <el-button
        type="primary"
        size="medium"
        @click="editNickname"
        style="width: 100%; margin-top: 16px;"
      >编辑昵称</el-button>
    </div>
  </div>
</template>

<script>
export default {
  name: 'UserCenter',
  computed: {
    nickname() {
      return localStorage.getItem('nickname') || ''
    },
    displayName() {
      return this.nickname || '新用户'
    },
    avatarInitial() {
      const name = this.displayName
      return name ? name.charAt(0).toUpperCase() : '用'
    }
  },
  methods: {
    async editNickname() {
      try {
        const { value } = await this.$prompt('请输入昵称', '编辑昵称', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          inputValue: this.nickname,
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
  }
}
</script>

<style scoped>
.user-center {
  padding: 30px;
  width: 100%;
  height: 100%;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  display: flex;
  justify-content: center;
  align-items: flex-start;
}

.profile-card {
  max-width: 400px;
  width: 100%;
  background: white;
  border-radius: 12px;
  padding: 40px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  text-align: center;
  transition: transform 0.3s, box-shadow 0.3s;
}

.profile-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
}

.avatar {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 36px;
  font-weight: bold;
  margin: 0 auto 20px;
  flex-shrink: 0;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
}

.user-name {
  margin: 0 0 8px 0;
  color: #303133;
  font-size: 22px;
  font-weight: 600;
}

.user-hint {
  font-size: 13px;
  color: #909399;
  margin: 0 0 16px 0;
}

/* 深色模式支持 */
[data-theme='dark'] .profile-card {
  background: var(--surface-container-lowest);
  box-shadow: var(--shadow-sm);
}

[data-theme='dark'] .user-name {
  color: var(--on-surface);
}

[data-theme='dark'] .user-hint {
  color: var(--on-surface-variant);
}

/* 响应式布局 */
@media (max-width: 768px) {
  .user-center {
    padding: 16px;
  }

  .profile-card {
    padding: 30px 20px;
  }
}
</style>
