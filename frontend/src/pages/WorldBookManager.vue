<template>
  <div class="worldbook-manager-page">
    <!-- 顶部栏 -->
    <header class="wb-header">
      <div class="wb-header-left">
        <span class="wb-logo">📖👁 世界书管理员</span>
        <span class="wb-badge" v-if="connected">● 监控中</span>
        <span class="wb-badge disconnected" v-else>● 未连接</span>
      </div>
      <div class="wb-header-right">
        <span class="wb-book-label">目标书：<strong>{{ bookId }}</strong></span>
      </div>
    </header>

    <!-- 三栏主体 -->
    <div class="wb-main">
      <!-- 左栏：监控节点 -->
      <aside class="wb-left">
        <h4>监控节点</h4>
        <div v-if="monitoredNodes.length === 0" class="wb-empty">暂无节点启用世界书总结</div>
        <div v-for="node in monitoredNodes" :key="node.nodeId" class="wb-node-card" :class="{ active: node.active }">
          <span class="node-status" :class="node.active ? 'on' : 'off'">●</span>
          <span class="node-name">{{ node.nodeName || node.nodeId }}</span>
          <span class="node-type-tag">{{ node.nodeType === 'group_chat' ? '群聊' : '专家' }}</span>
        </div>
      </aside>

      <!-- 中栏：处理日志 -->
      <main class="wb-center">
        <h4>处理日志</h4>
        <div v-if="logs.length === 0" class="wb-empty">等待事件...</div>
        <div v-for="log in logs" :key="log.id" class="wb-log-entry">
          <div class="log-header">
            <span class="log-time">{{ formatTime(log.timestamp) }}</span>
            <span class="log-type" :class="log.type">{{ log.typeLabel }}</span>
            <span class="log-node">{{ log.nodeName }}</span>
          </div>
          <div class="log-body">
            <template v-if="log.type === 'task_queued'">收到总结任务 <code>{{ log.taskId?.slice(0, 12) }}...</code></template>
            <template v-else-if="log.type === 'analyze_start'">开始分析聊天内容 ({{ log.chatContentLength }} 字符)</template>
            <template v-else-if="log.type === 'actions_ready'">
              分析完成：{{ log.summary }}
              <div class="log-counts">
                <span class="count-tag create">新增 {{ log.createCount }}</span>
                <span class="count-tag update">更新 {{ log.updateCount }}</span>
                <span class="count-tag merge">合并 {{ log.mergeCount }}</span>
                <span class="count-tag skip">跳过 {{ log.skipCount }}</span>
              </div>
            </template>
            <template v-else-if="log.type === 'action_applied'">条目已写入：{{ log.actionType }} → {{ log.keys?.join(', ') }}</template>
            <template v-else-if="log.type === 'task_complete'">
              任务完成
              <span v-if="log.error" class="log-error">{{ log.error }}</span>
              <span v-else>：应用 {{ log.appliedCount }} / 共 {{ log.totalActions }} 条</span>
            </template>
          </div>
        </div>
      </main>

      <!-- 右栏：建议条目预览 -->
      <aside class="wb-right">
        <h4>建议条目</h4>

        <!-- 待确认 -->
        <div class="wb-section">
          <h5 class="section-title">待确认 ({{ pendingActions.length }})</h5>
          <div v-if="pendingActions.length === 0" class="wb-empty">暂无待确认条目</div>
          <div v-for="action in pendingActions" :key="action.actionId" class="wb-action-card">
            <div class="action-header">
              <span class="action-badge" :class="action.action">{{ actionLabels[action.action] }}</span>
              <span class="action-keys">{{ action.keys?.join(', ') }}</span>
            </div>
            <div class="action-content">{{ action.content?.slice(0, 200) }}{{ action.content?.length > 200 ? '...' : '' }}</div>
            <div class="action-reason" v-if="action.reason">原因：{{ action.reason }}</div>
            <div class="action-buttons">
              <button class="btn-accept" @click="confirmAction(action)">确认</button>
              <button class="btn-modify" @click="modifyAction(action)">修改</button>
              <button class="btn-reject" @click="rejectAction(action)">拒绝</button>
            </div>
            <!-- 修改表单 -->
            <div v-if="editingActionId === action.actionId" class="action-edit-form">
              <label>关键词</label>
              <input v-model="editKeys" placeholder="逗号分隔" />
              <label>内容</label>
              <textarea v-model="editContent" rows="3"></textarea>
              <div class="edit-buttons">
                <button @click="saveModify(action)">保存</button>
                <button class="btn-reject" @click="editingActionId = null">取消</button>
              </div>
            </div>
          </div>
        </div>

        <!-- 已处理 -->
        <div class="wb-section">
          <h5 class="section-title">已处理 ({{ appliedActions.length }})</h5>
          <div v-for="action in appliedActions" :key="action.actionId" class="wb-action-card processed">
            <div class="action-header">
              <span class="action-status" :class="action.status">✓ {{ action.status === 'applied' ? '已确认' : '已修改' }}</span>
              <span class="action-badge small" :class="action.action">{{ actionLabels[action.action] }}</span>
            </div>
            <div class="action-content-small">{{ action.content?.slice(0, 100) }}{{ action.content?.length > 100 ? '...' : '' }}</div>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'

