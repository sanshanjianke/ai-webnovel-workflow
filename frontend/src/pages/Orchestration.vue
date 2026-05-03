<template>
  <div class="orchestration-page">
    <div class="canvas-full">
      <OrchestrationCanvas 
        :projectId="projectId" 
        :isRunning="isRunning"
        @run="onRun"
      />
    </div>
    <div class="pipeline-status" v-if="isRunning">
      <span class="status-dot running"></span>
      <span>运行中 · 发言 {{ speechCount }}</span>
      <button class="btn btn-warning btn-sm" @click="stopMeeting">停止</button>
      <span class="status-hint">右键节点 → 打开聊天窗口查看输出</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, reactive } from 'vue'
import { useRoute } from 'vue-router'
import OrchestrationCanvas from '../components/OrchestrationCanvas.vue'

const route = useRoute()
const projectId = computed(() => route.query.projectId || '')

const isRunning = ref(false)
const speechCount = ref(0)
const messageBuffer = reactive({})
const queueState = ref({ index: 0, total: 0 })
let chatChannel = null

onMounted(() => {
  chatChannel = new BroadcastChannel('meeting-chat')
  chatChannel.onmessage = (event) => {
    if (event.data?.type === 'sync') {
      const msgs = messageBuffer[event.data.targetId] || []
      for (const m of msgs) {
        chatChannel.postMessage({ type: 'message', data: m, timestamp: m.timestamp })
      }
      // 同步队列状态
      if (queueState.value.total > 0) {
        chatChannel.postMessage({ type: 'queue_state', data: queueState.value })
      }
    }
  }
})

onUnmounted(() => {
  if (chatChannel) { chatChannel.close(); chatChannel = null }
})

function onRun(config) {
  for (const key of Object.keys(messageBuffer)) delete messageBuffer[key]
  speechCount.value = 0
  isRunning.value = true
  startMeeting(config)
}

function stopMeeting() {
  isRunning.value = false
  chatChannel?.postMessage({ type: 'done' })
  if (projectId.value) {
    fetch(`/api/projects/${projectId.value}/meeting/feedback`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'stop' })
    }).catch(() => {})
  }
}

async function startMeeting(config) {
  const url = `/api/projects/${projectId.value}/meeting/start`
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config)
    })
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      let eventType = ''
      for (const line of lines) {
        if (!line.trim()) { eventType = ''; continue }
        if (line.startsWith('event: ')) { eventType = line.slice(7).trim() }
        else if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))
            const type = eventType || data.type || 'message'
            handleSSEEvent(type, data)
          } catch (e) {}
          eventType = ''
        }
      }
    }
  } catch (err) {
    console.error('Meeting error:', err)
    isRunning.value = false
  }
}

function handleSSEEvent(type, data) {
  switch (type) {
    case 'queue_start':
    case 'queue_item_start':
      queueState.value = { index: (data.index || 0) + 1, total: data.total || 0 }
      broadcast(type, data)
      break
    case 'queue_complete':
      queueState.value = { index: data.total || 0, total: data.total || 0 }
      broadcast(type, data)
      break
    case 'expert_speak':
      speechCount.value = data.speech_count || (speechCount.value + 1)
      broadcast('message', data)
      break
    case 'expert_chunk':
      broadcast('chunk', data)
      break
    case 'expert_start':
      speechCount.value = data.speech_count || (speechCount.value + 1)
      broadcast('expert_start', data)
      break
    case 'pipeline_complete':
      isRunning.value = false
      broadcast('done', { output: data.output })
      break
    case 'level_start':
    case 'level_complete':
      broadcast(type, data)
      break
    default:
      broadcast('message', data)
  }
}

function broadcast(type, data) {
  if (!chatChannel) return
  const ts = new Date().toISOString()
  chatChannel.postMessage({ type, data, timestamp: ts })
  // 缓冲消息以供新打开的窗口同步
  const cid = data.container_id || data.expert_id || data.node_id || 'solo'
  if (!messageBuffer[cid]) messageBuffer[cid] = []
  messageBuffer[cid].push({ ...data, type, timestamp: ts })
  // 只保留最近 50 条
  if (messageBuffer[cid].length > 50) messageBuffer[cid].shift()
}
</script>

<style scoped>
.orchestration-page { height: calc(100vh - 42px); display: flex; flex-direction: column; overflow: hidden; }
.canvas-full { flex: 1; min-height: 0; }
.pipeline-status {
  display: flex; align-items: center; gap: 12px;
  padding: 8px 16px; background: #fff; border-top: 1px solid #e0e0e0;
  font-size: 0.85rem;
}
.status-dot { width: 10px; height: 10px; border-radius: 50%; background: #ccc; }
.status-dot.running { background: #27ae60; animation: pulse 1s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }
.status-hint { margin-left: auto; color: #999; font-size: 0.75rem; }
.btn { padding: 4px 12px; border: 1px solid #ddd; border-radius: 4px; cursor: pointer; font-size: 0.8rem; background: white; }
.btn-warning { background: #f39c12; color: white; border-color: #f39c12; }
</style>
