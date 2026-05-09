<template>
  <div class="worldbook"
    @dragover.prevent="onDragOver"
    @dragenter.prevent="onDragEnter"
    @dragleave="onDragLeave"
    @dragend="onDragEnd"
    @drop.prevent="onDrop"
    :class="{ 'drag-over': dragOver }">
    <div v-if="dragOver" class="drop-banner">📖 松开鼠标导入世界书</div>
    <h1>世界书管理</h1>

    <!-- ── 书选择器 ── -->
    <div class="book-bar">
      <div class="book-selector">
        <label>当前书：</label>
        <select v-model="currentBookId" @change="switchBook">
          <option v-for="b in books" :key="b.bookId" :value="b.bookId">
            {{ b.name }} ({{ b.entryCount }} 条)
          </option>
        </select>
      </div>
      <button class="btn btn-primary btn-sm" @click="showNewBook = true">+ 新建</button>
      <button class="btn btn-sm" @click="deleteCurrentBook" :disabled="currentBookId === 'default'">删除</button>
      <span class="book-bar-sep"></span>
      <button class="btn btn-sm" @click="downloadBook" :disabled="entries.length === 0">⬇ 下载</button>
      <button class="btn btn-sm" @click="triggerImport">📥 导入</button>
      <button class="btn btn-sm" @click="saveToLibrary">📚 存到文档库</button>
      <input ref="importInput" type="file" accept=".json,.png" @change="handleImport" style="display:none" />
    </div>

    <div v-if="showNewBook" class="new-book-row">
      <input v-model="newBookName" placeholder="书名" @keyup.enter="createBook" />
      <button class="btn btn-primary btn-sm" @click="createBook">创建</button>
      <button class="btn btn-sm" @click="showNewBook = false">取消</button>
    </div>

    <div class="wb-layout">
      <!-- ── 条目列表 ── -->
      <div class="main-area">
        <div class="card">
          <div class="card-header">
            <h2>条目列表</h2>
            <button class="btn btn-primary" @click="startNewEntry">新建条目</button>
          </div>

          <div class="entries-list">
            <div v-for="entry in sortedEntries" :key="entry.id"
              class="entry-item"
              :class="{ 'entry-disabled': entry.disable }"
              @click="editEntry(entry)">
              <div class="entry-row">
                <span class="entry-status" :class="{ 'status-constant': entry.constant, 'status-disabled': entry.disable }">
                  {{ entry.constant ? '常驻' : entry.disable ? '禁用' : '' }}
                </span>
                <span class="entry-comment">{{ entry.comment || entry.id }}</span>
                <span class="entry-keys">{{ (entry.keys || []).join(', ') }}</span>
                <span class="entry-priority">P{{ entry.priority || 10 }}</span>
                <span class="entry-secondary" v-if="entry.secondaryKeys?.length">
                  & {{ (entry.secondaryKeys || []).join(', ') }}
                </span>
              </div>
            </div>
            <p v-if="entries.length === 0" class="hint">暂无条目，点击"新建条目"添加</p>
          </div>
        </div>

        <!-- ── 编辑表单 ── -->
        <div v-if="showForm" class="card">
          <h2>{{ editingId ? '编辑条目' : '新建条目' }} <small v-if="editingId">— {{ editingId }}</small></h2>

          <div class="form-row">
            <div class="form-group flex-2">
              <label>ID / 备注</label>
              <input v-model="form.id" type="text" :disabled="!!editingId" placeholder="条目唯一标识">
            </div>
            <div class="form-group">
              <label>标题</label>
              <input v-model="form.comment" type="text" placeholder="便于记忆的标题">
            </div>
          </div>

          <div class="form-group">
            <label>主触发词（逗号分隔）</label>
            <input v-model="keysText" type="text" placeholder="如: 老周, 周师傅, 鉴定师">
          </div>

          <div class="form-group">
            <label>内容</label>
            <textarea v-model="form.content" placeholder="条目描述文本，将注入到 prompt 中" rows="6"></textarea>
          </div>

          <div class="form-group">
            <label>次要触发词（逗号分隔）</label>
            <input v-model="secondaryKeysText" type="text" placeholder="可选，配合主触发词">
          </div>

          <div class="form-row">
            <div class="form-group">
              <label>选择逻辑</label>
              <select v-model="form.selectiveLogic">
                <option value="AND_ANY">任一命中 (AND_ANY)</option>
                <option value="NOT_ALL">不含全部 (NOT_ALL)</option>
                <option value="NOT_ANY">不含任一 (NOT_ANY)</option>
                <option value="AND_ALL">全部命中 (AND_ALL)</option>
              </select>
            </div>
            <div class="form-group">
              <label>注入位置</label>
              <select v-model="form.position">
                <option value="before_char">角色前 (before_char)</option>
                <option value="after_char">角色后 (after_char)</option>
                <option value="an_top">作者笔记顶 (an_top)</option>
                <option value="an_bottom">作者笔记底 (an_bottom)</option>
                <option value="at_depth">深度处 (at_depth)</option>
                <option value="em_top">示例消息顶 (em_top)</option>
                <option value="em_bottom">示例消息底 (em_bottom)</option>
              </select>
            </div>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label>优先级 (1-100)</label>
              <input v-model.number="form.priority" type="number" min="1" max="100">
            </div>
            <div class="form-group">
              <label>触发概率 %</label>
              <input v-model.number="form.probability" type="number" min="0" max="100">
            </div>
            <div class="form-group">
              <label>搜索深度 <span class="unimplemented">(尚未实现)</span></label>
              <input v-model.number="form.depth" type="number" min="0" max="20" disabled>
            </div>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label>分组名（互斥）</label>
              <input v-model="form.group" type="text" placeholder="同组只激活一个">
            </div>
            <div class="form-group">
              <label>组内权重</label>
              <input v-model.number="form.groupWeight" type="number" min="1" max="100">
            </div>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label>常驻</label>
              <select v-model="form.constant">
                <option :value="false">否</option>
                <option :value="true">是（忽略关键词始终激活）</option>
              </select>
            </div>
            <div class="form-group">
              <label>禁用</label>
              <select v-model="form.disable">
                <option :value="false">否</option>
                <option :value="true">是</option>
              </select>
            </div>
          </div>

          <details class="advanced-section">
            <summary>高级设置 <span class="unimplemented">(标注"尚未实现"的功能暂时不可用)</span></summary>
            <div class="form-row">
              <div class="form-group">
                <label>Sticky（激活后保持 N 条消息）<span class="unimplemented">尚未实现</span></label>
                <input v-model.number="form.sticky" type="number" min="0" placeholder="0=不保持" disabled>
              </div>
              <div class="form-group">
                <label>Cooldown（停用后冷却 N 条消息）<span class="unimplemented">尚未实现</span></label>
                <input v-model.number="form.cooldown" type="number" min="0" placeholder="0=不冷却" disabled>
              </div>
              <div class="form-group">
                <label>Delay（延迟 N 条消息后激活）<span class="unimplemented">尚未实现</span></label>
                <input v-model.number="form.delay" type="number" min="0" placeholder="0=无延迟" disabled>
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label>大小写敏感</label>
                <select v-model="form.caseSensitive">
                  <option :value="false">否</option>
                  <option :value="true">是</option>
                </select>
              </div>
              <div class="form-group">
                <label>全词匹配</label>
                <select v-model="form.matchWholeWords">
                  <option :value="false">否</option>
                  <option :value="true">是</option>
                </select>
              </div>
              <div class="form-group">
                <label>不可递归激活 <span class="unimplemented">尚未实现</span></label>
                <select v-model="form.excludeRecursion" disabled>
                  <option :value="false">否</option>
                  <option :value="true">是</option>
                </select>
              </div>
              <div class="form-group">
                <label>无视 token 预算 <span class="unimplemented">尚未实现</span></label>
                <select v-model="form.ignoreBudget" disabled>
                  <option :value="false">否</option>
                  <option :value="true">是</option>
                </select>
              </div>
            </div>
          </details>

          <div class="actions">
            <button class="btn btn-primary" @click="saveEntry">保存</button>
            <button class="btn" :class="deleteEntryConfirm ? 'btn-danger' : ''" v-if="editingId" @click="onDeleteEntryClick">
              {{ deleteEntryConfirm ? '确认删除？' : '删除' }}
            </button>
            <button class="btn" @click="cancelEdit">取消</button>
          </div>
        </div>
      </div>

      <!-- ── 右侧栏 ── -->
      <div class="sidebar">
        <div class="card">
          <h3>书信息</h3>
          <p>书名：{{ currentBook?.name || '—' }}</p>
          <p>条目数：{{ entries.length }}</p>
          <p>常驻条目：{{ entries.filter(e => e.constant && !e.disable).length }}</p>
          <p>禁用条目：{{ entries.filter(e => e.disable).length }}</p>
        </div>

        <div class="card">
          <h3>版本管理</h3>
          <button class="btn btn-primary btn-sm" @click="commitChanges">提交快照</button>
          <div v-if="commits.length > 0" class="commits-list">
            <div v-for="commit in commits" :key="commit.hash" class="commit-item">
              <small>{{ commit.message }}</small>
              <small class="commit-time">{{ formatDate(commit.timestamp) }}</small>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ── 删除确认弹窗 ── -->
    <div v-if="confirmDeleteBook" class="modal-overlay" @click.self="confirmDeleteBook = false">
      <div class="modal-content card" style="width:380px; text-align:center;">
        <p style="font-size:1.1rem; margin-bottom:1rem;">确定删除书「{{ currentBook?.name || currentBookId }}」？</p>
        <p style="color:#e74c3c; font-size:0.85rem;">此操作不可恢复，所有条目将被删除。</p>
        <div class="actions" style="justify-content:center; margin-top:1.5rem;">
          <button class="btn btn-danger" @click="doDeleteBook">确认删除</button>
          <button class="btn" @click="confirmDeleteBook = false">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'

