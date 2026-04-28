<template>
  <div class="l3-narrative">
    <div class="page-header">
      <h1>L3 叙事层 - 章纲编排</h1>
      <div class="nav-actions">
        <router-link to="/" class="btn">← 返回仪表盘</router-link>
        <div class="layer-nav">
          <router-link :to="`/l1?projectId=${projectId}`" class="btn">L1</router-link>
          <router-link :to="`/l2/${projectId}`" class="btn">L2</router-link>
          <router-link :to="`/l3/${projectId}`" class="btn active">L3</router-link>
          <router-link :to="`/l4/${projectId}`" class="btn">L4</router-link>
        </div>
      </div>
    </div>
    
    <div class="l3-layout">
      <div class="main-area">
        <div class="card">
          <h2>场景编排</h2>
          
          <div v-for="(scene, idx) in scenes" :key="idx" class="scene-card">
            <div class="scene-header">
              <h3>场景 {{ idx + 1 }}</h3>
              <button class="btn btn-danger" @click="removeScene(idx)">删除</button>
            </div>
            
            <div class="form-group">
              <label>场景名称</label>
              <input v-model="scene.name" type="text">
            </div>
            
            <div class="form-row">
              <div class="form-group">
                <label>视角</label>
                <select v-model="scene.perspective">
                  <option value="外聚焦">外聚焦 - 客观镜头</option>
                  <option value="内聚焦-主角">内聚焦 - 主角视角</option>
                  <option value="内聚焦-反派">内聚焦 - 反派视角</option>
                  <option value="内聚焦-路人">内聚焦 - 路人视角</option>
                  <option value="自由间接引语">自由间接引语</option>
                </select>
              </div>
              <div class="form-group">
                <label>节奏</label>
                <select v-model="scene.pace">
                  <option value="扩述">慢速扩述</option>
                  <option value="等述">中速等述</option>
                  <option value="概述">快速概述</option>
                </select>
              </div>
            </div>
            
            <div class="form-row">
              <div class="form-group">
                <label>话语模式</label>
                <select v-model="scene.discourse_mode">
                  <option value="对话+动作">对话+动作</option>
                  <option value="对话">大量对话</option>
                  <option value="动作">动作描写</option>
                  <option value="心理">心理描写</option>
                  <option value="环境">环境烘托</option>
                </select>
              </div>
              <div class="form-group">
                <label>字数</label>
                <input v-model.number="scene.word_count" type="number">
              </div>
            </div>
          </div>
          
          <button class="btn btn-primary" @click="addScene">添加场景</button>
        </div>
        
        <div class="card">
          <h2>章节信息</h2>
          <div class="form-group">
            <label>章节名称</label>
            <input v-model="chapterName" type="text">
          </div>
          <div class="form-group">
            <label>情绪曲线</label>
            <input v-model="emotionCurve" placeholder="如: 压抑 → 爆发 → 余韵">
          </div>
          <div class="form-group">
            <label>伏笔/钩子</label>
            <textarea v-model="hooksText" placeholder="每行一个伏笔或钩子"></textarea>
          </div>
          
          <div class="actions">
            <button class="btn btn-primary" @click="generateChapterPlan" :disabled="loading">
              {{ loading ? '生成中...' : '生成章纲' }}
            </button>
            <button class="btn" @click="loadChapterPlan">加载已有</button>
          </div>
        </div>
      </div>
      
      <div class="sidebar">
        <div class="card">
          <h3>L2大纲参考</h3>
          <div v-if="outline" class="outline-ref">
            <div v-for="seq in outline.sequences" :key="seq.name" class="seq-item">
              {{ seq.name }}
            </div>
          </div>
          <p v-else class="hint">暂无大纲</p>
        </div>
        
        <div v-if="chapterPlan" class="card">
          <h3>生成的章纲</h3>
          <p><strong>章节:</strong> {{ chapterPlan.chapter_name }}</p>
          <p><strong>场景数:</strong> {{ chapterPlan.scenes?.length || 0 }}</p>
          <router-link :to="`/l4/${projectId}`" class="btn btn-success">
            进入L4渲染 →
          </router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'

const route = useRoute()
const projectId = route.params.projectId

const scenes = ref([{ name: '', perspective: '外聚焦', pace: '等述', discourse_mode: '对话+动作', word_count: 500 }])
const chapterName = ref('')
const emotionCurve = ref('')
const hooksText = ref('')
const outline = ref(null)
const chapterPlan = ref(null)
const loading = ref(false)

const addScene = () => {
  scenes.value.push({ name: '', perspective: '外聚焦', pace: '等述', discourse_mode: '对话+动作', word_count: 500 })
}

const removeScene = (idx) => {
  if (scenes.value.length > 1) {
    scenes.value.splice(idx, 1)
  }
}

const generateChapterPlan = async () => {
  loading.value = true
  try {
    const res = await axios.post(`/api/projects/${projectId}/l3/generate`, {
      scenes: scenes.value,
      chapter_name: chapterName.value,
      emotion_curve: emotionCurve.value,
      hooks: hooksText.value.split('\n').filter(h => h.trim())
    })
    chapterPlan.value = res.data.chapter_plan
  } finally {
    loading.value = false
  }
}

const loadChapterPlan = async () => {
  try {
    const res = await axios.get(`/api/projects/${projectId}/l3/plan`)
    chapterPlan.value = res.data.chapter_plan
    if (chapterPlan.value) {
      chapterName.value = chapterPlan.value.chapter_name
      emotionCurve.value = chapterPlan.value.emotion_curve
      hooksText.value = (chapterPlan.value.hooks || []).join('\n')
      scenes.value = chapterPlan.value.scenes || scenes.value
    }
  } catch (e) {
    alert('尚未生成章纲')
  }
}

const loadOutline = async () => {
  try {
    const res = await axios.get(`/api/projects/${projectId}/l2/outline`)
    outline.value = res.data.outline
  } catch (e) {
    console.log('No outline yet')
  }
}

onMounted(() => {
  loadOutline()
  loadChapterPlan()
})
</script>

<style scoped>
.l3-narrative h1 {
  margin-bottom: 1.5rem;
}

.l3-layout {
  display: grid;
  grid-template-columns: 1fr 280px;
  gap: 1.5rem;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.scene-card {
  background: #f8f9fa;
  padding: 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
}

.scene-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.scene-header h3 {
  margin: 0;
}

.actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 1rem;
}

.outline-ref .seq-item {
  padding: 0.5rem;
  background: #f0f0f0;
  border-radius: 4px;
  margin-bottom: 0.5rem;
  font-size: 0.875rem;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
  gap: 1rem;
}

.page-header h1 {
  margin: 0;
}

.nav-actions {
  display: flex;
  gap: 1rem;
  align-items: center;
}

.layer-nav {
  display: flex;
  gap: 0.25rem;
}

.layer-nav .btn {
  padding: 0.5rem 1rem;
  min-width: 3rem;
}

.layer-nav .btn.active {
  background: #3498db;
  color: white;
}

@media (max-width: 768px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
  }
  
  .nav-actions {
    width: 100%;
    flex-wrap: wrap;
  }
}
</style>
