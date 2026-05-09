<template>
  <div 
    class="library-sidebar" 
    :class="{ collapsed: isCollapsed }"
    :style="{ width: isCollapsed ? '40px' : sidebarWidth + 'px' }"
  >
    <div class="sidebar-header">
      <span v-if="!isCollapsed" class="sidebar-title">文档库</span>
      <button class="btn-toggle" @click="toggleCollapse">
        {{ isCollapsed ? '▶' : '◀' }}
      </button>
    </div>
    
    <div v-if="!isCollapsed" class="sidebar-content">
      <div class="sidebar-toolbar">
        <button class="btn-sm" @click="refresh" title="刷新">⟳</button>
        <button class="btn-sm" @click="createDirectory" title="新建目录">📁</button>
        <button class="btn-sm" @click="triggerImport" title="导入文件">📥</button>
        <button class="btn-sm btn-danger-sm" @click="deleteSelected" title="删除选中文档" :disabled="!activeDocUid">🗑️</button>
        <input 
          ref="fileInput" 
          type="file" 
          accept=".json,.md,.txt" 
          @change="handleImport"
          style="display: none"
        />
      </div>
      
      <div v-if="!hasProject" class="loading">请先选择项目</div>
      <div v-else-if="loading" class="loading">加载中...</div>
      
      <div v-else class="document-tree" 
        @contextmenu.prevent="showDirContext($event, '/')"
        @dragover="onDragOver($event, '/')"
        @dragleave="onDragLeave($event)"
        @drop="onDrop($event, '/')"
        :class="{ 'drag-over': dragOverDir === '/' }"
      >
        <template v-for="item in getTreeItems('/')" :key="item.path || item.uid">
          <div v-if="item.type === 'dir'" class="directory-item">
            <div 
              class="directory-header"
              :class="{ 'drag-over': dragOverDir === item.path }"
              @click="toggleDirectory(item.path)"
              @contextmenu.prevent.stop="showDirContext($event, item.path)"
              @dragover.stop="onDragOver($event, item.path)"
              @dragleave.stop="onDragLeave($event)"
              @drop.stop="onDrop($event, item.path)"
            >
              <span class="dir-icon">{{ expandedDirs.has(item.path) ? '📂' : '📁' }}</span>
              <span class="dir-name">{{ item.name }}</span>
            </div>
            <div v-show="expandedDirs.has(item.path)" class="directory-children">
              <div
                v-for="doc in getDocsInDir(item.path)"
                :key="doc.uid"
                class="document-item"
                :class="{ 
                  active: activeDocUid === doc.uid,
                  archived: doc.status === 'archived',
                  draft: doc.status === 'draft'
                }"
                draggable="true"
                @click="selectDocument(doc)"
                @dblclick="openDocument(doc)"
                @contextmenu.prevent.stop="showDocContext($event, doc)"
                @dragstart="onDragStart($event, doc)"
                @dragend="onDragEnd($event)"
              >
                <span class="doc-icon">{{ getDocIcon(doc.layer) }}</span>
                <span class="doc-name">{{ doc.name }}</span>
                <span v-if="isActiveForLayer(doc)" class="active-badge">●</span>
              </div>
            </div>
          </div>
          <div
            v-else
            class="document-item"
            :class="{ 
              active: activeDocUid === item.uid,
              archived: item.status === 'archived',
              draft: item.status === 'draft'
            }"
            draggable="true"
            @click="selectDocument(item)"
            @dblclick="openDocument(item)"
            @contextmenu.prevent.stop="showDocContext($event, item)"
            @dragstart="onDragStart($event, item)"
            @dragend="onDragEnd($event)"
          >
            <span class="doc-icon">{{ getDocIcon(item.layer) }}</span>
            <span class="doc-name">{{ item.name }}</span>
            <span v-if="isActiveForLayer(item)" class="active-badge">●</span>
          </div>
        </template>
      </div>
      
      <div class="sidebar-footer">
        <span class="doc-count">{{ documents.length }} 个文档</span>
      </div>
    </div>
    
    <div 
      v-if="contextMenu.show" 
      class="context-menu"
      :style="{ top: contextMenu.y + 'px', left: contextMenu.x + 'px' }"
    >
      <div v-if="contextMenu.type === 'doc'" class="menu-items" @click.stop>
        <div @click="openDocument(contextMenu.item)">打开</div>
        <div @click="setAsActive">设为活跃</div>
        <div @click="renameDocument">重命名</div>
        <div @click="toggleArchive">{{ contextMenu.item?.status === 'archived' ? '取消归档' : '归档' }}</div>
        <div class="menu-divider"></div>
        <div @click="exportDocument">导出</div>
        <div class="menu-danger" @click.stop="deleteDocument">删除</div>
      </div>
      <div v-else-if="contextMenu.type === 'dir'" class="menu-items" @click.stop>
        <div @click="createDocInDir">新建文档</div>
        <div @click="importToDir">导入文件</div>
        <div @click="createSubDirectory">新建子目录</div>
        <div v-if="contextMenu.item !== '/'" class="menu-danger" @click="removeDirectory">删除目录</div>
      </div>
    </div>
    
    <div v-if="viewDialog.show" class="view-dialog">
      <div class="dialog-overlay" @click="viewDialog.show = false"></div>
      <div class="dialog-content">
        <div class="dialog-header">
          <h3>{{ viewDialog.name }}</h3>
          <button class="btn-close" @click="viewDialog.show = false">×</button>
        </div>
        <textarea 
          v-if="viewDialog.editing" 
          v-model="viewDialog.content" 
          class="dialog-body-edit"
        ></textarea>
        <pre v-else class="dialog-body">{{ viewDialog.content }}</pre>
        <div class="dialog-footer">
          <button class="btn" @click="viewDialog.show = false">关闭</button>
          <button v-if="!viewDialog.editing" class="btn" @click="startEdit">编辑</button>
          <button v-if="viewDialog.editing" class="btn" @click="cancelEdit">取消</button>
          <button v-if="viewDialog.editing" class="btn btn-primary" @click="saveContent" :disabled="viewDialog.saving">
            {{ viewDialog.saving ? '保存中...' : '保存' }}
          </button>
          <button v-if="!viewDialog.editing" class="btn btn-primary" @click="copyViewContent">复制</button>
        </div>
      </div>
    </div>
    
    <div v-if="createDocDialog.show" class="view-dialog">
      <div class="dialog-overlay" @click="createDocDialog.show = false"></div>
      <div class="dialog-content" style="width: 400px;">
        <div class="dialog-header">
          <h3>新建文档</h3>
          <button class="btn-close" @click="createDocDialog.show = false">×</button>
        </div>
        <div style="padding: 1rem;">
          <div class="form-group">
            <label>名称</label>
            <input v-model="createDocDialog.name" placeholder="文档名称" />
          </div>
          <div class="form-group">
            <label>目录</label>
            <input :value="createDocDialog.directory" disabled />
          </div>
        </div>
        <div class="dialog-footer">
          <button class="btn" @click="createDocDialog.show = false">取消</button>
          <button class="btn btn-primary" @click="submitCreateDoc">创建</button>
        </div>
      </div>
    </div>
    
    <div 
      v-if="!isCollapsed"
      class="resize-handle"
      @mousedown="startResize"
    ></div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const props = defineProps({
  projectId: {
    type: String,
    required: true
  }
})