const route = useRoute()
const projectId = computed(() => route.query.projectId)
const initialBookId = computed(() => route.query.bookId || 'default')

const books = ref([])
const currentBookId = ref('default')
const currentBook = ref(null)
const entries = ref([])
const commits = ref([])
const showForm = ref(false)
const editingId = ref(null)
const showNewBook = ref(false)
const newBookName = ref('')
const importInput = ref(null)
const dragOver = ref(false)
const deleteEntryConfirm = ref(false)
const confirmDeleteBook = ref(false)

const defaultForm = () => ({
  id: '',
  keys: [],
  content: '',
  secondaryKeys: [],
  constant: false,
  disable: false,
  comment: '',
  priority: 10,
  probability: 100,
  depth: 4,
  position: 'before_char',
  selectiveLogic: 'AND_ANY',
  group: '',
  groupWeight: 100,
  sticky: null,
  cooldown: null,
  delay: null,
  caseSensitive: false,
  matchWholeWords: false,
  excludeRecursion: false,
  ignoreBudget: false
})

const form = ref(defaultForm())

const keysText = computed({
  get: () => (form.value.keys || []).join(', '),
  set: (val) => { form.value.keys = val.split(',').map(k => k.trim()).filter(k => k) }
})

const secondaryKeysText = computed({
  get: () => (form.value.secondaryKeys || []).join(', '),
  set: (val) => { form.value.secondaryKeys = val.split(',').map(k => k.trim()).filter(k => k) }
})

