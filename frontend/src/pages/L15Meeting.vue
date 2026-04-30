<template>
  <div class="l1-5-meeting">
    <div class="page-header">
      <h1>L1.5 情节编排层 - 两专家会议</h1>
      <div class="nav-actions">
        <router-link to="/" class="btn">← 返回仪表盘</router-link>
        <div class="layer-nav">
          <router-link :to="`/l1?projectId=${projectId}`" class="btn">L1</router-link>
          <router-link :to="`/l1-5?projectId=${projectId}`" class="btn active">L1.5</router-link>
          <router-link :to="`/l2?projectId=${projectId}`" class="btn">L2</router-link>
          <router-link :to="`/l3?projectId=${projectId}`" class="btn">L3</router-link>
          <router-link :to="`/l4?projectId=${projectId}`" class="btn">L4</router-link>
        </div>
      </div>
    </div>
    
    <div class="meeting-layout">
      <div class="chat-area">
        <div class="messages" ref="messagesContainer">
          <div v-for="(msg, idx) in messages" :key="idx" 
               :class="['message', msg.type, `expert-${msg.expert_type}`]">
            <div class="message-header">
              <span class="expert-icon">{{ getExpertIcon(msg.expert_type) }}</span>
              <span class="expert-name">{{ msg.expert_type || '系统' }}</span>
              <span class="timestamp">{{ formatTime(msg.timestamp) }}</span>
            </div>
            <div class="message-content" v-html="renderMarkdown(msg.content)"></div>
          </div>
        </div>
        
        <div class="input-area">
          <textarea v-model="userInput" placeholder="输入您的意见或指令"></textarea>
          <div class="input-actions">
            <button class="btn btn-success" @click="approve">通过</button>
            <button class="btn btn-primary" @click="sendUserMessage">发送</button>
          </div>
        </div>
      </div>
      
      <div class="sidebar">
        <div class="card">
          <h3>会议状态</h3>
          <p>当前轮次: {{ currentRound }} / {{ maxRounds }}</p>
          <p>协作模式: {{ collaborationMode }}</p>
        </div>
        
        <div class="card">
          <h3>卷纲预览</h3>
          <div v-if="volumePlan && volumePlan.volumes" class="volume-preview">
            <div v-for="(vol, idx) in volumePlan.volumes" :key="idx" class="volume-item">
              <strong>{{ vol.name }}</strong>
            </div>
          </div>
          <p v-else class="empty-hint">等待会议完成</p>
        </div>
        
        <div class="card">
          <h3>操作</h3>
          <button class="btn btn-primary" @click="startMeeting" :disabled="isMeetingRunning">
            {{ isMeetingRunning ? '会议进行中...' : '开始会议' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, computed } from 'vue'
import { useRoute } from 'vue-router'
import MarkdownIt from 'markdown-it'

const route = useRoute()
const projectId = computed(() => route.query.projectId)

const md = new MarkdownIt()

const messages = ref([])
const userInput = ref('')
const currentRound = ref(0)
const maxRounds = ref(3)
const collaborationMode = ref('semi_auto')
const volumePlan = ref(null)
const messagesContainer = ref(null)
const isMeetingRunning = ref(false)
let eventSource = null

const getExpertIcon = (expertType) => {
  const icons = {
    '资深作者': '📕',
    '读者代表': '📙',
    '主编': '💬',
    '系统': '⚙️'
  }
  return icons[expertType] || '📄'
}

const renderMarkdown = (text) => {
  if (!text) return ''
  return md.render(text)
}

const formatTime = (ts) => {
  if (!ts) return ''
  return new Date(ts).toLocaleTimeString('zh-CN')
}

const scrollToBottom = async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

const startMeeting = async () => {
  if (!projectId.value) {
    alert('请先从仪表盘选择项目')
    return
  }
  
  messages.value = []
  currentRound.value = 0
  volumePlan.value = null
  isMeetingRunning.value = true
  
  eventSource = new EventSource(
    `/api/projects/${projectId.value}/l1_5/stream?collaboration_mode=${collaborationMode.value}`
  )
  
  eventSource.addEventListener('round_start', (event) => {
    const data = JSON.parse(event.data)
    currentRound.value = data.round
    messages.value.push({
      type: 'system',
      content: `--- 第 ${data.round} 轮讨论开始 ---`,
      timestamp: new Date().toISOString()
    })
    scrollToBottom()
  })
  
  eventSource.addEventListener('expert_speak', (event) => {
    const data = JSON.parse(event.data)
    messages.value.push({
      type: 'expert',
      expert_type: data.expert_type,
      content: data.content,
      timestamp: new Date().toISOString()
    })
    scrollToBottom()
  })
  
  eventSource.addEventListener('waiting_user', () => {
    messages.value.push({
      type: 'system',
      content: '等待主编决策...',
      timestamp: new Date().toISOString()
    })
    scrollToBottom()
  })
  
  eventSource.addEventListener('volume_plan_ready', (event) => {
    const data = JSON.parse(event.data)
    volumePlan.value = data.volume_plan
    messages.value.push({
      type: 'system',
      content: '会议完成！卷纲已生成。',
      timestamp: new Date().toISOString()
    })
    scrollToBottom()
    isMeetingRunning.value = false
    eventSource.close()
  })
  
  eventSource.addEventListener('done', () => {
    isMeetingRunning.value = false
    eventSource.close()
  })
  
  eventSource.onerror = () => {
    isMeetingRunning.value = false
    if (eventSource) {
      eventSource.close()
    }
  }
}

const approve = async () => {
  if (!isMeetingRunning.value) return
  
  try {
    const response = await fetch(`/api/projects/${projectId.value}/l1_5/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action: 'approve',
        message: ''
      })
    })
    
    messages.value.push({
      type: 'user',
      expert_type: '主编',
      content: '同意当前方案，继续。',
      timestamp: new Date().toISOString()
    })
    scrollToBottom()
  } catch (err) {
    console.error('Approve failed:', err)
  }
}

const sendUserMessage = async () => {
  if (!userInput.value.trim() || !isMeetingRunning.value) return
  
  messages.value.push({
    type: 'user',
    expert_type: '主编',
    content: userInput.value,
    timestamp: new Date().toISOString()
  })
  
  try {
    await fetch(`/api/projects/${projectId.value}/l1_5/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action: 'modify',
        message: userInput.value
      })
    })
  } catch (err) {
    console.error('Send feedback failed:', err)
  }
  
  userInput.value = ''
  scrollToBottom()
}

