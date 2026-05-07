<template>
  <div class="viewer-page">
    <!-- 顶部 -->
    <div class="viewer-header">
      <button class="btn btn-back" @click="goBack">← 返回</button>
      <h2>{{ currentObject?.name || '对象查看' }}</h2>
      <span v-if="currentExpert" class="current-expert">· {{ currentExpert }}</span>
    </div>

    <div class="viewer-body">
      <!-- 中栏：聊天内容(上) + 产出文档(下) -->
      <div class="center-panel">
        <div class="chat-section">
          <div class="section-header">💬 聊天内容</div>
          <div class="chat-content" ref="chatEl">
            <div v-if="!currentExpert" class="empty-hint">请从右侧选择专家查看讨论内容</div>
            <template v-else-if="chatRounds.length > 0">
              <RoundCard v-for="(r, idx) in chatRounds" :key="idx" :round="r" />
            </template>
            <div v-else class="empty-hint">
              该专家无聊天记录<br><small>聊天记录在 ZIP 导出时包含，或通过管道运行实时推送</small>
            </div>
          </div>
        </div>
        <div class="doc-section">
          <div class="section-header">📝 产出文档</div>
          <div class="doc-content" v-if="currentReport">
            <div class="report-render" v-html="renderMarkdown(currentReport)"></div>
          </div>
          <div v-else class="empty-hint small">选择专家以查看产出文档</div>
        </div>
      </div>

      <!-- 右栏 -->
      <div class="right-panel">
        <!-- ZIP 模式: 对象列表 -->
        <div v-if="isZipMode && allObjects.length > 1" class="objects-section">
          <div class="section-header">📦 对象列表</div>
          <div
            v-for="obj in allObjects"
            :key="obj.id"
            :class="['list-item', { active: obj.id === selectedObjectId }]"
            @click="selectObject(obj.id)"
          >
            <span>📦</span>
            <span>{{ obj.name }}</span>
            <span class="item-badge">{{ obj.status }}</span>
          </div>
        </div>

        <!-- 专家列表 -->
        <div class="experts-section" :class="{ flex: isZipMode && allObjects.length > 1 }">
          <div class="section-header">👥 专家列表</div>
          <div
            v-for="expert in experts"
            :key="expert.id"
            :class="['list-item', { active: expert.id === selectedExpertId }]"
            @click="selectExpert(expert.id)"
          >
            <span>{{ expert.icon }}</span>
            <span>{{ expert.name }}</span>
            <span class="item-badge">{{ expert.fileCount }} 文件</span>
          </div>
          <div v-if="experts.length === 0" class="empty-hint small">
            {{ currentObject ? '无专家处理此对象' : '未选择对象' }}
          </div>
        </div>
      </div>
    </div>

    <!-- 状态栏 -->
    <div class="status-bar">
      <span v-if="currentObject">{{ currentObject.name }}</span>
      <span v-if="currentExpert">· {{ currentExpert }}</span>
      <span v-if="chatRounds.length > 0">· {{ chatRounds.length }} 轮迭代</span>
      <span v-if="reportStats">{{ '· ' + reportStats }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import MarkdownIt from 'markdown-it'
import RoundCard from '../components/RoundCard.vue'

const route = useRoute()
const router = useRouter()
const md = new MarkdownIt()

const projectId = computed(() => route.query.projectId || '')
const selectedObjectId = ref(route.query.objectId || '')
const isZipMode = computed(() => route.query.source === 'zip' || sessionData.value?.sourceZip)

// 数据
const sessionData = ref(null)
const allObjects = ref([])
const currentObject = ref(null)
const selectedExpertId = ref('')
const currentExpert = ref('')
const currentReport = ref('')
const chatRounds = ref([])
const reportStats = ref('')
const chatEl = ref(null)

// 从 sessionStorage 加载数据
function loadData() {
  const stored = sessionStorage.getItem('pipelineOutput')
  if (stored) {
    try {
      sessionData.value = JSON.parse(stored)
      allObjects.value = sessionData.value.objects || []
    } catch {}
  }
  // 根据 URL 参数加载对象
  if (selectedObjectId.value) {
    selectObject(selectedObjectId.value)
  } else if (allObjects.value.length > 0) {
    selectObject(allObjects.value[0].id)
  }
}

const experts = computed(() => {
  if (!currentObject.value) return []
  const files = currentObject.value.files || []
  // 按 producer 分组
  const byProducer = new Map()
  for (const f of files) {
    if (f.producer === 'input') continue
    if (!byProducer.has(f.producer)) {
      byProducer.set(f.producer, [])
    }
    byProducer.get(f.producer).push(f)
  }

  const icons = {
    '资深作者': '📕', '读者代表': '📙', '剧情架构师': '🏛',
    '人物设计师': '🎭', '网络编辑': '💼', '讨论总结师': '📋', '主编': '💬'
  }

  return [...byProducer.entries()].map(([name, files]) => ({
    id: name,
    name,
    icon: icons[name] || '📄',
    fileCount: files.length,
    files
  }))
})

function selectObject(objectId) {
  selectedObjectId.value = objectId
  currentObject.value = allObjects.value.find(o => o.id === objectId) || null
  selectedExpertId.value = ''
  currentExpert.value = ''
  currentReport.value = ''
  chatRounds.value = []
  reportStats.value = ''

  if (currentObject.value && experts.value.length > 0) {
    selectExpert(experts.value[0].id)
  }
}

function selectExpert(expertId) {
  selectedExpertId.value = expertId
  const expert = experts.value.find(e => e.id === expertId)
  if (!expert) return

  currentExpert.value = expert.name

  // 找报告文件
  const reportFile = expert.files.find(f => f.category === 'report' && f.content)
  if (reportFile) {
    currentReport.value = reportFile.content
    reportStats.value = `${Math.ceil(reportFile.content.length / 500)} ≈字`
  } else {
    currentReport.value = ''
    reportStats.value = ''
  }

  // 找聊天日志
  const chatFile = expert.files.find(f => f.category === 'chat_log' && f.content)
  if (chatFile) {
    try {
      const chatLog = typeof chatFile.content === 'string'
        ? JSON.parse(chatFile.content)
        : chatFile.content
      chatRounds.value = (chatLog.rounds || []).map(r => ({
        round: r.round,
        messages: r.messages || [],
        selfScore: r.selfScore,
        streaming: false,
        startedAt: r.messages?.[0]?.timestamp || '',
        completedAt: r.completedAt || null
      }))
    } catch {
      chatRounds.value = []
    }
  } else {
    chatRounds.value = []
  }
}

function renderMarkdown(text) {
  return text ? md.render(text) : ''
}

function goBack() {
  if (isZipMode.value) {
    router.push(`/output?projectId=${projectId.value}`)
  } else {
    const pid = projectId.value
    if (pid) router.push(`/orchestrate?projectId=${pid}`)
    else router.back()
  }
}

onMounted(loadData)
</script>

<style scoped>
.viewer-page {
  height: calc(100vh - 42px);
  display: flex;
  flex-direction: column;
  background: #f5f5f5;
  overflow: hidden;
}

.viewer-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  background: white;
  border-bottom: 1px solid #e0e0e0;
  flex-shrink: 0;
}
.viewer-header h2 { margin: 0; font-size: 1rem; flex: 1; }
.current-expert { font-size: 0.8rem; color: #666; }

.viewer-body {
  flex: 1;
  display: flex;
  overflow: hidden;
  min-height: 0;
}

/* ── 左栏 ── */
.viewer-library {
  width: 220px;
  flex-shrink: 0;
  border-right: 1px solid #e0e0e0;
  overflow-y: auto;
}

/* ── 中栏 ── */
.center-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}
.chat-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.doc-section {
  height: 35%;
  min-height: 120px;
  display: flex;
  flex-direction: column;
  border-top: 2px solid #e0e0e0;
}

