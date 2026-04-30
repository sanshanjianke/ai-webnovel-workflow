<template>
  <div class="l1-seed">
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
          <div class="header-actions">
            <button class="btn btn-small" @click="openContextDialog">📄 上下文</button>
            <button class="btn btn-small" @click="resetChat">🔄 重置</button>
            <button class="btn btn-small" @click="showSettings = true">⚙️ 设置</button>
          </div>
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
              <!-- 思考过程（可折叠） -->
              <div v-if="msg.thinking" class="message-thinking">
                <div class="thinking-header" @click="msg.showThinking = !msg.showThinking">
                  <span class="thinking-icon">{{ msg.showThinking ? '▼' : '▶' }}</span>
                  <span>思考过程</span>
                </div>
                <div v-show="msg.showThinking" class="thinking-content" v-html="renderMarkdown(msg.thinking)"></div>
              </div>
              <!-- 用户消息编辑 -->
              <template v-if="msg.editing && msg.role === 'user'">
                <textarea v-model="msg.editContent" class="edit-textarea"></textarea>
                <div class="edit-actions">
                  <button class="btn-small btn-primary" @click="saveEditAndGenerate(idx)">保存并生成</button>
                  <button class="btn-small" @click="saveEditOnly(idx)">仅保存</button>
                  <button class="btn-small" @click="cancelEdit(idx)">取消</button>
                </div>
              </template>
              <!-- AI消息编辑 -->
              <template v-else-if="msg.editing && msg.role === 'ai'">
                <textarea v-model="msg.editContent" class="edit-textarea"></textarea>
                <div class="edit-actions">
                  <button class="btn-small btn-primary" @click="saveEditOnly(idx)">保存</button>
                  <button class="btn-small" @click="cancelEdit(idx)">取消</button>
                </div>
              </template>
              <!-- 消息内容 -->
              <template v-else>
                <div class="message-text" v-html="renderMarkdown(msg.content)"></div>
              </template>
              <!-- 消息操作 -->
              <div class="message-actions">
                <div class="message-time">{{ formatTime(msg.time) }}</div>
                <button v-if="!msg.editing" 
                        class="btn-edit" 
                        @click="startEdit(idx)">
                  ✏️ 编辑
                </button>
                <button 
                        class="btn-delete" 
                        @click="deleteMessage(idx)"
                        :disabled="aiTyping">
                  🗑️ 删除
                </button>
                <button v-if="msg.role === 'ai' && idx === chatMessages.length - 1" 
                        class="btn-regenerate" 
                        @click="regenerateMessage(idx)"
                        :disabled="aiTyping">
                  🔄 重新生成
                </button>
              </div>
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
            ref="inputTextarea"
            v-model="userInput" 
            :placeholder="inputPlaceholder"
            @keydown.enter="handleEnterKey"
            @input="adjustTextareaHeight"
            @dblclick="handleTextareaDblClick"
            @dragover.prevent="onDragOver"
            @dragleave="onDragLeave"
            @drop.prevent="onDrop"
            :disabled="aiTyping"
            :class="{ 'drag-over': isDragOver }"
          ></textarea>
          <button 
            class="btn btn-primary" 
            @click="sendMessage"
            :disabled="!userInput.trim() || aiTyping"
          >
            发送
          </button>
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
              <button v-if="showRaw" class="btn btn-small" @click="saveVisionEdit">保存</button>
              <button class="btn btn-small btn-primary" @click="downloadVision">
                下载
              </button>
            </div>
          </div>
          
          <div 
            v-if="vision" 
            class="preview-body"
            @dragover.prevent="onVisionDragOver"
            @dragleave="onVisionDragLeave"
            @drop.prevent="onVisionDrop"
            :class="{ 'drag-over': isVisionDragOver }"
          >
            <!-- 结构化展示 - 解析后的Markdown -->
            <div v-if="!showRaw" class="vision-structured" v-html="renderMarkdown(formattedVisionDocument)"></div>
            
            <!-- 原文展示 - 可编辑的Markdown文本 -->
            <textarea v-else class="vision-raw-editor" v-model="editableVisionDocument"></textarea>
          </div>
          
          <div v-else class="preview-empty">
            <p>尚未生成愿景文档</p>
            <p class="hint">可从文档库拖入文件导入</p>
            <button class="btn" @click="rightTab = 'form'">去填写表单 →</button>
          </div>
        </div>
      </div>
    </div>
  </div>
  
  <!-- 设置弹窗 -->
  <teleport to="body">
    <div v-if="showSettings" class="settings-modal" @click="closeSettings">
      <div class="settings-panel" @click.stop>
        <div class="settings-header">
          <h3>⚙️ 对话设置</h3>
          <button class="btn-close" @click="closeSettings">×</button>
        </div>
        <div class="settings-body">
          <div class="settings-section">
            <h4>AI 模型</h4>
            <select v-model="chatSettings.model">
              <option value="default">默认模型</option>
              <option value="gpt4">GPT-4</option>
              <option value="claude">Claude</option>
            </select>
          </div>
          <div class="settings-section">
            <h4>字体大小</h4>
            <select v-model="chatSettings.fontSize">
              <option value="12px">小</option>
              <option value="14px">中</option>
              <option value="16px">大</option>
            </select>
          </div>
          <div class="settings-section">
            <h4>字体</h4>
            <select v-model="chatSettings.fontFamily">
              <option value="system-ui">系统默认</option>
              <option value="serif">衬线体</option>
              <option value="monospace">等宽体</option>
            </select>
          </div>
        </div>
        <div class="settings-footer">
          <button class="btn btn-primary" @click="closeSettings">确定</button>
        </div>
      </div>
    </div>
  </teleport>
  
  <!-- 上下文查看弹窗 -->
  <teleport to="body">
    <div v-if="showContextDialog" class="settings-modal" @click="showContextDialog = false">
      <div class="context-panel" @click.stop>
        <div class="settings-header">
          <h3>📄 API上下文</h3>
          <button class="btn-close" @click="showContextDialog = false">×</button>
        </div>
        <div class="context-body">
          <pre class="context-content">{{ fullContextText }}</pre>
        </div>
        <div class="settings-footer">
          <button class="btn" @click="copyContext">复制</button>
          <button class="btn btn-primary" @click="showContextDialog = false">关闭</button>
        </div>
      </div>
    </div>
  </teleport>
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