const route = useRoute()
const projectId = route.query.projectId || ''
const bookId = route.query.bookId || 'default'

const connected = ref(false)
const monitoredNodes = ref([])
const logs = ref([])
const pendingActions = ref([])
const appliedActions = ref([])
const editingActionId = ref(null)
const editKeys = ref('')
const editContent = ref('')
const pendingTasks = ref(new Map())

const actionLabels = { create: '新增', update: '更新', merge: '合并', skip: '跳过' }

let channel = null

function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function addLog(type, data) {
  const labels = {
    task_queued: '任务排队', analyze_start: '开始分析', analyze_chunk: '流式输出',
    actions_ready: '分析完成', action_applied: '条目写入', task_complete: '任务完成'
  }
  const nodeId = data.nodeId || data.node_id
  const nodeConfig = monitoredNodes.value.find(n => n.nodeId === nodeId)

  logs.value.unshift({
    id: `${type}_${Date.now()}`,
    type,
    typeLabel: labels[type.replace('worldbook_', '')] || type,
    timestamp: data.timestamp || new Date().toISOString(),
    nodeName: nodeConfig?.nodeName || nodeId || '未知',
    ...data
  })

  // 保持日志在 100 条以内
  if (logs.value.length > 100) logs.value = logs.value.slice(0, 100)
}

function handleWorldBookEvent(type, data) {
  const shortType = type.replace('worldbook_', '')

  switch (shortType) {
    case 'task_queued': {
      const nodeId = data.nodeId
      const existing = monitoredNodes.value.find(n => n.nodeId === nodeId)
      if (existing) {
        existing.active = true
      } else {
        monitoredNodes.value.push({
          nodeId, nodeType: data.nodeType, nodeName: data.nodeId, active: true
        })
      }
      pendingTasks.value.set(data.taskId, { taskId: data.taskId, nodeId })
      addLog('task_queued', data)
      break
    }
    case 'analyze_start':
      addLog('analyze_start', data)
      break
    case 'analyze_chunk':
      // 流式输出 — 不记录日志，但可扩展为实时展示
      break
    case 'actions_ready': {
      addLog('actions_ready', data)
      const actions = data.actions || []
      for (const action of actions) {
        if (action.action !== 'skip') {
          pendingActions.value.unshift(action)
        }
      }
      // 去重（按 actionId）
      const seen = new Set()
      pendingActions.value = pendingActions.value.filter(a => {
        const ok = !seen.has(a.actionId)
        seen.add(a.actionId)
        return ok
      })
      break
    }
    case 'action_applied':
      addLog('action_applied', data)
      // 从待确认移除，加入已处理
      const idx = pendingActions.value.findIndex(a => a.actionId === data.actionId)
      if (idx >= 0) {
        const [action] = pendingActions.value.splice(idx, 1)
        action.status = 'applied'
        appliedActions.value.unshift(action)
      }
      break
    case 'task_complete': {
      addLog('task_complete', data)
      const taskInfo = pendingTasks.value.get(data.taskId)
      if (taskInfo) {
        const node = monitoredNodes.value.find(n => n.nodeId === taskInfo.nodeId)
        if (node) node.active = false
        pendingTasks.value.delete(data.taskId)
      }
      break
    }
    default:
      addLog(shortType, data)
  }
}

