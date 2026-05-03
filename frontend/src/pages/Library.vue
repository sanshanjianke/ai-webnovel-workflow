<template>
  <div class="library-page">
    <div class="library-main">
      <div class="library-header">
        <h2>文档库</h2>
        <div class="header-actions">
          <button class="btn btn-primary" @click="createNewDoc">新建文档</button>
          <button class="btn" @click="loadLibrary">刷新</button>
        </div>
      </div>
      
      <div class="library-content" v-if="selectedDoc">
        <div class="doc-preview">
          <div class="doc-meta">
            <h3>{{ selectedDoc.name }}</h3>
            <div class="meta-info">
              <span class="meta-item">
                <span class="meta-label">层级:</span>
                <span class="meta-value">{{ selectedDoc.layer.toUpperCase() }}</span>
              </span>
              <span class="meta-item">
                <span class="meta-label">来源:</span>
                <span class="meta-value">{{ sourceLabel }}</span>
              </span>
              <span class="meta-item">
                <span class="meta-label">字数:</span>
                <span class="meta-value">{{ selectedDoc.word_count }}</span>
              </span>
              <span class="meta-item">
                <span class="meta-label">创建:</span>
                <span class="meta-value">{{ formatDate(selectedDoc.created_at) }}</span>
              </span>
            </div>
            <div class="meta-tags" v-if="selectedDoc.tags?.length">
              <span class="tag" v-for="tag in selectedDoc.tags" :key="tag">{{ tag }}</span>
            </div>
          </div>
          
          <div class="doc-provenance" v-if="provenance.length > 1">
            <h4>溯源链</h4>
            <div class="provenance-chain">
              <div 
                v-for="(p, i) in provenance" 
                :key="p.uid"
                class="chain-item"
                :class="{ current: p.uid === selectedDoc.uid }"
              >
                <span class="chain-icon">{{ getDocIcon(p.layer) }}</span>
                <span class="chain-name">{{ p.name }}</span>
                <span v-if="i < provenance.length - 1" class="chain-arrow">←</span>
              </div>
            </div>
          </div>
          
          <div class="doc-content">
            <h4>内容预览</h4>
            <pre class="content-preview">{{ contentPreview }}</pre>
          </div>
          
          <div class="doc-actions">
            <button class="btn btn-primary" @click="openDoc">查看全文</button>
            <button class="btn" @click="setAsActive">设为活跃文档</button>
            <button class="btn" @click="exportDoc">导出</button>
            <button class="btn btn-danger" @click="deleteDoc">删除</button>
          </div>
        </div>
      </div>
      
      <div class="library-empty" v-else>
        <p>从左侧选择一个文档查看详情</p>
      </div>
    </div>
    
    <div class="create-dialog" v-if="showCreateDialog">
      <div class="dialog-overlay" @click="showCreateDialog = false"></div>
      <div class="dialog-content">
        <h3>新建文档</h3>
        <div class="form-group">
          <label>名称</label>
          <input v-model="newDoc.name" placeholder="文档名称" />
        </div>
        <div class="form-group">
          <label>层级</label>
          <select v-model="newDoc.layer">
            <option value="l1">L1 愿景</option>
            <option value="l2">L2 大纲</option>
            <option value="l3">L3 章纲</option>
            <option value="l4">L4 正文</option>
          </select>
        </div>
        <div class="form-group">
          <label>内容 (JSON)</label>
          <textarea v-model="newDoc.content" placeholder='{"key": "value"}' rows="5"></textarea>
        </div>
        <div class="dialog-actions">
          <button class="btn" @click="showCreateDialog = false">取消</button>
          <button class="btn btn-primary" @click="submitNewDoc">创建</button>
        </div>
      </div>
    </div>
    
    <div class="create-dialog" v-if="showViewDialog">
      <div class="dialog-overlay" @click="showViewDialog = false"></div>
      <div class="dialog-content large">
        <div class="view-header">
          <h3>{{ selectedDoc?.name }}</h3>
          <button class="btn-close" @click="closeViewDialog">×</button>
        </div>
        <textarea v-if="isEditing" v-model="editContent" class="view-content-edit"></textarea>
        <pre v-else class="view-content">{{ fullContent }}</pre>
        <div class="dialog-actions">
          <button class="btn" @click="closeViewDialog">关闭</button>
          <button v-if="!isEditing" class="btn" @click="startEditing">编辑</button>
          <button v-if="isEditing" class="btn" @click="cancelEditing">取消</button>
          <button v-if="isEditing" class="btn btn-primary" @click="saveEditedContent" :disabled="isSaving">
            {{ isSaving ? '保存中...' : '保存' }}
          </button>
          <button v-if="!isEditing" class="btn btn-primary" @click="copyContent">复制内容</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const projectId = computed(() => route.query.projectId)

