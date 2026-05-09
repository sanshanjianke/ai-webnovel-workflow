<template>
  <div class="rag-manager">
    <h1>RAG 管理</h1>

    <!-- ── 实例栏 ── -->
    <div class="instance-bar">
      <div class="instance-selector">
        <label>当前实例：</label>
        <select v-model="currentId" @change="switchInstance">
          <option v-for="inst in instances" :key="inst.instanceId" :value="inst.instanceId">
            {{ inst.name }} ({{ inst.retrieverType }}, {{ inst.documentCount }} 条)
          </option>
        </select>
      </div>
      <button class="btn btn-primary btn-sm" @click="showCreate = true">+ 新建</button>
      <button class="btn btn-sm" @click="deleteCurrent" :disabled="instances.length <= 1">删除</button>
      <span class="sep"></span>
      <button class="btn btn-sm" @click="exportInstance">⬇ 导出</button>
      <button class="btn btn-sm" @click="triggerImport">📥 导入</button>
      <input ref="importInput" type="file" accept=".json" @change="handleImport" style="display:none" />
    </div>

    <!-- ── 新建弹窗 ── -->
    <div v-if="showCreate" class="modal-overlay" @click.self="showCreate = false">
      <div class="modal-box">
        <h3>创建 RAG 实例</h3>
        <div class="form-group">
          <label>名称</label>
          <input v-model="createForm.name" placeholder="实例名称" />
        </div>
        <div class="form-group">
          <label>类型</label>
          <select v-model="createForm.type">
            <option value="history">历史回顾 — 检索已写章节</option>
            <option value="technique">技法参考 — 写作范例+映射规则</option>
            <option value="custom">自定义 — 上传任意文档</option>
          </select>
        </div>
        <div class="form-group">
          <label>检索机制</label>
          <select v-model="createForm.retrieverType">
            <option value="keyword">简单关键词 — 纯 TF-IDF，零依赖</option>
            <option value="hybrid">混合检索 (推荐) — 向量 60% + 关键词 40%，需 ChromaDB</option>
            <option value="vector">纯向量 — 仅 ChromaDB embedding</option>
          </select>
        </div>
        <div class="form-group" v-if="createForm.retrieverType !== 'keyword'">
          <label>Embedding 模型</label>
          <select v-model="createForm.embeddingModel">
            <option value="text-embedding-v3">text-embedding-v3 (在线, 1024维)</option>
            <option value="qwen3-embedding-4b">qwen3-embedding-4b (本地)</option>
          </select>
        </div>
        <p class="mechanism-hint">{{ mechanismHint }}</p>
        <div class="modal-btns">
          <button class="btn btn-sm" @click="showCreate = false">取消</button>
          <button class="btn btn-primary btn-sm" @click="createInstance" :disabled="!createForm.name">创建</button>
        </div>
      </div>
    </div>

    <!-- ── 机制特定配置（根据 retrieverType 切换） ── -->
    <div v-if="currentConfig" class="config-area">

      <!-- ============ Keyword ============ -->
      <template v-if="currentConfig.retrieverType === 'keyword'">
        <div class="tab-bar">
          <button :class="{ active: kwTab === 'docs' }" @click="kwTab = 'docs'">📋 文档管理</button>
          <button :class="{ active: kwTab === 'search' }" @click="kwTab = 'search'">🔎 检索测试</button>
        </div>

        <!-- Tab: 文档管理 -->
        <div v-if="kwTab === 'docs'" class="tab-content">
          <div class="toolbar-row">
            <button class="btn btn-primary btn-sm" @click="kwShowAddDoc = true">＋添加文档</button>
            <button class="btn btn-sm" @click="clearDocs">🗑 清空全部</button>
            <span class="hint">共 {{ kwDocs.length }} 条文档</span>
          </div>
          <div v-if="kwShowAddDoc" class="add-doc-form">
            <input v-model="kwNewDoc.id" placeholder="ID" />
            <textarea v-model="kwNewDoc.content" placeholder="内容" rows="3"></textarea>
            <input v-model="kwNewDoc.tags" placeholder="标签（逗号分隔）" />
            <button class="btn btn-primary btn-sm" @click="addDocument">添加</button>
            <button class="btn btn-sm" @click="kwShowAddDoc = false">取消</button>
          </div>
          <table v-if="kwDocs.length > 0" class="doc-table">
            <thead><tr><th>ID</th><th>内容</th><th>标签</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="doc in kwDocs" :key="doc.id">
                <td>{{ doc.id }}</td>
                <td class="content-cell">{{ (doc.content || '').slice(0, 100) }}{{ (doc.content || '').length > 100 ? '...' : '' }}</td>
                <td>{{ (doc.metadata?.tags || []) }}</td>
                <td><button class="btn btn-sm" @click="deleteDoc(doc.id)">✕</button></td>
              </tr>
            </tbody>
          </table>
          <p v-else class="hint">暂无文档</p>
        </div>

        <!-- Tab: 检索测试 -->
        <div v-if="kwTab === 'search'" class="tab-content">
          <RAGSearchTest :instanceId="currentId" :projectId="projectId" retrieverType="keyword" />
        </div>
      </template>

      <!-- ============ Hybrid ============ -->
      <template v-if="currentConfig.retrieverType === 'hybrid'">
        <div class="tab-bar">
          <button :class="{ active: hyTab === 'config' }" @click="hyTab = 'config'">⚙ 配置</button>
          <button :class="{ active: hyTab === 'search' }" @click="hyTab = 'search'">🔎 检索测试</button>
          <button :class="{ active: hyTab === 'index' }" @click="hyTab = 'index'">📋 索引管理</button>
          <button :class="{ active: hyTab === 'log' }" @click="hyTab = 'log'">📜 检索日志</button>
        </div>

        <!-- Tab: 配置 -->
        <div v-if="hyTab === 'config'" class="tab-content config-tab">
          <div class="form-row">
            <div class="form-group">
              <label>名称</label>
              <input v-model="hyConfigForm.name" />
            </div>
            <div class="form-group">
              <label>类型</label>
              <select v-model="hyConfigForm.type">
                <option value="history">历史回顾</option>
                <option value="technique">技法参考</option>
                <option value="custom">自定义</option>
              </select>
            </div>
          </div>
          <div class="form-group">
            <label>Embedding 模型</label>
            <select v-model="hyConfigForm.embeddingModel">
              <option value="text-embedding-v3">text-embedding-v3 (在线, 1024维)</option>
              <option value="qwen3-embedding-4b">qwen3-embedding-4b (本地)</option>
            </select>
          </div>
          <div class="form-group">
            <label>检索维度</label>
            <div class="checkbox-row">
              <label><input type="checkbox" v-model="hyConfigForm.dimPlot" /> plot</label>
              <label><input type="checkbox" v-model="hyConfigForm.dimCharacter" /> character</label>
              <label><input type="checkbox" v-model="hyConfigForm.dimEmotion" /> emotion</label>
              <label><input type="checkbox" v-model="hyConfigForm.dimFunction" /> function</label>
            </div>
          </div>
          <div class="form-group config-inline">
            <label>文档增强</label>
            <input type="checkbox" v-model="hyConfigForm.enhancementEnabled" /> 索引时生成5视角改写
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>向量权重: {{ hyConfigForm.vectorWeight }}</label>
              <input type="range" min="0" max="1" step="0.1" v-model.number="hyConfigForm.vectorWeight" />
            </div>
            <div class="form-group">
              <label>关键词权重: {{ hyConfigForm.keywordWeight }}</label>
              <input type="range" min="0" max="1" step="0.1" v-model.number="hyConfigForm.keywordWeight" />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>单次返回</label>
              <input type="number" v-model.number="hyConfigForm.maxResults" min="1" max="50" />
            </div>
            <div class="form-group">
              <label>最大注入 tokens</label>
              <input type="number" v-model.number="hyConfigForm.maxInjectionTokens" min="100" max="10000" />
            </div>
            <div class="form-group">
              <label>最低阈值</label>
              <input type="number" v-model.number="hyConfigForm.threshold" min="0" max="1" step="0.05" />
            </div>
          </div>
          <button class="btn btn-primary" @click="saveHyConfig">保存配置</button>
        </div>

        <!-- Tab: 检索测试 -->
        <div v-if="hyTab === 'search'" class="tab-content">
          <RAGSearchTest :instanceId="currentId" :projectId="projectId" retrieverType="hybrid" />
        </div>

        <!-- Tab: 索引管理 -->
        <div v-if="hyTab === 'index'" class="tab-content">
          <div class="toolbar-row">
            <button class="btn btn-primary btn-sm" @click="addHybridDocs">＋添加文档</button>
            <button class="btn btn-sm" @click="rebuildIndex">🔄 重建索引</button>
            <span class="hint">共 {{ hyDocs.length }} 条索引</span>
          </div>
          <RAGDocTable :docs="hyDocs" @delete="deleteDoc" />
        </div>

        <!-- Tab: 检索日志 -->
        <div v-if="hyTab === 'log'" class="tab-content">
          <RAGSearchLog :instanceId="currentId" :projectId="projectId" />
        </div>
      </template>

      <!-- ============ Vector ============ -->
      <template v-if="currentConfig.retrieverType === 'vector'">
        <div class="tab-bar">
          <button :class="{ active: vTab === 'config' }" @click="vTab = 'config'">⚙ 配置</button>
          <button :class="{ active: vTab === 'search' }" @click="vTab = 'search'">🔎 检索测试</button>
          <button :class="{ active: vTab === 'index' }" @click="vTab = 'index'">📋 索引管理</button>
        </div>

        <div v-if="vTab === 'config'" class="tab-content config-tab">
          <div class="form-group"><label>名称</label><input v-model="vConfigForm.name" /></div>
          <div class="form-group">
            <label>Embedding 模型</label>
            <select v-model="vConfigForm.embeddingModel">
              <option value="text-embedding-v3">text-embedding-v3</option>
              <option value="qwen3-embedding-4b">qwen3-embedding-4b (本地)</option>
            </select>
          </div>
          <div class="form-group">
            <label>切片维度</label>
            <div class="checkbox-row">
              <label><input type="checkbox" v-model="vConfigForm.dimPlot" /> plot</label>
              <label><input type="checkbox" v-model="vConfigForm.dimCharacter" /> character</label>
              <label><input type="checkbox" v-model="vConfigForm.dimEmotion" /> emotion</label>
              <label><input type="checkbox" v-model="vConfigForm.dimFunction" /> function</label>
            </div>
          </div>
          <div class="form-row">
            <div class="form-group"><label>返回</label><input type="number" v-model.number="vConfigForm.maxResults" /></div>
            <div class="form-group"><label>阈值</label><input type="number" v-model.number="vConfigForm.threshold" step="0.05" /></div>
          </div>
          <button class="btn btn-primary" @click="saveVConfig">保存配置</button>
        </div>

        <div v-if="vTab === 'search'" class="tab-content">
          <RAGSearchTest :instanceId="currentId" :projectId="projectId" retrieverType="vector" />
        </div>

        <div v-if="vTab === 'index'" class="tab-content">
          <RAGDocTable :docs="hyDocs" @delete="deleteDoc" />
        </div>
      </template>

    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import RAGSearchTest from '../components/rag/RAGSearchTest.vue'