const emit = defineEmits(['document-selected', 'document-opened', 'active-changed'])

const route = useRoute()
const router = useRouter()

const isCollapsed = ref(false)
const loading = ref(false)
const documents = ref([])
const directories = ref(['/'])
const activeDocs = ref({})
const expandedDirs = ref(new Set(['/']))
const activeDocUid = ref(null)
const fileInput = ref(null)
const importDirectory = ref('/')
const sidebarWidth = ref(280)
const isResizing = ref(false)

const contextMenu = ref({
  show: false,
  x: 0,
  y: 0,
  type: null,
  item: null
})

const viewDialog = ref({
  show: false,
  name: '',
  content: '',
  uid: '',
  editing: false,
  originalContent: '',
  saving: false
})

const createDocDialog = ref({
  show: false,
  name: '',
  directory: '/'
})

const apiBase = computed(() => `/api/projects/${props.projectId}/library`)

const toggleCollapse = () => {
  isCollapsed.value = !isCollapsed.value
}

const toggleDirectory = (dir) => {
  if (expandedDirs.value.has(dir)) {
    expandedDirs.value.delete(dir)
  } else {
    expandedDirs.value.add(dir)
  }
  expandedDirs.value = new Set(expandedDirs.value)
}

const getDocsInDir = (dir) => {
  return documents.value.filter(doc => doc.directory === dir && doc.status !== 'archived')
}