// 设置相关
const showSettings = ref(false)
const showContextDialog = ref(false)
const chatSettings = ref({
  model: 'default',
  fontSize: '14px',
  fontFamily: 'system-ui'
})
const closeSettings = () => {
  showSettings.value = false
}

// 上下文文本
const visionDocument = ref(null)

const loadVisionForContext = async () => {
  if (!projectId.value) return
  try {
    const res = await axios.get(`/api/projects/${projectId.value}/l1/vision`)
    visionDocument.value = res.data.vision
  } catch (e) {
    visionDocument.value = null
  }
}

const fullContextText = computed(() => {
  const systemPrompt = `你是L1种子层的创作引导助手。你的任务是通过对话帮助用户梳理小说创意。

对话策略：
1. 每次只问一个问题，逐步引导
2. 根据用户回答，自然地追问下一个要素
3. 当收集到足够信息时，可以主动总结
4. 保持友好、专业的语气

需要收集的要素（按优先级）：
- 类型/题材（重生/玄幻/科幻等）
- 主角人设
- 金手指/核心能力
- 核心爽点
- 世界观背景
- 风格基调
- 粗略大纲

当前对话阶段：根据已有信息判断下一步该问什么。`
  
  let text = `=== SYSTEM PROMPT ===\n${systemPrompt}\n\n`
  
  // 添加愿景文档
  if (visionDocument.value) {
    text += `=== 愿景文档 ===\n${JSON.stringify(visionDocument.value, null, 2)}\n\n`
  }
  
  text += `=== MESSAGES ===\n\n`
  
  for (const msg of chatMessages.value) {
    const role = msg.role === 'ai' ? 'ASSISTANT' : 'USER'
    
    // 添加思考过程
    if (msg.thinking) {
      text += `--- ${role} (思考过程) ---\n${msg.thinking}\n\n`
    }
    
    text += `--- ${role} ---\n${msg.content}\n\n`
  }
  
  return text
})

const copyContext = async () => {
  try {
    await navigator.clipboard.writeText(fullContextText.value)
    alert('已复制到剪贴板')
  } catch (err) {
    console.error('Copy failed:', err)
  }
}

const openContextDialog = async () => {
  await loadVisionForContext()
  showContextDialog.value = true
}

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
const inputTextarea = ref(null)
const isDragOver = ref(false)
const enterKeyBehavior = ref('newline')
const inputAttachments = ref([])

const loadUiConfig = () => {
  const saved = localStorage.getItem('uiConfig')
  if (saved) {
    try {
      const parsed = JSON.parse(saved)
      enterKeyBehavior.value = parsed.enterKeyBehavior || 'newline'
    } catch (e) {}
  }
}

