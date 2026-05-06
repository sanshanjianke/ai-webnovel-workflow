<template>
  <div class="output-page">
    <div class="output-header">
      <button class="btn btn-back" @click="goBack">← 返回画布</button>
      <h2>📤 输出结果 — {{ pipelineName }}</h2>
      <div class="header-actions">
        <button class="btn btn-primary" @click="downloadZip" :disabled="objects.length === 0">
          ⬇ ZIP 下载
        </button>
      </div>
    </div>

    <div class="output-stats" v-if="objects.length > 0">
      共 {{ objects.length }} 个对象，{{ totalFiles }} 个文件 · {{ totalReports }} 份报告 · {{ totalChatLogs }} 份聊天记录
    </div>

    <div class="output-body">
      <!-- 拖拽 ZIP 导入区 -->
      <div
        class="drop-zone"
        :class="{ hover: isDragOver }"
        @dragover.prevent="isDragOver = true"
        @dragleave.prevent="isDragOver = false"
        @drop.prevent="onDropZip"
      >
        <div v-if="objects.length === 0 && !zipLoaded" class="drop-hint">
          📂 拖入 ZIP 文件查看历史输出<br>
          <small>或运行管道后自动显示</small>
        </div>

        <!-- 对象列表 -->
        <div v-if="objects.length > 0" class="object-list">
          <div
            v-for="obj in objects"
            :key="obj.id"
            class="object-item"
            @dblclick="openViewer(obj)"
            :title="'双击查看详情'"
          >
            <div class="object-header-row">
              <span class="object-icon">📦</span>
              <span class="object-name">{{ obj.name }}</span>
              <span class="object-status" :class="obj.status">{{ statusLabel(obj.status) }}</span>
            </div>
            <div class="object-meta">
              <span class="expert-chain">{{ expertChain(obj) }}</span>
              <span class="file-counts">{{ fileStats(obj) }}</span>
            </div>
            <div class="object-hint">双击查看</div>
          </div>
        </div>

        <!-- ZIP 已加载 -->
        <div v-if="zipLoaded" class="zip-info">
          ✅ 已加载: {{ zipFileName }}
          <span class="zip-object-count">{{ objects.length }} 个对象</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import JSZip from 'jszip'

const route = useRoute()
const router = useRouter()
const projectId = computed(() => route.query.projectId || '')
const pipelineName = ref('管道输出')

const objects = ref([])
const isDragOver = ref(false)
const zipLoaded = ref(false)
const zipFileName = ref('')

const totalFiles = computed(() => objects.value.reduce((s, o) => s + (o.files?.length || 0), 0))
const totalReports = computed(() => objects.value.reduce((s, o) => s + (o.files || []).filter(f => f.category === 'report').length, 0))
const totalChatLogs = computed(() => objects.value.reduce((s, o) => s + (o.files || []).filter(f => f.category === 'chat_log').length, 0))

function statusLabel(s) {
  const labels = { completed: '✅ 完成', running: '⏳ 运行中', failed: '❌ 失败', pending: '⏸ 等待' }
  return labels[s] || s
}

function expertChain(obj) {
  const producers = [...new Set((obj.files || []).filter(f => f.producer !== 'input').map(f => f.producer))]
  if (producers.length === 0) return '无专家处理'
  return producers.join(' → ')
}

function fileStats(obj) {
  const files = obj.files || []
  const reports = files.filter(f => f.category === 'report').length
  const chats = files.filter(f => f.category === 'chat_log').length
  const inputs = files.filter(f => f.category === 'input').length
  const parts = []
  if (inputs > 0) parts.push(`${inputs} 输入`)
  if (reports > 0) parts.push(`${reports} 报告`)
  if (chats > 0) parts.push(`${chats} 聊天`)
  return `${files.length} 个文件` + (parts.length > 0 ? ` · ${parts.join(' · ')}` : '')
}

function openViewer(obj) {
  const url = `/view?projectId=${projectId.value}&objectId=${obj.id}`
  window.open(url, '_blank')
}

function goBack() {
  router.push(`/orchestrate?projectId=${projectId.value}`)
}

async function downloadZip() {
  // Phase 5: 调用后端 ZIP 导出接口
  const sessionId = sessionStorage.getItem('lastMeetingId') || ''
  if (!sessionId) {
    alert('未找到会话 ID，请重新运行管道')
    return
  }
  try {
    const resp = await fetch(`/api/projects/${projectId.value}/meeting/export/${sessionId}`)
    if (!resp.ok) {
      alert('导出失败: ' + resp.statusText)
      return
    }
    const blob = await resp.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `pipeline_output_${sessionId}.zip`
    a.click()
    URL.revokeObjectURL(url)
  } catch (err) {
    console.error('Download error:', err)
    alert('下载失败，导出功能将在 Phase 5 实现')
  }
}