const getSubDirectories = (parentDir) => {
  return directories.value.filter(d => {
    if (d === parentDir) return false
    if (parentDir === '/') {
      return d.startsWith('/') && d.lastIndexOf('/') === 0
    }
    return d.startsWith(parentDir + '/') && d.lastIndexOf('/') === parentDir.length
  })
}

const getTreeItems = (dir) => {
  const items = []
  const subDirs = getSubDirectories(dir)
  
  for (const subDir of subDirs) {
    const name = subDir.split('/').pop()
    items.push({
      type: 'dir',
      path: subDir,
      name: name
    })
  }
  
  const docs = getDocsInDir(dir)
  for (const doc of docs) {
    items.push({
      type: 'doc',
      ...doc
    })
  }
  
  return items
}

const getDocIcon = (layer) => {
  const icons = {
    l1: '💡',
    l2: '🏗️',
    imported: '📥'
  }
  return icons[layer] || '📄'
}

const isActiveForLayer = (doc) => {
  return activeDocs.value[doc.layer] === doc.uid
}

const selectDocument = (doc) => {
  activeDocUid.value = doc.uid
  emit('document-selected', doc)
  window.dispatchEvent(new CustomEvent('document-selected', { detail: doc }))
}

const onDragStart = (event, doc) => {
  event.dataTransfer.setData('text/plain', doc.uid)
  event.dataTransfer.setData('application/json', JSON.stringify(doc))
  event.dataTransfer.setData('document-name', doc.name)
  event.dataTransfer.effectAllowed = 'move'
  event.target.style.opacity = '0.5'
}

const onDragEnd = (event) => {
  event.target.style.opacity = '1'
}

const dragOverDir = ref(null)

const onDragOver = (event, dir) => {
  event.preventDefault()
  event.dataTransfer.dropEffect = 'move'
  dragOverDir.value = dir
}

const onDragLeave = (event) => {
  if (!event.currentTarget.contains(event.relatedTarget)) {
    dragOverDir.value = null
  }
}

const onDrop = async (event, targetDir) => {
  event.preventDefault()
  dragOverDir.value = null
  
  const docUid = event.dataTransfer.getData('text/plain')
  if (!docUid) return
  
  const doc = documents.value.find(d => d.uid === docUid)
  if (!doc) return
  
  if (doc.directory === targetDir) return
  
  try {
    await fetch(`${apiBase.value}/${docUid}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ directory: targetDir })
    })
    await refresh()
  } catch (err) {
    console.error('Move document failed:', err)
    alert('移动文档失败')
  }
}

const openDocument = async (doc) => {
  console.log('openDocument called, doc:', doc)
  
  if (route.path === '/library') {
    window.dispatchEvent(new CustomEvent('document-selected', { detail: doc }))
    window.dispatchEvent(new CustomEvent('document-view', { detail: doc }))
  } else {
    try {
      const res = await fetch(`${apiBase.value}/${doc.uid}`)
      const data = await res.json()
      
      let content = data.content
      if (typeof content === 'object' && content.content) {
        content = content.content
      }
      if (typeof content !== 'string') {
        content = JSON.stringify(content, null, 2)
      }
      
      viewDialog.value = {
        show: true,
        name: doc.name,
        content: content,
        uid: doc.uid,
        editing: false,
        originalContent: content,
        saving: false
      }
    } catch (err) {
      console.error('Failed to load document:', err)
      alert('加载文档失败')
    }
  }
  emit('document-opened', doc)
}

const copyViewContent = async () => {
  try {
    await navigator.clipboard.writeText(viewDialog.value.content)
    alert('已复制到剪贴板')
  } catch (err) {
    console.error('Copy failed:', err)
  }
}

const startEdit = () => {
  viewDialog.value.editing = true
  viewDialog.value.originalContent = viewDialog.value.content
}

const cancelEdit = () => {
  viewDialog.value.editing = false
  viewDialog.value.content = viewDialog.value.originalContent
}

const saveContent = async () => {
  viewDialog.value.saving = true
  try {
    let content = viewDialog.value.content
    try {
      content = JSON.parse(content)
    } catch {
    }
    
    await fetch(`${apiBase.value}/${viewDialog.value.uid}/content`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content })
    })
    
    viewDialog.value.editing = false
    viewDialog.value.originalContent = viewDialog.value.content
  } catch (err) {
    console.error('Save failed:', err)
    alert('保存失败')
  } finally {
    viewDialog.value.saving = false
  }
}

const MENU_HEIGHTS = { doc: 220, dir: 140 }

function calcMenuPos(event, type) {
  const h = MENU_HEIGHTS[type] || 200
  return {
    x: event.clientX,
    y: event.clientY + h > window.innerHeight ? event.clientY - h : event.clientY
  }
}

const showDocContext = (event, doc) => {
  const pos = calcMenuPos(event, 'doc')
  contextMenu.value = {
    show: true,
    x: pos.x,
    y: pos.y,
    type: 'doc',
    item: doc
  }
  activeDocUid.value = doc.uid
}

const showDirContext = (event, dir) => {
  const pos = calcMenuPos(event, 'dir')
  contextMenu.value = {
    show: true,
    x: pos.x,
    y: pos.y,
    type: 'dir',
    item: dir
  }
}

const hideContextMenu = () => {
  contextMenu.value.show = false
}

const setAsActive = async () => {
  const doc = contextMenu.value.item
  if (!doc) return
  
  try {
    const res = await fetch(`${apiBase.value}/active/${doc.layer}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ uid: doc.uid })
    })
    if (res.ok) {
      activeDocs.value[doc.layer] = doc.uid
      emit('active-changed', doc)
    }
  } catch (err) {
    console.error('Set active failed:', err)
  }
  hideContextMenu()
}

