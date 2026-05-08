<template>
  <div class="group-chat-view">
    <!-- 中栏：群聊消息流 + 输入框 -->
    <div class="center-panel">
      <div class="chat-messages" ref="msgEl">
        <div v-if="rounds.length === 0" class="empty-hint">
          等待群聊开始...<br><small>在编排画布上运行管道后，群聊消息将在此显示</small>
        </div>
        <RoundCard v-for="(r, idx) in rounds" :key="idx" :round="r" />
      </div>
      <div class="input-area">
        <textarea
          v-model="userInput"
          class="input-textarea"
          placeholder="输入反馈或修改意见... (Enter 发送，Shift+Enter 换行)"
          rows="2"
          @keydown.enter.exact.prevent="sendFeedback"
          :disabled="!isRunning || waitingForUser"
        ></textarea>
        <div class="input-actions">
          <button class="btn btn-primary" @click="sendFeedback" :disabled="!isRunning || !userInput.trim()">
            发送
          </button>
          <button class="btn btn-warning" @click="acceptAndStop" :disabled="!isRunning">
            {{ waitingForUser ? '采纳并继续' : '结束群聊' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 右栏：群聊成员 + 对象文件队列 -->
    <div class="right-panel">
      <!-- 群聊成员列表 -->
      <div class="group-members">
        <div class="panel-header">
          👥 群聊成员
          <span class="member-count">{{ groupMembers.length }}</span>
        </div>
        <div v-for="m in groupMembers" :key="m.id" class="member-item" :class="{ speaking: m.id === currentSpeakerId }">
          <span class="member-icon">{{ m.icon }}</span>
          <span class="member-name">{{ m.name }}</span>
          <span v-if="m.id === currentSpeakerId" class="speaking-badge">发言中</span>
        </div>
      </div>

      <!-- 退出条件状态 -->
      <div class="exit-status" v-if="exitMode">
        <div class="panel-header">🚪 退出条件</div>
        <div class="exit-info">
          <span class="exit-mode">{{ exitModeLabel }}</span>
          <span v-if="exitStops !== null" class="exit-progress">{{ exitStops }}/{{ exitTotal }}</span>
        </div>
      </div>

      <!-- 对象文件队列 -->
      <div class="file-queue">
        <div class="panel-header">
          📋 对象文件
          <span v-if="fileQueue.length > 0" class="queue-count">{{ fileQueue.length }}</span>
        </div>
        <div v-if="fileQueue.length === 0" class="empty-hint small">暂无对象</div>
        <div v-for="(file, idx) in fileQueue" :key="idx" class="queue-item" @dblclick="previewContent(file)" :title="'双击查看内容'">
          <span class="file-icon-s">📄</span>
          <span class="queue-filename">{{ file.name }}</span>
          <span class="file-size-s" v-if="file.size">{{ formatSize(file.size) }}</span>
        </div>
        <div class="queue-progress" v-if="queueProgress.total > 0">
          进度: {{ queueProgress.done }}/{{ queueProgress.total }}
        </div>
      </div>
    </div>

    <!-- 文件内容预览弹窗 -->
    <div v-if="showPreview" class="preview-overlay" @click.self="closePreview">
      <div class="preview-modal">
        <div class="preview-header">
          <span>📄 {{ previewFile?.name || '' }}</span>
          <button class="btn btn-sm" @click="closePreview">✕ 关闭</button>
        </div>
        <div class="preview-body">
          <div v-if="previewFile?.content" class="preview-content" v-html="renderMarkdown(previewFile.content)"></div>
          <div v-else class="empty-hint">该文件暂无内容</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import MarkdownIt from 'markdown-it'
import RoundCard from './RoundCard.vue'
import axios from 'axios'

const props = defineProps({
  targetId: { type: String, required: true },
  projectId: { type: String, default: '' },
  nodeName: { type: String, default: '群聊' }
})

const emit = defineEmits(['status'])

const md = new MarkdownIt()

// ── 核心状态 ──
const isRunning = ref(true)
const msgEl = ref(null)

// 群聊轮次
const rounds = ref([])
const currentSpeakerId = ref('')
let currentRoundNum = 0

// 用户输入
const userInput = ref('')
const waitingForUser = ref(false)

// 文件队列
const fileQueue = ref([])
const queueProgress = ref({ total: 0, done: 0 })
const showPreview = ref(false)
const previewFile = ref(null)

// 群聊成员
const groupMembers = ref([])

// 退出条件
const exitMode = ref('')
const exitTotal = ref(0)
const exitStops = ref(null)

// 会议ID
const meetingId = ref('')

let channel = null

// ── 匹配目标节点 ──
function matchesTarget(data) {
  if (!data) return false
  const cid = data.container_id || data.node_id || data.nodeId || data.expert_id || data.expertId || ''
  if (cid === props.targetId) return true
  if (data.nodeId === props.targetId || data.node_id === props.targetId) return true
  return false
}

// ── 工具函数 ──
function getIcon(expertType) {
  const icons = { '资深作者': '📕', '读者代表': '📙', '剧情架构师': '🏛', '人物设计师': '🎭', '网络编辑': '💼', '系统': '⚙️', '主编': '💬', '讨论总结师': '📋' }
  return icons[expertType] || '📄'
}

function renderMarkdown(text) { return text ? md.render(text) : '' }

function previewContent(file) {
  previewFile.value = file
  showPreview.value = true
}

function closePreview() {
  showPreview.value = false
  previewFile.value = null
}

function formatSize(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  while (bytes >= 1024 && i < units.length - 1) { bytes /= 1024; i++ }
  return `${bytes.toFixed(1)} ${units[i]}`
}

const exitModeLabel = computed(() => {
  const labels = { manual: '手动结束', consensus: '全员共识', ratio: '多数赞同', gatekeeper: '门禁专家' }
  return labels[exitMode.value] || exitMode.value
})

function emitStatus() {
  emit('status', {
    currentExpert: currentSpeakerId.value || props.nodeName,
    roundCurrent: currentRoundNum,
    roundTotal: 0,
    isRunning: isRunning.value
  })
}

// ── 用户反馈 ──
async function sendFeedback() {
  if (!userInput.value.trim() || !isRunning.value) return
  const msg = userInput.value.trim()
  userInput.value = ''
  waitingForUser.value = false

  try {
    await axios.post(`/api/projects/${props.projectId}/meeting/feedback`, {
      meetingId: meetingId.value,
      expertId: props.targetId,
      action: 'chat',
      message: msg
    })
  } catch (err) { console.error('Feedback error:', err) }
}

async function acceptAndStop() {
  waitingForUser.value = false
  try {
    if (userInput.value.trim()) {
      await axios.post(`/api/projects/${props.projectId}/meeting/feedback`, {
        meetingId: meetingId.value,
        expertId: props.targetId,
        action: 'accept',
        message: userInput.value.trim()
      })
    } else {
      await axios.post(`/api/projects/${props.projectId}/meeting/feedback`, {
        meetingId: meetingId.value,
        expertId: props.targetId,
        action: 'accept'
      })
    }
    userInput.value = ''
  } catch (err) { console.error('Accept error:', err) }
}

// ── 滚动到底部 ──
let scrollPending = false
function scrollDown() {
  if (scrollPending) return
  scrollPending = true
  requestAnimationFrame(() => {
    scrollPending = false
    if (msgEl.value) msgEl.value.scrollTop = msgEl.value.scrollHeight
  })
}

// ── 当前轮次 ──
function currentRound() {
  if (rounds.value.length === 0) return null
  return rounds.value[rounds.value.length - 1]
}

// ── SSE 事件处理 ──
function handleEvent(type, data, timestamp) {
  const globalTypes = ['pipeline_start_v2', 'pipeline_complete', 'object_progress']
  if (!globalTypes.includes(type) && !matchesTarget(data)) return

  const ts = timestamp || new Date().toISOString()

  switch (type) {
    case 'pipeline_start_v2':
      meetingId.value = data.meetingId || data.meeting_id || ''
      queueProgress.value = { total: data.totalObjects || 0, done: 0 }
      fileQueue.value = []
      break

    case 'object_progress':
      if (data.files && Array.isArray(data.files)) {
        fileQueue.value = data.files
          .map(f => ({ name: f.path || f.name || '', size: 0, content: f.content || '' }))
      }
      break

    case 'pipeline_complete':
      isRunning.value = false
      break

    // ── 群聊事件 ──
    case 'group_chat_start':
      currentSpeakerId.value = ''
      currentRoundNum = 0
      rounds.value = []
      exitStops.value = null
      // 设置群聊成员列表
      if (data.members) {
        groupMembers.value = (Array.isArray(data.members) ? data.members : []).map(m => ({
          id: m, name: m, icon: getIcon(m)
        }))
      }
      if (data.exitMode) {
        exitMode.value = data.exitMode
        exitTotal.value = data.members ? data.members.length : 0
      }
      // 用当前对象的文件列表替换文件队列
      fileQueue.value = (data.files && Array.isArray(data.files))
        ? data.files.map(f => ({ name: f.path || '', size: 0, content: f.content || '' }))
        : []
      emitStatus()
      scrollDown()
      break

    case 'group_chat_round_start':
      currentRoundNum = data.round || (currentRoundNum + 1)
      exitStops.value = null
      rounds.value.push({
        round: currentRoundNum,
        messages: [{ role: 'system', content: `👥 第${currentRoundNum}轮讨论开始`, timestamp: ts }],
        streaming: true,
        startedAt: ts,
        completedAt: null
      })
      emitStatus()
      scrollDown()
      break

    case 'group_chat_member_start': {
      currentSpeakerId.value = data.expertId || data.expert_id || ''
      const speakerType = data.expertType || data.expert_id || ''
      rounds.value.push({
        round: rounds.value.length + 1,
        messages: [{
          role: 'assistant',
          thinking: '',
          content: '',
          timestamp: ts,
          speakerName: speakerType,
          speakerIcon: getIcon(speakerType)
        }],
        streaming: true,
        startedAt: ts,
        completedAt: null,
        isGroupChat: true,
        speakerName: speakerType,
        speakerIcon: getIcon(speakerType)
      })
      emitStatus()
      scrollDown()
      break
    }

    case 'group_chat_chunk': {
      const chunkType = data.chunkType || data.chunk_type || 'content'
      const chunkContent = data.content || ''
      const cr = currentRound()
      if (!cr) break

      const lastMsg = cr.messages[cr.messages.length - 1]
      if (chunkType === 'thinking') {
        if (!lastMsg || lastMsg.role !== 'assistant') {
          cr.messages.push({ role: 'assistant', thinking: chunkContent, content: '', timestamp: ts })
        } else {
          lastMsg.thinking = (lastMsg.thinking || '') + chunkContent
        }
      } else {
        if (!lastMsg || lastMsg.role !== 'assistant') {
          cr.messages.push({ role: 'assistant', thinking: '', content: chunkContent, timestamp: ts })
        } else {
          lastMsg.content = (lastMsg.content || '') + chunkContent
        }
      }
      scrollDown()
      break
    }

    case 'group_chat_member_complete': {
      const cr = currentRound()
      if (cr) {
        cr.streaming = false
        cr.completedAt = ts
      }
      currentSpeakerId.value = ''
      emitStatus()
      break
    }

    case 'group_chat_round_complete':
      exitStops.value = data.totalSpeeches || 0
      if (rounds.value.length > 0) {
        rounds.value[rounds.value.length - 1].streaming = false
      }
      break

    case 'group_chat_complete':
      currentRoundNum = 0
      currentSpeakerId.value = ''
      rounds.value = []
      isRunning.value = false
      emitStatus()
      break

    case 'group_chat_error': {
      const cr = currentRound()
      if (cr) {
        cr.messages.push({
          role: 'system',
          content: `❌ ${data.expertId || ''}: ${data.error || '群聊错误'}`,
          timestamp: ts
        })
        cr.streaming = false
      }
      currentSpeakerId.value = ''
      break
    }
  }
}

// ── BroadcastChannel ──
onMounted(() => {
  channel = new BroadcastChannel('meeting-chat')
  channel.onmessage = (event) => {
    const { type, data, timestamp } = event.data || {}
    if (!type) return
    handleEvent(type, data, timestamp)
  }
  channel.postMessage({ type: 'sync', targetId: props.targetId })
})

onUnmounted(() => {
  if (channel) { channel.close(); channel = null }
})

// ── 监听 targetId 变化 ──
watch(() => props.targetId, () => {
  rounds.value = []
  groupMembers.value = []
  fileQueue.value = []
  currentRoundNum = 0
  currentSpeakerId.value = ''
  isRunning.value = true
})
</script>

<style scoped>
.group-chat-view {
  display: flex;
  flex: 1;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

/* ── 中栏：聊天消息流 ── */
.center-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

/* ── 输入区 ── */
.input-area {
  border-top: 1px solid #e0e0e0;
  padding: 10px 12px;
  background: white;
  flex-shrink: 0;
}

.input-textarea {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 0.85rem;
  resize: none;
  outline: none;
  font-family: inherit;
  box-sizing: border-box;
}

.input-textarea:focus { border-color: #3498db; box-shadow: 0 0 0 2px rgba(52,152,219,0.15); }
.input-textarea:disabled { background: #f5f5f5; color: #999; }

.input-actions {
  display: flex;
  gap: 8px;
  margin-top: 6px;
  justify-content: flex-end;
}

/* ── 右栏面板 ── */
.right-panel {
  width: 280px;
  flex-shrink: 0;
  border-left: 1px solid #e0e0e0;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  background: #fafafa;
}

.group-members, .exit-status, .file-queue {
  padding: 10px 12px;
  border-bottom: 1px solid #e8e8e8;
}

.panel-header {
  font-size: 0.8rem;
  font-weight: 600;
  color: #555;
  margin-bottom: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.member-count, .queue-count {
  background: #9b59b6;
  color: white;
  padding: 1px 7px;
  border-radius: 10px;
  font-size: 0.7rem;
  font-weight: 600;
}

.member-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  font-size: 0.78rem;
  border-radius: 4px;
  margin-bottom: 2px;
  transition: background 0.2s;
}

.member-item.speaking {
  background: #e8f5e9;
  border-left: 3px solid #27ae60;
}

.member-icon { font-size: 1rem; flex-shrink: 0; }
.member-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.speaking-badge {
  font-size: 0.65rem;
  color: #27ae60;
  font-weight: 600;
  animation: blink 1s infinite;
}

/* 退出条件状态 */
.exit-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.78rem;
}

.exit-mode { color: #666; }

.exit-progress {
  color: #e65100;
  font-weight: 600;
  font-size: 0.75rem;
}

/* 文件队列 */
.file-queue { flex: 1; }

.queue-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 6px;
  font-size: 0.78rem;
  border-radius: 4px;
  margin-bottom: 2px;
  cursor: pointer;
}

.queue-item:hover { background: #e8f4fd; }

.queue-filename {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-icon-s { font-size: 0.9rem; flex-shrink: 0; }
.file-size-s { font-size: 0.7rem; color: #999; }

.queue-progress {
  font-size: 0.75rem;
  color: #666;
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px dashed #ddd;
}

/* ── 空状态 ── */
.empty-hint {
  text-align: center;
  color: #999;
  padding: 3rem 1rem;
  font-size: 0.9rem;
  line-height: 1.8;
}

.empty-hint.small { padding: 1.5rem 0.5rem; font-size: 0.8rem; }

/* ── 按钮 ── */
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
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: #3498db; color: white; border-color: #3498db; }
.btn-primary:hover:not(:disabled) { background: #2980b9; }
.btn-sm { padding: 2px 8px; font-size: 0.75rem; }
.btn-warning { background: #f39c12; color: white; border-color: #f39c12; }
.btn-warning:hover:not(:disabled) { background: #e67e22; }

/* ── 内容预览弹窗 ── */
.preview-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.preview-modal {
  background: white;
  border-radius: 10px;
  width: 70vw;
  max-width: 900px;
  height: 75vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
}

.preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 18px;
  border-bottom: 1px solid #e0e0e0;
  font-weight: 600;
  flex-shrink: 0;
}

.preview-body {
  flex: 1;
  overflow-y: auto;
  padding: 18px;
}

.preview-content {
  line-height: 1.8;
  font-size: 0.9rem;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
</style>
