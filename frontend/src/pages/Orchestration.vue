<template>
  <div class="orchestration-page">
    <div class="canvas-full">
      <OrchestrationCanvas
        :projectId="projectId"
        :isRunning="isRunning"
        :isPaused="isPaused"
        :pipelineOutput="pipelineOutput"
        :layer="layer"
        @run="onRun"
        @stop="stopMeeting"
        @toggle-pause="togglePause"
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
const layer = computed(() => route.meta.layer || 'l2')

// 从 sessionStorage 恢复状态
const isRunning = ref(sessionStorage.getItem('meetingRunning') === 'true')
const isPaused = ref(false)
const speechCount = ref(0)
const messageBuffer = reactive({})
const queueState = ref({ index: 0, total: 0 })
const pipelineOutput = ref(null)
let chatChannel = null
let pauseResolve = null

onMounted(() => {
  chatChannel = new BroadcastChannel('meeting-chat')
  chatChannel.onmessage = (event) => {
    if (event.data?.type === 'sync') {
      const targetMsgs = messageBuffer[event.data.targetId] || []
      const soloMsgs = messageBuffer['solo'] || []
      const allMsgs = [...soloMsgs, ...targetMsgs]
      for (const m of allMsgs) {
        // 使用JSON序列化/反序列化确保数据可克隆
        const plainMsg = JSON.parse(JSON.stringify(m))
        chatChannel.postMessage({ type: 'message', data: plainMsg, timestamp: m.timestamp })
      }
      // 同步队列状态
      if (queueState.value.total > 0) {
        chatChannel.postMessage({ type: 'queue_state', data: { ...queueState.value } })
      }
      // 如果正在运行，发送运行状态
      if (isRunning.value) {
        chatChannel.postMessage({ type: 'running_state', data: { isRunning: true } })
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
  pipelineOutput.value = null
  sessionStorage.removeItem('pipelineOutput')
  sessionStorage.setItem('meetingRunning', 'true')
  startMeeting(config)
}

function stopMeeting() {
  isRunning.value = false
  isPaused.value = false
  sessionStorage.removeItem('meetingRunning')
  chatChannel?.postMessage({ type: 'done' })
  if (projectId.value) {
    fetch(`/api/projects/${projectId.value}/meeting/feedback`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'stop' })
    }).catch(() => {})
  }
}

function togglePause() {
  isPaused.value = !isPaused.value
  if (!isPaused.value && pauseResolve) {
    pauseResolve()
    pauseResolve = null
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
      // 暂停检查
      if (isPaused.value) {
        await new Promise(resolve => { pauseResolve = resolve })
      }
      
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
  // console.log(`[SSE] ${type}`, data)  // 流太大，调试时再打开
  
  // 统一字段名：expertId -> expert_id, expertType -> expert_type
  const normalizedData = {
    ...data,
    expert_id: data.expert_id || data.expertId,
    expert_type: data.expert_type || data.expertType
  }
  
  switch (type) {
    case 'queue_start':
      console.log(`[QUEUE] 队列开始, 总文件数: ${data.total}`)
      queueState.value = { index: 0, total: data.total || 0 }
      broadcast(type, normalizedData)
      break
    case 'queue_init':
      console.log(`[QUEUE] 初始化节点 ${data.nodeId} 队列, 文件数: ${data.total}`)
      broadcast('queue_init', normalizedData)
      break
    case 'queue_item_start':
      console.log(`[QUEUE] 文件 ${data.index + 1}/${data.total} 开始处理`)
      queueState.value = { index: (data.index || 0) + 1, total: data.total || 0 }
      broadcast(type, normalizedData)
      break
    case 'queue_item_complete':
      console.log(`[QUEUE] 文件 ${data.index + 1}/${data.total} 处理完成`)
      broadcast('queue_item_complete', normalizedData)
      break
    case 'queue_complete':
      console.log(`[QUEUE] 队列完成, 总文件数: ${data.total}`)
      queueState.value = { index: data.total || 0, total: data.total || 0 }
      broadcast(type, normalizedData)
      break
    case 'expert_speak':
      console.log(`[EXPERT] ${normalizedData.expert_type} 完成发言, 文件 ${data.file_index + 1}`)
      speechCount.value = data.speech_count || (speechCount.value + 1)
      broadcast('message', normalizedData)
      break
    case 'expert_chunk':
      broadcast('chunk', normalizedData)
      break
    case 'expert_start':
      console.log(`[EXPERT] ${normalizedData.expert_type} 开始处理文件 ${data.file_index + 1}`)
      speechCount.value = data.speech_count || (speechCount.value + 1)
      broadcast('expert_start', normalizedData)
      break
    case 'pipeline_complete':
      isRunning.value = false
      sessionStorage.removeItem('meetingRunning')
      pipelineOutput.value = data.output // 保存输出数据
      // 持久化完整输出数据供输出页/查看页使用
      if (data.objects) {
        sessionStorage.setItem('pipelineOutput', JSON.stringify({
          objects: data.objects,
          projectId: projectId.value,
          timestamp: new Date().toISOString()
        }))
      }
      // 向output节点发送输出文件列表
      if (data.output) {
        const nodeOutputs = data.output.node_outputs || data.output.nodeOutputs || {}
        console.log('[PIPELINE_COMPLETE] nodeOutputs:', nodeOutputs)
        if (Object.keys(nodeOutputs).length > 0) {
          const outputFiles = Object.entries(nodeOutputs).map(([key, content]) => ({
            name: `${key}.md`,
            content: content
          }))
          console.log('[PIPELINE_COMPLETE] Sending output_files:', outputFiles)
          broadcast('output_files', { files: outputFiles })
        }
      }
      broadcast('done', { output: data.output })
      break
    case 'level_start':
    case 'level_complete':
      broadcast(type, normalizedData)
      break
    // ── v2 Agent 事件 ──
    case 'pipeline_start_v2':
      console.log(`[PIPELINE_V2] 开始, ${data.totalObjects} 对象, ${data.levels} 层级, 节点: ${data.nodes}`)
      pipelineOutput.value = { v2: true, objects: data.objects || [] }
      // 存储会议 ID 供反馈使用
      if (data.meetingId) {
        sessionStorage.setItem('lastMeetingId', data.meetingId)
      }
      broadcast(type, normalizedData)
      break
    case 'object_init':
      console.log(`[PIPELINE_V2] 对象 ${data.objectName} 开始处理`)
      broadcast(type, normalizedData)
      break
    case 'level_start_v2':
      console.log(`[PIPELINE_V2] 层级 ${data.level}/${data.totalLevels}, 对象: ${data.objectName}`)
      broadcast(type, normalizedData)
      break
    case 'agent_start':
      console.log(`[AGENT] ${normalizedData.expertType} 开始 Agent 迭代, 对象: ${data.objectName}`)
      broadcast(type, normalizedData)
      break
    case 'agent_round_start':
      broadcast('agent_round_start', normalizedData)
      break
    case 'agent_chunk':
      broadcast('chunk', { ...normalizedData, chunkType: data.chunkType, content: data.content })
      break
    case 'agent_round_complete':
      broadcast('agent_round_complete', normalizedData)
      break
    case 'agent_complete':
      console.log(`[AGENT] ${normalizedData.expertType} Agent 完成, 轮次: ${data.totalRounds}`)
      broadcast(type, normalizedData)
      break
    case 'agent_error':
      console.error(`[AGENT] ${data.nodeId} error:`, data.error)
      broadcast(type, normalizedData)
      break
    case 'object_progress':
      broadcast('object_progress', normalizedData)
      break
    case 'object_complete':
      console.log(`[PIPELINE_V2] 对象 ${data.objectName} 完成, 状态: ${data.status}`)
      broadcast(type, normalizedData)
      break
    // ── 群聊事件 ──
    case 'group_chat_start':
      console.log(`[GROUP] 群聊 ${data.nodeName || data.nodeId} 开始, 成员: ${data.members}`)
      broadcast(type, normalizedData)
      break
    case 'group_chat_round_start':
      broadcast('group_chat_round_start', normalizedData)
      break
    case 'group_chat_member_start':
      broadcast('group_chat_member_start', normalizedData)
      break
    case 'group_chat_chunk':
      broadcast('group_chat_chunk', { ...normalizedData, chunkType: data.chunkType, content: data.content })
      break
    case 'group_chat_member_complete':
      broadcast('group_chat_member_complete', normalizedData)
      break
    case 'group_chat_round_complete':
      broadcast('group_chat_round_complete', normalizedData)
      break
    case 'group_chat_complete':
      console.log(`[GROUP] 群聊完成, ${data.totalSpeeches} 次发言`)
      broadcast(type, normalizedData)
      break
    case 'group_chat_error':
      console.error(`[GROUP] ${data.nodeId}/${data.expertId} error:`, data.error)
      broadcast(type, normalizedData)
      break
    default:
      broadcast('message', normalizedData)
  }
}

function broadcast(type, data) {
  if (!chatChannel) {
    console.warn('[BROADCAST] chatChannel is null')
    return
  }
  const ts = new Date().toISOString()
  const message = { type, data, timestamp: ts }
  // console.log('[BROADCAST] Sending:', type, data)  // 流太大，调试时再打开
  chatChannel.postMessage(message)
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