.section-header {
  padding: 8px 14px;
  font-size: 0.8rem;
  font-weight: 600;
  color: #555;
  background: #fafafa;
  border-bottom: 1px solid #eee;
  flex-shrink: 0;
}

.chat-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.doc-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.report-render {
  line-height: 1.7;
  font-size: 0.9rem;
}

/* ── 右栏 ── */
.right-panel {
  width: 220px;
  flex-shrink: 0;
  border-left: 1px solid #e0e0e0;
  background: #fafafa;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}

.objects-section, .experts-section {
  border-bottom: 1px solid #e8e8e8;
}
.experts-section.flex { flex: 1; }

.list-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  font-size: 0.8rem;
  cursor: pointer;
  border-bottom: 1px solid #f0f0f0;
  transition: background 0.15s;
}
.list-item:hover { background: #f0f0f0; }
.list-item.active { background: #e3f2fd; color: #1565c0; font-weight: 600; }
.item-badge {
  margin-left: auto;
  font-size: 0.65rem;
  color: #999;
  font-weight: 400;
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

/* ── 空状态 ── */
.empty-hint {
  text-align: center;
  color: #999;
  padding: 2rem 1rem;
  font-size: 0.85rem;
  line-height: 1.8;
}
.empty-hint.small { font-size: 0.78rem; padding: 1rem; }

/* ── 按钮 ── */
.btn {
  padding: 4px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.8rem;
  background: white;
}
.btn:hover { background: #f0f0f0; }
.btn-back { font-size: 0.78rem; }
</style>