const sortedEntries = computed(() => {
  return [...entries.value].sort((a, b) => (b.priority || 0) - (a.priority || 0))
})

// ── API ──

const fetchBooks = async () => {
  try {
    const res = await axios.get(`/api/projects/${projectId.value}/worldbooks`)
    books.value = res.data.books || []
  } catch (e) { console.warn('Failed to fetch books:', e) }
}

const fetchEntries = async () => {
  if (!currentBookId.value) return
  try {
    const res = await axios.get(`/api/projects/${projectId.value}/worldbooks/${currentBookId.value}/entries`)
    currentBook.value = res.data.book || null
    entries.value = res.data.entries || []
  } catch {
    try {
      const res = await axios.get(`/api/projects/${projectId.value}/worldbook`)
      entries.value = res.data.entries || []
      currentBook.value = res.data.book || { name: '默认世界书', bookId: 'default' }
    } catch (e) { console.warn('Failed to fetch entries:', e) }
  }
}

const fetchCommits = async () => {
  try {
    const res = await axios.get(`/api/projects/${projectId.value}/worldbook/history`)
    commits.value = res.data.commits || []
  } catch { /* ignore */ }
}

const switchBook = () => { fetchEntries(); fetchCommits() }

const createBook = async () => {
  if (!newBookName.value.trim()) return
  try {
    const res = await axios.post(`/api/projects/${projectId.value}/worldbooks`, { name: newBookName.value.trim() })
    await fetchBooks()
    currentBookId.value = res.data.book.bookId
    showNewBook.value = false
    newBookName.value = ''
    fetchEntries()
  } catch (e) { alert('创建失败：' + (e.response?.data?.error || e.message)) }
}