const handleEnterKey = (event) => {
  const isShiftPressed = event.shiftKey
  
  if (enterKeyBehavior.value === 'newline') {
    // Enter 换行，Shift+Enter 发送
    if (isShiftPressed) {
      event.preventDefault()
      if (!aiTyping.value && userInput.value.trim()) {
        sendMessage()
      }
    }
    // 否则默认换行，不阻止
  } else {
    // Enter 发送，Shift+Enter 换行
    if (!isShiftPressed) {
      event.preventDefault()
      if (!aiTyping.value && userInput.value.trim()) {
        sendMessage()
      }
    }
    // Shift+Enter 默认换行，不阻止
  }
}

const onDragOver = (event) => {
  isDragOver.value = true
}

const onDragLeave = (event) => {
  isDragOver.value = false
}

const onDrop = async (event) => {
  isDragOver.value = false
  
  const docInfo = event.dataTransfer.getData('application/json')
  if (!docInfo) return
  
  try {
    const doc = JSON.parse(docInfo)
    
    // 在输入框中插入标签占位符
    const tag = `[${doc.name}]`
    const textarea = inputTextarea.value
    const cursorPos = textarea?.selectionStart || userInput.value.length
    const textBefore = userInput.value.substring(0, cursorPos)
    const textAfter = userInput.value.substring(cursorPos)
    userInput.value = textBefore + tag + textAfter
    
    // 存储附件信息
    inputAttachments.value.push({
      id: doc.uid,
      name: doc.name,
      content: null,  // 延迟加载
      tag: tag
    })
  } catch (err) {
    console.error('Failed to load dropped document:', err)
  }
}

const expandAttachment = async (tag) => {
  const att = inputAttachments.value.find(a => a.tag === tag)
  if (!att) return
  
  // 如果已加载，直接展开
  if (att.content !== null) {
    userInput.value = userInput.value.replace(att.tag, att.content)
    inputAttachments.value = inputAttachments.value.filter(a => a.tag !== tag)
    return
  }
  
  // 加载内容
  try {
    const projectId = route.query.projectId
    const res = await fetch(`/api/projects/${projectId}/library/${att.id}`)
    const data = await res.json()
    
    let content = data.content
    if (typeof content === 'object' && content.content) {
      content = content.content
    }
    if (typeof content !== 'string') {
      content = JSON.stringify(content, null, 2)
    }
    
    // 展开内容
    userInput.value = userInput.value.replace(att.tag, content)
    inputAttachments.value = inputAttachments.value.filter(a => a.tag !== tag)
  } catch (err) {
    console.error('Failed to load document:', err)
  }
}

const handleTextareaDblClick = (event) => {
  const textarea = inputTextarea.value
  const cursorPos = textarea?.selectionStart || 0
  const text = userInput.value
  
  // 查找光标所在的 [xxx] 标签
  let start = text.lastIndexOf('[', cursorPos)
  let end = text.indexOf(']', cursorPos)
  
  if (start === -1 || end === -1 || start > end) {
    // 尝试从光标位置前后查找
    start = text.lastIndexOf('[', cursorPos - 1)
    end = text.indexOf(']', cursorPos)
  }
  
  if (start !== -1 && end !== -1 && start < end) {
    const tag = text.substring(start, end + 1)
    const att = inputAttachments.value.find(a => a.tag === tag)
    if (att) {
      expandAttachment(tag)
    }
  }
}

const inputPlaceholder = computed(() => {
  if (enterKeyBehavior.value === 'newline') {
    return '输入你的想法... (Enter换行，Shift+Enter发送，可拖入文档生成[文件名]标签)'
  } else {
    return '输入你的想法... (Enter发送，Shift+Enter换行，可拖入文档生成[文件名]标签)'
  }
})

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
const isVisionDragOver = ref(false)

// 愿景文档拖放
const onVisionDragOver = (event) => {
  isVisionDragOver.value = true
}

const onVisionDragLeave = (event) => {
  isVisionDragOver.value = false
}

