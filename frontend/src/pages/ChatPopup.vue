<template>
  <div class="chat-popup">
    <!-- 顶部工具栏 -->
    <div class="popup-header">
      <h2>{{ title }}</h2>
      <span class="popup-type-badge">{{ nodeTypeLabel }}</span>
      <span class="popup-status running" v-if="isRunning">● 运行中</span>
      <span class="popup-status stopped" v-else>已完成</span>
      <span v-if="currentExpert" class="current-expert">· {{ currentExpert }}</span>
    </div>

    <div class="popup-body">
      <!-- 左栏：文档库 -->
      <DocumentSidebar v-if="projectId" :projectId="projectId" class="popup-library" />

      <!-- 输入源节点 -->
      <div v-if="nodeType === 'inputSource'" class="popup-content">
        <div class="input-source-panel">
          <h3>📥 输入源</h3>
          <div class="input-files-list">
            <div v-for="(file, idx) in inputFiles" :key="idx" class="input-file-item">
              <span class="file-icon">📄</span>
              <span class="file-name">{{ file.name }}</span>
              <span class="file-size">{{ formatSize(file.size) }}</span>
            </div>
            <div v-if="inputFiles.length === 0" class="empty-hint">暂无输入文件</div>
          </div>
        </div>
      </div>

      <!-- 输出节点 -->
      <div v-else-if="nodeType === 'output'" class="popup-content">
        <div class="output-panel">
          <h3>📤 输出结果</h3>
          <div v-if="outputFiles.length > 0" class="output-files-list">
            <div v-for="(file, idx) in outputFiles" :key="idx" class="output-file-item">
              <span class="file-icon">📄</span>
              <span class="file-name">{{ file.name }}</span>
              <button class="btn btn-sm" @click="downloadFile(file)">下载</button>
            </div>
            <div class="output-actions">
              <button class="btn btn-primary" @click="downloadAll">下载全部 (zip)</button>
              <button class="btn btn-secondary" @click="transferToLibrary">导入文档库</button>
            </div>
          </div>
          <div v-else class="empty-hint">等待输出...</div>
        </div>
      </div>

      <!-- 专家和群聊节点：三栏布局 -->
      <template v-else>
        <!-- 中栏：迭代日志 + 输入框 -->
        <div class="center-panel">
          <div class="chat-messages" ref="msgEl">
            <div v-if="rounds.length === 0" class="empty-hint">
              等待消息...<br><small>在编排画布上运行管道后，消息将在此显示</small>
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
                采纳当前产出并停止
              </button>
            </div>
          </div>
        </div>

        <!-- 右栏：文件队列 + 报告预览 -->
        <div class="right-panel">
          <!-- 文件队列 -->
          <div class="file-queue" v-if="fileQueue.length > 0 || pendingCount > 0">
            <div class="panel-header">
              📋 对象文件
              <span v-if="pendingCount > 0" class="queue-count">{{ pendingCount }}</span>
            </div>
            <div v-for="(file, idx) in fileQueue" :key="idx" class="queue-item">
              <span class="file-icon-s">📄</span>
              <span class="queue-filename">{{ file.name }}</span>
              <span class="file-size-s" v-if="file.size">{{ formatSize(file.size) }}</span>
            </div>
            <div class="queue-progress" v-if="queueProgress.total > 0">
              进度: {{ queueProgress.done }}/{{ queueProgress.total }}
            </div>
          </div>

          <!-- 群聊成员列表 -->
          <div class="group-members" v-if="nodeType === 'container' && groupMembers.length > 0">
            <div class="panel-header">👥 群聊成员</div>
            <div v-for="m in groupMembers" :key="m.id" class="member-item">
              <span>{{ m.icon }}</span>
              <span>{{ m.name }}</span>
            </div>
          </div>

          <!-- 报告预览 -->
          <div class="report-preview">
            <div class="panel-header">📝 产出报告</div>
            <div v-if="currentReport" class="report-content" v-html="renderMarkdown(currentReport)"></div>
            <div v-else-if="isRunning" class="report-placeholder">产出中...</div>
            <div v-else class="report-placeholder">等待运行...</div>
            <div class="report-actions" v-if="currentReport">
              <button class="btn btn-sm" @click="downloadReport">📥 下载</button>
              <button class="btn btn-sm" @click="transferReportToLibrary">📚 导入文档库</button>
            </div>
          </div>
        </div>
      </template>
    </div>

    <!-- 状态栏 -->
    <div class="status-bar" v-if="nodeType !== 'inputSource' && nodeType !== 'output'">
      <span v-if="objectInfo.current > 0">对象 {{ objectInfo.current }}/{{ objectInfo.total }}</span>
      <span v-if="currentExpert">· {{ currentExpert }}</span>
      <span v-if="roundInfo.current > 0">· 第 {{ roundInfo.current }}/{{ roundInfo.total }} 轮</span>
      <span v-if="statusTokens">· {{ statusTokens }} tokens</span>
      <span class="status-hint" v-if="isRunning">右键其他节点 → 打开聊天窗口查看</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import MarkdownIt from 'markdown-it'