const deleteCurrentBook = () => {
  if (currentBookId.value === 'default') return
  confirmDeleteBook.value = true
}

const doDeleteBook = async () => {
  confirmDeleteBook.value = false
  try {
    await axios.delete(`/api/projects/${projectId.value}/worldbooks/${currentBookId.value}`)
    currentBookId.value = 'default'
    await fetchBooks()
    fetchEntries()
  } catch (e) { alert('删除失败：' + (e.response?.data?.error || e.message)) }
}

// 通知画布刷新世界书节点条目数
function notifyCanvas() {
  if (window.opener) {
    window.opener.postMessage({ type: 'worldbook-updated', bookId: currentBookId.value }, '*')
  }
}

// ── 导入/导出 ──

const triggerImport = () => { importInput.value?.click() }

// ── PNG 元数据提取（兼容 SillyTavern 角色卡/世界书 PNG）──

function extractDataFromPng(data) {
  if (!data || data[0] !== 0x89 || data[1] !== 0x50 || data[2] !== 0x4E || data[3] !== 0x47) return null
  const td = new TextDecoder('ascii')

  const uint8 = new Uint8Array(4), uint32 = new Uint32Array(uint8.buffer)
  let idx = 8, chunks = []

  while (idx < data.length) {
    uint8[3] = data[idx++]; uint8[2] = data[idx++]; uint8[1] = data[idx++]; uint8[0] = data[idx++]
    let length = uint32[0] + 4
    let chunk = new Uint8Array(length)
    chunk[0] = data[idx++]; chunk[1] = data[idx++]; chunk[2] = data[idx++]; chunk[3] = data[idx++]
    let name = td.decode(chunk.slice(0, 4))
    for (let i = 4; i < length; i++) chunk[i] = data[idx++]
    idx += 4 // skip CRC
    chunks.push({ name, data: new Uint8Array(chunk.buffer.slice(4)) })
    if (name === 'IEND') break
  }

  // 解码 tEXt chunks
  const results = []
  for (const c of chunks) {
    if (c.name !== 'tEXt') continue
    let sep = c.data.indexOf(0)
    if (sep <= 0) continue
    const keyword = td.decode(c.data.slice(0, sep))
    const text = td.decode(c.data.slice(sep + 1))
    try {
      // atob → binary string → UTF-8 bytes → JSON
      const binary = atob(text)
      const bytes = Uint8Array.from(binary, c => c.charCodeAt(0))
      const decoded = new TextDecoder('utf-8').decode(bytes)
      const parsed = JSON.parse(decoded)
      results.push({ keyword, data: parsed })
    } catch {}
  }
  return results.length > 0 ? results : null
}

