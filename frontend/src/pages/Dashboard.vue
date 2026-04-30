<template>
  <div class="dashboard">
    <h1>项目仪表盘</h1>
    
    <div class="actions">
      <button class="btn btn-primary" @click="showCreateModal = true">
        新建项目
      </button>
    </div>
    
    <div class="projects-grid">
      <div v-for="project in projects" :key="project.id" class="project-card card">
        <h3>{{ project.config?.name || '未命名项目' }}</h3>
        <p class="meta">{{ project.config?.genre || '未分类' }} · {{ project.config?.target_platform || '未设置平台' }}</p>
        <p class="time">创建于: {{ formatDate(project.config?.created_at) }}</p>
        <div class="card-actions">
          <router-link :to="`/l1?projectId=${project.id}`" class="btn btn-primary">L1</router-link>
          <router-link :to="`/l1-5?projectId=${project.id}`" class="btn btn-primary">L1.5</router-link>
          <router-link :to="`/l2?projectId=${project.id}`" class="btn btn-primary">L2</router-link>
          <router-link :to="`/l3?projectId=${project.id}`" class="btn btn-primary">L3</router-link>
          <router-link :to="`/l4?projectId=${project.id}`" class="btn btn-primary">L4</router-link>
          <router-link :to="`/worldbook?projectId=${project.id}`" class="btn btn-primary">世界书</router-link>
          <button class="btn btn-danger" @click="deleteProject(project.id)">删除</button>
        </div>
      </div>
    </div>
    
    <div v-if="showCreateModal" class="modal">
      <div class="modal-content card">
        <h2>新建项目</h2>
        <div class="form-group">
          <label>项目名称</label>
          <input v-model="newProject.name" type="text" placeholder="输入项目名称">
        </div>
        <div class="form-group">
          <label>类型</label>
          <input v-model="newProject.genre" type="text" placeholder="如: 玄幻、都市">
        </div>
        <div class="form-group">
          <label>目标平台</label>
          <input v-model="newProject.target_platform" type="text" placeholder="如: 起点、晋江">
        </div>
        <div class="form-group">
          <label>驱动模式</label>
          <select v-model="newProject.driving_mode">
            <option value="plot_driven">剧情驱动</option>
            <option value="character_driven">人物驱动</option>
            <option value="market_driven">市场驱动</option>
          </select>
        </div>
        <div class="modal-actions">
          <button class="btn btn-primary" @click="createProject">创建</button>
          <button class="btn" @click="showCreateModal = false">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const projects = ref([])
const showCreateModal = ref(false)
const newProject = ref({
  name: '',
  genre: '',
  target_platform: '',
  driving_mode: 'plot_driven'
})

const fetchProjects = async () => {
  const res = await axios.get('/api/projects/')
  projects.value = res.data
}

const createProject = async () => {
  if (!newProject.value.name) return
  await axios.post('/api/projects/', newProject.value)
  showCreateModal.value = false
  newProject.value = { name: '', genre: '', target_platform: '', driving_mode: 'plot_driven' }
  fetchProjects()
}

const deleteProject = async (id) => {
  if (confirm('确定删除此项目？')) {
    await axios.delete(`/api/projects/${id}`)
    fetchProjects()
  }
}

const formatDate = (date) => {
  if (!date) return ''
  return new Date(date).toLocaleString('zh-CN')
}

onMounted(fetchProjects)
</script>

<style scoped>
.dashboard {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: auto;
  padding: 1.5rem;
}

.dashboard h1 {
  margin-bottom: 1.5rem;
}

.actions {
  margin-bottom: 1.5rem;
}

.projects-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1rem;
}

.project-card h3 {
  margin-bottom: 0.5rem;
}

.project-card .meta {
  color: #666;
  font-size: 0.875rem;
}

.project-card .time {
  color: #999;
  font-size: 0.75rem;
  margin-bottom: 1rem;
}

.card-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.card-actions .btn {
  text-decoration: none;
  display: inline-block;
}

.modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-content {
  width: 400px;
  max-width: 90%;
}

.modal-content h2 {
  margin-bottom: 1rem;
}

.modal-actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 1rem;
}
</style>