const renameDocument = async () => {
  const doc = contextMenu.value.item
  if (!doc) return
  
  const newName = prompt('新名称:', doc.name)
  if (newName && newName !== doc.name) {
    try {
      await fetch(`${apiBase.value}/${doc.uid}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newName })
      })
      await refresh()
    } catch (err) {
      console.error('Rename failed:', err)
    }
  }
  hideContextMenu()
}

const toggleArchive = async () => {
  const doc = contextMenu.value.item
  if (!doc) return
  
  const shouldArchive = doc.status !== 'archived'
  try {
    await fetch(`${apiBase.value}/${doc.uid}/archive?archive=${shouldArchive}`, {
      method: 'PUT'
    })
    await refresh()
  } catch (err) {
    console.error('Archive failed:', err)
  }
  hideContextMenu()
}

const exportDocument = async () => {
  const doc = contextMenu.value.item
  if (!doc) return
  
  try {
    const res = await fetch(`${apiBase.value}/${doc.uid}`)
    const data = await res.json()
    
    let content = data.content
    if (typeof content === 'object' && content.content) {
      content = content.content
    }
    if (typeof content !== 'string') {
      content = JSON.stringify(content, null, 2)
    }
    
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${doc.name}.txt`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  } catch (err) {
    console.error('Export failed:', err)
    alert('导出失败: ' + err.message)
  }
  hideContextMenu()
}

const deleteDocument = async () => {
  const doc = contextMenu.value.item
  if (!doc) return
  
  if (confirm(`确定删除文档 "${doc.name}"？`)) {
    try {
      await fetch(`${apiBase.value}/${doc.uid}`, { method: 'DELETE' })
      await refresh()
    } catch (err) {
      console.error('Delete failed:', err)
    }
  }
  hideContextMenu()
}

const deleteSelected = async () => {
  const uid = activeDocUid.value
  if (!uid) return
  const doc = documents.value.find(d => d.uid === uid)
  if (!doc) return
  if (!confirm(`确定删除文档 "${doc.name}"？`)) return
  
  try {
    await fetch(`${apiBase.value}/${uid}`, { method: 'DELETE' })
    activeDocUid.value = null
    await refresh()
  } catch (err) {
    console.error('Delete failed:', err)
    alert('删除失败')
  }
}

const createDirectory = async () => {
  const name = prompt('目录名称:')
  if (name) {
    try {
      const res = await fetch(`${apiBase.value}/directories`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: name })
      })
      const data = await res.json()
      console.log('Create directory result:', data)
      await refresh()
      console.log('Directories after refresh:', directories.value)
    } catch (err) {
      console.error('Create directory failed:', err)
    }
  }
}

const createSubDirectory = async () => {
  const parentDir = contextMenu.value.item
  console.log('createSubDirectory, parent:', parentDir)
  const name = prompt('子目录名称:')
  if (name) {
    const fullPath = parentDir === '/' ? `/${name}` : `${parentDir}/${name}`
    console.log('Creating subdirectory:', fullPath)
    try {
      const res = await fetch(`${apiBase.value}/directories`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: fullPath })
      })
      const data = await res.json()
      console.log('Create subdirectory result:', data)
      await refresh()
      console.log('Directories after refresh:', directories.value)
    } catch (err) {
      console.error('Create subdirectory failed:', err)
    }
  }
  hideContextMenu()
}