async function confirmAction(action) {
  try {
    // 在主动管理的 manager 实例中找到对应 task
    await axios.put(`/api/projects/${projectId}/worldbooks/${bookId}/actions/${action.actionId}`, {
      action: 'confirm', taskId: action.taskId
    })
    const idx = pendingActions.value.findIndex(a => a.actionId === action.actionId)
    if (idx >= 0) {
      const [removed] = pendingActions.value.splice(idx, 1)
      removed.status = 'applied'
      appliedActions.value.unshift(removed)
    }
  } catch (err) {
    console.error('Confirm action failed:', err)
  }
}

function modifyAction(action) {
  editingActionId.value = action.actionId
  editKeys.value = action.keys?.join(', ') || ''
  editContent.value = action.content || ''
}

async function saveModify(action) {
  try {
    await axios.put(`/api/projects/${projectId}/worldbooks/${bookId}/actions/${action.actionId}`, {
      action: 'modify',
      modifiedContent: editContent.value,
      modifiedKeys: editKeys.value.split(',').map(k => k.trim()).filter(Boolean),
      taskId: action.taskId
    })
    const idx = pendingActions.value.findIndex(a => a.actionId === action.actionId)
    if (idx >= 0) {
      const [removed] = pendingActions.value.splice(idx, 1)
      removed.content = editContent.value
      removed.keys = editKeys.value.split(',').map(k => k.trim()).filter(Boolean)
      removed.status = 'modified'
      appliedActions.value.unshift(removed)
    }
    editingActionId.value = null
  } catch (err) {
    console.error('Modify action failed:', err)
  }
}

async function rejectAction(action) {
  try {
    await axios.put(`/api/projects/${projectId}/worldbooks/${bookId}/actions/${action.actionId}`, {
      action: 'reject', taskId: action.taskId
    })
    const idx = pendingActions.value.findIndex(a => a.actionId === action.actionId)
    if (idx >= 0) {
      const [removed] = pendingActions.value.splice(idx, 1)
      removed.status = 'rejected'
      appliedActions.value.unshift(removed)
    }
  } catch (err) {
    console.error('Reject action failed:', err)
  }
}

onMounted(() => {
  channel = new BroadcastChannel('meeting-chat')
  channel.onmessage = (event) => {
    const { type, data } = event.data || {}
    if (!type || !type.startsWith('worldbook_')) return
    connected.value = true
    handleWorldBookEvent(type, data)
  }

  // 同步请求
  channel.postMessage({ type: 'sync', targetId: '__worldbook_manager__' })

  // 如果过了一段时间还没连接，显示等待
  setTimeout(() => {
    if (!connected.value && monitoredNodes.value.length === 0) {
      addLog('task_queued', { nodeId: '等待中', nodeType: 'expert', taskId: 'init', timestamp: new Date().toISOString() })
    }
  }, 3000)
})

onUnmounted(() => {
  if (channel) channel.close()
})
</script>

<style scoped>
.worldbook-manager-page {
  display: flex; flex-direction: column; height: 100vh;
  background: #f5f6fa; font-family: -apple-system, BlinkMacSystemFont, sans-serif;
}

