<template>
  <div class="orchestration-meeting">
    <div v-if="viewMode === 'canvas'" class="canvas-view">
      <OrchestrationCanvas 
        :projectId="projectId" 
        @run="onCanvasRun" 
      />
    </div>

    <div v-else class="meeting-view">
      <div class="meeting-header">
        <button class="btn btn-outline" @click="backToCanvas">← 返回编排</button>
        <h2>{{ meetingConfig.meeting_name || '专家会议' }}</h2>
      </div>

      <div class="meeting-layout">
        <div class="chat-area">
          <!-- 聊天标签栏 -->
          <div class="chat-tabs" v-if="chatGroups.length > 1">
            <button 
              v-for="g in chatGroups" :key="g.key"
              :class="['chat-tab', { active: activeChat === g.key }]"
              @click="activeChat = g.key"
            >
              <span class="tab-icon">{{ g.icon }}</span>
              <span class="tab-name">{{ g.name }}</span>
              <span class="tab-badge" v-if="g.unread > 0">{{ g.unread }}</span>
            </button>
          </div>

          <div class="messages" ref="messagesContainers">
            <div v-for="(msg, idx) in activeMessages" :key="idx"
              :class="['message', msg.type, ...expertClass(msg)]">
              <div class="message-header">
                <span class="expert-icon">{{ getIcon(msg) }}</span>
                <span class="expert-name">{{ msg.expert_type || msg.type }}</span>
                <span class="timestamp">{{ formatTime(msg.timestamp) }}</span>
              </div>
              <div class="message-content" v-html="renderMarkdown(msg.content)"></div>
            </div>
          </div>

          <div class="input-area" v-if="isRunning">
            <textarea v-model="userInput" placeholder="输入意见，或用 @专家名 点名..."></textarea>
            <div class="input-actions">
              <button class="btn btn-success" @click="sendFeedback('approve')">通过 ✓</button>
              <button class="btn btn-primary" @click="sendFeedback('modify')">发送</button>
              <button class="btn btn-warning" @click="sendFeedback('stop')">停止</button>
              <button class="btn btn-outline btn-sm" @click="sendFeedback('restart')">重开</button>
            </div>
            <div class="call-expert-row" v-if="meetingConfig.experts.length > 0">
              <select v-model="callExpertId" class="call-expert-select">
                <option value="">-- 点名专家 --</option>
                <option v-for="exp in meetingConfig.experts" :key="exp.expert_id" :value="exp.expert_id">
                  {{ getExpertLabel(exp.expert_id) }}
                </option>
              </select>
              <button class="btn btn-outline btn-sm" @click="callExpert" :disabled="!callExpertId">点名</button>
            </div>
          </div>
        </div>

        <div class="meeting-sidebar">
          <div class="card">
            <h3>会议信息</h3>
            <p>状态: {{ isRunning ? '运行中' : '已完成' }}</p>
            <p>发言次数: {{ speechCount }}</p>
          </div>

          <div class="card">
            <h3>专家队列</h3>
            <div v-for="(exp, idx) in meetingConfig.experts" :key="idx" class="expert-queue-item">
              <span class="queue-num">{{ idx + 1 }}</span>
              <span>{{ getExpertLabel(exp.expert_id) }}</span>
              <span class="queue-role">({{ exp.role }})</span>
              <span class="queue-container" v-if="exp.container_id">📦</span>
            </div>
          </div>

          <div class="card" v-if="meetingOutput">
            <h3>产出</h3>
            <div class="output-preview" v-html="renderMarkdown(meetingOutput.meeting_summary || '无内容')"></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, reactive, watch } from 'vue'
import MarkdownIt from 'markdown-it'
import { useRoute } from 'vue-router'
import OrchestrationCanvas from '../components/OrchestrationCanvas.vue'

const route = useRoute()
const projectId = computed(() => route.query.projectId || '')

