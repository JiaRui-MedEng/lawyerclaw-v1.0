import api from './index'

/**
 * 流式对话 - 支持统一事件格式
 * @param {string} sessionId - 会话 ID
 * @param {string} content - 消息内容
 * @param {function} onChunk - 内容块回调
 * @param {function} onDone - 完成回调
 * @param {function} onError - 错误回调
 * @param {function} onEvent - 通用事件回调（支持 tool_start, tool_end, thinking 等）
 */
export async function sendMessageStream(sessionId, content, onChunk, onDone, onError, onEvent) {
  
  // 添加参数验证
  if (!sessionId || !content) {
    onError?.(new Error('缺少必要参数'))
    return
  }

  try {
    const headers = { 'Content-Type': 'application/json' }

    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers,
      credentials: 'include',
      body: JSON.stringify({ session_id: sessionId, content })
    })


    if (!response.ok) {
      const text = await response.text()
      onError?.(new Error(`HTTP ${response.status}: ${text}`))
      return
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let chunkCount = 0
    let finalContent = ''
    let eventCount = 0
    let doneCalled = false

    const callDone = () => {
      if (doneCalled) return
      doneCalled = true
      onDone?.()
    }

    while (true) {
      const { done, value } = await reader.read()
      if (done) {
        break
      }

      buffer += decoder.decode(value, { stream: true })

      // SSE 以\n\n分隔事件
      const parts = buffer.split('\n\n')
      buffer = parts.pop() || ''

      for (const part of parts) {
        const trimmed = part.trim()
        if (!trimmed) continue

        // 解析 SSE 数据
        const dataLine = trimmed.replace(/^data: /, '')
        if (!dataLine) continue

        if (dataLine === '[DONE]') {
          callDone()
          return
        }

        try {
          const parsed = JSON.parse(dataLine)
          
          // ✅ 新增：支持统一事件格式
          if (parsed.type) {
            eventCount++
            
            // 触发通用事件回调
            onEvent?.(parsed.type, parsed.data)
            
            // 处理不同类型的事件
            switch (parsed.type) {
              case 'chunk':
                chunkCount++
                const chunkContent = parsed.data?.content || ''
                if (chunkContent) {
                  finalContent += chunkContent
                  onChunk?.(chunkContent)
                }
                break
              
              case 'tool_start':
              case 'tool_end':
              case 'thinking':
              case 'file_start':
              case 'file_end':
              case 'file_read_start':
              case 'file_read_end':
                // 这些事件通过 onEvent 处理
                break
              
              case 'done':
                if (!finalContent && parsed.data?.content) {
                  finalContent = parsed.data.content
                  onChunk?.(`[FULL_CONTENT_START]${finalContent}[FULL_CONTENT_END]`)
                }
                callDone()
                return
              
              case 'error':
                onError?.(new Error(parsed.data.message))
                return
            }
          }
          
          // 兼容旧格式：流式 chunk 事件
          if (parsed && parsed.chunk) {
            chunkCount++
            finalContent += parsed.chunk
            onChunk?.(parsed.chunk)
          }
          
          // 兼容旧格式：最终成功响应
          if (parsed && parsed.success) {
            const fullContent = (parsed.message && parsed.message.content) || ''
            
            if (!finalContent && fullContent) {
              finalContent = fullContent
              if (fullContent.length > 0) {
                onChunk?.(`[FULL_CONTENT_START]${fullContent}[FULL_CONTENT_END]`)
              }
            }
            
            callDone()
            return
          }
        } catch (e) {
          // 解析失败，可能是纯文本块
          if (dataLine && dataLine.trim()) {
            chunkCount++
            finalContent += dataLine
            onChunk?.(dataLine)
          }
        }
      }
    }

    callDone()
  } catch (e) {
    onError?.(e)
  }
}

/**
 * 获取会话历史消息
 */
export function getMessages(sessionId) {
  return api.get(`/sessions/${sessionId}/messages`).then(r => r.data)
}