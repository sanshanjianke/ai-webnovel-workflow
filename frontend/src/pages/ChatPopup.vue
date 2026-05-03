<template>
  <div class="chat-popup">
    <div class="popup-header">
      <h2>{{ title }}</h2>
      <span class="popup-status" v-if="isRunning">● 运行中</span>
      <span class="popup-status stopped" v-else>已完成</span>
    </div>
    <div class="popup-messages" ref="msgEl">
      <div v-for="(msg, idx) in messages" :key="idx"
        :class="['message', msg.type]">
        <div class="message-header">
          <span class="expert-icon">{{ getIcon(msg) }}</span>
          <span class="expert-name">{{ msg.expert_type || msg.type }}</span>
          <span class="timestamp">{{ formatTime(msg.timestamp) }}</span>
        </div>
        <div class="message-content" v-html="renderMarkdown(msg.content)"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import MarkdownIt from 'markdown-it'

const route = useRoute()
const md = new MarkdownIt()
const targetId = computed(() => route.query.containerId || route.query.expertId || 'solo')
const title = computed(() => route.query.name || (targetId.value === 'solo' ? '主聊天' : targetId.value))
const messages = ref([])
const isRunning = ref(true)
const msgEl = ref(null)
let channel = null

function getIcon(msg) {
  const icons = { '资深作者': '📕', '读者代表': '📙', '剧情架构师': '🏛', '人物设计师': '🎭', '网络编辑': '💼', '系统': '⚙️', '主编': '💬', '讨论总结师': '📋' }
  return icons[msg.expert_type || msg.type] || '📄'
}
function renderMarkdown(text) { return text ? md.render(text) : '' }
function formatTime(ts) { return ts ? new Date(ts).toLocaleTimeString('zh-CN') : '' }

onMounted(() => {
  channel = new BroadcastChannel('meeting-chat')
  channel.onmessage = (event) => {
    const { type, msg } = event.data || {}
    if (type === 'message' && msg) {
      const cid = msg.container_id || 'solo'
      if (cid === targetId.value) {
        messages.value.push(msg)
        nextTick(() => { if (msgEl.value) msgEl.value.scrollTop = msgEl.value.scrollHeight })
      }
    } else if (type === 'done') {
      isRunning.value = false
    }
  }
  // Request existing messages from main window
  channel.postMessage({ type: 'sync', targetId: targetId.value })
})

onUnmounted(() => {
  if (channel) { channel.close(); channel = null }
})
</script>

<style scoped>
.chat-popup {
  height: 100vh; display: flex; flex-direction: column; background: #f5f5f5;
}
.popup-header {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 16px; background: white; border-bottom: 1px solid #e0e0e0;
}
.popup-header h2 { margin: 0; font-size: 1rem; }
.popup-status { font-size: 0.75rem; color: #27ae60; font-weight: 600; }
.popup-status.stopped { color: #999; }
.popup-messages {
  flex: 1; overflow-y: auto; padding: 1rem;
}
.message {
  margin-bottom: 1rem; padding: 0.75rem; border-radius: 8px; background: white;
  box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}
.message.system { background: #e3f2fd; text-align: center; font-style: italic; color: #666; }
.message.user { background: #e8f4fd; border-left: 3px solid #3498db; }
.message-header { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem; }
.expert-icon { font-size: 1.1rem; }
.expert-name { font-weight: 600; color: #333; font-size: 0.9rem; }
.timestamp { margin-left: auto; font-size: 0.75rem; color: #999; }
.message-content { line-height: 1.6; font-size: 0.9rem; }
</style>
