<template>
  <div class="l2-meeting">
    <div class="page-header">
      <h1>L2 架构层 - 专家会议</h1>
      <div class="nav-actions">
        <router-link to="/" class="btn">← 返回仪表盘</router-link>
        <div class="layer-nav">
          <router-link :to="`/l1?projectId=${projectId}`" class="btn">L1</router-link>
          <router-link :to="`/l2?projectId=${projectId}`" class="btn active">L2</router-link>
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
          <h3>精修大纲预览</h3>
          <div v-if="outline" class="outline-preview">
            <div v-for="seq in outline.sequences" :key="seq.name" class="sequence-item">
              {{ seq.name }}
            </div>
          </div>
          <p v-else class="empty-hint">等待会议完成</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, computed } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import MarkdownIt from 'markdown-it'

const route = useRoute()
const projectId = computed(() => route.query.projectId)

const md = new MarkdownIt()

const messages = ref([])
const userInput = ref('')
const currentRound = ref(0)
const maxRounds = ref(3)
const collaborationMode = ref('semi_auto')
const outline = ref(null)
const messagesContainer = ref(null)

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
  outline.value = null
  
  const eventSource = new EventSource(
    `/api/projects/${projectId.value}/l2/stream?collaboration_mode=${collaborationMode.value}`
  )
  
  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      handleMessage(data)
    } catch (e) {
      console.error('Parse error:', e)
    }
  }
  
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
  
  eventSource.addEventListener('outline_ready', (event) => {
    const data = JSON.parse(event.data)
    outline.value = data.outline
    messages.value.push({
      type: 'system',
      content: '会议完成！精修大纲已生成。',
      timestamp: new Date().toISOString()
    })
    scrollToBottom()
    eventSource.close()
  })
  
  eventSource.addEventListener('done', () => {
    eventSource.close()
  })
  
  eventSource.onerror = () => {
    eventSource.close()
  }
}

const handleMessage = (data) => {
  if (data.type === 'waiting_user') {
    messages.value.push({
      type: 'system',
      content: '等待主编决策...',
      timestamp: new Date().toISOString()
    })
    scrollToBottom()
  }
}

const approve = async () => {
  await axios.post(`/api/projects/${projectId.value}/l2/feedback`, {
    action: 'approve',
    message: ''
  })
  messages.value.push({
    type: 'user',
    expert_type: '主编',
    content: '同意当前方案，继续。',
    timestamp: new Date().toISOString()
  })
  scrollToBottom()
}

const sendUserMessage = async () => {
  if (!userInput.value.trim()) return
  
  messages.value.push({
    type: 'user',
    expert_type: '主编',
    content: userInput.value,
    timestamp: new Date().toISOString()
  })
  
  await axios.post(`/api/projects/${projectId.value}/l2/feedback`, {
    action: 'modify',
    message: userInput.value
  })
  
  userInput.value = ''
  scrollToBottom()
}

onMounted(startMeeting)
</script>

<style scoped>
.l2-meeting {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  padding: 1.5rem;
}

.l2-meeting h1 {
  margin-bottom: 1.5rem;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
  gap: 1rem;
  flex-shrink: 0;
}

.page-header h1 {
  margin: 0;
}

.nav-actions {
  display: flex;
  gap: 1rem;
  align-items: center;
}

.layer-nav {
  display: flex;
  gap: 0.25rem;
}

.layer-nav .btn {
  padding: 0.5rem 1rem;
  min-width: 3rem;
}

.layer-nav .btn.active {
  background: #3498db;
  color: white;
}

.meeting-layout {
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: 1.5rem;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.chat-area {
  display: flex;
  flex-direction: column;
  background: white;
  border-radius: 8px;
  overflow: hidden;
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
}

.message.system {
  background: #f0f0f0;
  text-align: center;
  font-size: 0.875rem;
  color: #666;
}

.message.expert {
  background: #f8f9fa;
}

.message.user {
  background: #e3f2fd;
}

.message-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.5rem;
  font-size: 0.75rem;
}

.expert-name {
  font-weight: bold;
}

.timestamp {
  color: #999;
}

.input-area {
  padding: 1rem;
  border-top: 1px solid #eee;
}

.input-area textarea {
  width: 100%;
  min-height: 60px;
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  resize: none;
  margin-bottom: 0.5rem;
}

.input-actions {
  display: flex;
  gap: 0.5rem;
}

.sidebar .card {
  margin-bottom: 1rem;
}

.outline-preview {
  font-size: 0.875rem;
}

.sequence-item {
  padding: 0.5rem;
  background: #f5f5f5;
  border-radius: 4px;
  margin-bottom: 0.5rem;
}

.empty-hint {
  color: #999;
  font-size: 0.875rem;
}

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
  }
  
  .nav-actions {
    width: 100%;
    flex-wrap: wrap;
  }
  
  .meeting-layout {
    grid-template-columns: 1fr;
  }
}
</style>