import RAGSearchLog from '../components/rag/RAGSearchLog.vue'
import RAGDocTable from '../components/rag/RAGDocTable.vue'

const route = useRoute()
const projectId = computed(() => route.query.projectId || '')

const instances = ref([])
const currentId = ref('默认实例')
const currentConfig = ref(null)
const showCreate = ref(false)
const createForm = ref({ name: '', type: 'history', retrieverType: 'keyword', embeddingModel: 'text-embedding-v3' })
const kwTab = ref('docs')
const hyTab = ref('config')
const vTab = ref('config')
const kwDocs = ref([])
const hyDocs = ref([])
const kwShowAddDoc = ref(false)
const kwNewDoc = ref({ id: '', content: '', tags: '' })

const importInput = ref(null)

const mechanismHint = computed(() => {
  switch (createForm.value.retrieverType) {
    case 'keyword': return '纯 TF-IDF 关键词匹配，无需外部依赖。适合小数据量快速原型。'
    case 'hybrid': return '向量相似度 60% + 关键词 40%。生产环境推荐。需要 ChromaDB + Embedding API。'
    case 'vector': return '纯 ChromaDB embedding 语义检索。需要 ChromaDB + Embedding API。'
    default: return ''
  }
})

// Hybrid 配置表单
const hyConfigForm = ref({
  name: '', type: 'history', embeddingModel: 'text-embedding-v3',
  dimPlot: true, dimCharacter: true, dimEmotion: true, dimFunction: true,
  enhancementEnabled: true, vectorWeight: 0.6, keywordWeight: 0.4,
  maxResults: 5, maxInjectionTokens: 2000, threshold: 0.2
})