const md = new MarkdownIt()
const viewMode = ref('canvas')
const userInput = ref('')
const currentRound = ref(0)
const speechCount = ref(0)
const isRunning = ref(false)
const meetingOutput = ref(null)
const messagesContainers = ref(null)
const activeChat = ref('solo')
const readMessages = reactive({})

let eventSource = null

const meetingConfig = ref({
  meeting_name: '专家会议',
  experts: [],
  containers: []
})

const callExpertId = ref('')

// 按容器分组的消息
const messagesByContainer = reactive({})

// 容器信息缓存
const containerInfo = ref({})

const chatGroups = computed(() => {
  const groups = []
  // 容器群聊
  for (const c of (meetingConfig.value.containers || [])) {
    const key = c.container_id
    const msgs = messagesByContainer[key] || []
    const unread = readMessages[key] != null ? msgs.filter((_, i) => i > (readMessages[key] || -1)).length : 0
    groups.push({ key, name: c.name || '容器', icon: '📦', unread })
  }
  // 未归属专家（solo）
  const soloMsgs = messagesByContainer['solo'] || []
  if (soloMsgs.length > 0 || groups.length === 0) {
    const unread = readMessages['solo'] != null ? soloMsgs.filter((_, i) => soloMsgs.length - 1 > (readMessages['solo'] || 0)).length : 0
    groups.unshift({ key: 'solo', name: '主聊天', icon: '💬', unread })
  }
  return groups
})

const activeMessages = computed(() => messagesByContainer[activeChat.value] || [])

function onCanvasRun(config) {
  meetingConfig.value = config
  containerInfo.value = {}
  for (const c of config.containers || []) {
    containerInfo.value[c.container_id] = { name: c.name, chat_mode: 'group' }
  }
  viewMode.value = 'meeting'
  startMeeting()
}

function backToCanvas() {
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
  isRunning.value = false
  viewMode.value = 'canvas'
}

function routeMessage(msg) {
  const cid = msg.container_id || 'solo'
  if (!messagesByContainer[cid]) messagesByContainer[cid] = []
  messagesByContainer[cid].push(msg)

  // 自动切换标签到有新消息的聊天
  if (!isRunning.value || activeChat.value === cid) {
    markRead(cid)
  }
}

function markRead(cid) {
  const msgs = messagesByContainer[cid]
  if (msgs) readMessages[cid] = msgs.length - 1
}

watch(activeChat, (cid) => {
  if (cid) markRead(cid)
})