import DocumentSidebar from '../components/library/DocumentSidebar.vue'
import RoundCard from '../components/RoundCard.vue'
import JSZip from 'jszip'
import { saveAs } from 'file-saver'
import axios from 'axios'

const route = useRoute()
const md = new MarkdownIt()
const targetId = computed(() => route.query.containerId || route.query.expertId || 'solo')
const projectId = computed(() => route.query.projectId || '')
const nodeType = computed(() => route.query.nodeType || 'expert')
const title = computed(() => route.query.name || (targetId.value === 'solo' ? '主聊天' : targetId.value))
const nodeTypeLabel = computed(() => {
  const labels = { expert: '专家', container: '群聊', inputSource: '输入源', output: '输出' }
  return labels[nodeType.value] || '节点'
})

// ── 核心状态 ──
const isRunning = ref(true)
const msgEl = ref(null)

// 迭代轮次
const rounds = ref([])
const currentExpert = ref('')
const currentExpertId = ref('')
let currentRoundNum = 0

// 用户输入
const userInput = ref('')
const waitingForUser = ref(false)

// 文件队列
const fileQueue = ref([])
const pendingCount = ref(0)
const queueProgress = ref({ total: 0, done: 0 })

// 报告
const currentReport = ref('')
const currentReportName = ref('')

// 状态栏信息
const objectInfo = ref({ current: 0, total: 0 })
const roundInfo = ref({ current: 0, total: 0 })
const statusTokens = ref('')

// 群聊
const groupMembers = ref([])

// 输出节点（复用旧逻辑）
const inputFiles = ref([])
const outputFiles = ref([])

// 会议ID（从 SSE 获取）
const meetingId = ref('')

let channel = null

// ── 匹配目标节点 ──
function matchesTarget(data) {
  if (!data) return false
  const cid = data.container_id || data.expert_id || data.node_id || data.nodeId || 'solo'
  if (cid === targetId.value) return true
  if (data.nodeId === targetId.value || data.node_id === targetId.value) return true
  if (data.expertId === targetId.value || data.expert_id === targetId.value) return true
  return false
}