// Vector 配置表单
const vConfigForm = ref({
  name: '', embeddingModel: 'text-embedding-v3',
  dimPlot: true, dimCharacter: true, dimEmotion: true, dimFunction: true,
  maxResults: 5, threshold: 0.3
})

async function loadInstances() {
  if (!projectId.value) return
  try {
    const res = await axios.get(`/api/projects/${projectId.value}/rags`)
    instances.value = res.data.instances || []
    if (instances.value.length > 0 && !instances.value.find(i => i.instanceId === currentId.value)) {
      currentId.value = instances.value[0].instanceId
    }
    await loadCurrentConfig()
  } catch (e) { console.error('loadInstances', e) }
}

async function loadCurrentConfig() {
  if (!currentId.value) return
  try {
    const res = await axios.get(`/api/projects/${projectId.value}/rags/${currentId.value}`)
    currentConfig.value = res.data.instance
    // 加载文档
    const docsRes = await axios.get(`/api/projects/${projectId.value}/rags/${currentId.value}/documents`)
    kwDocs.value = docsRes.data.documents || []
    hyDocs.value = docsRes.data.documents || []

    // 填充 hybrid 表单
    const c = currentConfig.value
    if (c.retrieverType === 'hybrid') {
      hyConfigForm.value = {
        name: c.name, type: c.type, embeddingModel: c.embeddingModel || 'text-embedding-v3',
        dimPlot: c.slicingDimensions?.includes('plot') ?? true,
        dimCharacter: c.slicingDimensions?.includes('character') ?? true,
        dimEmotion: c.slicingDimensions?.includes('emotion') ?? true,
        dimFunction: c.slicingDimensions?.includes('function') ?? true,
        enhancementEnabled: c.enhancementEnabled ?? true,
        vectorWeight: c.vectorWeight ?? 0.6, keywordWeight: c.keywordWeight ?? 0.4,
        maxResults: c.maxResults || 5, maxInjectionTokens: c.maxInjectionTokens || 2000,
        threshold: c.threshold || 0.2
      }
    }
    if (c.retrieverType === 'vector') {
      vConfigForm.value = {
        name: c.name, embeddingModel: c.embeddingModel || 'text-embedding-v3',
        dimPlot: c.slicingDimensions?.includes('plot') ?? true,
        dimCharacter: c.slicingDimensions?.includes('character') ?? true,
        dimEmotion: c.slicingDimensions?.includes('emotion') ?? true,
        dimFunction: c.slicingDimensions?.includes('function') ?? true,
        maxResults: c.maxResults || 5, threshold: c.threshold || 0.3
      }
    }
  } catch (e) { console.error('loadCurrentConfig', e) }
}