function convertCharacterBookToEntries(characterBook) {
  const entries = {}
  if (!characterBook.entries) return entries
  characterBook.entries.forEach((entry, index) => {
    const id = entry.id !== undefined ? entry.id : index
    entries[id] = {
      id: String(id),
      keys: entry.keys || [],
      content: entry.content || '',
      secondaryKeys: entry.secondary_keys || [],
      constant: entry.constant || false,
      selective: entry.selective !== undefined ? entry.selective : typeof entry.enabled !== 'undefined' ? entry.enabled : true,
      selectiveLogic: (entry.extensions?.selectiveLogic) || 'AND_ANY',
      priority: entry.insertion_order || 10,
      position: entry.position || 'before_char',
      disable: entry.enabled === false,
      comment: entry.comment || '',
      probability: entry.extensions?.probability ?? 100,
      depth: entry.extensions?.depth ?? 4,
      group: entry.extensions?.group || '',
      groupWeight: entry.extensions?.group_weight ?? 100,
      sticky: entry.extensions?.sticky ?? null,
      cooldown: entry.extensions?.cooldown ?? null,
      delay: entry.extensions?.delay ?? null,
      caseSensitive: entry.extensions?.case_sensitive || false,
      matchWholeWords: entry.extensions?.match_whole_words || false,
      excludeRecursion: entry.extensions?.exclude_recursion ?? false,
      preventRecursion: entry.extensions?.prevent_recursion ?? false,
      delayUntilRecursion: entry.extensions?.delay_until_recursion ?? 0,
      ignoreBudget: entry.extensions?.ignore_budget || false,
      role: entry.extensions?.role || ''
    }
  })
  return entries
}

const handleImport = async (event) => {
  const file = event.target.files?.[0]
  if (!file) return
  try {
    if (file.name.endsWith('.png')) {
      // PNG: 提取内嵌的角色卡 → 转换 worldbook
      const buffer = new Uint8Array(await file.arrayBuffer())
      const textChunks = extractDataFromPng(buffer)
      if (!textChunks) { alert('PNG 文件中未找到内嵌数据'); return }

      // 优先取 ccv3，其次 chara
      const ccv3 = textChunks.find(t => t.keyword.toLowerCase() === 'ccv3')
      const chara = textChunks.find(t => t.keyword.toLowerCase() === 'chara')
      const cardData = (ccv3 || chara)?.data

      if (!cardData?.data?.character_book) {
        alert('PNG 角色卡中未包含世界书 (character_book)')
        return
      }

      const bookName = cardData.data.character_book.name || cardData.data.name || file.name.replace(/\.png$/, '')
      const entries = convertCharacterBookToEntries(cardData.data.character_book)
      await importWorldBookData({ name: bookName, entries }, file.name)
    } else {
      const text = await file.text()
      const data = JSON.parse(text)
      await importWorldBookData(data, file.name)
    }
  } catch (e) { alert('导入失败：' + (e.response?.data?.error || e.message)) }
  event.target.value = ''
}

async function importWorldBookData(data, sourceName) {
  if (!data.entries) { alert('无效的世界书文件：缺少 entries'); return }
  const bookName = data.name || sourceName.replace(/\.json$/, '')
  const res = await axios.post(`/api/projects/${projectId.value}/worldbooks/import`, {
    name: bookName,
    entries: data.entries
  })
  await fetchBooks()
  currentBookId.value = res.data.book.bookId
  fetchEntries()
  notifyCanvas()
}

const downloadBook = async () => {
  try {
    const res = await axios.get(`/api/projects/${projectId.value}/worldbooks/${currentBookId.value}/export`)
    const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `worldbook-${currentBookId.value}.json`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) { alert('下载失败：' + (e.response?.data?.error || e.message)) }
}

const saveToLibrary = async () => {
  try {
    const res = await axios.get(`/api/projects/${projectId.value}/worldbooks/${currentBookId.value}/export`)
    const jsonStr = JSON.stringify(res.data, null, 2)
    const name = `${currentBook.value?.name || currentBookId.value}.worldbook.json`
    await axios.post(`/api/projects/${projectId.value}/library/import`, {
      name,
      content: jsonStr,
      format: 'json',
      directory: '/',
      tags: ['世界书', currentBook.value?.name || '']
    })
    window.postMessage({ type: 'library-refresh' }, '*')
    alert(`已保存「${name}」到文档库`)
  } catch (e) { alert('保存失败：' + (e.response?.data?.error || e.message)) }
}

