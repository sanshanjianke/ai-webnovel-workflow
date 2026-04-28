<template>
  <div class="worldbook">
    <h1>世界书管理</h1>
    
    <div class="wb-layout">
      <div class="main-area">
        <div class="card">
          <div class="card-header">
            <h2>条目列表</h2>
            <button class="btn btn-primary" @click="showCreateForm = true">新建条目</button>
          </div>
          
          <div class="entries-list">
            <div v-for="entry in entries" :key="entry.id" class="entry-item">
              <div class="entry-header">
                <strong>{{ entry.keys?.[0] || entry.id }}</strong>
                <div class="entry-actions">
                  <button class="btn" @click="editEntry(entry)">编辑</button>
                  <button class="btn btn-danger" @click="deleteEntry(entry.id)">删除</button>
                </div>
              </div>
              <p class="entry-content">{{ entry.content }}</p>
              <div class="entry-meta">
                <span v-if="entry.constant" class="tag">常驻</span>
                <span>优先级: {{ entry.priority }}</span>
              </div>
            </div>
            <p v-if="entries.length === 0" class="hint">暂无条目</p>
          </div>
        </div>
        
        <div v-if="showCreateForm || editingEntry" class="card">
          <h2>{{ editingEntry ? '编辑条目' : '新建条目' }}</h2>
          
          <div class="form-group">
            <label>ID</label>
            <input v-model="form.id" type="text" :disabled="!!editingEntry">
          </div>
          <div class="form-group">
            <label>触发词 (逗号分隔)</label>
            <input v-model="keysText" type="text" placeholder="如: 老周, 周师傅, 鉴定师">
          </div>
          <div class="form-group">
            <label>内容</label>
            <textarea v-model="form.content" placeholder="条目描述"></textarea>
          </div>
          <div class="form-group">
            <label>次要触发词 (逗号分隔)</label>
            <input v-model="secondaryKeysText" type="text" placeholder="可选">
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>优先级</label>
              <input v-model.number="form.priority" type="number" min="1" max="100">
            </div>
            <div class="form-group">
              <label>常驻</label>
              <select v-model="form.constant">
                <option :value="false">否</option>
                <option :value="true">是</option>
              </select>
            </div>
          </div>
          
          <div class="actions">
            <button class="btn btn-primary" @click="saveEntry">保存</button>
            <button class="btn" @click="cancelEdit">取消</button>
          </div>
        </div>
      </div>
      
      <div class="sidebar">
        <div class="card">
          <h3>统计</h3>
          <p>条目数: {{ entries.length }}</p>
          <p>常驻条目: {{ entries.filter(e => e.constant).length }}</p>
        </div>
        
        <div class="card">
          <h3>版本管理</h3>
          <button class="btn btn-primary" @click="commitChanges">提交快照</button>
          <div v-if="commits.length > 0" class="commits-list">
            <div v-for="commit in commits" :key="commit.hash" class="commit-item">
              <small>{{ commit.message }}</small>
              <small class="commit-time">{{ formatDate(commit.timestamp) }}</small>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'

const route = useRoute()
const projectId = route.params.projectId

const entries = ref([])
const commits = ref([])
const showCreateForm = ref(false)
const editingEntry = ref(null)

const form = ref({
  id: '',
  keys: [],
  content: '',
  secondary_keys: [],
  priority: 10,
  constant: false
})

const keysText = computed({
  get: () => form.value.keys?.join(', ') || '',
  set: (val) => { form.value.keys = val.split(',').map(k => k.trim()).filter(k => k) }
})

const secondaryKeysText = computed({
  get: () => form.value.secondary_keys?.join(', ') || '',
  set: (val) => { form.value.secondary_keys = val.split(',').map(k => k.trim()).filter(k => k) }
})

const fetchEntries = async () => {
  const res = await axios.get(`/api/projects/${projectId}/worldbook`)
  entries.value = res.data.entries || []
}

const fetchCommits = async () => {
  const res = await axios.get(`/api/projects/${projectId}/worldbook/commits`)
  commits.value = res.data.commits || []
}

const editEntry = (entry) => {
  editingEntry.value = entry
  form.value = { ...entry }
  showCreateForm.value = false
}

const saveEntry = async () => {
  if (!form.value.id || !form.value.content) return
  
  if (editingEntry.value) {
    await axios.put(`/api/projects/${projectId}/worldbook/entry/${form.value.id}`, form.value)
  } else {
    await axios.post(`/api/projects/${projectId}/worldbook`, form.value)
  }
  
  cancelEdit()
  fetchEntries()
}

const deleteEntry = async (id) => {
  if (confirm('确定删除此条目？')) {
    await axios.delete(`/api/projects/${projectId}/worldbook/entry/${id}`)
    fetchEntries()
  }
}

const cancelEdit = () => {
  showCreateForm.value = false
  editingEntry.value = null
  form.value = { id: '', keys: [], content: '', secondary_keys: [], priority: 10, constant: false }
}

const commitChanges = async () => {
  const message = prompt('请输入提交说明:', '手动提交')
  if (message) {
    await axios.post(`/api/projects/${projectId}/worldbook/commit?message=${encodeURIComponent(message)}`)
    fetchCommits()
  }
}

const formatDate = (ts) => {
  if (!ts) return ''
  return new Date(ts).toLocaleString('zh-CN')
}

onMounted(() => {
  fetchEntries()
  fetchCommits()
})
</script>

<style scoped>
.worldbook h1 {
  margin-bottom: 1.5rem;
}

.wb-layout {
  display: grid;
  grid-template-columns: 1fr 280px;
  gap: 1.5rem;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.card-header h2 {
  margin: 0;
}

.entries-list {
  max-height: 400px;
  overflow-y: auto;
}

.entry-item {
  padding: 1rem;
  border-bottom: 1px solid #eee;
}

.entry-item:last-child {
  border-bottom: none;
}

.entry-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.entry-actions {
  display: flex;
  gap: 0.5rem;
}

.entry-content {
  color: #666;
  font-size: 0.875rem;
  margin-bottom: 0.5rem;
}

.entry-meta {
  font-size: 0.75rem;
  color: #999;
}

.tag {
  background: #3498db;
  color: white;
  padding: 0.125rem 0.5rem;
  border-radius: 4px;
  margin-right: 0.5rem;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 1rem;
}

.hint {
  color: #999;
  text-align: center;
  padding: 2rem;
}

.commits-list {
  margin-top: 1rem;
  max-height: 200px;
  overflow-y: auto;
}

.commit-item {
  padding: 0.5rem;
  background: #f5f5f5;
  border-radius: 4px;
  margin-bottom: 0.5rem;
}

.commit-item small {
  display: block;
}

.commit-time {
  color: #999;
}
</style>