const onVisionDrop = async (event) => {
  isVisionDragOver.value = false
  
  const docInfo = event.dataTransfer.getData('application/json')
  if (!docInfo) return
  
  try {
    const doc = JSON.parse(docInfo)
    const projectId = route.query.projectId
    
    const res = await fetch(`/api/projects/${projectId}/library/${doc.uid}`)
    const data = await res.json()
    
    let content = data.content
    if (typeof content === 'object' && content.content) {
      content = content.content
    }
    if (typeof content !== 'string') {
      content = JSON.stringify(content, null, 2)
    }
    
    // 设置为愿景文档
    editableVisionDocument.value = content
    showRaw.value = true
    
    // 尝试解析为JSON更新表单
    try {
      const parsed = JSON.parse(content)
      if (parsed.idea !== undefined) form.value.idea = parsed.idea || ''
      if (parsed.genre !== undefined) form.value.genre = parsed.genre || ''
      if (parsed.target_readers !== undefined) form.value.target_readers = parsed.target_readers || ''
      if (parsed.core_appeal !== undefined) form.value.core_appeal = parsed.core_appeal || ''
      if (parsed.style !== undefined) form.value.style = parsed.style || ''
      if (parsed.rough_outline !== undefined) form.value.rough_outline = parsed.rough_outline || ''
      if (parsed.world_setting !== undefined) form.value.world_setting = parsed.world_setting || ''
      if (parsed.protagonist !== undefined) form.value.protagonist = parsed.protagonist || ''
      if (parsed.golden_finger !== undefined) form.value.golden_finger = parsed.golden_finger || ''
      if (parsed.hot_elements !== undefined) form.value.hot_elements = parsed.hot_elements || ''
      if (parsed.expected_length !== undefined) form.value.expected_length = parsed.expected_length || ''
      
      vision.value = parsed
    } catch (e) {
      // 不是JSON，作为纯文本
    }
  } catch (err) {
    console.error('Failed to import document:', err)
  }
}

const saveVisionEdit = async () => {
  if (!projectId.value) return
  
  try {
    // 尝试解析为JSON
    let visionData
    try {
      visionData = JSON.parse(editableVisionDocument.value)
    } catch {
      // 不是JSON，创建一个简单结构
      visionData = { content: editableVisionDocument.value }
    }
    
    // 使用POST创建/覆盖
    await axios.post(`/api/projects/${projectId.value}/l1/vision`, visionData)
    vision.value = visionData
  } catch (err) {
    console.error('Failed to save vision:', err)
    alert('保存失败')
  }
}

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
const adjustTextareaHeight = () => {
  const textarea = inputTextarea.value
  if (!textarea) return
  
  // 重置高度以获取正确的 scrollHeight
  textarea.style.height = 'auto'
  
  // 根据内容设置新高度（有最小和最大限制）
  const newHeight = Math.min(Math.max(textarea.scrollHeight, 32), 160) // 32px min, 160px=10rem max
  textarea.style.height = newHeight + 'px'
}