function switchInstance() { loadCurrentConfig() }

async function createInstance() {
  try {
    await axios.post(`/api/projects/${projectId.value}/rags`, createForm.value)
    showCreate.value = false
    createForm.value = { name: '', type: 'history', retrieverType: 'keyword', embeddingModel: 'text-embedding-v3' }
    await loadInstances()
    currentId.value = instances.value[instances.value.length - 1].instanceId
    await loadCurrentConfig()
  } catch (e) { alert('创建失败: ' + (e.response?.data?.error || e.message)) }
}

async function deleteCurrent() {
  if (!confirm('确定删除实例 "' + currentId.value + '"？')) return
  await axios.delete(`/api/projects/${projectId.value}/rags/${currentId.value}`)
  await loadInstances()
}

async function exportInstance() {
  const res = await axios.get(`/api/projects/${projectId.value}/rags/${currentId.value}/export`)
  const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a'); a.href = url; a.download = `rag_${currentId.value}.json`; a.click()
  URL.revokeObjectURL(url)
}

function triggerImport() { importInput.value?.click() }

async function handleImport(e) {
  const file = e.target.files?.[0]
  if (!file) return
  try {
    const data = JSON.parse(await file.text())
    await axios.post(`/api/projects/${projectId.value}/rags/import`, data)
    await loadInstances()
  } catch (err) { alert('导入失败: ' + err.message) }
  e.target.value = ''
}

