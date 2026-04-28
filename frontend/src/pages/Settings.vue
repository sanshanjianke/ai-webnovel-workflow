<template>
  <div class="settings">
    <h1>系统设置</h1>
    
    <div class="card">
      <h2>模块列表</h2>
      <div v-for="(mods, category) in modules" :key="category" class="module-category">
        <h3>{{ categoryLabels[category] || category }}</h3>
        <ul class="module-list">
          <li v-for="mod in mods" :key="mod">{{ mod }}</li>
        </ul>
      </div>
    </div>
    
    <div class="card">
      <h2>配置</h2>
      <pre class="config-display">{{ JSON.stringify(config, null, 2) }}</pre>
    </div>
    
    <div class="card">
      <h2>LLM配置</h2>
      <div class="form-group">
        <label>API Key</label>
        <input v-model="llmConfig.api_key" type="password" placeholder="sk-...">
      </div>
      <div class="form-group">
        <label>Base URL</label>
        <input v-model="llmConfig.base_url" type="text" placeholder="https://api.openai.com/v1">
      </div>
      <div class="form-group">
        <label>Primary Model</label>
        <input v-model="llmConfig.primary" type="text" placeholder="open_ai_compat">
      </div>
      <button class="btn btn-primary" @click="saveConfig">保存配置</button>
    </div>
    
    <div class="card">
      <h2>Pipeline配置</h2>
      <div class="form-group">
        <label>L2 会议协议</label>
        <select v-model="pipelineConfig.l2.meeting_protocol">
          <option value="plot_driven">剧情驱动</option>
          <option value="character_driven">人物驱动</option>
          <option value="market_driven">市场驱动</option>
        </select>
      </div>
      <div class="form-group">
        <label>L2 协作模式</label>
        <select v-model="pipelineConfig.l2.collaboration_mode">
          <option value="semi_auto">半自动</option>
          <option value="full_auto">全自动</option>
          <option value="manual">手动</option>
        </select>
      </div>
      <div class="form-group">
        <label>L2 最大轮次</label>
        <input v-model.number="pipelineConfig.l2.max_rounds" type="number" min="1" max="10">
      </div>
      <button class="btn btn-primary" @click="saveConfig">保存配置</button>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import axios from 'axios'

const modules = ref({})
const config = ref({})
const llmConfig = reactive({
  api_key: '',
  base_url: '',
  primary: ''
})
const pipelineConfig = reactive({
  l2: {
    meeting_protocol: 'plot_driven',
    collaboration_mode: 'semi_auto',
    max_rounds: 3
  }
})

const categoryLabels = {
  llm: 'LLM模块',
  rag: 'RAG模块',
  worldbook: '世界书模块',
  l1: 'L1种子层模块',
  l2: 'L2架构层模块',
  l3: 'L3叙事层模块',
  l4: 'L4渲染层模块',
  meeting_protocol: '会议协议'
}

const fetchModules = async () => {
  const res = await axios.get('/api/modules')
  modules.value = res.data
}

const fetchConfig = async () => {
  const res = await axios.get('/api/config')
  config.value = res.data
  
  if (config.value.llm) {
    llmConfig.api_key = config.value.llm.api_key || ''
    llmConfig.base_url = config.value.llm.base_url || ''
    llmConfig.primary = config.value.llm.primary || ''
  }
  
  if (config.value.pipeline?.l2) {
    pipelineConfig.l2 = { ...config.value.pipeline.l2 }
  }
}

const saveConfig = async () => {
  const update = {
    llm: { ...llmConfig },
    pipeline: {
      l2: { ...pipelineConfig.l2 }
    }
  }
  
  await axios.put('/api/config', update)
  alert('配置已保存')
  fetchConfig()
}

onMounted(() => {
  fetchModules()
  fetchConfig()
})
</script>

<style scoped>
.settings {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: auto;
  padding: 1.5rem;
}

.settings h1 {
  margin-bottom: 1.5rem;
}

.settings .card {
  margin-bottom: 1.5rem;
}

.module-category {
  margin-bottom: 1rem;
}

.module-category h3 {
  font-size: 1rem;
  margin-bottom: 0.5rem;
}

.module-list {
  list-style: none;
  padding-left: 1rem;
}

.module-list li {
  padding: 0.25rem 0;
  font-family: monospace;
  color: #666;
}

.config-display {
  background: #f5f5f5;
  padding: 1rem;
  border-radius: 4px;
  overflow-x: auto;
  font-size: 0.875rem;
}

.form-group {
  margin-bottom: 1rem;
}
</style>