async function onDropZip(event) {
  isDragOver.value = false
  const files = event.dataTransfer?.files || []
  if (files.length === 0) return
  const file = files[0]
  if (!file.name.endsWith('.zip')) return

  try {
    const zip = await JSZip.loadAsync(file)
    zipFileName.value = file.name
    zipLoaded.value = true

    // 解析 ZIP 结构
    const parsed = []
    const objDirs = new Map()

    for (const [path, entry] of Object.entries(zip.files)) {
      if (entry.dir) continue
      // 跳过 config.cfg
      if (path === 'config.cfg') continue

      // 解析对象目录：大纲1_xxx/ 或直接的文件前缀
      const parts = path.split('/')
      let objName, fileName
      if (parts.length >= 2) {
        objName = parts[0]
        fileName = parts.slice(1).join('/')
      } else {
        objName = 'root'
        fileName = parts[0]
      }

      if (!objDirs.has(objName)) {
        objDirs.set(objName, { name: objName, files: [] })
      }

      const content = await entry.async('text')
      const category = fileName.endsWith('_chatlog.json') ? 'chat_log'
        : fileName.endsWith('_report.md') || fileName.endsWith('.md') && !fileName.startsWith('0') ? 'report'
        : fileName.startsWith('0') && !fileName.includes('_') ? 'input'
        : 'report'

      const producer = category === 'input' ? 'input'
        : fileName.replace(/^\d+_/, '').replace(/_report\.md$/, '').replace(/_chatlog\.json$/, '').replace(/\.md$/, '')

      objDirs.get(objName).files.push({
        path: fileName,
        content,
        category,
        producer
      })
    }

    objects.value = Array.from(objDirs.values())
    // 存储到 sessionStorage 供查看页使用
    sessionStorage.setItem('pipelineOutput', JSON.stringify({
      objects: objects.value,
      projectId: projectId.value,
      timestamp: new Date().toISOString(),
      sourceZip: true
    }))
  } catch (err) {
    console.error('ZIP parse error:', err)
    alert('ZIP 解析失败: ' + err.message)
  }
}

onMounted(() => {
  // 从 sessionStorage 恢复数据
  const stored = sessionStorage.getItem('pipelineOutput')
  if (stored) {
    try {
      const data = JSON.parse(stored)
      objects.value = data.objects || []
    } catch {}
  }
})
</script>

<style scoped>
.output-page {
  height: calc(100vh - 42px);
  display: flex;
  flex-direction: column;
  background: #f5f5f5;
  overflow: hidden;
}

.output-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 20px;
  background: white;
  border-bottom: 1px solid #e0e0e0;
  flex-shrink: 0;
}
.output-header h2 { margin: 0; font-size: 1.1rem; flex: 1; }
.header-actions { display: flex; gap: 8px; }

.output-stats {
  padding: 8px 20px;
  font-size: 0.8rem;
  color: #666;
  background: #fafafa;
  border-bottom: 1px solid #eee;
}

.output-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.drop-zone {
  min-height: 300px;
  border: 2px dashed #ddd;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: border-color 0.2s, background 0.2s;
}
.drop-zone.hover {
  border-color: #3498db;
  background: #e8f4fd;
}

.drop-hint {
  text-align: center;
  color: #999;
  font-size: 1rem;
  line-height: 1.8;
}
.drop-hint small { font-size: 0.8rem; color: #bbb; }

.object-list {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.object-item {
  background: white;
  border-radius: 8px;
  padding: 14px 18px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  cursor: pointer;
  transition: box-shadow 0.2s, transform 0.1s;
}
.object-item:hover {
  box-shadow: 0 3px 12px rgba(0,0,0,0.1);
  transform: translateY(-1px);
}

.object-header-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}
.object-icon { font-size: 1.2rem; }
.object-name { font-weight: 600; font-size: 0.95rem; color: #2c3e50; flex: 1; }
.object-status { font-size: 0.75rem; padding: 2px 8px; border-radius: 10px; }
.object-status.completed { background: #d5f5e3; color: #27ae60; }
.object-status.failed { background: #fadbd8; color: #e74c3c; }
.object-status.running { background: #d6eaf8; color: #2980b9; }
.object-status.pending { background: #fdebd0; color: #f39c12; }

.object-meta {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 0.78rem;
  color: #777;
}
.expert-chain { color: #555; font-weight: 500; }
.object-hint {
  font-size: 0.7rem;
  color: #bbb;
  margin-top: 4px;
}

.zip-info {
  text-align: center;
  padding: 20px;
  color: #27ae60;
  font-weight: 600;
}
.zip-object-count { margin-left: 12px; color: #666; font-weight: 400; }

.btn {
  padding: 6px 14px;
  border: 1px solid #ddd;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
  background: white;
  transition: all 0.2s;
}
.btn:hover { background: #f0f0f0; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: #3498db; color: white; border-color: #3498db; }
.btn-primary:hover:not(:disabled) { background: #2980b9; }
.btn-back { font-size: 0.8rem; }
</style>