onMounted(() => {
  if (projectId.value) {
    loadVolumePlan()
  }
})

const loadVolumePlan = async () => {
  try {
    const response = await fetch(`/api/projects/${projectId.value}/l1_5/volume_plan`)
    const data = await response.json()
    if (data.volume_plan) {
      volumePlan.value = data.volume_plan
    }
  } catch (err) {
    console.error('Load volume plan failed:', err)
  }
}
</script>

<style scoped>
.l1-5-meeting {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f5f5f5;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 2rem;
  background: white;
  border-bottom: 1px solid #e0e0e0;
}

.page-header h1 {
  margin: 0;
  font-size: 1.5rem;
}

.nav-actions {
  display: flex;
  gap: 1rem;
  align-items: center;
}

.layer-nav {
  display: flex;
  gap: 0.5rem;
}

.layer-nav .btn {
  padding: 0.5rem 1rem;
  font-size: 0.875rem;
}

.layer-nav .btn.active {
  background: #3498db;
  color: white;
}

.meeting-layout {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: white;
  margin: 1rem;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
}

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

.message-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.expert-icon {
  font-size: 1.25rem;
}

.expert-name {
  font-weight: 600;
  color: #333;
}

.timestamp {
  margin-left: auto;
  font-size: 0.75rem;
  color: #999;
}

.message-content {
  line-height: 1.6;
}

.expert-资深作者 {
  border-left: 3px solid #e74c3c;
}

.expert-读者代表 {
  border-left: 3px solid #f39c12;
}

.expert-主编 {
  border-left: 3px solid #3498db;
  background: #e8f4fd;
}

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

.sidebar {
  width: 300px;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.card {
  background: white;
  padding: 1rem;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.card h3 {
  margin: 0 0 0.75rem 0;
  font-size: 1rem;
  border-bottom: 1px solid #e0e0e0;
  padding-bottom: 0.5rem;
}

.card p {
  margin: 0.5rem 0;
  font-size: 0.875rem;
  color: #666;
}

.volume-preview {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.volume-item {
  padding: 0.5rem;
  background: #f8f9fa;
  border-radius: 4px;
  font-size: 0.875rem;
}

.empty-hint {
  color: #999;
  font-style: italic;
}

.btn {
  padding: 0.5rem 1rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  background: white;
  cursor: pointer;
  text-decoration: none;
  color: #333;
  display: inline-block;
}

.btn:hover {
  background: #f0f0f0;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: #3498db;
  color: white;
  border-color: #3498db;
}

.btn-success {
  background: #27ae60;
  color: white;
  border-color: #27ae60;
}
</style>
