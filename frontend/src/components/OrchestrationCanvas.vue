<template>
  <div class="orchestration-page">
    <div class="preset-bar">
      <button 
        v-for="p in presets" :key="p.key"
        :class="['preset-btn', { active: activePreset === p.key }]"
        @click="loadPreset(p.key)"
      >
        {{ p.label }}
      </button>
    </div>

    <div class="canvas-layout">
      <!-- ── 左侧工具箱 ── -->
      <div class="toolbox">
        <div class="toolbox-section" :class="{ collapsed: !builtinOpen }" @click="builtinOpen = !builtinOpen">
          <span class="section-arrow">{{ builtinOpen ? '▾' : '▸' }}</span>
          <h4>默认专家</h4>
        </div>
        <div v-show="builtinOpen">
          <div v-for="(expert, id) in availableExperts" :key="id"
            class="toolbox-item"
            draggable="true"
            @dragstart="onDragStart($event, id, expert)"
          >
            <span class="expert-icon">{{ expert.icon }}</span>
            <div class="expert-info">
              <span class="expert-name">{{ expert.label }}</span>
              <span class="expert-desc">{{ expert.desc }}</span>
            </div>
          </div>
        </div>

        <div class="toolbox-section" :class="{ collapsed: !customOpen }" @click="customOpen = !customOpen">
          <span class="section-arrow">{{ customOpen ? '▾' : '▸' }}</span>
          <h4>自定义专家</h4>
        </div>
        <div v-show="customOpen">
          <div v-for="(expert, id) in customExperts" :key="id"
            class="toolbox-item custom-item"
            draggable="true"
            @dragstart="onDragStart($event, id, expert)"
          >
            <span class="expert-icon">{{ expert.icon }}</span>
            <div class="expert-info">
              <span class="expert-name">{{ expert.label }}</span>
              <span class="expert-desc">{{ expert.desc }}</span>
            </div>
            <button class="btn-delete-expert" @click.stop="deleteCustomExpert(id)" title="删除">×</button>
          </div>
          <div v-if="Object.keys(customExperts).length === 0" class="hint" style="padding:6px 10px;">
            暂无自定义专家
          </div>
          <button class="btn-create-expert" @click="showCreateModal = true">+ 创建专家</button>
        </div>
      </div>

      <!-- ── 画布 ── -->
      <div class="canvas-area" 
        @drop="onDrop" 
        @dragover="onDragOver"
        @dragenter="onDragEnterCanvas"
        @dragleave="onDragLeaveCanvas"
        :class="{ 'drag-over-canvas': draggingOverCanvas }"
      >
        <VueFlow
          v-model:nodes="nodes"
          v-model:edges="edges"
          :node-types="nodeTypes"
          :default-viewport="{ x: 0, y: 0, zoom: 1 }"
          fit-view-on-init
          @node-click="onNodeClick"
          @pane-click="onPaneClick"
          @edge-click="onEdgeClick"
          @connect="onConnect"
          class="flow-canvas"
        >
          <Background :gap="20" />
          <Controls position="bottom-right" />
        </VueFlow>
        <div class="floating-toolbar">
          <span class="toolbar-label">工具</span>
          <span class="toolbar-sep"></span>
          <button class="toolbar-btn" @click="addContainer" title="容器（框选专家，可配群聊/循环）">📦</button>
          <button class="toolbar-btn" @click="addPlaceholder('worldbook')" title="世界书节点">📖</button>
          <button class="toolbar-btn" @click="addPlaceholder('rag')" title="RAG节点">🔍</button>
          <button class="toolbar-btn" @click="addPlaceholder('splitter')" title="章节拆分师">✂️</button>
          <span class="toolbar-sep"></span>
          <button class="toolbar-btn" @click="saveDesign" :disabled="!projectId || saveStatus === 'saving'" :title="saveStatus === 'saved' ? '已保存' : saveStatus === 'error' ? '保存失败' : '保存到文档库'">
            {{ saveStatus === 'saving' ? '⏳' : saveStatus === 'saved' ? '✅' : saveStatus === 'error' ? '❌' : '💾' }}
          </button>
        </div>
      </div>

      <!-- ── 右侧面板：容器配置 ── -->
      <div class="config-panel" v-if="selectedNode && selectedNode.type === 'container'">
        <div class="panel-header-row">
          <h4>容器配置</h4>
          <button class="btn-back" @click="selectedNode = null">← 返回</button>
        </div>
        <div class="config-field">
          <label>名称</label>
          <input v-model="containerCfg.name" @change="onContainerChange" />
        </div>
        <div class="config-field">
          <label>并发方式</label>
          <select v-model="containerCfg.concurrency" @change="onContainerChange">
            <option value="serial">串行（一次一个）</option>
            <option value="parallel">并行（可同时）</option>
          </select>
        </div>
        <div class="config-field">
          <label>发言方式</label>
          <select v-model="containerCfg.speaking_mode" @change="onContainerChange">
            <option value="ordered">顺序循环（按连线）</option>
            <option value="mention_driven">提及驱动（互相 @）</option>
          </select>
        </div>
        <div class="config-field">
          <label>重复次数（1=不循环，提及驱动模式忽略此项）</label>
          <input v-model.number="containerCfg.repeat" type="number" min="1" max="100" @change="onContainerChange" :disabled="containerCfg.speaking_mode === 'mention_driven'" />
        </div>

        <div class="config-section">
          <label class="section-label">提及驱动退出条件</label>
        </div>
        <div class="config-field">
          <label>退出方式</label>
          <select v-model="containerCfg.exit_mode" @change="onContainerChange" :disabled="containerCfg.speaking_mode !== 'mention_driven'">
            <option value="manual">手动</option>
            <option value="consensus">全部赞同</option>
            <option value="ratio">多数赞同</option>
            <option value="gatekeeper">门禁专家</option>
          </select>
        </div>
        <div class="config-field" v-if="containerCfg.exit_mode === 'ratio'">
          <label>赞同比例 ({{ (containerCfg.exit_ratio * 100).toFixed(0) }}%)</label>
          <input v-model.number="containerCfg.exit_ratio" type="range" min="0.1" max="1" step="0.1" @change="onContainerChange" :disabled="containerCfg.speaking_mode !== 'mention_driven'" />
        </div>
        <div class="config-field" v-if="containerCfg.exit_mode === 'gatekeeper'">
          <label>门禁专家</label>
          <select v-model="containerCfg.exit_gatekeeper" @change="onContainerChange" :disabled="containerCfg.speaking_mode !== 'mention_driven'">
            <option :value="null">---</option>
            <option v-for="child in containerChildren" :key="child" :value="child">{{ child }}</option>
          </select>
        </div>
        <div class="config-field">
          <label>最大发言次数（0=不限）</label>
          <input v-model.number="containerCfg.exit_max_speeches" type="number" min="0" max="500" @change="onContainerChange" :disabled="containerCfg.speaking_mode !== 'mention_driven'" />
        </div>

        <div class="config-section">
          <label class="section-label">上下文深度（可选，以先触达为准）</label>
        </div>
        <div class="config-field config-inline">
          <label class="checkbox-label">
            <input type="checkbox" v-model="containerCfg.use_layers" @change="onContainerChange" />
            按楼层
          </label>
          <input v-if="containerCfg.use_layers" v-model.number="containerCfg.context_layers" type="number" min="1" max="50" placeholder="层数" @change="onContainerChange" style="width:70px;margin-left:8px;" />
        </div>
        <div class="config-field config-inline">
          <label class="checkbox-label">
            <input type="checkbox" v-model="containerCfg.use_tokens" @change="onContainerChange" />
            按 token
          </label>
          <input v-if="containerCfg.use_tokens" v-model.number="containerCfg.context_tokens" type="number" min="1000" max="1000000" step="10000" placeholder="token数" @change="onContainerChange" style="width:100px;margin-left:8px;" />
        </div>

        <div class="config-section">
          <label class="section-label">数据绑定（暂留接口）</label>
        </div>
        <div class="config-field">
          <label>世界书（逗号分隔）</label>
          <input v-model="containerCfg.worldbook_bindings" placeholder="核心设定, 角色追踪" @change="onContainerChange" />
        </div>
        <div class="config-field">
          <label>RAG（逗号分隔）</label>
          <input v-model="containerCfg.rag_bindings" placeholder="历史回顾, 技法参考" @change="onContainerChange" />
        </div>

        <div class="config-actions">
          <button class="btn btn-danger btn-sm" @click="removeNode">删除容器</button>
        </div>
      </div>

      <!-- ── 右侧面板：专家节点配置 ── -->
      <div class="config-panel" v-else-if="selectedNode && selectedNode.type === 'expert'">
        <div class="panel-header-row">
          <h4>节点配置</h4>
          <button class="btn-back" @click="selectedNode = null" title="返回会议配置">← 返回</button>
        </div>
        <div class="config-field">
          <label>专家</label>
          <div class="expert-label-row">
            <span class="expert-icon">{{ getExpertIcon(selectedNode) }}</span>
            <strong>{{ selectedNode.data.label }}</strong>
            <span v-if="selectedNode.data.isPlaceholder" class="placeholder-badge">占位</span>
            <span v-if="nodeTriggers.worldbook" class="trigger-icon" title="世界书查询">📖</span>
            <span v-if="nodeTriggers.rag" class="trigger-icon" title="RAG检索">🔍</span>
          </div>
        </div>
        <div class="config-field">
          <label>角色</label>
          <select v-model="selectedNode.data.role" @change="onConfigChange">
            <option value="main">主导 (main)</option>
            <option value="review">审核 (review)</option>
            <option value="supplement">补充 (supplement)</option>
          </select>
        </div>
        <div class="config-field">
          <label>世界书查询</label>
          <select :value="nodeTriggers.worldbook" @change="setTrigger('worldbook', $event.target.value)" class="trigger-select-wb">
            <option value="off">关闭</option>
            <option value="manual">手动</option>
            <option value="auto">自动（发言前注入）</option>
          </select>
        </div>
        <div class="config-field">
          <label>RAG 检索</label>
          <select :value="nodeTriggers.rag" @change="setTrigger('rag', $event.target.value)" class="trigger-select-rag">
            <option value="off">关闭</option>
            <option value="manual">手动</option>
            <option value="auto">自动（发言前注入）</option>
          </select>
        </div>
        <div class="config-field">
          <label>自定义 prompt</label>
          <textarea v-model="customPrompt" placeholder="可选，额外指令" rows="3" @change="onConfigChange"></textarea>
        </div>
        <div class="config-actions">
          <button class="btn btn-danger btn-sm" @click="removeNode">删除节点</button>
        </div>
      </div>

      <!-- ── 右侧面板：会议总配置 ── -->
      <div class="config-panel" v-else>
        <h4>当前配置</h4>
        <div class="meeting-settings">
          <div class="config-field">
            <label>会议名称</label>
            <input v-model="meetingName" placeholder="专家会议" />
          </div>
        </div>
        <div class="order-list">
          <h4 style="margin-top: 12px;">发言顺序</h4>
          <div v-if="orderedNodes.length === 0" class="hint">
            从左侧拖拽专家到画布，连线定义顺序
          </div>
          <div v-for="(node, idx) in orderedNodes" :key="node.id + '-' + idx" class="order-item">
            <span class="order-num">{{ idx + 1 }}</span>
            <span class="order-icon">{{ getExpertIcon(node) }}</span>
            <span class="order-label">{{ node.data.label }}</span>
            <span class="order-role">({{ node.data.role }})</span>
            <span v-if="node.containerName" class="order-container">「{{ node.containerName }}」</span>
          </div>
        </div>
        <button class="btn btn-primary btn-run" @click="runMeeting" :disabled="orderedNodes.length === 0">
          运行会议
        </button>
        <button class="btn btn-outline btn-save" style="width:100%; margin-top:6px;" @click="saveDesign" :disabled="!projectId || saveStatus === 'saving'">
          {{ saveStatus === 'saving' ? '保存中...' : saveStatus === 'saved' ? '已保存 ✓' : saveStatus === 'error' ? '保存失败 ✗' : '清空' }}
        </button>
        <button class="btn btn-outline btn-clear" @click="clearCanvas">清空画布</button>
      </div>
    </div>

    <!-- ── 创建自定义专家模态框 ── -->
    <div v-if="showCreateModal" class="modal-overlay" @click.self="showCreateModal = false">
      <div class="modal-content card">
        <h2>创建自定义专家</h2>
        <div class="form-group">
          <label>专家 ID（英文，如 my_expert）</label>
          <input v-model="newExpert.id" placeholder="my_expert" />
        </div>
        <div class="form-group">
          <label>名称</label>
          <input v-model="newExpert.name" placeholder="打脸检测师" />
        </div>
        <div class="form-group">
          <label>图标（emoji）</label>
          <input v-model="newExpert.icon" placeholder="📄" maxlength="4" />
        </div>
        <div class="form-group">
          <label>描述</label>
          <input v-model="newExpert.description" placeholder="检查打脸密度是否达标" />
        </div>
        <div class="form-group">
          <label>Prompt 模板</label>
          <div class="vars-hint">
            可用变量: <code>{vision}</code> <code>{worldbook}</code> <code>{author_proposal}</code> 
            <code>{reader_opinion}</code> <code>{user_feedback}</code> <code>{history}</code> <code>{custom_prompt}</code>
          </div>
          <textarea v-model="newExpert.prompt_template" placeholder="你是XXX专家，负责...&#10;&#10;故事愿景：{vision}&#10;&#10;请分析..." rows="10"></textarea>
        </div>
        <div class="modal-actions">
          <button class="btn btn-primary" @click="createCustomExpert" :disabled="!newExpert.id || !newExpert.name">创建</button>
          <button class="btn" @click="showCreateModal = false">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, markRaw, onMounted, watch } from 'vue'
import { VueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import axios from 'axios'

import ExpertNode from './ExpertNode.vue'
import GroupNode from './GroupNode.vue'

const emit = defineEmits(['run'])
const props = defineProps({
  projectId: { type: String, default: '' }
})

const nodeTypes = { expert: markRaw(ExpertNode), container: markRaw(GroupNode) }

const nodes = ref([])
const edges = ref([])
const selectedNode = ref(null)
const activePreset = ref('custom')
const builtinOpen = ref(true)
const customOpen = ref(true)

const meetingName = ref('专家会议')
const saveStatus = ref('')
const loadStatus = ref('')
const draggingOverCanvas = ref(false)
const showCreateModal = ref(false)
const customPrompt = ref('')

const customExperts = ref({})

const newExpert = reactive({
  id: '',
  name: '',
  icon: '📄',
  description: '',
  prompt_template: ''
})

const containerCfg = reactive({
  name: '容器', concurrency: 'serial', speaking_mode: 'ordered',
  use_layers: false, context_layers: null,
  use_tokens: false, context_tokens: null,
  repeat: 1,
  exit_mode: 'manual', exit_ratio: 0.6, exit_gatekeeper: null, exit_max_speeches: 20,
  worldbook_bindings: '', rag_bindings: ''
})

const containerChildren = computed(() => {
  if (!selectedNode.value || selectedNode.value.type !== 'container') return []
  return selectedNode.value.data.children || []
})

let nodeCounter = 0

const availableExperts = {
  senior_author_v1: { label: '资深作者', icon: '📕', desc: '方向/市场判断' },
  reader_representative_v1: { label: '读者代表', icon: '📙', desc: '体验审核' },
  plot_architect_v1: { label: '剧情架构师', icon: '🏛', desc: '逻辑/功能拆解' },
  character_designer_v1: { label: '人物设计师', icon: '🎭', desc: 'OOC/行动元' },
  web_editor_v1: { label: '网络编辑', icon: '💼', desc: '爽点/毒点' },
  chapter_splitter_v1: { label: '章节拆分师', icon: '✂️', desc: '卷纲→章节目录' },
  discussion_summarizer_v1: { label: '讨论总结师', icon: '📋', desc: '提炼共识/标注分歧' }
}

const presets = [
  { key: 'quick_review', label: '快速审核' },
  { key: 'volume_planning', label: '卷纲规划' },
  { key: 'chapter_design', label: '章纲设计' },
  { key: 'custom', label: '自定义' }
]

const presetConfigs = {
  quick_review: {
    meeting_name: '快速审核',
    experts: [{ expert_id: 'web_editor_v1', role: 'main' }]
  },
  volume_planning: {
    meeting_name: '卷纲编排',
    experts: [
      { expert_id: 'senior_author_v1', role: 'main' },
      { expert_id: 'reader_representative_v1', role: 'review' },
      { expert_id: 'senior_author_v1', role: 'supplement' }
    ]
  },
  chapter_design: {
    meeting_name: '章纲设计',
    experts: [
      { expert_id: 'plot_architect_v1', role: 'main' },
      { expert_id: 'web_editor_v1', role: 'review' },
      { expert_id: 'character_designer_v1', role: 'supplement' }
    ]
  }
}

function getAllExperts() {
  return { ...availableExperts, ...customExperts.value }
}

onMounted(() => { fetchCustomExperts() })

async function fetchCustomExperts() {
  try {
    const res = await axios.get('/api/experts')
    customExperts.value = res.data.custom_experts || {}
  } catch (e) { console.warn('Failed to fetch custom experts:', e) }
}

async function saveDesign() {
  saveStatus.value = 'saving'
  try {
    const design = {
      meeting_name: meetingName.value,
      nodes: nodes.value.map(n => ({
        id: n.id, type: n.type, position: n.position,
        parentNode: n.parentNode || null,
        style: n.style || {},
        data: { ...n.data }
      })),
      edges: edges.value.map(e => ({
        id: e.id, source: e.source, target: e.target, animated: true
      }))
    }
    const now = new Date()
    const ts = `${String(now.getFullYear()).slice(-2)}_${now.getMonth() + 1}_${now.getDate()}_${String(now.getHours()).padStart(2, '0')}${String(now.getMinutes()).padStart(2, '0')}`
    const name = `${meetingName.value || '未命名'} — ${ts}`
    const res = await axios.post(`/api/projects/${props.projectId}/library`, {
      name, layer: 'orchestration', content: design, source: 'generate',
      directory: '/', tags: ['编排', meetingName.value]
    })
    await axios.put(`/api/projects/${props.projectId}/library/active/orchestration`, { uid: res.data.uid })
    window.postMessage({ type: 'library-refresh' }, '*')
    saveStatus.value = 'saved'
    setTimeout(() => { saveStatus.value = '' }, 2000)
  } catch (e) {
    saveStatus.value = 'error'
    console.warn('Save design failed:', e)
    setTimeout(() => { saveStatus.value = '' }, 3000)
  }
}

async function createCustomExpert() {
  try {
    await axios.post('/api/experts/custom', { ...newExpert })
    await fetchCustomExperts()
    showCreateModal.value = false
    Object.assign(newExpert, { id: '', name: '', icon: '📄', description: '', prompt_template: '' })
  } catch (e) { alert(e.response?.data?.detail || '创建失败') }
}

async function deleteCustomExpert(id) {
  if (!confirm('确定删除此自定义专家？')) return
  try { await axios.delete(`/api/experts/custom/${id}`); await fetchCustomExperts() }
  catch (e) { alert('删除失败') }
}

function loadPreset(key) {
  activePreset.value = key
  if (key === 'custom') { clearCanvas(); return }
  const preset = presetConfigs[key]
  if (!preset) return
  meetingName.value = preset.meeting_name
  nodes.value = []; edges.value = []; nodeCounter = 0
  const allExperts = getAllExperts()
  let prevId = null
  for (const exp of preset.experts) {
    const expert = allExperts[exp.expert_id]
    if (!expert) continue
    const id = `node_${++nodeCounter}`
    nodes.value.push({
      id, type: 'expert', position: { x: nodeCounter * 200, y: 200 },
      data: { label: expert.label, role: exp.role, expertId: exp.expert_id, customPrompt: '' },
      style: { zIndex: 5 }
    })
    if (prevId) {
      edges.value.push({ id: `edge_${prevId}_${id}`, source: prevId, target: id, animated: true })
    }
    prevId = id
  }
}

function onDragStart(event, expertId, expert) {
  event.dataTransfer.setData('application/json', JSON.stringify({ expertId, label: expert.label, icon: expert.icon }))
  event.dataTransfer.effectAllowed = 'move'
}

function onDragOver(event) { event.preventDefault(); event.dataTransfer.dropEffect = 'move' }

function onDrop(event) {
  event.preventDefault()
  draggingOverCanvas.value = false
  const raw = event.dataTransfer.getData('application/json')
  if (!raw) return
  const data = JSON.parse(raw)
  if (data.layer && data.uid) {
    if (data.layer === 'orchestration') loadDesignByUid(data.uid)
    return
  }
  if (!data.expertId) return
  const canvasEl = event.target.closest('.vue-flow')
  if (!canvasEl) return
  const rect = canvasEl.getBoundingClientRect()
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top
  const id = `node_${++nodeCounter}`
  nodes.value.push({
    id, type: 'expert', position: { x, y },
    data: { label: data.label, role: 'main', expertId: data.expertId, customPrompt: '' },
    style: { zIndex: 5 }
  })
}

function onDragEnterCanvas(event) { event.preventDefault(); draggingOverCanvas.value = true }
function onDragLeaveCanvas(event) {
  if (!event.currentTarget.contains(event.relatedTarget)) draggingOverCanvas.value = false
}

async function loadDesignByUid(uid) {
  loadStatus.value = 'loading'
  try {
    const res = await axios.get(`/api/projects/${props.projectId}/library/${uid}`)
    const { content } = res.data
    if (!content || !content.nodes) { loadStatus.value = 'empty'; setTimeout(() => { loadStatus.value = '' }, 2000); return }
    loadStatus.value = 'loaded'; setTimeout(() => { loadStatus.value = '' }, 2000)
    meetingName.value = content.meeting_name || '专家会议'
    nodes.value = content.nodes.map(n => ({
      id: n.id, type: n.type || 'expert', position: n.position,
      parentNode: n.parentNode || null,
      style: n.style || (n.type === 'expert' ? { zIndex: 5 } : { zIndex: 0 }),
      data: { ...n.data }
    }))
    edges.value = content.edges.map(e => ({ id: e.id, source: e.source, target: e.target, animated: true }))
    nodeCounter = nodes.value.length
    activePreset.value = 'custom'
    selectedNode.value = null
  } catch (e) {
    loadStatus.value = 'error'; console.warn('Load design failed:', e)
    setTimeout(() => { loadStatus.value = '' }, 3000)
  }
}

function onConnect(connection) {
  edges.value.push({ id: `edge_${connection.source}_${connection.target}`, source: connection.source, target: connection.target, animated: true })
}

function onEdgeClick({ edge }) { edges.value = edges.value.filter(e => e.id !== edge.id) }

function removeNode() {
  if (!selectedNode.value) return
  const id = selectedNode.value.id
  nodes.value = nodes.value.filter(n => n.id !== id)
  edges.value = edges.value.filter(e => e.source !== id && e.target !== id)
  selectedNode.value = null
}

function onConfigChange() {
  if (selectedNode.value) selectedNode.value.data.customPrompt = customPrompt.value
}

const nodeTriggers = computed(() => {
  if (!selectedNode.value || !selectedNode.value.data) return { worldbook: 'off', rag: 'off' }
  const t = selectedNode.value.data.triggers || {}
  return { worldbook: t.worldbook || 'off', rag: t.rag || 'off' }
})

function setTrigger(field, value) {
  if (selectedNode.value && selectedNode.value.type === 'expert') {
    if (!selectedNode.value.data.triggers) selectedNode.value.data.triggers = {}
    selectedNode.value.data.triggers[field] = value
  }
}

function getExpertIcon(node) {
  if (!node || !node.data) return '📄'
  const icons = { '资深作者': '📕', '读者代表': '📙', '剧情架构师': '🏛', '人物设计师': '🎭', '网络编辑': '💼' }
  return icons[node.data.label] || '📄'
}

// ── 容器配置 ──

function onContainerChange() {
  if (selectedNode.value && selectedNode.value.type === 'container') {
    selectedNode.value.data.name = containerCfg.name
    selectedNode.value.data.label = containerCfg.name
    selectedNode.value.data.concurrency = containerCfg.concurrency
    selectedNode.value.data.speaking_mode = containerCfg.speaking_mode
    selectedNode.value.data.context_layers = containerCfg.use_layers ? (containerCfg.context_layers || 3) : null
    selectedNode.value.data.context_tokens = containerCfg.use_tokens ? (containerCfg.context_tokens || 100000) : null
    selectedNode.value.data.repeat = containerCfg.repeat
    selectedNode.value.data.exit_mode = containerCfg.exit_mode
    selectedNode.value.data.exit_ratio = containerCfg.exit_ratio
    selectedNode.value.data.exit_gatekeeper = containerCfg.exit_gatekeeper
    selectedNode.value.data.exit_max_speeches = containerCfg.exit_max_speeches
    selectedNode.value.data.worldbook_bindings = containerCfg.worldbook_bindings
      .split(',').map(s => s.trim()).filter(Boolean)
    selectedNode.value.data.rag_bindings = containerCfg.rag_bindings
      .split(',').map(s => s.trim()).filter(Boolean)
    updateContainerChildren()
  }
}

function loadContainerConfig(node) {
  containerCfg.name = node.data.name || node.data.label || '容器'
  containerCfg.concurrency = node.data.concurrency || 'serial'
  containerCfg.speaking_mode = node.data.speaking_mode || 'ordered'
  containerCfg.use_layers = node.data.context_layers != null
  containerCfg.context_layers = node.data.context_layers ?? null
  containerCfg.use_tokens = node.data.context_tokens != null
  containerCfg.context_tokens = node.data.context_tokens ?? null
  containerCfg.repeat = node.data.repeat || 1
  containerCfg.exit_mode = node.data.exit_mode || 'manual'
  containerCfg.exit_ratio = node.data.exit_ratio ?? 0.6
  containerCfg.exit_gatekeeper = node.data.exit_gatekeeper ?? null
  containerCfg.exit_max_speeches = node.data.exit_max_speeches ?? 20
  containerCfg.worldbook_bindings = (node.data.worldbook_bindings || []).join(', ')
  containerCfg.rag_bindings = (node.data.rag_bindings || []).join(', ')
}

// ── 发言顺序计算 ──

const orderedNodes = computed(() => {
  const expertNodes = nodes.value.filter(n => n.type === 'expert')
  if (edges.value.length === 0) return expertNodes.map(n => {
    const container = nodes.value.find(c => c.type === 'container' && c.id === n.parentNode)
    return { ...n, containerName: container ? container.data.name : null }
  })

  const inDegree = {}, outEdges = {}, nodeMap = {}
  for (const n of expertNodes) { nodeMap[n.id] = n; inDegree[n.id] = 0; outEdges[n.id] = [] }
  for (const e of edges.value) {
    if (!nodeMap[e.source] || !nodeMap[e.target]) continue
    inDegree[e.target] = (inDegree[e.target] || 0) + 1
    outEdges[e.source] = (outEdges[e.source] || []).concat(e.target)
  }

  const queue = expertNodes.filter(n => (inDegree[n.id] || 0) === 0)
  const result = []
  while (queue.length > 0) {
    const current = queue.shift()
    const container = nodes.value.find(n => n.id === current.parentNode && n.type === 'container')
    const isMentionDriven = container && container.data.speaking_mode === 'mention_driven'
    const repeat = isMentionDriven ? 1 : (container ? (container.data.repeat || 1) : 1)
    const containerName = container ? container.data.name : null
    for (let i = 0; i < repeat; i++) {
      result.push({ ...current, containerName, loopIteration: repeat > 1 ? i + 1 : 0 })
    }
    for (const target of (outEdges[current.id] || [])) {
      inDegree[target]--
      if (inDegree[target] === 0) queue.push(nodeMap[target])
    }
  }
  return result.length >= expertNodes.length ? result : expertNodes.map(n => {
    const container = nodes.value.find(c => c.type === 'container' && c.id === n.parentNode)
    return { ...n, containerName: container ? container.data.name : null }
  })
})

function runMeeting() {
  const experts = orderedNodes.value.map(node => ({
    expert_id: node.data.expertId,
    role: node.data.role || 'main',
    custom_prompt: node.data.customPrompt || null,
    container_id: node.parentNode || null,
    loop_iteration: node.loopIteration || 0
  }))

  const containers = nodes.value
    .filter(n => n.type === 'container')
    .map(n => ({
      container_id: n.id,
      name: n.data.name || n.data.label || '容器',
      concurrency: n.data.concurrency || 'serial',
      speaking_mode: n.data.speaking_mode || 'ordered',
      context_layers: n.data.context_layers ?? null,
      context_tokens: n.data.context_tokens ?? null,
      repeat: n.data.repeat || 1,
      exit_mode: n.data.exit_mode || 'manual',
      exit_ratio: n.data.exit_ratio ?? 0.6,
      exit_gatekeeper: n.data.exit_gatekeeper ?? null,
      exit_max_speeches: n.data.exit_max_speeches ?? 20,
      worldbook_bindings: n.data.worldbook_bindings || [],
      rag_bindings: n.data.rag_bindings || [],
      mention_isolation: n.data.mention_isolation !== false,
      children: n.data.children || [],
      edges: edges.value
        .filter(e => {
          const srcIn = (n.data.children || []).includes(e.source)
          const tgtIn = (n.data.children || []).includes(e.target)
          return srcIn || tgtIn || e.source === n.id || e.target === n.id
        })
        .map(e => ({ source: e.source, target: e.target }))
    }))

  emit('run', {
    meeting_name: meetingName.value,
    experts,
    containers
  })
}

function clearCanvas() {
  nodes.value = []; edges.value = []; selectedNode.value = null
  nodeCounter = 0; activePreset.value = 'custom'
}

// ── 容器子节点同步 ──

function updateContainerChildren() {
  const map = {}
  for (const n of nodes.value) {
    if (n.type === 'expert' && n.parentNode) {
      if (!map[n.parentNode]) map[n.parentNode] = []
      map[n.parentNode].push(n.data.label)
    }
  }
  for (const n of nodes.value) {
    if (n.type === 'container') {
      const labels = map[n.id] || []
      n.data.children = [...new Set(labels)]
    }
  }
}

watch(() => nodes.value.length, () => { updateContainerChildren() })
watch(() => nodes.value.map(n => n.parentNode).join(','), () => { updateContainerChildren() }, { immediate: true })

// ── 占位节点 ──

function addPlaceholder(type) {
  const configs = {
    worldbook: { label: '世界书', icon: '📖', expertId: '__worldbook__', desc: '设定查询/更新' },
    rag: { label: 'RAG检索', icon: '🔍', expertId: '__rag__', desc: '历史/技法检索' },
    splitter: { label: '章节拆分师', icon: '✂️', expertId: 'chapter_splitter_v1', desc: '卷纲→章节' }
  }
  const cfg = configs[type]; if (!cfg) return
  const id = `node_${++nodeCounter}`
  nodes.value.push({
    id, type: 'expert', position: { x: 100 + nodeCounter * 80, y: 300 + nodeCounter * 30 },
    data: { label: cfg.label, role: 'main', expertId: cfg.expertId, customPrompt: '', isPlaceholder: type !== 'splitter', triggers: {} },
    style: { zIndex: 5 }
  })
}

function addContainer() {
  const id = `container_${++nodeCounter}`
  nodes.value.push({
    id, type: 'container', position: { x: 250, y: 180 },
    data: {
      name: '容器', label: '容器', icon: '📦',
      concurrency: 'serial', speaking_mode: 'ordered',
      context_layers: null, context_tokens: null,
      repeat: 1,
      exit_mode: 'manual', exit_ratio: 0.6, exit_gatekeeper: null, exit_max_speeches: 20,
      worldbook_bindings: [], rag_bindings: [],
      children: [], width: 520, height: 280
    },
    style: { zIndex: 0 }
  })
}

function onNodeClick({ node }) {
  selectedNode.value = node
  if (node.type === 'expert') {
    customPrompt.value = node.data.customPrompt || ''
  } else if (node.type === 'container') {
    loadContainerConfig(node)
  }
}

function onPaneClick() {
  selectedNode.value = null
}
</script>

<style scoped>
.orchestration-page {
  height: calc(100vh - 42px);
  display: flex;
  flex-direction: column;
  background: #f5f5f5;
}

.preset-bar {
  display: flex; gap: 8px; padding: 10px 16px;
  background: white; border-bottom: 1px solid #e0e0e0;
}
.preset-btn {
  padding: 6px 16px; border: 1px solid #ddd; border-radius: 6px;
  background: white; cursor: pointer; font-size: 0.875rem; transition: all 0.2s;
}
.preset-btn:hover { background: #f0f7ff; border-color: #3498db; }
.preset-btn.active { background: #3498db; color: white; border-color: #3498db; }

.floating-toolbar {
  position: absolute; top: 12px; left: 50%; transform: translateX(-50%);
  display: flex; align-items: center; gap: 2px; padding: 6px 12px;
  background: #fff; border: 1px solid #d0d0d0; border-radius: 10px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.12); z-index: 10;
}
.toolbar-label { font-size: 0.7rem; color: #999; font-weight: 600; letter-spacing: 0.05em; }
.floating-toolbar .toolbar-sep { width: 1px; height: 20px; background: #ddd; margin: 0 4px; }
.toolbar-btn {
  width: 32px; height: 32px; border: 1px solid transparent; border-radius: 6px;
  background: transparent; cursor: pointer; font-size: 1.1rem;
  display: flex; align-items: center; justify-content: center; transition: all 0.15s;
}
.toolbar-btn:hover { background: #f0f7ff; border-color: #3498db; }
.toolbar-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.canvas-layout { flex: 1; display: flex; overflow: hidden; }

.toolbox { width: 190px; background: white; border-right: 1px solid #e0e0e0; padding: 4px; overflow-y: auto; display: flex; flex-direction: column; }
.toolbox-section { display: flex; align-items: center; gap: 4px; padding: 8px 8px 6px 8px; cursor: pointer; user-select: none; border-radius: 4px; }
.toolbox-section:hover { background: #f5f5f5; }
.toolbox-section.collapsed { margin-bottom: 2px; }
.toolbox-section h4 { font-size: 0.75rem; color: #999; margin: 0; text-transform: uppercase; letter-spacing: 0.05em; }
.section-arrow { font-size: 0.7rem; color: #bbb; width: 12px; }
.toolbox-item { display: flex; align-items: center; gap: 8px; padding: 10px; border-radius: 8px; cursor: grab; transition: background 0.2s; margin-bottom: 4px; border: 1px solid transparent; }
.toolbox-item:hover { background: #f0f7ff; border-color: #d0e3f7; }
.toolbox-item:active { cursor: grabbing; }
.custom-item { position: relative; }
.btn-delete-expert { position: absolute; top: 4px; right: 4px; width: 18px; height: 18px; border: none; background: rgba(0,0,0,0.1); border-radius: 50%; cursor: pointer; font-size: 0.7rem; color: #999; display: flex; align-items: center; justify-content: center; opacity: 0; transition: opacity 0.2s; }
.custom-item:hover .btn-delete-expert { opacity: 1; }
.btn-delete-expert:hover { background: #e74c3c; color: white; }
.expert-icon { font-size: 1.3rem; }
.expert-info { flex: 1; }
.expert-name { font-size: 0.85rem; font-weight: 600; display: block; }
.expert-desc { font-size: 0.7rem; color: #999; }
.btn-create-expert { width: calc(100% - 4px); margin: 8px 2px; padding: 8px; border: 1px dashed #ccc; border-radius: 6px; background: transparent; cursor: pointer; font-size: 0.8rem; color: #888; transition: all 0.2s; }
.btn-create-expert:hover { border-color: #3498db; color: #3498db; background: #f0f7ff; }

.canvas-area { flex: 1; position: relative; transition: background 0.2s; border-radius: 4px; }
.canvas-area.drag-over-canvas { background: rgba(52, 152, 219, 0.08); box-shadow: inset 0 0 0 2px #3498db; }
.flow-canvas { width: 100%; height: 100%; }

.config-panel { width: 280px; background: white; border-left: 1px solid #e0e0e0; padding: 14px; overflow-y: auto; }
.config-panel h4 { font-size: 0.85rem; color: #666; margin: 0; padding-bottom: 6px; border-bottom: 1px solid #eee; }
.panel-header-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.panel-header-row h4 { border: none; padding: 0; margin: 0; }
.btn-back { padding: 2px 8px; border: 1px solid #ddd; border-radius: 4px; background: white; cursor: pointer; font-size: 0.75rem; color: #3498db; transition: all 0.15s; }
.btn-back:hover { background: #f0f7ff; border-color: #3498db; }
.config-field { margin-bottom: 10px; }
.config-field label { display: block; font-size: 0.75rem; color: #888; margin-bottom: 4px; }
.checkbox-label { display: flex; align-items: center; gap: 6px; cursor: pointer; font-size: 0.8rem; }
.checkbox-label input { width: auto; }
.config-field input, .config-field select, .config-field textarea { width: 100%; padding: 6px 8px; border: 1px solid #ddd; border-radius: 4px; font-size: 0.85rem; }
.config-field textarea { resize: vertical; font-family: inherit; }
.config-field strong { font-size: 0.85rem; }
.expert-label-row { display: flex; align-items: center; gap: 6px; }
.placeholder-badge { font-size: 0.65rem; background: #f0f0f0; color: #999; padding: 1px 6px; border-radius: 4px; }
.trigger-icon { font-size: 0.9rem; margin-left: 2px; }
.order-list { margin-top: 8px; }
.order-item { display: flex; align-items: center; gap: 6px; padding: 6px 8px; border-radius: 4px; background: #f8f9fa; margin-bottom: 4px; font-size: 0.8rem; }
.order-num { background: #3498db; color: white; border-radius: 50%; width: 20px; height: 20px; display: flex; align-items: center; justify-content: center; font-size: 0.7rem; }
.order-label { font-weight: 600; }
.order-role { color: #999; font-size: 0.7rem; }
.order-container { color: #9b59b6; font-size: 0.65rem; background: #f5f0ff; padding: 1px 6px; border-radius: 4px; }
.hint { font-size: 0.8rem; color: #999; font-style: italic; padding: 12px 0; }

.btn { padding: 0.5rem 1rem; border: 1px solid #ddd; border-radius: 4px; cursor: pointer; font-size: 0.875rem; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: #3498db; color: white; border-color: #3498db; }
.btn-danger { background: #e74c3c; color: white; border-color: #e74c3c; }
.btn-outline { background: white; color: #666; }
.btn-sm { padding: 4px 10px; font-size: 0.8rem; }
.btn-run { width: 100%; margin-top: 14px; padding: 10px; font-size: 0.95rem; }
.btn-clear { width: 100%; margin-top: 6px; padding: 8px; font-size: 0.85rem; }
.config-actions { margin-top: 10px; }
.config-section { margin: 12px 0 6px 0; }
.section-label { font-size: 0.7rem; color: #888; font-weight: 600; text-transform: uppercase; }
.config-inline { display: flex; align-items: center; gap: 6px; }
.config-inline label { margin-bottom: 0 !important; }

.modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 999; }
.modal-content { width: 520px; max-width: 90vw; max-height: 85vh; overflow-y: auto; background: white; padding: 1.5rem; border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.2); }
.modal-content h2 { margin: 0 0 1rem 0; font-size: 1.2rem; }
.form-group { margin-bottom: 1rem; }
.form-group label { display: block; font-size: 0.8rem; color: #666; margin-bottom: 4px; font-weight: 500; }
.form-group input, .form-group textarea { width: 100%; padding: 8px 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 0.9rem; font-family: inherit; }
.form-group textarea { resize: vertical; min-height: 120px; font-family: 'Courier New', monospace; font-size: 0.85rem; }
.vars-hint { font-size: 0.7rem; color: #999; margin-bottom: 6px; line-height: 1.5; }
.vars-hint code { background: #f0f0f0; padding: 1px 5px; border-radius: 3px; font-size: 0.7rem; }
.modal-actions { display: flex; gap: 8px; margin-top: 1rem; }
.modal-actions .btn { flex: 1; }
</style>
