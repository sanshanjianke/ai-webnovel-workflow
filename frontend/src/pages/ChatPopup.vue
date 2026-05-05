<template>
  <div class="chat-popup">
    <div class="popup-header">
      <h2>{{ title }}</h2>
      <span class="popup-type-badge">{{ nodeTypeLabel }}</span>
      <span class="popup-status" v-if="isRunning">● 运行中</span>
      <span class="popup-status stopped" v-else>已完成</span>
    </div>
    <div class="popup-body">
      <DocumentSidebar v-if="projectId" :projectId="projectId" class="popup-library" />
      
      <!-- 输入源节点 -->
      <div v-if="nodeType === 'inputSource'" class="popup-content">
        <div class="input-source-panel">
          <h3>📥 输入源</h3>
          <div class="input-files-list">
            <div v-for="(file, idx) in inputFiles" :key="idx" class="input-file-item">
              <span class="file-icon">📄</span>
              <span class="file-name">{{ file.name }}</span>
              <span class="file-size">{{ formatSize(file.size) }}</span>
            </div>
            <div v-if="inputFiles.length === 0" class="empty-hint">
              暂无输入文件
            </div>
          </div>
        </div>
      </div>
      
      <!-- 输出节点 -->
      <div v-else-if="nodeType === 'output'" class="popup-content">
        <div class="output-panel">
          <h3>📤 输出结果</h3>
          <div v-if="outputFiles.length > 0" class="output-files-list">
            <div v-for="(file, idx) in outputFiles" :key="idx" class="output-file-item">
              <span class="file-icon">📄</span>
              <span class="file-name">{{ file.name }}</span>
              <button class="btn btn-sm" @click="downloadFile(file)">下载</button>
            </div>
            <button class="btn btn-primary" @click="downloadAll">下载全部 (zip)</button>
          </div>
          <div v-else class="empty-hint">
            等待输出...
          </div>
        </div>
      </div>
      
      <!-- 专家和容器节点 -->
      <div v-else class="popup-messages-container">
        <div class="popup-messages" ref="msgEl">
          <div v-if="messages.length === 0" class="empty-hint">
            等待消息...<br><small>在编排画布上运行管道后，消息将在此显示</small>
          </div>
          <div v-for="(msg, idx) in messages" :key="idx"
            :class="['message', msg.type]">
            <div class="message-header">
              <span class="expert-icon">{{ getIcon(msg) }}</span>
              <span class="expert-name">{{ msg.expert_type || msg.type }}</span>
              <span class="timestamp">{{ formatTime(msg.timestamp) }}</span>
            </div>
            <details v-if="msg.thinking" class="thinking-block" :open="msg.streaming">
              <summary>💭 思考过程 <span v-if="msg.streaming" class="thinking-indicator">...</span></summary>
              <pre class="thinking-text">{{ msg.thinking }}</pre>
            </details>
            <div class="message-content" v-html="renderMarkdown(msg.content)"></div>
            <span v-if="msg.streaming" class="streaming-cursor">▊</span>
          </div>
        </div>
        <div class="queue-sidebar" v-if="queueState.total > 0">
          <div class="queue-sidebar-header">
            📥 队列 
            <span v-if="remainingFiles > 0" class="queue-count">{{ remainingFiles }}</span>
            <span v-else class="queue-done">✓</span>
          </div>
          <div v-for="(file, idx) in pendingFiles" :key="idx"
            :class="['queue-sidebar-item', {
              current: idx === 0
            }]">
            <span class="queue-dot"></span>
            <span>{{ file }}</span>
          </div>
          <div v-if="pendingFiles.length === 0" class="queue-complete-hint">
            全部完成
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import MarkdownIt from 'markdown-it'
import DocumentSidebar from '../components/library/DocumentSidebar.vue'

const route = useRoute()
const md = new MarkdownIt()
const targetId = computed(() => route.query.containerId || route.query.expertId || 'solo')
const projectId = computed(() => route.query.projectId || '')
const nodeType = computed(() => route.query.nodeType || 'expert') // expert, container, inputSource, output
const title = computed(() => route.query.name || (targetId.value === 'solo' ? '主聊天' : targetId.value))
const nodeTypeLabel = computed(() => {
  const labels = { expert: '专家', container: '容器', inputSource: '输入源', output: '输出' }
  return labels[nodeType.value] || '节点'
})
const messages = ref([])
const isRunning = ref(true)
const msgEl = ref(null)
const queueState = ref({ total: 0, files: [] })
const inputFiles = ref([]) // 输入源文件列表
const outputFiles = ref([]) // 输出文件列表
let channel = null