// ── 拖拽导入（模板 + document 双监听） ──

const onDragOver = (e) => { e.dataTransfer.dropEffect = 'move' }
const onDragEnter = () => { dragOver.value = true }
const onDragLeave = (e) => {
  if (!e.currentTarget.contains(e.relatedTarget)) dragOver.value = false
}
const onDrop = () => { dragOver.value = false }
const onDragEnd = () => { dragOver.value = false }

const onDocumentDragOver = (e) => {
  e.preventDefault()
  // 用 'move' 匹配侧边栏的 effectAllowed='move'，否则浏览器会拒绝 drop
  e.dataTransfer.dropEffect = 'move'
}

const onDocumentDrop = async (e) => {
  e.preventDefault()
  dragOver.value = false
  const raw = e.dataTransfer.getData('application/json')
  if (!raw) return
  let doc
  try { doc = JSON.parse(raw) } catch { return }
  if (!doc.uid) return
  try {
    const res = await axios.get(`/api/projects/${projectId.value}/library/${doc.uid}`)
    const content = res.data.content
    let data
    if (typeof content === 'string') {
      data = JSON.parse(content)
    } else if (content && content.entries) {
      data = content
    } else {
      return
    }
    if (!data.entries) return
    await importWorldBookData(data, doc.name || '拖入的世界书')
  } catch (e) {
    console.error('[WorldBook] drop error:', e)
  }
}

// ── 条目 CRUD ──

const startNewEntry = () => {
  editingId.value = null
  form.value = defaultForm()
  showForm.value = true
}

const editEntry = (entry) => {
  editingId.value = entry.id
  form.value = { ...defaultForm(), ...entry }
  showForm.value = true
}

const saveEntry = async () => {
  if (!form.value.id || !form.value.content) return

  const payload = { ...form.value }
  if (payload.sticky === 0) payload.sticky = null
  if (payload.cooldown === 0) payload.cooldown = null
  if (payload.delay === 0) payload.delay = null

  try {
    if (editingId.value) {
      await axios.put(`/api/projects/${projectId.value}/worldbooks/${currentBookId.value}/entries/${editingId.value}`, payload)
    } else {
      await axios.post(`/api/projects/${projectId.value}/worldbooks/${currentBookId.value}/entries`, payload)
    }
    cancelEdit()
    fetchEntries()
    notifyCanvas()
  } catch (e) { alert('保存失败：' + (e.response?.data?.error || e.message)) }
}

const onDeleteEntryClick = () => {
  if (!deleteEntryConfirm.value) {
    deleteEntryConfirm.value = true
    setTimeout(() => { deleteEntryConfirm.value = false }, 3000)
    return
  }
  doDeleteEntry()
}

const doDeleteEntry = async () => {
  if (!editingId.value) return
  try {
    await axios.delete(`/api/projects/${projectId.value}/worldbooks/${currentBookId.value}/entries/${editingId.value}`)
    deleteEntryConfirm.value = false
    cancelEdit()
    fetchEntries()
    notifyCanvas()
  } catch (e) { alert('删除失败：' + (e.response?.data?.error || e.message)) }
}

const cancelEdit = () => {
  showForm.value = false
  editingId.value = null
  form.value = defaultForm()
}

const commitChanges = async () => {
  const message = prompt('请输入提交说明:', '手动提交')
  if (message) {
    await axios.post(`/api/projects/${projectId.value}/worldbook/commit?message=${encodeURIComponent(message)}`)
    fetchCommits()
  }
}

const formatDate = (ts) => {
  if (!ts) return ''
  return new Date(ts).toLocaleString('zh-CN')
}

onMounted(async () => {
  document.addEventListener('dragover', onDocumentDragOver)
  document.addEventListener('drop', onDocumentDrop)
  currentBookId.value = initialBookId.value
  await fetchBooks()
  fetchEntries()
  fetchCommits()
})