.wb-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 8px 16px; background: #2c3e50; color: white; flex-shrink: 0;
}
.wb-logo { font-size: 16px; font-weight: 600; }
.wb-badge { margin-left: 12px; font-size: 12px; color: #2ecc71; }
.wb-badge.disconnected { color: #e74c3c; }
.wb-book-label { font-size: 13px; opacity: 0.8; }

.wb-main { display: flex; flex: 1; overflow: hidden; }

.wb-left { width: 200px; padding: 12px; border-right: 1px solid #ddd; overflow-y: auto; background: #fff; }
.wb-center { flex: 1; padding: 12px; overflow-y: auto; background: #fafafa; }
.wb-right { width: 340px; padding: 12px; border-left: 1px solid #ddd; overflow-y: auto; background: #fff; }

.wb-empty { color: #999; font-size: 12px; padding: 16px 0; }

.wb-node-card {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 8px; margin-bottom: 4px; border-radius: 6px; background: #f8f9fa;
  font-size: 12px;
}
.wb-node-card.active { background: #e8f5e9; }
.node-status { font-size: 8px; }
.node-status.on { color: #2ecc71; }
.node-status.off { color: #ccc; }
.node-type-tag { margin-left: auto; font-size: 10px; color: #888; background: #eee; padding: 1px 4px; border-radius: 3px; }

.wb-log-entry { margin-bottom: 8px; padding: 8px; background: #fff; border-radius: 6px; border: 1px solid #eee; font-size: 12px; }
.log-header { display: flex; gap: 8px; margin-bottom: 4px; }
.log-time { color: #999; font-size: 11px; }
.log-type { font-weight: 600; font-size: 11px; }
.log-type.task_queued { color: #3498db; }
.log-type.analyze_start { color: #f39c12; }
.log-type.actions_ready { color: #2ecc71; }
.log-type.action_applied { color: #27ae60; }
.log-type.task_complete { color: #7f8c8d; }
.log-node { color: #888; }
.log-counts { margin-top: 4px; display: flex; gap: 6px; }
.count-tag { font-size: 11px; padding: 1px 6px; border-radius: 3px; }
.count-tag.create { background: #d5f5e3; color: #27ae60; }
.count-tag.update { background: #d6eaf8; color: #2980b9; }
.count-tag.merge { background: #fdebd0; color: #e67e22; }
.count-tag.skip { background: #eee; color: #999; }
.log-error { color: #e74c3c; }

.wb-section { margin-bottom: 16px; }
.section-title { font-size: 13px; color: #555; margin-bottom: 8px; border-bottom: 1px solid #eee; padding-bottom: 4px; }

.wb-action-card {
  margin-bottom: 8px; padding: 8px; background: #fefefe; border-radius: 6px;
  border: 1px solid #e0e0e0; font-size: 12px;
}
.wb-action-card.processed { opacity: 0.7; background: #f8f8f8; }
.action-header { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
.action-badge { font-size: 10px; padding: 1px 6px; border-radius: 3px; font-weight: 600; }
.action-badge.create { background: #d5f5e3; color: #27ae60; }
.action-badge.update { background: #d6eaf8; color: #2980b9; }
.action-badge.merge { background: #fdebd0; color: #e67e22; }
.action-badge.skip { background: #eee; color: #999; }
.action-badge.small { font-size: 9px; }
.action-keys { font-weight: 600; color: #2c3e50; }
.action-content { color: #555; margin-bottom: 4px; line-height: 1.5; }
.action-reason { color: #999; font-size: 11px; margin-bottom: 6px; }
.action-content-small { color: #999; font-size: 11px; }
.action-status { font-size: 10px; color: #27ae60; }
.action-buttons { display: flex; gap: 4px; margin-top: 6px; }
.btn-accept, .btn-modify, .btn-reject {
  padding: 2px 10px; border-radius: 4px; border: 1px solid #ddd;
  font-size: 11px; cursor: pointer; background: #fff;
}
.btn-accept { color: #27ae60; border-color: #27ae60; }
.btn-accept:hover { background: #d5f5e3; }
.btn-modify { color: #2980b9; border-color: #2980b9; }
.btn-modify:hover { background: #d6eaf8; }
.btn-reject { color: #e74c3c; border-color: #e74c3c; }
.btn-reject:hover { background: #fadbd8; }

.action-edit-form { margin-top: 8px; padding: 8px; background: #f8f9fa; border-radius: 4px; }
.action-edit-form label { font-size: 11px; color: #888; display: block; margin: 4px 0 2px; }
.action-edit-form input, .action-edit-form textarea {
  width: 100%; padding: 4px 6px; font-size: 12px; border: 1px solid #ddd; border-radius: 4px;
  box-sizing: border-box;
}
.edit-buttons { display: flex; gap: 4px; margin-top: 6px; }
.edit-buttons button { padding: 2px 10px; font-size: 11px; border-radius: 4px; border: 1px solid #ddd; cursor: pointer; }
</style>
