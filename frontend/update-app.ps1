# 更新 App.vue 以集成 FileExplorer 组件

$filePath = "D:\Projects\Pycharm\lawyerclaw\frontend\src\App.vue"
$encoding = New-Object System.Text.UTF8Encoding $false

$content = [System.IO.File]::ReadAllText($filePath, $encoding)

# 替换模板中的文件树部分
$oldTemplate = @'
      <!-- 第 3 列：文件资源管理器 (surface_container_low) -->
      <aside class="col-files">
        <div class="files-header">
          <span class="files-title">📁 工作空间</span>
          <button class="btn-icon" @click="refreshFiles" title="刷新">↻</button>
        </div>

        <div class="files-path">
          <span class="path-text">{{ workspaceRoot ? shortPath(workspaceRoot) : '未设置' }}</span>
          <button class="btn-path" @click="changeWorkspace">修改</button>
        </div>

        <div class="file-tree" v-loading="workspaceLoading">
          <file-tree-node
            v-for="node in workspaceTree"
            :key="node.name"
            :node="node"
            :depth="0"
          />
          <div v-if="workspaceTree.length === 0 && !workspaceLoading" class="empty-hint">
            暂无文件
          </div>
        </div>
      </aside>
'@

$newTemplate = @'
      <!-- 第 3 列：文件资源管理器 (surface_container_low) -->
      <aside class="col-files">
        <file-explorer
          @send-to-chat="handleSendToChat"
          @preview-file="handlePreviewFile"
        />
      </aside>
'@

$content = $content.Replace($oldTemplate, $newTemplate)

[System.IO.File]::WriteAllText($filePath, $content, $encoding)

Write-Host "✅ App.vue 已更新 - FileExplorer 组件已集成" -ForegroundColor Green
Write-Host ""
Write-Host "下一步：" -ForegroundColor Yellow
Write-Host "1. 刷新浏览器查看更新"
Write-Host "2. 在右侧侧边栏选择文件"
Write-Host "3. 点击'发送到对话'按钮"