const sendMessage = async () => {
  if (!userInput.value.trim() || aiTyping.value) return
  
  // 展开所有未展开的附件标签
  let messageContent = userInput.value
  for (const att of inputAttachments.value) {
    if (messageContent.includes(att.tag)) {
      // 如果还没加载内容，加载它
      if (att.content === null) {
        try {
          const projectId = route.query.projectId
          const res = await fetch(`/api/projects/${projectId}/library/${att.id}`)
          const data = await res.json()
          
          let content = data.content
          if (typeof content === 'object' && content.content) {
            content = content.content
          }
          if (typeof content !== 'string') {
            content = JSON.stringify(content, null, 2)
          }
          att.content = content
        } catch (err) {
          console.error('Failed to load document:', err)
          att.content = `[加载失败: ${att.name}]`
        }
      }
      messageContent = messageContent.replace(att.tag, att.content)
    }
  }
  
  // 清空附件列表
  inputAttachments.value = []
  
  // 添加用户消息
  chatMessages.value.push({
    role: 'user',
    content: messageContent,
    time: new Date()
  })
  
  userInput.value = ''
  
  // 重置输入框高度
  if (inputTextarea.value) {
    inputTextarea.value.style.height = 'auto'
  }
  
  await nextTick()
  scrollToBottom()
  
  aiTyping.value = true
  
  // 添加AI消息占位
  const aiMsgIdx = chatMessages.value.length
  chatMessages.value.push({
    role: 'ai',
    content: '',
    thinking: '',
    showThinking: false,
    time: new Date()
  })
  
  try {
    // 使用fetch发送POST请求接收SSE流
    const response = await fetch(`/api/projects/${projectId.value}/l1/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages: chatMessages.value.slice(0, -1).map(m => ({ role: m.role, content: m.content })),
        currentForm: form.value
      })
    })
    
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let lastDataTime = Date.now()
    const TIMEOUT_MS = 30000 // 30秒超时
    
    while (true) {
      // 检查超时
      if (Date.now() - lastDataTime > TIMEOUT_MS) {
        throw new Error('响应超时')
      }
      
      const { done, value } = await reader.read()
      if (done) break
      
      // 更新最后接收数据时间
      lastDataTime = Date.now()
      
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))
            if (data.type === 'thinking') {
              chatMessages.value[aiMsgIdx].thinking += data.content
              chatMessages.value[aiMsgIdx].showThinking = true
            } else if (data.type === 'chunk') {
              chatMessages.value[aiMsgIdx].content += data.content
              scrollToBottom()
            } else if (data.type === 'done') {
              if (data.thinking) {
                chatMessages.value[aiMsgIdx].thinking = data.thinking
              }
              if (data.content) {
                chatMessages.value[aiMsgIdx].content = data.content
              }
              if (data.extracted) {
                Object.assign(form.value, data.extracted)
              }
            }
          } catch (e) {}
        }
      }
    }
  } catch (err) {
    console.error('Chat error:', err)
    if (err.message === '响应超时') {
      chatMessages.value[aiMsgIdx].content += '\n\n[系统提示：响应超时，请重试或点击"重新生成"]'
    } else {
      chatMessages.value[aiMsgIdx].content = '抱歉，发生了错误，请重试。'
    }
  }
  
  aiTyping.value = false
  await nextTick()
  scrollToBottom()
}

// 重新生成最后一条AI消息
const regenerateMessage = async (idx) => {
  if (aiTyping.value) return
  
  // 删除这条AI消息及之后的所有消息
  chatMessages.value = chatMessages.value.slice(0, idx)
  
  aiTyping.value = true
  
  // 添加AI消息占位
  const aiMsgIdx = chatMessages.value.length
  chatMessages.value.push({
    role: 'ai',
    content: '',
    thinking: '',
    showThinking: false,
    time: new Date()
  })
  
  try {
    const response = await fetch(`/api/projects/${projectId.value}/l1/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages: chatMessages.value.slice(0, -1).map(m => ({ role: m.role, content: m.content })),
        currentForm: form.value
      })
    })
    
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let lastDataTime = Date.now()
    const TIMEOUT_MS = 30000
    
    while (true) {
      if (Date.now() - lastDataTime > TIMEOUT_MS) {
        throw new Error('响应超时')
      }
      
      const { done, value } = await reader.read()
      if (done) break
      
      lastDataTime = Date.now()
      
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))
            if (data.type === 'thinking') {
              chatMessages.value[aiMsgIdx].thinking += data.content
              chatMessages.value[aiMsgIdx].showThinking = true
            } else if (data.type === 'chunk') {
              chatMessages.value[aiMsgIdx].content += data.content
              scrollToBottom()
            } else if (data.type === 'done') {
              if (data.thinking) {
                chatMessages.value[aiMsgIdx].thinking = data.thinking
              }
              if (data.content) {
                chatMessages.value[aiMsgIdx].content = data.content
              }
              if (data.extracted) {
                Object.assign(form.value, data.extracted)
              }
            }
          } catch (e) {}
        }
      }
    }
  } catch (err) {
    console.error('重新生成失败:', err)
    if (err.message === '响应超时') {
      chatMessages.value[aiMsgIdx].content += '\n\n[系统提示：响应超时，请重试]'
    } else {
      chatMessages.value[aiMsgIdx].content = '抱歉，发生了错误，请重试。'
    }
  }
  
  aiTyping.value = false
  await nextTick()
  scrollToBottom()
}

// 编辑用户消息
const startEdit = (idx) => {
  chatMessages.value[idx].editing = true
  chatMessages.value[idx].editContent = chatMessages.value[idx].content
}

const cancelEdit = (idx) => {
  chatMessages.value[idx].editing = false
  delete chatMessages.value[idx].editContent
}

// 仅保存编辑，不触发AI生成
const saveEditOnly = (idx) => {
  const newContent = chatMessages.value[idx].editContent.trim()
  if (!newContent) return
  
  // 更新消息内容
  chatMessages.value[idx].content = newContent
  chatMessages.value[idx].editing = false
  delete chatMessages.value[idx].editContent
}