onUnmounted(() => {
  document.removeEventListener('dragover', onDocumentDragOver)
  document.removeEventListener('drop', onDocumentDrop)
})

watch(initialBookId, (id) => {
  if (id && id !== currentBookId.value) {
    currentBookId.value = id
    fetchEntries()
  }
})
</script>

<style scoped>
.worldbook {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow-y: auto;
  padding: 1.5rem;
  position: relative;
  transition: background 0.2s;
}
.worldbook.drag-over {
  background: rgba(14, 165, 233, 0.06);
  box-shadow: inset 0 0 0 3px #0ea5e9;
}
.drop-banner {
  position: sticky;
  top: 0;
  z-index: 5;
  text-align: center;
  font-size: 0.9rem;
  color: #0ea5e9;
  font-weight: 600;
  background: rgba(14, 165, 233, 0.1);
  padding: 8px;
  margin: -1.5rem -1.5rem 1rem -1.5rem;
  border-bottom: 2px dashed #0ea5e9;
  pointer-events: none;
}

.worldbook h1 { margin-bottom: 0.75rem; }

.book-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 1rem;
  padding: 10px 14px;
  background: #f0f7ff;
  border: 1px solid #d0e3f7;
  border-radius: 8px;
}

.book-selector { display: flex; align-items: center; gap: 8px; flex: 1; }
.book-selector label { font-size: 0.85rem; color: #555; white-space: nowrap; }
.book-selector select { flex: 1; padding: 6px 8px; border: 1px solid #ddd; border-radius: 4px; font-size: 0.9rem; }
.book-bar-sep { width: 1px; height: 20px; background: #ddd; }

.new-book-row {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 1rem; padding: 8px 14px;
  background: #fafafa; border: 1px dashed #ccc; border-radius: 8px;
}
.new-book-row input { flex: 1; padding: 6px 8px; border: 1px solid #ddd; border-radius: 4px; }

.wb-layout {
  display: grid;
  grid-template-columns: 1fr 260px;
  gap: 1.5rem;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}
.card-header h2 { margin: 0; }

.entries-list {
  max-height: 360px;
  overflow-y: auto;
}

.entry-item {
  padding: 0.6rem 0.75rem;
  border-bottom: 1px solid #eee;
  cursor: pointer;
  transition: background 0.15s;
}
.entry-item:hover { background: #f0f7ff; }
.entry-item:last-child { border-bottom: none; }
.entry-disabled { opacity: 0.5; }

.entry-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.85rem;
}

.entry-status {
  font-size: 0.6rem;
  padding: 1px 5px;
  border-radius: 3px;
  white-space: nowrap;
}
.status-constant { background: #3498db; color: white; }
.status-disabled { background: #999; color: white; }

.entry-comment { font-weight: 600; color: #333; min-width: 60px; }
.entry-keys { color: #3498db; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.entry-priority { color: #999; font-size: 0.75rem; }
.entry-secondary { color: #e67e22; font-size: 0.75rem; }

.form-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 1rem;
}
.flex-2 { grid-column: span 2; }

.advanced-section {
  margin: 0.75rem 0;
  padding: 0.5rem 0.75rem;
  background: #fafafa;
  border-radius: 6px;
}
.advanced-section summary {
  cursor: pointer;
  font-size: 0.8rem;
  color: #888;
  padding: 4px 0;
}
.advanced-section .form-row {
  margin-top: 0.75rem;
}

.actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 1rem;
}

.hint { color: #999; text-align: center; padding: 2rem; }
.unimplemented { font-size: 0.7rem; color: #bbb; font-weight: normal; font-style: italic; }

.commits-list { margin-top: 1rem; max-height: 200px; overflow-y: auto; }
.commit-item {
  padding: 0.5rem;
  background: #f5f5f5;
  border-radius: 4px;
  margin-bottom: 0.5rem;
}
.commit-item small { display: block; }
.commit-time { color: #999; }

.sidebar .card { margin-bottom: 1rem; }

.modal-overlay {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center;
  z-index: 999;
}
.modal-content {
  background: white;
  padding: 1.5rem;
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.2);
}
</style>