async function startMeeting() {
  // 清空旧消息
  for (const key of Object.keys(messagesByContainer)) delete messagesByContainer[key]
  for (const key of Object.keys(readMessages)) delete readMessages[key]
  activeChat.value = 'solo'

  currentRound.value = 0
  meetingOutput.value = null
  isRunning.value = true

  const url = `/api/projects/${projectId.value}/meeting/start`

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(meetingConfig.value)
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
        if (line.startsWith('event: ')) {
          eventType = line.slice(7).trim()
        } else if (line.startsWith('data: ') && eventType) {
          try {
            const data = JSON.parse(line.slice(6))
            handleSSEEvent(eventType, data)
          } catch (e) {
            console.warn('Parse error:', e)
          }
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
    case 'round_start':
      currentRound.value = data.round || data.round_num || (currentRound.value + 1)
      speechCount.value = data.speech_count || speechCount.value
      routeMessage({
        type: 'system',
        content: `--- 第 ${currentRound.value} 轮 · ${speechCount.value} 次发言 ---`,
        timestamp: new Date().toISOString()
      })
      break

    case 'expert_speak':
      speechCount.value = data.speech_count || speechCount.value
      routeMessage({
        type: 'expert',
        expert_type: data.expert_type,
        content: data.content,
        container_id: data.container_id,
        timestamp: new Date().toISOString()
      })
      if (data.mention) {
        routeMessage({
          type: 'system',
          content: `→ @${getExpertLabel(data.mention)} 被提及，接下来将点名发言`,
          container_id: data.container_id,
          timestamp: new Date().toISOString()
        })
      }
      break

    case 'summarizer':
      routeMessage({
        type: 'summarizer',
        expert_type: '讨论总结师',
        content: data.content,
        container_id: data.container_id,
        timestamp: new Date().toISOString()
      })
      break

    case 'mention_detected':
      routeMessage({
        type: 'system',
        content: `→ ${data.from} 点名了 @${getExpertLabel(data.to)}`,
        container_id: data.container_id,
        timestamp: new Date().toISOString()
      })
      break

    case 'waiting_user':
      routeMessage({
        type: 'system',
        content: `⏳ 等待决策（已发言 ${data.speech_count || speechCount.value} 次）`,
        timestamp: new Date().toISOString()
      })
      break

    case 'user_call_expert':
      routeMessage({
        type: 'system',
        content: `→ 主编点名 @${getExpertLabel(data.expert_id)}`,
        container_id: data.container_id,
        timestamp: new Date().toISOString()
      })
      break

    case 'meeting_restarted':
      routeMessage({
        type: 'system',
        content: '--- 会议已重开 ---',
        timestamp: new Date().toISOString()
      })
      for (const key of Object.keys(messagesByContainer)) delete messagesByContainer[key]
      speechCount.value = 0
      currentRound.value = 0
      break

    case 'output_ready':
      meetingOutput.value = data.output
      routeMessage({
        type: 'system',
        content: `会议完成！共 ${data.speech_count || 0} 次发言。`,
        timestamp: new Date().toISOString()
      })
      isRunning.value = false
      break

    case 'done':
      isRunning.value = false
      break

    case 'user_feedback':
      routeMessage({
        type: 'user',
        expert_type: '主编',
        content: `已处理: ${data.action || '操作'}`,
        timestamp: new Date().toISOString()
      })
      break
  }
  scrollToBottom()
}

async function sendFeedback(action) {
  const message = action === 'modify' ? userInput.value : ''
  const body = { action, message }
  try {
    await fetch(`/api/projects/${projectId.value}/meeting/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })

    const labels = { approve: '同意继续', modify: '已发送意见', stop: '已停止', restart: '重新开始' }
    routeMessage({
      type: 'user',
      expert_type: '主编',
      content: labels[action] || `操作: ${action}`,
      timestamp: new Date().toISOString()
    })
    userInput.value = ''
    scrollToBottom()
  } catch (err) {
    console.error('Feedback error:', err)
  }
}

async function callExpert() {
  if (!callExpertId.value) return
  try {
    await fetch(`/api/projects/${projectId.value}/meeting/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'call_expert', expert_id: callExpertId.value })
    })
    routeMessage({
      type: 'user',
      expert_type: '主编',
      content: `点名 @${getExpertLabel(callExpertId.value)}`,
      timestamp: new Date().toISOString()
    })
    callExpertId.value = ''
    scrollToBottom()
  } catch (err) {
    console.error('Call expert error:', err)
  }
}

async function scrollToBottom() {
  await nextTick()
  const el = document.querySelector('.chat-area .messages')
  if (el) el.scrollTop = el.scrollHeight
}

function getIcon(msg) {
  const icons = {
    '资深作者': '📕', '读者代表': '📙', '剧情架构师': '🏛',
    '人物设计师': '🎭', '网络编辑': '💼', '系统': '⚙️', '主编': '💬',
    '讨论总结师': '📋'
  }
  return icons[msg.expert_type || msg.type] || '📄'
}

function expertClass(msg) {
  if (msg.expert_type) return [`expert-${msg.expert_type}`]
  return []
}

function getExpertLabel(id) {
  const labels = {
    'senior_author_v1': '资深作者',
    'reader_representative_v1': '读者代表',
    'plot_architect_v1': '剧情架构师',
    'character_designer_v1': '人物设计师',
    'web_editor_v1': '网络编辑'
  }
  return labels[id] || id
}

function renderMarkdown(text) {
  if (!text) return ''
  return md.render(text)
}

