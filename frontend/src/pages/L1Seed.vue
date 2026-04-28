<template>
  <div class="l1-seed">
    <!-- 顶部导航栏 -->
    <div class="page-header">
      <div class="header-left">
        <router-link to="/" class="btn btn-back">← 仪表盘</router-link>
        <h1>L1 种子层</h1>
      </div>
      
      <!-- 层导航 -->
      <div class="layer-nav">
        <router-link :to="`/l1?projectId=${projectId}`" class="btn active">L1</router-link>
        <router-link :to="`/l2?projectId=${projectId}`" class="btn">L2</router-link>
        <router-link :to="`/l3?projectId=${projectId}`" class="btn">L3</router-link>
        <router-link :to="`/l4?projectId=${projectId}`" class="btn">L4</router-link>
      </div>
    </div>
    
    <!-- 主内容区 -->
    <div class="main-container" :class="currentView">
      <!-- 左侧面板：对话 -->
      <div 
        v-show="currentView === 'chat' || currentView === 'split'" 
        class="panel chat-panel"
        :style="splitStyle"
      >
        <div class="panel-header">
          <h3>💬 创意对话</h3>
          <span class="hint">AI引导你梳理创意</span>
        </div>
        
        <div class="chat-messages" ref="chatContainer">
          <div 
            v-for="(msg, idx) in chatMessages" 
            :key="idx"
            :class="['message', msg.role]"
          >
            <div class="message-avatar">
              {{ msg.role === 'ai' ? '🤖' : '👤' }}
            </div>
            <div class="message-content">
              <div class="message-text" v-html="renderMarkdown(msg.content)"></div>
              <div class="message-time">{{ formatTime(msg.time) }}</div>
            </div>
          </div>
          
          <!-- AI正在输入 -->
          <div v-if="aiTyping" class="message ai typing">
            <div class="message-avatar">🤖</div>
            <div class="message-content">
              <div class="typing-indicator">
                <span></span><span></span><span></span>
              </div>
            </div>
          </div>
        </div>
        
        <div class="chat-input-area">
          <textarea 
            v-model="userInput" 
            placeholder="输入你的想法..."
            @keydown.enter.prevent="sendMessage"
            :disabled="aiTyping"
          ></textarea>
          <button 
            class="btn btn-primary" 
            @click="sendMessage"
            :disabled="!userInput.trim() || aiTyping"
          >
            发送
          </button>
        </div>
        
        <div class="chat-actions">
          <button class="btn btn-small" @click="resetChat">🔄 重置对话</button>
          <button class="btn btn-small" @click="skipToForm">跳过对话 →</button>
        </div>
      </div>
      
      <!-- 拖动条（仅分屏模式） -->
      <div 
        v-if="currentView === 'split'" 
        class="resizer"
        @mousedown="startResize"
      ></div>
      
      <!-- 右侧面板 -->
      <div 
        v-show="currentView !== 'chat'" 
        class="panel right-panel"
        :style="rightPanelStyle"
      >
        <!-- 右侧标签 -->
        <div class="panel-tabs">
          <button 
            :class="['tab-btn', { active: rightTab === 'form' }]"
            @click="rightTab = 'form'"
          >
            📝 表单
          </button>
          <button 
            :class="['tab-btn', { active: rightTab === 'preview' }]"
            @click="rightTab = 'preview'"
            :disabled="!hasVision"
          >
            👁️ 预览
          </button>
        </div>
        
        <!-- 表单视图 -->
        <div v-show="rightTab === 'form'" class="panel-content form-content">
          <div class="form-header">
            <h3>故事要素</h3>
            <span class="sync-status" :class="{ synced: isSynced }">
              {{ isSynced ? '✓ 已同步' : '○ 待完善' }}
            </span>
          </div>
          
          <div class="form-groups">
            <div class="form-group">
              <label>核心梗/脑洞</label>
              <textarea v-model="form.idea" placeholder="一句话描述故事核心创意" rows="2"></textarea>
            </div>
            
            <div class="form-row">
              <div class="form-group">
                <label>类型</label>
                <input v-model="form.genre" placeholder="如：都市重生">
              </div>
              <div class="form-group">
                <label>核心爽点</label>
                <input v-model="form.core_appeal" placeholder="如：装逼打脸">
              </div>
            </div>
            
            <div class="form-group">
              <label>主角人设</label>
              <input v-model="form.protagonist" placeholder="主角的基本设定">
            </div>
            
            <div class="form-group">
              <label>金手指/核心道具</label>
              <input v-model="form.golden_finger" placeholder="主角的特殊能力">
            </div>
            
            <div class="form-group">
              <label>世界观</label>
              <input v-model="form.world_setting" placeholder="故事背景设定">
            </div>
            
            <div class="form-group">
              <label>风格基调</label>
              <input v-model="form.style" placeholder="如：轻松热血">
            </div>
            
            <div class="form-group">
              <label>粗略大纲</label>
              <textarea v-model="form.rough_outline" placeholder="故事起承转合" rows="3"></textarea>
            </div>
            
            <div class="form-row">
              <div class="form-group">
                <label>目标读者</label>
                <input v-model="form.target_readers" placeholder="如：男频18-35">
              </div>
              <div class="form-group">
                <label>预期字数</label>
                <input v-model="form.expected_length" placeholder="如：200万字">
              </div>
            </div>
          </div>
          
          <div class="form-actions">
            <button class="btn btn-primary" @click="generateVision" :disabled="loading">
              {{ loading ? '生成中...' : '🎯 生成愿景文档' }}
            </button>
            <button class="btn" @click="loadVision">加载已有</button>
          </div>
        </div>
        
        <!-- 预览视图 -->
        <div v-show="rightTab === 'preview'" class="panel-content preview-content">
          <div class="preview-header">
            <h3>愿景文档预览</h3>
            <div class="preview-actions">
              <button class="btn btn-small" @click="toggleRawView">
                {{ showRaw ? '结构化' : '原文' }}
              </button>
              <button class="btn btn-small btn-primary" @click="downloadVision">
                下载
              </button>
            </div>
          </div>
          
          <div v-if="vision" class="preview-body">
            <!-- 结构化展示 - 解析后的Markdown -->
            <div v-if="!showRaw" class="vision-structured" v-html="renderMarkdown(formattedVisionDocument)"></div>
            
            <!-- 原文展示 - 可编辑的Markdown文本 -->
            <textarea v-else class="vision-raw-editor" v-model="editableVisionDocument"></textarea>
          </div>
          
          <div v-else class="preview-empty">
            <p>尚未生成愿景文档</p>
            <button class="btn" @click="rightTab = 'form'">去填写表单 →</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import MarkdownIt from 'markdown-it'

