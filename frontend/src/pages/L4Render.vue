<template>
  <div class="l4-render">
    <div class="page-header">
      <h1>L4 渲染层 - 正文生成</h1>
      <div class="nav-actions">
        <router-link to="/" class="btn">← 返回仪表盘</router-link>
        <div class="layer-nav">
          <router-link :to="`/l1?projectId=${projectId}`" class="btn">L1</router-link>
          <router-link :to="`/l2/${projectId}`" class="btn">L2</router-link>
          <router-link :to="`/l3/${projectId}`" class="btn">L3</router-link>
          <router-link :to="`/l4/${projectId}`" class="btn active">L4</router-link>
        </div>
      </div>
    </div>
    
    <div class="render-layout">
      <div class="main-area">
        <div class="card">
          <h2>章纲参考</h2>
          <div v-if="chapterPlan">
            <p><strong>章节:</strong> {{ chapterPlan.chapter_name }}</p>
            <p><strong>情绪曲线:</strong> {{ chapterPlan.emotion_curve }}</p>
            <div class="scenes-list">
              <div v-for="(scene, idx) in chapterPlan.scenes" :key="idx" class="scene-item">
                <strong>场景{{ idx + 1 }}:</strong> {{ scene.name }}<br>
                <small>视角: {{ scene.perspective }} | 节奏: {{ scene.pace }} | 字数: {{ scene.word_count }}</small>
              </div>
            </div>
          </div>
          <p v-else class="hint">请先在L3层生成章纲</p>
        </div>
        
        <div class="card">
          <div class="card-header">
            <h2>生成正文</h2>
            <button class="btn btn-primary" @click="startRender" :disabled="rendering">
              {{ rendering ? '生成中...' : '开始生成' }}
            </button>
          </div>
          
          <div v-if="generatedText" class="generated-content">
            <h3>{{ generatedText.chapter_name }}</h3>
            <div class="text-content" v-html="renderMarkdown(generatedText.content)"></div>
            <p class="word-count">字数: {{ generatedText.word_count }}</p>
          </div>
          <div v-else-if="rendering" class="streaming-content">
            <pre>{{ streamingText }}</pre>
          </div>
          <p v-else class="hint">点击"开始生成"渲染正文</p>
        </div>
      </div>
      
      <div class="sidebar">
        <div class="card">
          <h3>生成状态</h3>
          <p v-if="rendering">正在生成...</p>
          <p v-else-if="generatedText">生成完成</p>
          <p v-else>等待开始</p>
        </div>
        
        <div v-if="generatedText" class="card">
          <h3>操作</h3>
          <button class="btn btn-primary" @click="copyText">复制全文</button>
          <button class="btn" @click="downloadText">下载TXT</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import MarkdownIt from 'markdown-it'

const route = useRoute()
const projectId = route.params.projectId

const md = new MarkdownIt()

const chapterPlan = ref(null)
const generatedText = ref(null)
const streamingText = ref('')
const rendering = ref(false)

const renderMarkdown = (text) => {
  if (!text) return ''
  return md.render(text)
}

const loadChapterPlan = async () => {
  try {
    const res = await axios.get(`/api/projects/${projectId}/l3/plan`)
    chapterPlan.value = res.data.chapter_plan
  } catch (e) {
    console.log('No chapter plan yet')
  }
}

const loadGeneratedText = async () => {
  try {
    const res = await axios.get(`/api/projects/${projectId}/l4/text`)
    generatedText.value = res.data.text
  } catch (e) {
    console.log('No generated text yet')
  }
}

const startRender = async () => {
  rendering.value = true
  streamingText.value = ''
  generatedText.value = null
  
  const eventSource = new EventSource(`/api/projects/${projectId}/l4/stream`)
  
  eventSource.addEventListener('text', (event) => {
    const data = JSON.parse(event.data)
    streamingText.value += data.content
  })
  
  eventSource.addEventListener('done', (event) => {
    eventSource.close()
    rendering.value = false
    loadGeneratedText()
  })
  
  eventSource.onerror = () => {
    eventSource.close()
    rendering.value = false
  }
}

const copyText = () => {
  if (generatedText.value) {
    navigator.clipboard.writeText(generatedText.value.content)
    alert('已复制到剪贴板')
  }
}

const downloadText = () => {
  if (generatedText.value) {
    const blob = new Blob([generatedText.value.content], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${generatedText.value.chapter_name}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }
}

onMounted(() => {
  loadChapterPlan()
  loadGeneratedText()
})
</script>

<style scoped>
.l4-render h1 {
  margin-bottom: 1.5rem;
}

.render-layout {
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

.scenes-list {
  margin-top: 1rem;
}

.scene-item {
  padding: 0.75rem;
  background: #f5f5f5;
  border-radius: 4px;
  margin-bottom: 0.5rem;
}

.generated-content {
  margin-top: 1rem;
}

.text-content {
  background: #fafafa;
  padding: 1rem;
  border-radius: 4px;
  white-space: pre-wrap;
  line-height: 1.8;
}

.word-count {
  text-align: right;
  color: #666;
  font-size: 0.875rem;
  margin-top: 1rem;
}

.streaming-content {
  margin-top: 1rem;
  background: #fafafa;
  padding: 1rem;
  border-radius: 4px;
}

.streaming-content pre {
  white-space: pre-wrap;
  font-family: inherit;
  margin: 0;
}

.hint {
  color: #999;
}

.sidebar .btn {
  display: block;
  width: 100%;
  margin-bottom: 0.5rem;
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