const selectedDoc = ref(null)
const docContent = ref(null)
const provenance = ref([])
const showCreateDialog = ref(false)
const showViewDialog = ref(false)
const isEditing = ref(false)
const editContent = ref('')
const isSaving = ref(false)

const newDoc = ref({
  name: '',
  layer: 'l1',
  content: '{}'
})

const apiBase = computed(() => `/api/projects/${projectId.value}/library`)

const sourceLabel = computed(() => {
  const labels = {
    generate: '系统生成',
    import: '导入',
    manual: '手动创建'
  }
  return labels[selectedDoc.value?.source] || selectedDoc.value?.source
})

const contentPreview = computed(() => {
  if (!docContent.value) return ''
  let content = docContent.value
  if (typeof content === 'object' && content.content) {
    content = content.content
  }
  const str = typeof content === 'string' 
    ? content 
    : JSON.stringify(content, null, 2)
  return str.length > 500 ? str.slice(0, 500) + '...' : str
})

const fullContent = computed(() => {
  if (!docContent.value) return ''
  let content = docContent.value
  if (typeof content === 'object' && content.content) {
    content = content.content
  }
  return typeof content === 'string' 
    ? content 
    : JSON.stringify(content, null, 2)
})

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleString('zh-CN')
}

const getDocIcon = (layer) => {
  const icons = {
    l1: '💡',
    l2: '🏗️',
    l3: '📝',
    l4: '📖',
    imported: '📥'
  }
  return icons[layer] || '📄'
}

const loadLibrary = async () => {
  window.dispatchEvent(new CustomEvent('library-refresh'))
}

const loadDocument = async (uid) => {
  if (!uid) return
  
  try {
    const res = await fetch(`${apiBase.value}/${uid}`)
    const data = await res.json()
    selectedDoc.value = data.entry
    docContent.value = data.content
    provenance.value = data.provenance || []
  } catch (err) {
    console.error('Failed to load document:', err)
  }
}

const openDoc = () => {
  console.log('openDoc called', { selectedDoc: selectedDoc.value, docContent: docContent.value })
  if (!selectedDoc.value || !docContent.value) {
    alert('请先选择一个文档')
    return
  }
  console.log('Setting showViewDialog to true')
  showViewDialog.value = true
  console.log('showViewDialog is now', showViewDialog.value)
}

const copyContent = async () => {
  try {
    await navigator.clipboard.writeText(fullContent.value)
    alert('已复制到剪贴板')
  } catch (err) {
    console.error('Copy failed:', err)
  }
}

const startEditing = () => {
  isEditing.value = true
  editContent.value = fullContent.value
}

const cancelEditing = () => {
  isEditing.value = false
  editContent.value = ''
}

const saveEditedContent = async () => {
  if (!selectedDoc.value) return
  
  isSaving.value = true
  try {
    let content = editContent.value
    try {
      content = JSON.parse(content)
    } catch {
    }
    
    await fetch(`${apiBase.value}/${selectedDoc.value.uid}/content`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content })
    })
    
    docContent.value = content
    isEditing.value = false
  } catch (err) {
    console.error('Save failed:', err)
    alert('保存失败')
  } finally {
    isSaving.value = false
  }
}

const closeViewDialog = () => {
  showViewDialog.value = false
  isEditing.value = false
  editContent.value = ''
}