// Keyword 操作
async function addDocument() {
  const tags = kwNewDoc.value.tags ? kwNewDoc.value.tags.split(',').map(t => t.trim()).filter(Boolean) : []
  await axios.post(`/api/projects/${projectId.value}/rags/${currentId.value}/documents`, {
    documents: [{ id: kwNewDoc.value.id || undefined, content: kwNewDoc.value.content, metadata: { tags } }]
  })
  kwNewDoc.value = { id: '', content: '', tags: '' }
  kwShowAddDoc.value = false
  await refreshDocs()
}

async function deleteDoc(id) {
  await axios.delete(`/api/projects/${projectId.value}/rags/${currentId.value}/documents`, { data: { ids: [id] } })
  await refreshDocs()
}

async function clearDocs() {
  if (!confirm('确定清空全部文档？')) return
  await axios.delete(`/api/projects/${projectId.value}/rags/${currentId.value}/documents/all`)
  await refreshDocs()
}

async function refreshDocs() {
  try {
    const res = await axios.get(`/api/projects/${projectId.value}/rags/${currentId.value}/documents`)
    kwDocs.value = res.data.documents || []
    hyDocs.value = res.data.documents || []
  } catch {}
}

// Hybrid 配置保存
async function saveHyConfig() {
  const dims = []
  if (hyConfigForm.value.dimPlot) dims.push('plot')
  if (hyConfigForm.value.dimCharacter) dims.push('character')
  if (hyConfigForm.value.dimEmotion) dims.push('emotion')
  if (hyConfigForm.value.dimFunction) dims.push('function')
  await axios.put(`/api/projects/${projectId.value}/rags/${currentId.value}`, {
    name: hyConfigForm.value.name,
    type: hyConfigForm.value.type,
    embeddingModel: hyConfigForm.value.embeddingModel,
    slicingDimensions: dims,
    enhancementEnabled: hyConfigForm.value.enhancementEnabled,
    vectorWeight: hyConfigForm.value.vectorWeight,
    keywordWeight: hyConfigForm.value.keywordWeight,
    maxResults: hyConfigForm.value.maxResults,
    maxInjectionTokens: hyConfigForm.value.maxInjectionTokens,
    threshold: hyConfigForm.value.threshold
  })
  await loadCurrentConfig()
  alert('配置已保存')
}

async function saveVConfig() {
  const dims = []
  if (vConfigForm.value.dimPlot) dims.push('plot')
  if (vConfigForm.value.dimCharacter) dims.push('character')
  if (vConfigForm.value.dimEmotion) dims.push('emotion')
  if (vConfigForm.value.dimFunction) dims.push('function')
  await axios.put(`/api/projects/${projectId.value}/rags/${currentId.value}`, {
    name: vConfigForm.value.name,
    embeddingModel: vConfigForm.value.embeddingModel,
    slicingDimensions: dims,
    maxResults: vConfigForm.value.maxResults,
    threshold: vConfigForm.value.threshold
  })
  await loadCurrentConfig()
  alert('配置已保存')
}