// 保存编辑并触发AI生成
const saveEditAndGenerate = async (idx) => {
  const newContent = chatMessages.value[idx].editContent.trim()
  if (!newContent) return
  
  // 更新消息内容
  chatMessages.value[idx].content = newContent
  chatMessages.value[idx].editing = false
  delete chatMessages.value[idx].editContent
  
  // 删除这条消息之后的所有消息
  chatMessages.value = chatMessages.value.slice(0, idx + 1)
  
  // 重新获取AI回复
  aiTyping.value = true
  
  const aiMsgIdx = chatMessages.value.length
  chatMessages.value.push({
    role: 'ai',
    content: '',
    thinking: '',
    showThinking: false,
    time: new Date()
  })
  
  try {
    const response = await fetch(`/api/projects/${projectId.value}/l1/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages: chatMessages.value.slice(0, -1).map(m => ({ role: m.role, content: m.content })),
        currentForm: form.value
      })
    })
    
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let lastDataTime = Date.now()
    const TIMEOUT_MS = 30000
    
    while (true) {
      if (Date.now() - lastDataTime > TIMEOUT_MS) {
        throw new Error('响应超时')
      }
      
      const { done, value } = await reader.read()
      if (done) break
      
      lastDataTime = Date.now()
      
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))
            if (data.type === 'thinking') {
              chatMessages.value[aiMsgIdx].thinking += data.content
              chatMessages.value[aiMsgIdx].showThinking = true
            } else if (data.type === 'chunk') {
              chatMessages.value[aiMsgIdx].content += data.content
              scrollToBottom()
            } else if (data.type === 'done') {
              if (data.thinking) {
                chatMessages.value[aiMsgIdx].thinking = data.thinking
              }
              if (data.content) {
                chatMessages.value[aiMsgIdx].content = data.content
              }
              if (data.extracted) {
                Object.assign(form.value, data.extracted)
              }
            }
          } catch (e) {}
        }
      }
    }
  } catch (err) {
    console.error('编辑后获取回复失败:', err)
    if (err.message === '响应超时') {
      chatMessages.value[aiMsgIdx].content += '\n\n[系统提示：响应超时，请重试]'
    } else {
      chatMessages.value[aiMsgIdx].content = '抱歉，发生了错误，请重试。'
    }
  }
  
  aiTyping.value = false
  await nextTick()
  scrollToBottom()
}

// 删除消息
const deleteMessage = (idx) => {
  if (aiTyping.value) return
  if (!confirm('确定要删除这条消息吗？')) return
  
  // 删除这条消息及之后的所有消息
  chatMessages.value = chatMessages.value.slice(0, idx)
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
    // 尚未生成愿景文档，静默处理
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

const saveDraft = async () => {
  if (!projectId.value) return
  try {
    await axios.post(`/api/projects/${projectId.value}/l1/draft`, form.value)
  } catch (e) {
    console.error('保存草稿失败:', e)
  }
}

const saveChatHistory = async () => {
  if (!projectId.value) return
  try {
    // 只保存非编辑状态的消息
    const messages = chatMessages.value
      .filter(m => !m.editing)
      .map(m => ({
        role: m.role,
        content: m.content,
        thinking: m.thinking || '',
        time: m.time
      }))
    await axios.post(`/api/projects/${projectId.value}/l1/chat-history`, { messages })
  } catch (e) {
    console.error('保存聊天历史失败:', e)
  }
}

const loadChatHistory = async () => {
  if (!projectId.value) return
  try {
    const res = await axios.get(`/api/projects/${projectId.value}/l1/chat-history`)
    if (res.data.messages && res.data.messages.length > 0) {
      // 直接用历史记录替换，但确保每条消息都有必要字段
      chatMessages.value = res.data.messages.map(m => ({
        role: m.role,
        content: m.content,
        thinking: m.thinking || '',
        showThinking: false,
        editing: false,
        time: new Date(m.time)
      }))
    }
  } catch (e) {
    console.error('加载聊天历史失败:', e)
  }
}

const loadDraft = async () => {
  if (!projectId.value) return
  try {
    const res = await axios.get(`/api/projects/${projectId.value}/l1/draft`)
    if (res.data.form && Object.keys(res.data.form).length > 0) {
      Object.assign(form.value, res.data.form)
    }
  } catch (e) {
    console.error('加载草稿失败:', e)
  }
}

let saveTimer = null
watch(form, () => {
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(() => {
    saveDraft()
  }, 1000)
}, { deep: true })

// 自动保存chat历史
let chatSaveTimer = null
watch(chatMessages, () => {
  if (chatSaveTimer) clearTimeout(chatSaveTimer)
  chatSaveTimer = setTimeout(() => {
    saveChatHistory()
  }, 1000)
}, { deep: true })

onMounted(() => {
  loadUiConfig()
  if (projectId.value) {
    loadDraft()
    loadVision()
    loadChatHistory()
  }
})

</script>

<style scoped>
.l1-seed {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

/* 主容器 */
.main-container {
  flex: 1;
  display: flex;
  overflow: hidden;
  width: 100%;
  max-width: 100%;
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
  padding: 0 1.25rem;
  border-bottom: 1px solid #e8e8e8;
  flex-shrink: 0;
  height: 42px;
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
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 右侧面板 */
.right-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
}

/* 分屏模式下，左右面板填满剩余空间 */
.main-container.split .chat-panel {
  width: 50%;
  flex: none;
  height: 100%;
}

.main-container.split .right-panel {
  flex: 1;
  height: 100%;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  min-height: 0;
  max-width: 100%;
  overflow-x: hidden;
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
  max-width: 100%;
  word-wrap: break-word;
  overflow-wrap: break-word;
}

.message.user .message-content {
  background: #e8e8e8;
  color: #333;
  border-top-left-radius: 12px;
  border-top-right-radius: 4px;
}

.message-text {
  line-height: 1.6;
}

.message-text :deep(p) {
  margin: 0.5rem 0;
}

.message-text :deep(p:first-child) {
  margin-top: 0;
}

.message-text :deep(p:last-child) {
  margin-bottom: 0;
}

.message-text :deep(strong) {
  font-weight: 600;
  color: #333;
}

.message-text :deep(em) {
  font-style: italic;
}

.message-text :deep(ul), .message-text :deep(ol) {
  margin: 0.5rem 0;
  padding-left: 1.5rem;
}

.message-text :deep(li) {
  margin: 0.25rem 0;
}

.message-text :deep(code) {
  background: #f5f5f5;
  padding: 0.1rem 0.3rem;
  border-radius: 3px;
  font-size: 0.9em;
}

.message-text :deep(pre) {
  background: #f5f5f5;
  padding: 0.75rem;
  border-radius: 4px;
  overflow-x: auto;
  margin: 0.5rem 0;
}

.message-text :deep(blockquote) {
  border-left: 3px solid #ddd;
  padding-left: 1rem;
  margin: 0.5rem 0;
  color: #666;
}

.message-text :deep(h1), .message-text :deep(h2), .message-text :deep(h3) {
  margin: 0.75rem 0 0.5rem;
  font-weight: 600;
}

.message-text :deep(h1) { font-size: 1.2em; }
.message-text :deep(h2) { font-size: 1.1em; }
.message-text :deep(h3) { font-size: 1em; }

.message-time {
  font-size: 0.7rem;
  opacity: 0.6;
}

/* 思考过程样式 */
.message-thinking {
  background: #f8f9fa;
  border-left: 3px solid #6366f1;
  border-radius: 4px;
  margin-bottom: 0.5rem;
  font-size: 0.9em;
}

.thinking-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  cursor: pointer;
  color: #6366f1;
  font-weight: 500;
}

.thinking-header:hover {
  background: #eee;
}

.thinking-icon {
  font-size: 0.7em;
}

.thinking-content {
  padding: 0.5rem 0.75rem;
  border-top: 1px solid #e5e7eb;
  color: #666;
  font-size: 0.9em;
  line-height: 1.5;
}

.thinking-content :deep(p) {
  margin: 0.25rem 0;
}

/* 消息操作 */
.message-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-top: 0.25rem;
}

.btn-regenerate {
  background: none;
  border: none;
  color: #999;
  font-size: 0.7rem;
  cursor: pointer;
  padding: 0.2rem 0.4rem;
  border-radius: 3px;
  transition: all 0.2s;
}

.btn-regenerate:hover {
  background: #f0f0f0;
  color: #333;
}

.btn-regenerate:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-edit {
  background: none;
  border: none;
  color: #999;
  font-size: 0.7rem;
  cursor: pointer;
  padding: 0.2rem 0.4rem;
  border-radius: 3px;
  transition: all 0.2s;
}

.btn-edit:hover {
  background: #f0f0f0;
  color: #333;
}

.btn-delete {
  background: none;
  border: none;
  color: #999;
  font-size: 0.7rem;
  cursor: pointer;
  padding: 0.2rem 0.4rem;
  border-radius: 3px;
  transition: all 0.2s;
}

.btn-delete:hover {
  background: #fee;
  color: #e74c3c;
}

.btn-delete:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.edit-textarea {
  width: 100%;
  min-height: 100px;
  padding: 0.75rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 0.9rem;
  resize: both;
  font-family: inherit;
  box-sizing: border-box;
}

.edit-actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.btn-small {
  padding: 0.25rem 0.75rem;
  font-size: 0.75rem;
  border: 1px solid #ddd;
  background: white;
  border-radius: 4px;
  cursor: pointer;
}

.btn-small:hover {
  background: #f5f5f5;
}

.btn-small.btn-primary {
  background: #3498db;
  color: white;
  border-color: #3498db;
}

.btn-small.btn-primary:hover {
  background: #2980b9;
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
  gap: 0.25rem;
  padding: 0.25rem 1rem;
  border-top: 1px solid #e8e8e8;
  background: #fafafa;
  flex-shrink: 0;
}

.chat-input-area textarea {
  flex: 1;
  padding: 0.375rem 0.75rem;
  border: 1px solid #ddd;
  border-radius: 8px;
  resize: none;
  min-height: 32px;
  max-height: 10rem;
  height: auto;
  overflow-y: auto;
  font-family: inherit;
  line-height: 1.5;
  box-sizing: border-box;
}

.chat-input-area textarea:focus {
  outline: none;
  border-color: #3498db;
}

.chat-input-area textarea.drag-over {
  border-color: #3498db;
  background: #e3f2fd;
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

/* 拖动条 */
.resizer {
  width: 8px;
  background: #e8e8e8;
  cursor: col-resize;
  transition: background 0.2s;
  position: relative;
  z-index: 10;
  align-self: stretch;
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
  height: 42px;
  align-items: center;
}

.panel-tabs .tab-btn {
  flex: 1;
  padding: 0.875rem;
  border-bottom: 2px solid transparent;
  border-radius: 0;
  height: 100%;
}

.panel-tabs .tab-btn.active {
  border-bottom-color: #3498db;
  background: rgba(52, 152, 219, 0.05);
}

.panel-content {
  flex: 1;
  padding: 1.25rem;
  min-height: 0;
  max-width: 100%;
  overflow-x: hidden;
}

.panel-content.form-content {
  overflow-y: auto;
}

.panel-content.preview-content {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 1rem;
  height: calc(100% - 2rem);
  max-height: calc(100% - 2rem);
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
  margin-bottom: 0.75rem;
  flex-shrink: 0;
}

.preview-header h3 {
  margin: 0;
  font-size: 0.875rem;
}

.preview-actions {
  display: flex;
  gap: 0.5rem;
}

.preview-body {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 1rem;
  overflow-y: auto;
  overflow-x: hidden;
  word-wrap: break-word;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  transition: background 0.2s, border 0.2s;
}

.preview-body.drag-over {
  background: #e3f2fd;
  border: 2px dashed #3498db;
}

.preview-body .vision-structured {
  flex: 1;
}

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

.vision-raw-editor {
  width: 100%;
  height: 100%;
  min-height: 0;
  padding: 1rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-family: 'Courier New', Courier, monospace;
  font-size: 0.875rem;
  line-height: 1.6;
  resize: none;
  background: #fafafa;
  color: #333;
  box-sizing: border-box;
}

.vision-raw-editor:focus {
  outline: none;
  border-color: #3498db;
  background: white;
}

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

.preview-empty .hint {
  font-size: 0.875rem;
  color: #bbb;
  margin-bottom: 1.5rem;
}

/* 头部按钮组 */
.header-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

/* 设置弹窗 */
.settings-modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.settings-panel {
  background: white;
  border-radius: 8px;
  width: 400px;
  max-width: 90vw;
  box-shadow: 0 4px 20px rgba(0,0,0,0.15);
}

.settings-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid #e8e8e8;
}

.settings-header h3 {
  margin: 0;
  font-size: 1rem;
}

.btn-close {
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: #999;
}

.btn-close:hover {
  color: #333;
}

.settings-body {
  padding: 1.25rem;
}

.settings-section {
  margin-bottom: 1rem;
}

.settings-section:last-child {
  margin-bottom: 0;
}

.settings-section h4 {
  margin: 0 0 0.5rem 0;
  font-size: 0.875rem;
  color: #666;
}

.settings-section select {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 0.875rem;
}

.settings-footer {
  padding: 1rem 1.25rem;
  border-top: 1px solid #e8e8e8;
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}

.context-panel {
  background: white;
  border-radius: 8px;
  width: 800px;
  max-width: 95vw;
  max-height: 90vh;
  box-shadow: 0 4px 20px rgba(0,0,0,0.15);
  display: flex;
  flex-direction: column;
}

.context-body {
  flex: 1;
  overflow: auto;
  padding: 1rem;
}

.context-content {
  background: #f8f9fa;
  padding: 1rem;
  border-radius: 4px;
  font-family: monospace;
  font-size: 0.875rem;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
  max-height: 60vh;
  overflow: auto;
}

/* 响应式 */
@media (max-width: 1024px) {
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
  .form-row {
    grid-template-columns: 1fr;
  }
}
</style>