function formatTime(ts) {
  if (!ts) return ''
  return new Date(ts).toLocaleTimeString('zh-CN')
}
</script>

<style scoped>
.orchestration-meeting { height: calc(100vh - 42px); display: flex; flex-direction: column; }
.canvas-view { flex: 1; display: flex; flex-direction: column; overflow: hidden; }

.meeting-view { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.meeting-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  background: white;
  border-bottom: 1px solid #e0e0e0;
}
.meeting-header h2 { margin: 0; font-size: 1.1rem; }

.meeting-layout { flex: 1; display: flex; overflow: hidden; }

.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: white;
  margin: 0.5rem;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

.chat-tabs {
  display: flex;
  gap: 2px;
  padding: 6px 6px 0 6px;
  border-bottom: 1px solid #e0e0e0;
  overflow-x: auto;
}
.chat-tab {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border: 1px solid transparent;
  border-bottom: none;
  border-radius: 8px 8px 0 0;
  background: transparent;
  cursor: pointer;
  font-size: 0.8rem;
  white-space: nowrap;
  transition: all 0.15s;
}
.chat-tab:hover { background: #f5f5f5; }
.chat-tab.active {
  background: white;
  border-color: #e0e0e0;
  font-weight: 600;
}
.tab-icon { font-size: 0.9rem; }
.tab-name { color: #333; }
.tab-badge {
  background: #e74c3c;
  color: white;
  border-radius: 10px;
  padding: 0 6px;
  font-size: 0.65rem;
  font-weight: 600;
  min-width: 16px;
  text-align: center;
}

.messages { flex: 1; overflow-y: auto; padding: 1rem; }
.message {
  margin-bottom: 1rem;
  padding: 0.75rem;
  border-radius: 8px;
  background: #f8f9fa;
}
.message.system {
  background: #e3f2fd;
  text-align: center;
  font-style: italic;
  color: #666;
}
.message.user {
  background: #e8f4fd;
  border-left: 3px solid #3498db;
}
.message.summarizer {
  background: #fce4ec;
  border-left: 3px solid #e91e63;
}
.message-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}
.expert-icon { font-size: 1.25rem; }
.expert-name { font-weight: 600; color: #333; }
.timestamp { margin-left: auto; font-size: 0.75rem; color: #999; }
.message-content { line-height: 1.6; }

.input-area {
  padding: 1rem;
  border-top: 1px solid #e0e0e0;
  display: flex;
  gap: 1rem;
}
.input-area textarea {
  flex: 1;
  padding: 0.75rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  resize: none;
  font-family: inherit;
}
.input-actions {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.meeting-sidebar {
  width: 280px;
  padding: 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  overflow-y: auto;
}
.card {
  background: white;
  padding: 1rem;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
.card h3 { margin: 0 0 0.5rem 0; font-size: 0.9rem; border-bottom: 1px solid #eee; padding-bottom: 0.4rem; }
.card p { margin: 0.3rem 0; font-size: 0.8rem; color: #666; }

.expert-queue-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
  font-size: 0.8rem;
}
.queue-num {
  background: #3498db;
  color: white;
  border-radius: 50%;
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.65rem;
}
.queue-role { color: #999; }
.queue-container { font-size: 0.8rem; opacity: 0.5; margin-left: auto; }

.output-preview {
  font-size: 0.8rem;
  max-height: 300px;
  overflow-y: auto;
}

.btn {
  padding: 0.5rem 1rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.875rem;
  background: white;
}
.btn-outline { background: white; color: #666; }
.btn-primary { background: #3498db; color: white; border-color: #3498db; }
.btn-success { background: #27ae60; color: white; border-color: #27ae60; }
.btn-warning { background: #f39c12; color: white; border-color: #f39c12; }
.btn-sm { padding: 4px 10px; font-size: 0.75rem; }
.call-expert-row {
  display: flex;
  gap: 6px;
  margin-top: 8px;
  align-items: center;
}
.call-expert-select {
  flex: 1;
  padding: 6px 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 0.8rem;
}
</style>