const createDocInDir = () => {
  const dir = contextMenu.value.item
  createDocDialog.value = {
    show: true,
    directory: dir
  }
  hideContextMenu()
}

const submitCreateDoc = async () => {
  if (!createDocDialog.value.name) return
  
  try {
    await fetch(`${apiBase.value}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: createDocDialog.value.name,
        layer: 'imported',
        source: 'manual',
        directory: createDocDialog.value.directory,
        content: {}
      })
    })
    createDocDialog.value.show = false
    createDocDialog.value.name = ''
    await refresh()
  } catch (err) {
    console.error('Create document failed:', err)
  }
}

const removeDirectory = async () => {
  const dir = contextMenu.value.item
  if (dir === '/') return
  
  if (confirm(`确定删除目录 "${dir}"？文档将移至根目录。`)) {
    try {
      await fetch(`${apiBase.value}/directories/${dir.slice(1)}`, { method: 'DELETE' })
      await refresh()
    } catch (err) {
      console.error('Remove directory failed:', err)
    }
  }
  hideContextMenu()
}

const triggerImport = () => {
  importDirectory.value = '/'
  fileInput.value?.click()
}

const importToDir = () => {
  importDirectory.value = contextMenu.value.item || '/'
  hideContextMenu()
  fileInput.value?.click()
}

const handleImport = async (event) => {
  const file = event.target.files?.[0]
  if (!file) return
  
  const formData = new FormData()
  formData.append('file', file)
  
  try {
    await fetch(`${apiBase.value}/import?directory=${encodeURIComponent(importDirectory.value)}`, {
      method: 'POST',
      body: formData
    })
    await refresh()
  } catch (err) {
    console.error('Import failed:', err)
  }
  
  event.target.value = ''
}

const hasProject = computed(() => !!props.projectId)

const refresh = async () => {
  if (!hasProject.value) return
  loading.value = true
  try {
    const res = await fetch(`${apiBase.value}`)
    const data = await res.json()
    documents.value = data.documents || []
    directories.value = data.directories || ['/']
    activeDocs.value = data.active_docs || {}

    for (const dir of directories.value) {
      if (!expandedDirs.value.has(dir)) {
        expandedDirs.value.add(dir)
      }
    }
  } catch (err) {
    console.error('Failed to load library:', err)
  } finally {
    loading.value = false
  }
}

const onMessage = (event) => {
  if (event.data?.type === 'library-refresh') {
    refresh()
  }
}

const startResize = (e) => {
  isResizing.value = true
  document.addEventListener('mousemove', handleResize)
  document.addEventListener('mouseup', stopResize)
  e.preventDefault()
}

const handleResize = (e) => {
  if (!isResizing.value) return
  const newWidth = e.clientX
  if (newWidth >= 200 && newWidth <= 600) {
    sidebarWidth.value = newWidth
  }
}

const stopResize = () => {
  isResizing.value = false
  document.removeEventListener('mousemove', handleResize)
  document.removeEventListener('mouseup', stopResize)
}

onMounted(() => {
  refresh()
  document.addEventListener('click', hideContextMenu)
  window.addEventListener('library-refresh', refresh)
  window.addEventListener('message', onMessage)
})

onUnmounted(() => {
  document.removeEventListener('click', hideContextMenu)
  window.removeEventListener('library-refresh', refresh)
  window.removeEventListener('message', onMessage)
  stopResize()
})

defineExpose({ refresh })
</script>

<style scoped>
.library-sidebar {
  position: relative;
  min-width: 200px;
  max-width: 600px;
  background: #fff;
  border-right: 1px solid #e0e0e0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  flex-shrink: 0;
}

.library-sidebar.collapsed {
  min-width: 32px;
  max-width: 32px;
}

.resize-handle {
  position: absolute;
  top: 0;
  right: 0;
  width: 4px;
  height: 100%;
  cursor: col-resize;
  background: transparent;
  transition: background 0.2s;
  z-index: 10;
}

.resize-handle:hover {
  background: #3498db;
}

.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem;
  border-bottom: 1px solid #e0e0e0;
  background: #f8f9fa;
}

.sidebar-title {
  font-weight: 600;
  font-size: 0.875rem;
}

.btn-toggle {
  background: none;
  border: none;
  cursor: pointer;
  padding: 0.25rem;
  color: #666;
}

.sidebar-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-toolbar {
  display: flex;
  gap: 0.5rem;
  padding: 0.5rem;
  border-bottom: 1px solid #e0e0e0;
}

.btn-sm {
  padding: 0.25rem 0.5rem;
  background: #f0f0f0;
  border: 1px solid #ddd;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.875rem;
}

.btn-sm:hover {
  background: #e0e0e0;
}

.btn-danger-sm {
  color: #e74c3c;
}

.btn-danger-sm:hover {
  background: #fde8e8;
}

.btn-danger-sm:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.loading {
  padding: 2rem;
  text-align: center;
  color: #666;
}

.document-tree {
  flex: 1;
  overflow-y: auto;
  padding: 0.5rem;
}

.directory-item {
  margin-bottom: 0.25rem;
}

.directory-item.nested {
  margin-left: 1rem;
}

.directory-header {
  display: flex;
  align-items: center;
  padding: 0.375rem 0.5rem;
  cursor: pointer;
  border-radius: 4px;
}

.directory-header:hover {
  background: #f0f0f0;
}

.directory-header.drag-over {
  background: #e3f2fd;
  border: 2px dashed #3498db;
}

.document-tree.drag-over {
  background: #f0f7ff;
}

.dir-icon {
  margin-right: 0.5rem;
}

.dir-name {
  font-size: 0.875rem;
  font-weight: 500;
  color: #333;
}

.directory-children {
  padding-left: 1rem;
}

.document-item {
  display: flex;
  align-items: center;
  padding: 0.375rem 0.5rem;
  cursor: pointer;
  border-radius: 4px;
  font-size: 0.875rem;
  user-select: none;
}

.document-item:hover {
  background: #f0f0f0;
}

.document-item:active {
  opacity: 0.6;
}

.document-item.active {
  background: #e3f2fd;
}

.document-item.archived {
  opacity: 0.5;
}

.document-item.draft .doc-name {
  font-style: italic;
}

.doc-icon {
  margin-right: 0.5rem;
}

.doc-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.active-badge {
  color: #4caf50;
  font-size: 0.75rem;
}

.sidebar-footer {
  padding: 0.5rem;
  border-top: 1px solid #e0e0e0;
  font-size: 0.75rem;
  color: #666;
}

.context-menu {
  position: fixed;
  background: white;
  border: 1px solid #ddd;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
  z-index: 1000;
  min-width: 120px;
}

.menu-items > div {
  padding: 0.5rem 0.75rem;
  cursor: pointer;
  font-size: 0.875rem;
}

.menu-items > div:hover {
  background: #f0f0f0;
}

.menu-divider {
  height: 1px;
  background: #e0e0e0;
  margin: 0.25rem 0;
}

.menu-danger {
  color: #e74c3c;
}

.view-dialog {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.view-dialog .dialog-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0,0,0,0.3);
}

.view-dialog .dialog-content {
  position: relative;
  background: white;
  border-radius: 8px;
  width: 800px;
  max-width: 95vw;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
}

.view-dialog .dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid #e0e0e0;
}

.view-dialog .dialog-header h3 {
  margin: 0;
  font-size: 1rem;
}

.view-dialog .btn-close {
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: #666;
  padding: 0;
  line-height: 1;
}

.view-dialog .btn-close:hover {
  color: #333;
}

.view-dialog .dialog-body {
  flex: 1;
  padding: 1rem;
  margin: 0;
  background: #f8f9fa;
  font-family: monospace;
  font-size: 0.875rem;
  white-space: pre-wrap;
  word-break: break-all;
  overflow: auto;
  max-height: 60vh;
}

.view-dialog .dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  padding: 1rem 1.5rem;
  border-top: 1px solid #e0e0e0;
}

.view-dialog .btn {
  padding: 0.5rem 1rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  background: white;
  cursor: pointer;
  font-size: 0.875rem;
}

.view-dialog .btn-primary {
  background: #3498db;
  border-color: #3498db;
  color: white;
}

.view-dialog .form-group {
  margin-bottom: 1rem;
}

.view-dialog .form-group label {
  display: block;
  margin-bottom: 0.25rem;
  font-size: 0.875rem;
  color: #666;
}

.view-dialog .form-group input,
.view-dialog .form-group select {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 0.875rem;
}

.view-dialog .dialog-body-edit {
  flex: 1;
  padding: 1rem;
  margin: 0;
  background: #fff;
  font-family: monospace;
  font-size: 0.875rem;
  white-space: pre-wrap;
  word-break: break-all;
  overflow: auto;
  max-height: 60vh;
  border: 2px solid #3498db;
  border-radius: 4px;
  resize: none;
}
</style>
