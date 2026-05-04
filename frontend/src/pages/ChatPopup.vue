<template>
  <div class="chat-popup">
    <div class="popup-header">
      <h2>{{ title }}</h2>
      <span class="popup-status" v-if="isRunning">● 运行中</span>
      <span class="popup-status stopped" v-else>已完成</span>
    </div>
    <div class="popup-body">
      <DocumentSidebar v-if="projectId" :projectId="projectId" class="popup-library" />
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
      <div class="queue-sidebar" v-if="queueState.total >= 1">
        <div class="queue-sidebar-header">📥 队列</div>
        <div v-for="i in queueState.total" :key="i"
          :class="['queue-sidebar-item', {
            done: i < queueState.index,
            current: i === queueState.index,
            pending: i > queueState.index
          }]">
          <span class="queue-dot"></span>
          <span>文件 {{ i }}</span>
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
const title = computed(() => route.query.name || (targetId.value === 'solo' ? '主聊天' : targetId.value))
const messages = ref([])
const isRunning = ref(true)
const msgEl = ref(null)
const queueState = ref({ index: 0, total: 0 })
let channel = null

function getIcon(msg) {
  const icons = { '资深作者': '📕', '读者代表': '📙', '剧情架构师': '🏛', '人物设计师': '🎭', '网络编辑': '💼', '系统': '⚙️', '主编': '💬', '讨论总结师': '📋' }
  return icons[msg.expert_type || msg.type] || '📄'
}
function renderMarkdown(text) { return text ? md.render(text) : '' }
function formatTime(ts) { return ts ? new Date(ts).toLocaleTimeString('zh-CN') : '' }

function matchesTarget(data) {
  if (!data) return false
  const cid = data.container_id || data.expert_id || 'solo'
  if (cid === targetId.value) return true
  if (data.node_id === targetId.value) return true
  return false
}

onMounted(() => {
  channel = new BroadcastChannel('meeting-chat')
  channel.onmessage = (event) => {
    const { type, data, timestamp } = event.data || {}
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
      queueState.value = { index: 0, total: data.total || 0 }
      return
    }

    if (type === 'queue_item_start') {
      queueState.value = { index: (data.index || 0) + 1, total: data.total || 0 }
      messages.value = []  // 清空上一份文件的聊天
      return
    }

    if (type === 'queue_item_complete') {
      // 文件处理完成，可以在这里添加完成标记
      return
    }

    if (type === 'running_state') {
      isRunning.value = data.isRunning || false
      return
    }

    if (type === 'queue_item_complete') {
      return
    }

    if (type === 'queue_complete') {
      isRunning.value = false
      queueState.value = { index: data.total || 0, total: data.total || 0 }
      return
    }

    if (type === 'expert_start') {
      if (!matchesTarget(data)) return
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
        last = { type: 'expert', expert_type: data.expert_type || '', content: '', thinking: '', streaming: true,
          timestamp: timestamp || new Date().toISOString() }
        msgs.push(last)
      }
      if (data.chunk_type === 'thinking') {
        last.thinking = (last.thinking || '') + (data.content || '')
      } else if (data.chunk_type === 'content') {
        last.content += data.content || ''
      }
      scrollDown()
      return
    }

    if (type === 'message') {
      if (!matchesTarget(data)) return
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
.queue-sidebar-header { font-size: 0.8rem; font-weight: 600; color: #666; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #eee; }
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
</style>