// ── 工具函数 ──
function getIcon(expertType) {
  const icons = { '资深作者': '📕', '读者代表': '📙', '剧情架构师': '🏛', '人物设计师': '🎭', '网络编辑': '💼', '系统': '⚙️', '主编': '💬', '讨论总结师': '📋' }
  return icons[expertType] || '📄'
}
function renderMarkdown(text) { return text ? md.render(text) : '' }
function formatTime(ts) { return ts ? new Date(ts).toLocaleTimeString('zh-CN') : '' }
function formatSize(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  while (bytes >= 1024 && i < units.length - 1) { bytes /= 1024; i++ }
  return `${bytes.toFixed(1)} ${units[i]}`
}
function downloadFile(file) {
  const blob = new Blob([file.content], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = file.name; a.click()
  URL.revokeObjectURL(url)
}
async function downloadAll() {
  if (outputFiles.value.length === 0) return
  const zip = new JSZip()
  for (const file of outputFiles.value) zip.file(file.name, file.content)
  const blob = await zip.generateAsync({ type: 'blob' })
  saveAs(blob, 'output.zip')
}
async function transferToLibrary() {
  if (outputFiles.value.length === 0 || !projectId.value) return
  try {
    for (const file of outputFiles.value) {
      await axios.post(`/api/projects/${projectId.value}/library/import`, {
        name: file.name, content: file.content, format: 'markdown', directory: '/管道输出'
      })
    }
    window.postMessage({ type: 'library-refresh' }, window.location.origin)
    alert('已导入文档库')
  } catch (err) { alert('导入失败: ' + (err.response?.data?.error || err.message)) }
}
function downloadReport() {
  if (!currentReport.value) return
  const blob = new Blob([currentReport.value], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = currentReportName.value || 'report.md'; a.click()
  URL.revokeObjectURL(url)
}
async function transferReportToLibrary() {
  if (!currentReport.value || !projectId.value) return
  try {
    await axios.post(`/api/projects/${projectId.value}/library/import`, {
      name: currentReportName.value || 'report.md',
      content: currentReport.value, format: 'markdown', directory: '/管道输出'
    })
    window.postMessage({ type: 'library-refresh' }, window.location.origin)
    alert('已导入文档库')
  } catch (err) { alert('导入失败: ' + (err.response?.data?.error || err.message)) }
}

// ── 用户反馈 ──
async function sendFeedback() {
  if (!userInput.value.trim() || !isRunning.value) return
  const msg = userInput.value.trim()
  userInput.value = ''
  waitingForUser.value = false

  try {
    await axios.post(`/api/projects/${projectId.value}/meeting/feedback`, {
      meetingId: meetingId.value,
      expertId: currentExpertId.value || targetId.value,
      action: 'chat',
      message: msg
    })
  } catch (err) { console.error('Feedback error:', err) }
}

async function acceptAndStop() {
  waitingForUser.value = false
  try {
    if (userInput.value.trim()) {
      await axios.post(`/api/projects/${projectId.value}/meeting/feedback`, {
        meetingId: meetingId.value,
        expertId: currentExpertId.value || targetId.value,
        action: 'accept',
        message: userInput.value.trim()
      })
    } else {
      await axios.post(`/api/projects/${projectId.value}/meeting/feedback`, {
        meetingId: meetingId.value,
        expertId: currentExpertId.value || targetId.value,
        action: 'accept'
      })
    }
    userInput.value = ''
  } catch (err) { console.error('Accept error:', err) }
}

// ── 归档 + 清空聊天 ──
function archiveAndClear() {
  rounds.value = []
  currentRoundNum = 0
  roundInfo.value = { current: 0, total: 0 }
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

// ── SSE 事件处理 ──
function handleEvent(type, data, timestamp) {
  // 过滤：只处理匹配的事件，但全局事件（pipeline_start_v2, done等）不过滤
  const globalTypes = ['pipeline_start_v2', 'pipeline_complete', 'done', 'running_state', 'output_files', 'queue_start', 'queue_complete']
  const nodeScoped = !globalTypes.includes(type)

  if (nodeScoped && !matchesTarget(data)) return

  const ts = timestamp || new Date().toISOString()

  switch (type) {
    // ── 管道 v2 全局 ──
    case 'pipeline_start_v2':
      meetingId.value = data.meetingId || data.meeting_id || ''
      objectInfo.value = { current: 0, total: data.totalObjects || 0 }
      fileQueue.value = []
      queueProgress.value = { total: data.totalObjects || 0, done: 0 }
      break

    // ── 对象事件 ──
    case 'object_init':
      objectInfo.value.current = (objectInfo.value.current || 0) + 1
      queueProgress.value.done = objectInfo.value.current - 1
      // 文件队列由 queue_init 设置
      break

    case 'object_progress':
      statusTokens.value = data.totalFiles ? `${data.totalFiles} 文件` : ''
      if (data.files && Array.isArray(data.files)) {
        fileQueue.value = data.files
          .filter(f => f.category === 'report')
          .map(f => ({ name: f.path || f.name || '', size: 0 }))
      }
      break

    case 'object_complete':
      queueProgress.value.done = objectInfo.value.current
      if (data.files && Array.isArray(data.files)) {
        fileQueue.value = data.files
          .filter(f => f.category === 'report')
          .map(f => ({ name: f.path || f.name || '', size: 0 }))
      }
      break

    // ── 文件队列 ──
    case 'queue_init': {
      const files = data.fileNames || data.file_names || []
      fileQueue.value = files.map(f => ({ name: f, size: 0 }))
      pendingCount.value = data.total || 0
      break
    }
    case 'queue_item_complete':
      pendingCount.value = Math.max(0, pendingCount.value - 1)
      queueProgress.value.done++
      break

    case 'queue_complete':
      pendingCount.value = 0
      isRunning.value = false
      break

    // ── Expert v1 ──
    case 'expert_start':
      currentExpert.value = data.expert_type || data.expertType || ''
      currentExpertId.value = data.expert_id || data.expertId || ''
      currentRoundNum = 0
      rounds.value = []
      currentReport.value = ''
      break

    // ── Agent v2 ──
    case 'agent_start':
      // 如果上一个 agent 的聊天还在，先归档
      if (rounds.value.length > 0 && currentReport.value) {
        archiveAndClear()
      }
      currentExpert.value = data.expert_type || data.expertType || ''
      currentExpertId.value = data.expert_id || data.expertId || ''
      currentRoundNum = 0
      rounds.value = []
      currentReport.value = ''
      roundInfo.value = { current: 0, total: data.stopConfig?.maxRounds || 5 }
      scrollDown()
      break

    case 'agent_round_start':
      currentRoundNum = data.round || (currentRoundNum + 1)
      roundInfo.value.current = currentRoundNum
      rounds.value.push({
        round: currentRoundNum,
        messages: [],
        selfScore: undefined,
        streaming: true,
        startedAt: ts,
        completedAt: null
      })
      scrollDown()
      break

    case 'agent_round_complete': {
      const cr = currentRound()
      if (cr) {
        cr.streaming = false
        cr.completedAt = ts
        if (data.selfScore !== undefined) cr.selfScore = data.selfScore
      }
      if (data.report) {
        currentReport.value = data.report
        currentReportName.value = data.reportFileName || `${currentExpert.value}意见.md`
      }
      break
    }

    case 'agent_complete':
      roundInfo.value.current = 0
      if (data.report) {
        currentReport.value = data.report
        currentReportName.value = data.reportFileName || `${currentExpert.value}意见.md`
      }
      rounds.value = []
      currentRoundNum = 0
      scrollDown()
      break

    case 'agent_error': {
      const cr2 = currentRound()
      if (cr2) {
        cr2.messages.push({
          role: 'system',
          content: `❌ 错误: ${data.error || '未知错误'}`,
          timestamp: ts
        })
        cr2.streaming = false
      }
      break
    }

    case 'agent_waiting_user':
      waitingForUser.value = true
      scrollDown()
      break

    // ── 群聊事件 ──
    case 'group_chat_start':
      currentExpert.value = data.nodeName || data.nodeId || '群聊'
      currentExpertId.value = data.nodeId || ''
      currentRoundNum = 0
      rounds.value = []
      currentReport.value = ''
      // 设置群聊成员列表
      if (data.members) {
        groupMembers.value = (Array.isArray(data.members) ? data.members : []).map(m => ({
          id: m, name: m, icon: getIcon(m)
        }))
      }
      scrollDown()
      break

    case 'group_chat_round_start':
      currentRoundNum = data.round || (currentRoundNum + 1)
      // 群聊轮次作为标记消息
      rounds.value.push({
        round: currentRoundNum,
        messages: [{ role: 'system', content: `👥 第${currentRoundNum}轮讨论`, timestamp: ts }],
        streaming: true,
        startedAt: ts,
        completedAt: null
      })
      scrollDown()
      break

    case 'group_chat_member_start': {
      // 创建此成员的发言轮次
      const speakerType = data.expertType || data.expert_id || ''
      const memberRound = {
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
        speakerName: speakerType
      }
      rounds.value.push(memberRound)
      scrollDown()
      break
    }

    case 'group_chat_member_complete': {
      const cr3 = currentRound()
      if (cr3) {
        cr3.streaming = false
        cr3.completedAt = ts
      }
      break
    }

    case 'group_chat_round_complete':
      // 标记最后一个 streaming round 完成
      if (rounds.value.length > 0) {
        rounds.value[rounds.value.length - 1].streaming = false
      }
      break

    case 'group_chat_complete':
      currentRoundNum = 0
      rounds.value = []
      break

    case 'group_chat_error': {
      const cr4 = currentRound()
      if (cr4) {
        cr4.messages.push({ role: 'system', content: `❌ ${data.expertId || ''}: ${data.error || '群聊错误'}`, timestamp: ts })
        cr4.streaming = false
      }
      break
    }

    // ── Chunk (v1/v2 agent 和群聊共用) ──
    case 'chunk': {
      const chunkType = data.chunk_type || data.chunkType
      const chunkContent = data.content || ''

      // v2: 追加到当前轮次
      let cr3 = currentRound()
      if (!cr3) {
        // 可能是 v1 流式，创建兼容轮次
        currentRoundNum = 1
        rounds.value.push({
          round: 1,
          messages: [{ role: 'assistant', thinking: '', content: '', timestamp: ts }],
          selfScore: undefined,
          streaming: true,
          startedAt: ts,
          completedAt: null
        })
        cr3 = currentRound()
      }

      const lastMsg = cr3.messages[cr3.messages.length - 1]
      if (chunkType === 'thinking') {
        if (!lastMsg || lastMsg.role !== 'assistant') {
          cr3.messages.push({ role: 'assistant', thinking: chunkContent, content: '', timestamp: ts })
        } else {
          lastMsg.thinking = (lastMsg.thinking || '') + chunkContent
        }
      } else {
        // content chunk
        if (!lastMsg || lastMsg.role !== 'assistant') {
          cr3.messages.push({ role: 'assistant', thinking: '', content: chunkContent, timestamp: ts })
        } else {
          lastMsg.content = (lastMsg.content || '') + chunkContent
        }
      }
      scrollDown()
      break
    }

    // ── Message (v1 专家完成发言) ──
    case 'message': {
      if (data.type === 'expert' || data.type === 'expert_speak') {
        const existingRound = currentRound()
        if (existingRound && existingRound.streaming) {
          existingRound.messages[existingRound.messages.length - 1].content = data.content || ''
          existingRound.streaming = false
        } else {
          rounds.value.push({
            round: rounds.value.length + 1,
            messages: [{
              role: 'assistant',
              content: data.content || '',
              thinking: data.thinking || '',
              timestamp: ts
            }],
            streaming: false,
            startedAt: ts,
            completedAt: ts
          })
        }
        if (data.report) currentReport.value = data.report
        currentExpert.value = data.expert_type || data.expertType || currentExpert.value
      }
      scrollDown()
      break
    }

    // ── 全局状态 ──
    case 'pipeline_complete':
      isRunning.value = false
      // Populate file queue from objects data (for expert/group nodes)
      if (data.objects && data.objects.length > 0) {
        const obj = data.objects[0]
        if (obj.files && Array.isArray(obj.files)) {
          fileQueue.value = obj.files
            .filter(f => f.category === 'report')
            .map(f => ({ name: f.path || f.name || '', size: f.content ? f.content.length : 0 }))
        }
      }
      if (data.output) {
        const nodeOutputs = data.output.node_outputs || data.output.nodeOutputs || {}
        if (Object.keys(nodeOutputs).length > 0) {
          outputFiles.value = Object.entries(nodeOutputs).map(([key, content]) => ({
            name: `${key}.md`, content
          }))
        }
      }
      break

    case 'done':
      isRunning.value = false
      if (nodeType.value === 'output' && data?.output) {
        const nodeOutputs = data.output.node_outputs || data.output.nodeOutputs || {}
        if (Object.keys(nodeOutputs).length > 0 && outputFiles.value.length === 0) {
          outputFiles.value = Object.entries(nodeOutputs).map(([key, content]) => ({
            name: `${key}.md`, content
          }))
        }
      }
      break

    case 'output_files':
      if (nodeType.value === 'output') {
        outputFiles.value = data.files || []
      }
      break

    case 'running_state':
      isRunning.value = data.isRunning || false
      break

    case 'queue_state':
      queueProgress.value = { total: data.total || 0, done: data.index || 0 }
      break
  }
}

function currentRound() {
  if (rounds.value.length === 0) return null
  return rounds.value[rounds.value.length - 1]
}

// ── BroadcastChannel ──
onMounted(() => {
  channel = new BroadcastChannel('meeting-chat')
  channel.onmessage = (event) => {
    const { type, data, timestamp } = event.data || {}
    if (!type) return
    handleEvent(type, data, timestamp)
  }
  channel.postMessage({ type: 'sync', targetId: targetId.value })
})

onUnmounted(() => {
  if (channel) { channel.close(); channel = null }
})
</script>

<style scoped>
/* ── 布局 ── */
.chat-popup {
  height: calc(100vh - 42px);
  display: flex;
  flex-direction: column;
  background: #f5f5f5;
  overflow: hidden;
}

.popup-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  background: white;
  border-bottom: 1px solid #e0e0e0;
  flex-shrink: 0;
}
.popup-header h2 { margin: 0; font-size: 1rem; }
.current-expert { font-size: 0.8rem; color: #666; }

.popup-body {
  flex: 1;
  display: flex;
  overflow: hidden;
  min-height: 0;
}

/* ── 三栏布局 ── */
.popup-library {
  width: 220px;
  flex-shrink: 0;
  border-right: 1px solid #e0e0e0;
  overflow-y: auto;
}

.center-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}

.right-panel {
  width: 300px;
  flex-shrink: 0;
  border-left: 1px solid #e0e0e0;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  background: #fafafa;
}

/* ── 聊天消息区 ── */
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
.file-queue, .group-members, .report-preview {
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
.queue-count {
  background: #3498db;
  color: white;
  padding: 1px 7px;
  border-radius: 10px;
  font-size: 0.7rem;
  font-weight: 600;
}

.queue-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 6px;
  font-size: 0.78rem;
  border-radius: 4px;
  margin-bottom: 2px;
}
.queue-item:hover { background: #f0f0f0; }
.queue-filename {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file-size-s { font-size: 0.7rem; color: #999; }

.queue-progress {
  font-size: 0.75rem;
  color: #666;
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px dashed #ddd;
}

.group-members .member-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 6px;
  font-size: 0.78rem;
}

.report-preview { flex: 1; display: flex; flex-direction: column; }
.report-content {
  flex: 1;
  overflow-y: auto;
  font-size: 0.82rem;
  line-height: 1.6;
  max-height: 300px;
}
.report-placeholder {
  color: #bbb;
  font-size: 0.78rem;
  font-style: italic;
  padding: 12px 0;
}
.report-actions {
  display: flex;
  gap: 6px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #eee;
}

/* ── 状态栏 ── */
.status-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 16px;
  background: white;
  border-top: 1px solid #e0e0e0;
  font-size: 0.75rem;
  color: #666;
  flex-shrink: 0;
}
.status-hint {
  margin-left: auto;
  color: #999;
  font-size: 0.7rem;
}

/* ── 徽章、状态等 ── */
.popup-type-badge {
  font-size: 0.7rem;
  padding: 2px 8px;
  border-radius: 10px;
  background: #e0e0e0;
  color: #666;
}
.popup-status { font-size: 0.75rem; color: #27ae60; font-weight: 600; }
.popup-status.stopped { color: #999; }

/* ── 输入源/输出节点面板 ── */
.popup-content { flex: 1; overflow-y: auto; padding: 1rem; }
.input-source-panel, .output-panel {
  background: white;
  border-radius: 8px;
  padding: 1.5rem;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
.input-source-panel h3, .output-panel h3 {
  margin: 0 0 1rem 0;
  font-size: 1rem;
  color: #333;
  border-bottom: 1px solid #eee;
  padding-bottom: 0.5rem;
}
.input-files-list, .output-files-list { display: flex; flex-direction: column; gap: 8px; }
.input-file-item, .output-file-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #f8f9fa;
  border-radius: 6px;
  font-size: 0.85rem;
}
.output-actions { display: flex; gap: 8px; margin-top: 4px; }
.file-icon { font-size: 1.2rem; }
.file-name { flex: 1; font-weight: 500; }
.file-size { color: #999; font-size: 0.75rem; }

/* ── 空状态 ── */
.empty-hint {
  text-align: center;
  color: #999;
  padding: 3rem 1rem;
  font-size: 0.9rem;
  line-height: 1.8;
}

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
.btn-secondary { background: #f0f0f0; }
.btn-warning { background: #f39c12; color: white; border-color: #f39c12; }
.btn-warning:hover:not(:disabled) { background: #e67e22; }

/* ── 动画 ── */
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
</style>