const route = useRoute()
const projectId = computed(() => route.query.projectId)

// Markdown 渲染器
const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true
})

// 渲染 Markdown
const renderMarkdown = (text) => {
  if (!text) return ''
  return md.render(text)
}

// 视图状态 - 默认分屏
const currentView = ref('split')
const rightTab = ref('form')
const showRaw = ref(false)

// 分屏宽度
const leftWidth = ref(50)
const isResizing = ref(false)

// 对话状态
const chatMessages = ref([
  {
    role: 'ai',
    content: '你好！我是你的创作助手。让我们从最简单的开始：**你想写什么类型的小说？**\n\n比如：都市重生、玄幻修仙、科幻未来、历史架空...',
    time: new Date()
  }
])
const userInput = ref('')
const aiTyping = ref(false)
const chatContainer = ref(null)

// 表单状态 - 字段名与后端 VisionDocument 保持一致
const form = ref({
  idea: '',
  genre: '',
  target_readers: '',
  core_appeal: '',
  style: '',
  rough_outline: '',
  world_setting: '',
  protagonist: '',
  golden_finger: '',
  hot_elements: '',
  expected_length: ''
})

const vision = ref(null)
const loading = ref(false)
const editableVisionDocument = ref('')  // 可编辑的原文

// 计算属性
const splitStyle = computed(() => {
  if (currentView.value !== 'split') return {}
  return { width: `${leftWidth.value}%` }
})

const rightPanelStyle = computed(() => {
  if (currentView.value !== 'split') return {}
  return { width: `${100 - leftWidth.value}%` }
})

const hasVision = computed(() => !!vision.value)

const isSynced = computed(() => {
  return form.value.idea && form.value.genre && form.value.protagonist
})

// 计算属性：格式化愿景文档
const formattedVisionDocument = computed(() => {
  if (!vision.value) return ''
  const v = vision.value
  return `# 故事愿景文档

## 核心梗
${v.core_idea || '未设置'}

## 阅读契约
- 目标读者: ${v.target_readers || '未设置'}
- 核心爽点: ${v.core_appeal || '未设置'}
- 风格基调: ${v.style || '未设置'}

## 粗略大纲
${v.rough_outline || '未设置'}

## 核心设定
- 世界观: ${v.world_setting || '未设置'}
- 主角人设: ${v.protagonist || '未设置'}
- 金手指/核心道具: ${v.golden_finger || '未设置'}

## 热点元素
${v.hot_elements || '无'}

## 预期字数
${v.expected_length || '未设置'}

---
生成时间: ${new Date().toLocaleString()}
项目ID: ${projectId.value}
`
})