// 计算剩余文件数
const remainingFiles = computed(() => {
  return (queueState.value.files || []).length
})

// 获取待处理的文件列表
const pendingFiles = computed(() => {
  return queueState.value.files || []
})

function getIcon(msg) {
  const icons = { '资深作者': '📕', '读者代表': '📙', '剧情架构师': '🏛', '人物设计师': '🎭', '网络编辑': '💼', '系统': '⚙️', '主编': '💬', '讨论总结师': '📋' }
  return icons[msg.expert_type || msg.type] || '📄'
}
function renderMarkdown(text) { return text ? md.render(text) : '' }
function formatTime(ts) { return ts ? new Date(ts).toLocaleTimeString('zh-CN') : '' }
function formatSize(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  while (bytes >= 1024 && i < units.length - 1) { bytes /= 1024; i++ }
  return `${bytes.toFixed(1)} ${units[i]}`
}
function downloadFile(file) {
  const blob = new Blob([file.content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = file.name
  a.click()
  URL.revokeObjectURL(url)
}
function downloadAll() {
  // TODO: 实现zip打包下载
  alert('zip下载功能待实现')
}

function matchesTarget(data) {
  if (!data) {
    console.log('[CHAT] matchesTarget: data is null')
    return false
  }
  const cid = data.container_id || data.expert_id || 'solo'
  console.log('[CHAT] matchesTarget:', { cid, targetId: targetId.value, nodeId: data.node_id, match: cid === targetId.value || data.node_id === targetId.value })
  if (cid === targetId.value) return true
  if (data.node_id === targetId.value) return true
  return false
}

onMounted(() => {
  channel = new BroadcastChannel('meeting-chat')
  channel.onmessage = (event) => {
    const { type, data, timestamp } = event.data || {}
    console.log('[CHAT] Received message:', type, data)
    if (!type) return

    if (type === 'done') {
      isRunning.value = false
      const msgs = messages.value
      for (let i = msgs.length - 1; i >= 0; i--) {
        if (msgs[i].streaming) { msgs[i].streaming = false; break }
      }
      return
    }

    if (type === 'queue_state') {
      queueState.value = data || { index: 0, total: 0 }
      return
    }

    if (type === 'queue_start') {
      // 只记录总文件数，不显示文件列表
      queueState.value = { total: data.total || 0, files: [] }
      return
    }

    if (type === 'queue_init') {
      // 只有当目标节点匹配时才初始化队列（支持驼峰和下划线）
      const nodeId = data.nodeId || data.node_id
      const expertId = data.expertId || data.expert_id
      // 同时检查nodeId和expertId，因为聊天窗口可能是用expertId打开的
      if (nodeId === targetId.value || expertId === targetId.value) {
        queueState.value = { 
          total: data.total || 0, 
          files: Array.isArray(data.fileNames) ? data.fileNames : (Array.isArray(data.file_names) ? data.file_names : [])
        }
      }
      return
    }

    if (type === 'running_state') {
      isRunning.value = data.isRunning || false
      return
    }

    if (type === 'queue_complete') {
      isRunning.value = false
      // 清空队列文件，但保留total用于显示
      queueState.value = { ...queueState.value, files: [] }
      return
    }

    if (type === 'output_files') {
      // 输出节点接收文件列表
      if (nodeType.value === 'output') {
        outputFiles.value = data.files || []
      }
      return
    }

    if (type === 'expert_start') {
      if (!matchesTarget(data)) return
      // 添加文件到队列
      if (data.fileIndex !== undefined) {
        const fileName = `文件${data.fileIndex + 1}`
        if (!queueState.value.files.includes(fileName)) {
          queueState.value.files.push(fileName)
        }
        // 更新total
        if (data.fileTotal && data.fileTotal > queueState.value.total) {
          queueState.value.total = data.fileTotal
        }
      }
      messages.value.push({
        type: 'expert', expert_type: data.expert_type,
        expert_id: data.expert_id, content: '', thinking: '', streaming: true,
        timestamp: timestamp || new Date().toISOString()
      })
      scrollDown()
      return
    }

    if (type === 'chunk') {
      if (!matchesTarget(data)) return
      const msgs = messages.value
      let last = msgs.length > 0 ? msgs[msgs.length - 1] : null
      if (!last || !last.streaming) {
        last = { type: 'expert', expert_type: data.expert_type || data.expertType || '', content: '', thinking: '', streaming: true,
          timestamp: timestamp || new Date().toISOString() }
        msgs.push(last)
      }
      const chunkType = data.chunk_type || data.chunkType
      if (chunkType === 'thinking') {
        last.thinking = (last.thinking || '') + (data.content || '')
      } else if (chunkType === 'content') {
        last.content += data.content || ''
      }
      scrollDown()
      return
    }

    if (type === 'message') {
      if (!matchesTarget(data)) return
      // 从队列中移除已完成的文件
      if (data.fileIndex !== undefined) {
        const fileName = `文件${data.fileIndex + 1}`
        const idx = queueState.value.files.indexOf(fileName)
        if (idx > -1) {
          queueState.value.files.splice(idx, 1)
        }
      }
      const msgs = messages.value
      let last = msgs.length > 0 ? msgs[msgs.length - 1] : null
      // 如果是 expert_speak 且有流式消息，定型之
      if (data.type === 'expert' && last && last.streaming) {
        last.content = data.content || last.content
        last.streaming = false
        last.expert_type = data.expert_type || last.expert_type
      } else {
        messages.value.push({ ...data, timestamp: timestamp || data.timestamp || new Date().toISOString() })
      }
      isRunning.value = data.type !== 'pipeline_complete' && data.type !== 'expert' && data.type !== 'done'
      scrollDown()
      return
    }

    // 其他事件（level_start 等）
    if (!matchesTarget(data)) return
    messages.value.push({
      type: 'system', content: data.content || JSON.stringify(data).slice(0, 120),
      timestamp: timestamp || new Date().toISOString()
    })
    scrollDown()
  }

  // 请求同步已有消息
  channel.postMessage({ type: 'sync', targetId: targetId.value })
})

let scrollPending = false
function scrollDown() {
  if (scrollPending) return
  scrollPending = true
  requestAnimationFrame(() => {
    scrollPending = false
    if (msgEl.value) msgEl.value.scrollTop = msgEl.value.scrollHeight
  })
}

onUnmounted(() => {
  if (channel) { channel.close(); channel = null }
})
</script>

<style scoped>
.chat-popup { height: calc(100vh - 42px); display: flex; flex-direction: column; background: #f5f5f5; overflow: hidden; }
.popup-header { display: flex; align-items: center; gap: 12px; padding: 10px 16px; background: white; border-bottom: 1px solid #e0e0e0; flex-shrink: 0; }
.popup-body { flex: 1; display: flex; overflow: hidden; }
.queue-sidebar { width: 140px; flex-shrink: 0; padding: 12px 8px; border-left: 1px solid #e0e0e0; background: #fafafa; overflow-y: auto; }
.popup-library { width: 240px; flex-shrink: 0; border-right: 1px solid #e0e0e0; overflow-y: auto; }
.queue-sidebar-header { font-size: 0.8rem; font-weight: 600; color: #666; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center; }
.queue-count { background: #3498db; color: white; padding: 1px 6px; border-radius: 10px; font-size: 0.7rem; }
.queue-done { background: #27ae60; color: white; padding: 1px 6px; border-radius: 10px; font-size: 0.7rem; }
.queue-complete-hint { text-align: center; color: #27ae60; font-size: 0.75rem; padding: 8px; font-style: italic; }
.queue-sidebar-item { display: flex; align-items: center; gap: 6px; padding: 4px 6px; font-size: 0.78rem; border-radius: 4px; margin-bottom: 2px; }
.queue-sidebar-item.current { background: #e8f4fd; color: #3498db; font-weight: 600; }
.queue-sidebar-item.done { color: #27ae60; }
.queue-sidebar-item.pending { color: #bbb; }
.queue-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.queue-sidebar-item.done .queue-dot { background: #27ae60; }
.queue-sidebar-item.current .queue-dot { background: #3498db; animation: pulse 1s infinite; }
.queue-sidebar-item.pending .queue-dot { background: #ddd; }
.popup-header h2 { margin: 0; font-size: 1rem; }
.popup-status { font-size: 0.75rem; color: #27ae60; font-weight: 600; }
.popup-status.stopped { color: #999; }
.popup-messages { flex: 1; overflow-y: auto; padding: 1rem; }
.message { margin-bottom: 1rem; padding: 0.75rem; border-radius: 8px; background: white; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
.message.system { background: #e3f2fd; text-align: center; font-style: italic; color: #666; }
.message.user { background: #e8f4fd; border-left: 3px solid #3498db; }
.message-header { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem; }
.expert-icon { font-size: 1.1rem; }
.expert-name { font-weight: 600; color: #333; font-size: 0.9rem; }
.timestamp { margin-left: auto; font-size: 0.75rem; color: #999; }
.message-content { line-height: 1.6; font-size: 0.9rem; }
.streaming-text { white-space: pre-wrap; word-break: break-word; font-family: inherit; font-size: 0.9rem; line-height: 1.6; margin: 0; }
.thinking-block { margin-bottom: 0.5rem; font-size: 0.8rem; }
.thinking-block summary { cursor: pointer; color: #7f8c8d; font-size: 0.8rem; user-select: none; }
.thinking-indicator { animation: blink 0.8s infinite; color: #3498db; }
.thinking-text { white-space: pre-wrap; word-break: break-word; font-family: inherit; font-size: 0.8rem; color: #7f8c8d; background: #f9f9f9; padding: 0.5rem; border-radius: 4px; margin-top: 0.3rem; max-height: 200px; overflow-y: auto; }
.streaming-cursor { display: inline; animation: blink 0.8s infinite; color: #3498db; font-weight: bold; }
.empty-hint { text-align: center; color: #999; padding: 3rem 1rem; font-size: 0.9rem; line-height: 1.8; }
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }

/* 节点类型徽章 */
.popup-type-badge { 
  font-size: 0.7rem; 
  padding: 2px 8px; 
  border-radius: 10px; 
  background: #e0e0e0; 
  color: #666; 
}

/* 输入源和输出节点的内容区域 */
.popup-content { 
  flex: 1; 
  overflow-y: auto; 
  padding: 1rem; 
}

/* 专家和容器节点的消息容器 */
.popup-messages-container { 
  flex: 1; 
  display: flex; 
  overflow: hidden; 
}

/* 输入源面板 */
.input-source-panel, .output-panel { 
  background: white; 
  border-radius: 8px; 
  padding: 1.5rem; 
  box-shadow: 0 2px 4px rgba(0,0,0,0.1); 
}
.input-source-panel h3, .output-panel h3 { 
  margin: 0 0 1rem 0; 
  font-size: 1rem; 
  color: #333; 
  border-bottom: 1px solid #eee; 
  padding-bottom: 0.5rem; 
}

/* 文件列表 */
.input-files-list, .output-files-list { 
  display: flex; 
  flex-direction: column; 
  gap: 8px; 
}
.input-file-item, .output-file-item { 
  display: flex; 
  align-items: center; 
  gap: 8px; 
  padding: 8px 12px; 
  background: #f8f9fa; 
  border-radius: 6px; 
  font-size: 0.85rem; 
}
.file-icon { font-size: 1.2rem; }
.file-name { flex: 1; font-weight: 500; }
.file-size { color: #999; font-size: 0.75rem; }

/* 按钮 */
.btn { 
  padding: 4px 12px; 
  border: 1px solid #ddd; 
  border-radius: 4px; 
  cursor: pointer; 
  font-size: 0.8rem; 
  background: white; 
  transition: all 0.2s; 
}
.btn:hover { background: #f0f0f0; }
.btn-primary { 
  background: #3498db; 
  color: white; 
  border-color: #3498db; 
  margin-top: 12px; 
}
.btn-primary:hover { background: #2980b9; }
.btn-sm { padding: 2px 8px; font-size: 0.75rem; }
</style>