async function addHybridDocs() {
  const id = prompt('文档 ID:')
  if (!id) return
  const content = prompt('内容:')
  if (!content) return
  await axios.post(`/api/projects/${projectId.value}/rags/${currentId.value}/documents`, {
    documents: [{ id, content }]
  })
  await refreshDocs()
}

async function rebuildIndex() {
  alert('重建索引：当前 ChromaDB 未集成，操作无效。文档已保存在 keyword 层。')
}

onMounted(() => { if (projectId.value) loadInstances() })
watch(projectId, () => { if (projectId.value) loadInstances() })
</script>

<style scoped>
.rag-manager { padding: 16px; max-width: 1100px; }
.instance-bar { display: flex; align-items: center; gap: 8px; margin: 12px 0 16px; padding: 8px 12px; background: #f8f9fa; border-radius: 8px; flex-wrap: wrap; }
.instance-bar .sep { width: 1px; height: 20px; background: #ddd; margin: 0 4px; }
.instance-selector label { font-weight: 600; margin-right: 4px; }
.instance-selector select { min-width: 200px; }

.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal-box { background: #fff; padding: 24px; border-radius: 12px; min-width: 420px; }
.modal-box h3 { margin-top: 0; }
.modal-box .form-group { margin-bottom: 12px; }
.modal-box label { display: block; font-weight: 600; margin-bottom: 4px; font-size: 13px; }
.modal-box input, .modal-box select { width: 100%; padding: 6px 10px; border: 1px solid #ddd; border-radius: 6px; box-sizing: border-box; }
.modal-btns { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }
.mechanism-hint { font-size: 12px; color: #888; margin-top: 8px; }

.tab-bar { display: flex; gap: 4px; border-bottom: 2px solid #eee; margin-bottom: 12px; }
.tab-bar button { padding: 8px 16px; border: none; background: none; cursor: pointer; font-size: 14px; border-bottom: 2px solid transparent; margin-bottom: -2px; }
.tab-bar button.active { border-bottom-color: #3498db; color: #3498db; font-weight: 600; }

.tab-content { min-height: 200px; }
.toolbar-row { display: flex; gap: 8px; align-items: center; margin-bottom: 12px; }
.add-doc-form { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; align-items: flex-end; }
.add-doc-form input, .add-doc-form textarea { padding: 4px 8px; border: 1px solid #ddd; border-radius: 4px; }

.doc-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.doc-table th { text-align: left; padding: 6px 8px; border-bottom: 2px solid #eee; background: #fafafa; }
.doc-table td { padding: 6px 8px; border-bottom: 1px solid #f0f0f0; }
.content-cell { max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.config-tab { max-width: 600px; }
.config-tab .form-group { margin-bottom: 12px; }
.config-tab label { display: block; font-weight: 600; margin-bottom: 4px; font-size: 13px; }
.config-tab input[type="text"],
.config-tab input[type="number"],
.config-tab select { width: 100%; padding: 6px 10px; border: 1px solid #ddd; border-radius: 6px; }
.config-tab input[type="range"] { width: 100%; }
.config-tab .form-row { display: flex; gap: 16px; }
.config-tab .form-row .form-group { flex: 1; }
.checkbox-row { display: flex; gap: 16px; }
.checkbox-row label { font-weight: 400; display: flex; align-items: center; gap: 4px; }
.config-inline { display: flex; align-items: center; gap: 8px; }
.config-inline label { margin-bottom: 0; }

.hint { color: #999; font-size: 12px; }

.btn { padding: 6px 14px; border: 1px solid #ddd; border-radius: 6px; background: #fff; cursor: pointer; font-size: 13px; }
.btn-primary { background: #3498db; color: #fff; border-color: #3498db; }
.btn-sm { padding: 4px 10px; font-size: 12px; }
.btn:disabled { opacity: 0.5; cursor: default; }
</style>