// 监听格式化文档变化，同步到可编辑文本
watch(formattedVisionDocument, (newDoc) => {
  if (newDoc) {
    editableVisionDocument.value = newDoc
  }
}, { immediate: true })

// 方法
const sendMessage = async () => {
  if (!userInput.value.trim() || aiTyping.value) return
  
  // 添加用户消息
  chatMessages.value.push({
    role: 'user',
    content: userInput.value,
    time: new Date()
  })
  
  const userText = userInput.value
  userInput.value = ''
  
  // 滚动到底部
  await nextTick()
  scrollToBottom()
  
  // AI思考中
  aiTyping.value = true
  
  try {
    // 调用后端API进行对话
    const res = await axios.post(`/api/projects/${projectId.value}/l1/chat`, {
      messages: chatMessages.value.map(m => ({ role: m.role, content: m.content })),
      currentForm: form.value
    })
    
    // AI回复
    chatMessages.value.push({
      role: 'ai',
      content: res.data.reply,
      time: new Date()
    })
    
    // 更新表单（如果AI提取了信息）
    if (res.data.extracted) {
      Object.assign(form.value, res.data.extracted)
    }
    
  } catch (err) {
    // 模拟AI回复（如果没有API）
    setTimeout(() => {
      const reply = generateMockReply(userText)
      chatMessages.value.push({
        role: 'ai',
        content: reply,
        time: new Date()
      })
      
      // 模拟提取信息
      extractFromText(userText)
      
      aiTyping.value = false
      nextTick(scrollToBottom)
    }, 1000)
    return
  }
  
  aiTyping.value = false
  await nextTick()
  scrollToBottom()
}

const generateMockReply = (text) => {
  const responses = [
    '很有趣的想法！那**主角**是什么样的人物？有什么特别的性格或背景吗？',
    '明白了。那主角的**金手指**是什么？或者说他/她有什么特殊能力？',
    '好的。这个故事发生在什么样的**世界观**里？是现代都市还是异世界？',
    '了解了。那你希望这个故事给读者带来什么样的**爽点**？是逆袭打脸还是情感共鸣？',
    '很有潜力！能不能简单描述一下故事的**起承转合**？也就是大概的剧情走向？'
  ]
  return responses[Math.min(chatMessages.value.filter(m => m.role === 'ai').length - 1, responses.length - 1)]
}

const extractFromText = (text) => {
  // 简单的信息提取逻辑
  if (text.includes('重生') || text.includes('穿越')) {
    if (!form.value.genre) form.value.genre = '都市重生'
  }
  if (text.includes('系统')) {
    if (!form.value.golden_finger) form.value.golden_finger = '系统'
  }
  if (text.length > 10 && !form.value.idea) {
    form.value.idea = text.slice(0, 50) + '...'
  }
}

const resetChat = () => {
  if (!confirm('确定要重置对话吗？已收集的信息不会丢失。')) return
  chatMessages.value = [{
    role: 'ai',
    content: '让我们重新开始！**你想写什么类型的小说？**',
    time: new Date()
  }]
}

const skipToForm = () => {
  // 切换到表单标签
  rightTab.value = 'form'
}

const startResize = (e) => {
  isResizing.value = true
  // 防止拖动时选中文本
  document.body.style.userSelect = 'none'
  document.body.style.cursor = 'col-resize'
  document.addEventListener('mousemove', handleResize)
  document.addEventListener('mouseup', stopResize)
}

const handleResize = (e) => {
  if (!isResizing.value) return
  const container = document.querySelector('.main-container')
  if (!container) return
  const rect = container.getBoundingClientRect()
  const percentage = ((e.clientX - rect.left) / rect.width) * 100
  leftWidth.value = Math.max(30, Math.min(70, percentage))
}

const stopResize = () => {
  isResizing.value = false
  document.body.style.userSelect = ''
  document.body.style.cursor = ''
  document.removeEventListener('mousemove', handleResize)
  document.removeEventListener('mouseup', stopResize)
}

const scrollToBottom = () => {
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
}

const toggleRawView = () => {
  console.log('切换前 showRaw:', showRaw.value)
  showRaw.value = !showRaw.value
  console.log('切换后 showRaw:', showRaw.value)
  // 重置预览区域滚动位置
  nextTick(() => {
    const previewBody = document.querySelector('.preview-body')
    if (previewBody) {
      previewBody.scrollTop = 0
    }
  })
}