const setAsActive = async () => {
  if (!selectedDoc.value) return
  
  try {
    await fetch(`${apiBase.value}/active/${selectedDoc.value.layer}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ uid: selectedDoc.value.uid })
    })
    alert('已设为活跃文档')
  } catch (err) {
    console.error('Failed to set active:', err)
  }
}

const exportDoc = async () => {
  console.log('exportDoc called', selectedDoc.value)
  if (!selectedDoc.value) return
  
  try {
    const res = await fetch(`${apiBase.value}/${selectedDoc.value.uid}`)
    const data = await res.json()
    console.log('export data', data)
    
    let content = data.content
    if (typeof content === 'object' && content.content) {
      content = content.content
    }
    if (typeof content !== 'string') {
      content = JSON.stringify(content, null, 2)
    }
    console.log('export content', content.substring(0, 100))
    
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${selectedDoc.value.name}.txt`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    console.log('export done')
  } catch (err) {
    console.error('Export failed:', err)
    alert('导出失败: ' + err.message)
  }
}

const deleteDoc = async () => {
  if (!selectedDoc.value) return
  if (!confirm(`确定删除文档 "${selectedDoc.value.name}"？`)) return
  
  try {
    await fetch(`${apiBase.value}/${selectedDoc.value.uid}`, { method: 'DELETE' })
    selectedDoc.value = null
    docContent.value = null
    loadLibrary()
  } catch (err) {
    console.error('Delete failed:', err)
    alert('删除失败')
  }
}

const createNewDoc = () => {
  newDoc.value = { name: '', layer: 'l1', content: '{}' }
  showCreateDialog.value = true
}

const submitNewDoc = async () => {
  let content
  try {
    content = JSON.parse(newDoc.value.content)
  } catch {
    content = newDoc.value.content
  }
  
  try {
    await fetch(`${apiBase.value}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: newDoc.value.name,
        layer: newDoc.value.layer,
        content
      })
    })
    showCreateDialog.value = false
    loadLibrary()
  } catch (err) {
    console.error('Failed to create document:', err)
  }
}

const onDocSelected = (event) => {
  if (event.detail) {
    loadDocument(event.detail.uid)
  }
}

const onDocView = async (event) => {
  console.log('onDocView called', event.detail)
  if (event.detail) {
    await loadDocument(event.detail.uid)
    console.log('loadDocument done, setting showViewDialog')
    showViewDialog.value = true
    console.log('showViewDialog:', showViewDialog.value)
  }
}

onMounted(() => {
  window.addEventListener('document-selected', onDocSelected)
  window.addEventListener('document-view', onDocView)
})

onUnmounted(() => {
  window.removeEventListener('document-selected', onDocSelected)
  window.removeEventListener('document-view', onDocView)
})
</script>

<style scoped>
.library-page {
  display: flex;
  height: 100%;
}

.library-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.library-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  background: white;
  border-bottom: 1px solid #e0e0e0;
}

.library-header h2 {
  font-size: 1.25rem;
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 0.5rem;
}

.library-content {
  flex: 1;
  padding: 1.5rem;
  overflow-y: auto;
}

.library-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #666;
}

.doc-preview {
  background: white;
  border-radius: 8px;
  padding: 1.5rem;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.doc-meta h3 {
  margin: 0 0 1rem 0;
  font-size: 1.25rem;
}

.meta-info {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  margin-bottom: 1rem;
}

.meta-item {
  font-size: 0.875rem;
}

.meta-label {
  color: #666;
  margin-right: 0.25rem;
}

.meta-value {
  font-weight: 500;
}

.meta-tags {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.tag {
  background: #e3f2fd;
  color: #1976d2;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
}

.doc-provenance {
  margin: 1.5rem 0;
  padding: 1rem;
  background: #f5f5f5;
  border-radius: 4px;
}

.doc-provenance h4 {
  margin: 0 0 0.75rem 0;
  font-size: 0.875rem;
  color: #666;
}

.provenance-chain {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.chain-item {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.25rem 0.5rem;
  background: white;
  border-radius: 4px;
  font-size: 0.875rem;
}

.chain-item.current {
  background: #e3f2fd;
  font-weight: 500;
}

.chain-arrow {
  color: #999;
}

.doc-content {
  margin-top: 1.5rem;
}

.doc-content h4 {
  margin: 0 0 0.75rem 0;
  font-size: 0.875rem;
  color: #666;
}

.content-preview {
  background: #f8f9fa;
  padding: 1rem;
  border-radius: 4px;
  font-family: monospace;
  font-size: 0.875rem;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 300px;
  overflow: auto;
  margin: 0;
}

.doc-actions {
  margin-top: 1.5rem;
  display: flex;
  gap: 0.5rem;
}

.btn {
  padding: 0.5rem 1rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  background: white;
  cursor: pointer;
  font-size: 0.875rem;
}

.btn:hover {
  background: #f5f5f5;
}

.btn-primary {
  background: #3498db;
  border-color: #3498db;
  color: white;
}

.btn-primary:hover {
  background: #2980b9;
}

.btn-danger {
  background: #e74c3c;
  border-color: #e74c3c;
  color: white;
}

.btn-danger:hover {
  background: #c0392b;
}

.create-dialog {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.dialog-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0,0,0,0.3);
}

.dialog-content {
  position: relative;
  background: white;
  padding: 1.5rem;
  border-radius: 8px;
  min-width: 400px;
  max-width: 90vw;
}

.dialog-content.large {
  width: 800px;
  max-width: 95vw;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
}

.view-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.view-header h3 {
  margin: 0;
  font-size: 1rem;
}

.btn-close {
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: #666;
  padding: 0;
  line-height: 1;
}

.btn-close:hover {
  color: #333;
}

.view-content {
  flex: 1;
  background: #f8f9fa;
  padding: 1rem;
  border-radius: 4px;
  font-family: monospace;
  font-size: 0.875rem;
  white-space: pre-wrap;
  word-break: break-all;
  overflow: auto;
  margin: 0;
  max-height: 60vh;
}

.view-content-edit {
  flex: 1;
  background: #fff;
  padding: 1rem;
  border-radius: 4px;
  font-family: monospace;
  font-size: 0.875rem;
  white-space: pre-wrap;
  word-break: break-all;
  overflow: auto;
  margin: 0;
  max-height: 60vh;
  border: 2px solid #3498db;
  resize: none;
}

.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-size: 0.875rem;
  font-weight: 500;
}

.form-group input,
.form-group select,
.form-group textarea {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 0.875rem;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 1rem;
}
</style>