const formatTime = (date) => {
  return new Date(date).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

const generateVision = async () => {
  if (!projectId.value) return
  loading.value = true
  try {
    const res = await axios.post(`/api/projects/${projectId.value}/l1/generate`, form.value)
    vision.value = res.data.vision
    rightTab.value = 'preview'
  } finally {
    loading.value = false
  }
}

const loadVision = async () => {
  if (!projectId.value) return
  try {
    const res = await axios.get(`/api/projects/${projectId.value}/l1/vision`)
    vision.value = res.data.vision
    // 不覆盖表单，用户填写的内容保留
    rightTab.value = 'preview'
  } catch (e) {
    alert('尚未生成愿景文档')
  }
}

const downloadVision = () => {
  const content = formattedVisionDocument.value
  const blob = new Blob([content], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `故事愿景_${projectId.value}_${new Date().toISOString().split('T')[0]}.md`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

onMounted(() => {
  if (projectId.value) {
    loadVision()
  }
})
</script>

<style scoped>
.l1-seed {
  height: 100%;
  display: flex;
  flex-direction: column;
}

/* 顶部导航 */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  background: white;
  border-bottom: 1px solid #e8e8e8;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.header-left h1 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
}

.btn-back {
  padding: 0.375rem 0.75rem;
  font-size: 0.875rem;
}

/* 标签按钮 */
.tab-btn {
  padding: 0.5rem 1rem;
  border: none;
  background: transparent;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.875rem;
  transition: all 0.2s;
}

.tab-btn:hover {
  background: rgba(0,0,0,0.05);
}

.tab-btn.active {
  background: white;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  font-weight: 500;
}

.tab-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 层导航 */
.layer-nav {
  display: flex;
  gap: 0.25rem;
}

.layer-nav .btn {
  padding: 0.5rem 0.875rem;
  min-width: 2.5rem;
}

.layer-nav .btn.active {
  background: #3498db;
  color: white;
}

/* 主容器 */
.main-container {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.main-container.chat .chat-panel {
  width: 100%;
}

.main-container.form .right-panel,
.main-container.preview .right-panel {
  width: 100%;
}

/* 面板通用样式 */
.panel {
  display: flex;
  flex-direction: column;
  background: white;
  overflow: hidden;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid #e8e8e8;
  flex-shrink: 0;
}

.panel-header h3 {
  margin: 0;
  font-size: 1rem;
}

.hint {
  font-size: 0.75rem;
  color: #999;
}

/* 对话面板 */
.chat-panel {
  flex: 1;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.message {
  display: flex;
  gap: 0.75rem;
  max-width: 85%;
}

.message.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.message-avatar {
  width: 2rem;
  height: 2rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  flex-shrink: 0;
}

.message-content {
  background: #f5f5f5;
  padding: 0.75rem 1rem;
  border-radius: 12px;
  border-top-left-radius: 4px;
}

.message.user .message-content {
  background: #3498db;
  color: white;
  border-top-left-radius: 12px;
  border-top-right-radius: 4px;
}

.message-text {
  line-height: 1.5;
}

.message-time {
  font-size: 0.7rem;
  opacity: 0.6;
  margin-top: 0.25rem;
}

/* 输入中动画 */
.typing-indicator {
  display: flex;
  gap: 0.25rem;
  padding: 0.5rem 0;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  background: #999;
  border-radius: 50%;
  animation: typing 1.4s infinite;
}

.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing {
  0%, 60%, 100% { transform: translateY(0); }
  30% { transform: translateY(-10px); }
}

/* 输入区 */
.chat-input-area {
  display: flex;
  gap: 0.5rem;
  padding: 1rem 1.25rem;
  border-top: 1px solid #e8e8e8;
  background: #fafafa;
}

.chat-input-area textarea {
  flex: 1;
  padding: 0.75rem;
  border: 1px solid #ddd;
  border-radius: 8px;
  resize: none;
  height: 3rem;
  font-family: inherit;
}

.chat-input-area textarea:focus {
  outline: none;
  border-color: #3498db;
}

.chat-actions {
  display: flex;
  justify-content: space-between;
  padding: 0 1.25rem 1rem;
  gap: 0.5rem;
}

.btn-small {
  padding: 0.375rem 0.75rem;
  font-size: 0.75rem;
}

/* 拖动条 */
.resizer {
  width: 8px;
  background: #e8e8e8;
  cursor: col-resize;
  transition: background 0.2s;
  position: relative;
  z-index: 10;
}

.resizer:hover,
.resizer:active {
  background: #3498db;
}

.resizer::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 2px;
  height: 30px;
  background: rgba(0,0,0,0.1);
  border-radius: 1px;
}

/* 右侧面板 */
.right-panel {
  flex: 1;
}

.panel-tabs {
  display: flex;
  border-bottom: 1px solid #e8e8e8;
}

.panel-tabs .tab-btn {
  flex: 1;
  padding: 0.875rem;
  border-bottom: 2px solid transparent;
  border-radius: 0;
}

.panel-tabs .tab-btn.active {
  border-bottom-color: #3498db;
  background: rgba(52, 152, 219, 0.05);
}

.panel-content {
  flex: 1;
  overflow-y: auto;
  padding: 1.25rem;
}

/* 表单内容 */
.form-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.form-header h3 {
  margin: 0;
}

.sync-status {
  font-size: 0.75rem;
  color: #999;
}

.sync-status.synced {
  color: #27ae60;
}

.form-groups {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.form-group label {
  display: block;
  font-size: 0.875rem;
  font-weight: 500;
  margin-bottom: 0.375rem;
  color: #555;
}

.form-group input,
.form-group textarea {
  width: 100%;
  padding: 0.625rem;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-family: inherit;
  font-size: 0.875rem;
}

.form-group input:focus,
.form-group textarea:focus {
  outline: none;
  border-color: #3498db;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.form-actions {
  display: flex;
  gap: 0.75rem;
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid #e8e8e8;
}

/* 预览内容 */
.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.preview-header h3 {
  margin: 0;
}

.preview-actions {
  display: flex;
  gap: 0.5rem;
}

.preview-body {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 1rem;
  max-height: calc(100vh - 300px);
  overflow-y: auto;
  /* 确保滚动条显示 */
  overflow-x: hidden;
}

/* Webkit滚动条样式 */
.preview-body::-webkit-scrollbar {
  width: 8px;
}

.preview-body::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 4px;
}

.preview-body::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 4px;
}

.preview-body::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}

.vision-section {
  margin-bottom: 1.25rem;
  padding-bottom: 1.25rem;
  border-bottom: 1px solid #e8e8e8;
}

.vision-section:last-child {
  border-bottom: none;
  margin-bottom: 0;
}

.vision-section h4 {
  margin: 0 0 0.5rem 0;
  font-size: 0.875rem;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.vision-section p {
  margin: 0;
  line-height: 1.6;
}

.vision-section pre {
  margin: 0;
  white-space: pre-wrap;
  font-family: inherit;
  line-height: 1.6;
}

.vision-raw {
  background: white;
  padding: 1.5rem;
  border-radius: 4px;
  border: 1px solid #e8e8e8;
  font-size: 0.9rem;
  line-height: 1.8;
}

/* 可编辑的原文文本框 */
.vision-raw-editor {
  width: 100%;
  min-height: 400px;
  padding: 1rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-family: 'Courier New', Courier, monospace;
  font-size: 0.875rem;
  line-height: 1.6;
  resize: vertical;
  background: #fafafa;
  color: #333;
}

.vision-raw-editor:focus {
  outline: none;
  border-color: #3498db;
  background: white;
}

/* Markdown 渲染后的样式 */
.vision-raw h1 {
  font-size: 1.5rem;
  margin: 0 0 1rem 0;
  padding-bottom: 0.5rem;
  border-bottom: 2px solid #3498db;
}

.vision-raw h2 {
  font-size: 1.1rem;
  margin: 1.5rem 0 0.75rem 0;
  color: #2c3e50;
}

.vision-raw ul,
.md-content ul {
  margin: 0.5rem 0;
  padding-left: 1.5rem;
}

.vision-raw li,
.md-content li {
  margin: 0.25rem 0;
}

.vision-raw p,
.md-content p {
  margin: 0.5rem 0;
}

.vision-raw hr {
  border: none;
  border-top: 1px solid #e8e8e8;
  margin: 1.5rem 0;
}

/* 结构化视图中的 Markdown 内容 */
.md-content {
  line-height: 1.7;
}

.md-content ol {
  margin: 0.5rem 0;
  padding-left: 1.5rem;
}

.md-content strong {
  color: #2c3e50;
}

.preview-empty {
  text-align: center;
  padding: 3rem 1rem;
  color: #999;
}

.preview-empty p {
  margin-bottom: 1rem;
}

/* 响应式 */
@media (max-width: 1024px) {
  .page-header {
    flex-wrap: wrap;
  }
  
  .main-container.split {
    flex-direction: column;
  }
  
  .resizer {
    display: none;
  }
  
  .chat-panel,
  .right-panel {
    width: 100% !important;
    height: 50%;
  }
}

@media (max-width: 768px) {
  .layer-nav {
    display: none;
  }
  
  .form-row {
    grid-template-columns: 1fr;
  }
}
</style>