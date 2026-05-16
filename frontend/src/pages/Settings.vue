<template>
  <div class="settings">
    <h1>系统设置</h1>

    <!-- LLM 配置 -->
    <div class="card">
      <h2>LLM 配置</h2>

      <div class="form-group">
        <label>服务商</label>
        <div class="provider-row">
          <select v-model="selectedProviderId" @change="onProviderChange">
            <optgroup label="内置">
              <option v-for="p in builtinProviders" :key="p.id" :value="p.id">{{ p.name }}</option>
            </optgroup>
            <optgroup v-if="customProviders.length" label="自定义">
              <option v-for="p in customProviders" :key="p.id" :value="p.id">{{ p.name }}</option>
            </optgroup>
          </select>
          <button class="btn btn-sm" @click="saveAsCustom">➕ 收藏当前</button>
          <button v-if="isCustomProvider" class="btn btn-sm btn-danger" @click="deleteCustom">✕ 删除</button>
        </div>
      </div>

      <div class="form-group">
        <label>Base URL</label>
        <input v-model="genConfig.base_url" type="text" placeholder="https://api.openai.com/v1">
      </div>

      <div class="form-group">
        <label>模型</label>
        <div class="model-row">
          <select v-model="genConfig.model" v-if="modelOptions.length">
            <option v-for="m in modelOptions" :key="m" :value="m">{{ m }}</option>
            <option value="__custom__">其他（手动输入）...</option>
          </select>
          <input v-model="genConfig.model" type="text" placeholder="输入模型名" v-if="!modelOptions.length || genConfig.model === '__custom__' || !modelOptions.includes(genConfig.model)">
        </div>
      </div>

      <div class="form-group">
        <label>API Key</label>
        <input v-model="genConfig.api_key" type="password" placeholder="sk-...">
      </div>

      <!-- 自定义请求头 -->
      <div class="form-group">
        <div class="section-toggle" @click="showHeaders = !showHeaders">
          <label style="cursor:pointer">自定义请求头 <span class="toggle-arrow">{{ showHeaders ? '▾' : '▸' }}</span></label>
        </div>
        <div v-if="showHeaders" class="headers-editor">
          <textarea v-model="headersText" rows="4" :placeholder="headersPlaceholder"></textarea>
          <div class="param-hint" v-if="headerError" style="color:#e74c3c;margin-top:0.25rem">{{ headerError }}</div>
          <div class="param-hint" v-else-if="headersText.trim()" style="margin-top:0.25rem">已解析 {{ parsedHeadersCount }} 个请求头</div>
          <div class="param-hint" v-else style="margin-top:0.25rem">JSON 格式，留空则使用默认 Bearer {apikey}。</div>
        </div>
      </div>

      <!-- 采样参数 -->
      <div class="form-group">
        <label>Temperature <span class="param-val">{{ genConfig.temperature.toFixed(2) }}</span></label>
        <div class="slider-row">
          <input type="range" v-model.number="genConfig.temperature" :min="tempRange.min" :max="tempRange.max" step="0.01" class="slider">
        </div>
        <div class="param-hint" v-if="tempHint">{{ tempHint }}</div>
      </div>

      <div class="form-group">
        <label>Top P <span class="param-val">{{ genConfig.top_p.toFixed(2) }}</span></label>
        <div class="slider-row">
          <input type="range" v-model.number="genConfig.top_p" min="0" max="1" step="0.01" class="slider">
        </div>
      </div>

      <div class="form-group" v-if="showFrequencyPenalty">
        <label>频率惩罚 <span class="param-val">{{ genConfig.frequency_penalty.toFixed(2) }}</span></label>
        <div class="slider-row">
          <input type="range" v-model.number="genConfig.frequency_penalty" :min="penaltyMin" max="2" step="0.01" class="slider">
        </div>
      </div>

      <div class="form-group" v-if="showPresencePenalty">
        <label>存在惩罚 <span class="param-val">{{ genConfig.presence_penalty.toFixed(2) }}</span></label>
        <div class="slider-row">
          <input type="range" v-model.number="genConfig.presence_penalty" :min="penaltyMin" max="2" step="0.01" class="slider">
        </div>
      </div>

      <div v-if="genConfig.thinking && samplingWarning" class="param-warn">{{ samplingWarning }}</div>

      <div class="form-group">
        <label>最大输出 Token</label>
        <input v-model.number="genConfig.max_tokens" type="number" min="256" max="131072" step="256">
      </div>

      <!-- 思维链 -->
      <div v-if="thinkingMode !== 'none'" class="subsection">
        <h3>思维链 (Chain of Thought)</h3>
        <div class="form-group">
          <label class="checkbox-label">
            <input type="checkbox" v-model="genConfig.thinking">
            启用思维链
          </label>
          <div class="param-hint">{{ thinkingHint }}</div>
        </div>

        <!-- effort 模式：reasoning_effort -->
        <div v-if="genConfig.thinking && thinkingMode === 'effort'">
          <div class="form-group">
            <label>推理强度</label>
            <select v-model="genConfig.reasoning_effort">
              <option value="low">low</option>
              <option value="medium">medium</option>
              <option value="high">high (默认)</option>
              <option value="max">max</option>
            </select>
            <div class="param-hint">{{ providerName }}: low/medium 均映射为 high，实际有效值为 high 或 max。</div>
          </div>
        </div>
      </div>

      <button class="btn btn-primary" @click="saveConfig">保存配置</button>
    </div>

    <!-- 界面设置 -->
    <div class="card">
      <h2>界面设置</h2>
      <div class="form-group">
        <label>回车键行为</label>
        <select v-model="uiConfig.enterKeyBehavior">
          <option value="newline">Enter 换行，Shift+Enter 发送</option>
          <option value="send">Enter 发送，Shift+Enter 换行</option>
        </select>
      </div>
      <button class="btn btn-primary" @click="saveUiConfig">保存界面设置</button>
    </div>

    <!-- 模块列表 -->
    <div class="card">
      <h2>模块列表</h2>
      <div v-for="(mods, category) in modules" :key="category" class="module-category">
        <h3>{{ categoryLabels[category] || category }}</h3>
        <ul class="module-list">
          <li v-for="mod in mods" :key="mod">{{ mod }}</li>
        </ul>
      </div>
    </div>

    <!-- 当前配置 -->
    <div class="card">
      <h2>当前配置</h2>
      <pre class="config-display">{{ JSON.stringify(config, null, 2) }}</pre>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import axios from 'axios'

const modules = ref({})
const config = ref({})

const builtinProviders = ref([])
const customProviders = ref([])
const selectedProviderId = ref('custom')

// 完整配置（LLM 连接 + 生成参数）
const genConfig = reactive({
  api_key: '',
  base_url: '',
  model: '',
  temperature: 0.7,
  top_p: 1.0,
  frequency_penalty: 0,
  presence_penalty: 0,
  max_tokens: 16384,
  thinking: false,
  thinking_budget: 10000,
  reasoning_effort: 'high'
})

const showHeaders = ref(false)
const headersText = ref('')

const uiConfig = reactive({
  enterKeyBehavior: 'newline'
})

const categoryLabels = {
  llm: 'LLM 实现',
  rag: 'RAG 实现',
  worldbook: '世界书实现',
  expert: '已注册专家'
}

// 所有可选服务商
const allProviders = computed(() => [...builtinProviders.value, ...customProviders.value])
const selectedProvider = computed(() => allProviders.value.find(p => p.id === selectedProviderId.value))
const isCustomProvider = computed(() => customProviders.value.some(p => p.id === selectedProviderId.value))
const modelOptions = computed(() => selectedProvider.value?.models || [])

// 根据服务商能力显示/隐藏参数
const showFrequencyPenalty = computed(() => selectedProvider.value?.supports?.frequencyPenalty !== false)
const showPresencePenalty = computed(() => selectedProvider.value?.supports?.presencePenalty !== false)
const thinkingMode = computed(() => selectedProvider.value?.thinkingMode || 'none')

// ── 动态提示文本（根据服务商变化） ──

const providerName = computed(() => selectedProvider.value?.name || '自定义')

// Temperature 范围（智谱/GLM 为 0-1，其余为 0-2）
const tempRange = computed(() => {
  const id = selectedProviderId.value
  if (id === 'zhipu' || id === 'jdcloud') return { min: 0, max: 1 }
  return { min: 0, max: 2 }
})

const tempHint = computed(() => {
  if (tempRange.value.max === 1) return `${providerName.value}: temperature 范围为 0-1`
  return ''
})

// 惩罚参数最小值（Kimi 为 -2，其余为 0）
const penaltyMin = computed(() => {
  if (selectedProviderId.value === 'moonshot') return -2
  return 0
})

// 思维链说明
const thinkingHint = computed(() => {
  const name = providerName.value
  if (thinkingMode.value === 'simple') return `${name}: thinking 参数仅 type: enabled/disabled，无额外配置。`
  if (thinkingMode.value === 'effort') return `${name}: 开启后通过 reasoning_effort 控制推理深度。`
  return ''
})

// 开启思维链时采样参数失效的警告
const samplingWarning = computed(() => {
  const id = selectedProviderId.value
  if (id === 'deepseek') return '⚠ DeepSeek 开启思维链时，Temperature、Top P、频率惩罚、存在惩罚均不生效。'
  if (id === 'moonshot') {
    const m = genConfig.model.toLowerCase()
    if (m.includes('k2.6') || m.includes('k2.5')) return '⚠ Kimi k2.6/k2.5 开启 thinking 时采样参数不生效。'
  }
  if (id === 'zhipu') return '⚠ 智谱不支持频率惩罚和存在惩罚参数（API 不接受这两个字段）。'
  if (id === 'jdcloud') return '⚠ 京东云代理 GLM 模型，频率/存在惩罚参数可能不生效。'
  return ''
})

// ── 自定义请求头 ──

const headersPlaceholder = `{
  "Authorization": "Bearer sk-xxx",
  "X-Custom-Header": "value"
}`

const headerError = computed(() => {
  if (!headersText.value.trim()) return ''
  try {
    const obj = JSON.parse(headersText.value)
    if (typeof obj !== 'object' || Array.isArray(obj)) return '格式错误：需要 JSON 对象，不是数组'
    return ''
  } catch (e) {
    return 'JSON 格式错误：' + e.message
  }
})

const parsedHeadersCount = computed(() => {
  if (!headersText.value.trim() || headerError.value) return 0
  try {
    const obj = JSON.parse(headersText.value)
    return Object.keys(obj).length
  } catch { return 0 }
})

function parseHeaders(text) {
  if (!text.trim()) return {}
  try {
    const obj = JSON.parse(text)
    if (typeof obj !== 'object' || Array.isArray(obj)) return {}
    const result = {}
    for (const [k, v] of Object.entries(obj)) {
      result[k] = typeof v === 'string' ? v : String(v)
    }
    return result
  } catch { return {} }
}

function serializeHeaders(headers) {
  if (!headers || Object.keys(headers).length === 0) return ''
  return JSON.stringify(headers, null, 2)
}

// ── 数据加载 ──

const fetchProviders = async () => {
  const res = await axios.get('/api/llm-providers')
  builtinProviders.value = res.data.builtin || []
  customProviders.value = res.data.custom || []
}

const fetchModules = async () => {
  const res = await axios.get('/api/modules')
  modules.value = res.data
}

const fetchConfig = async () => {
  const res = await axios.get('/api/config')
  config.value = res.data

  if (config.value.llm) {
    genConfig.api_key = ''
    genConfig.base_url = config.value.llm.base_url || ''
    genConfig.model = config.value.llm.model || ''
    headersText.value = serializeHeaders(config.value.llm.headers)
    showHeaders.value = !!headersText.value
  }
  if (config.value.generation) {
    genConfig.temperature = config.value.generation.temperature ?? 0.7
    genConfig.top_p = config.value.generation.top_p ?? 1.0
    genConfig.frequency_penalty = config.value.generation.frequency_penalty ?? 0
    genConfig.presence_penalty = config.value.generation.presence_penalty ?? 0
    genConfig.max_tokens = config.value.generation.max_tokens ?? 16384
    genConfig.thinking = config.value.generation.thinking ?? false
    genConfig.thinking_budget = config.value.generation.thinking_budget ?? 10000
    genConfig.reasoning_effort = config.value.generation.reasoning_effort || 'high'
  }

  matchProvider()
}

const matchProvider = () => {
  const url = genConfig.base_url || ''
  const builtin = builtinProviders.value.find(p => p.baseUrl === url)
  if (builtin) { selectedProviderId.value = builtin.id; return }
  const custom = customProviders.value.find(p => p.baseUrl === url)
  if (custom) { selectedProviderId.value = custom.id; return }
  try {
    const host = new URL(url).hostname
    for (const p of allProviders.value) {
      try { if (new URL(p.baseUrl).hostname === host) { selectedProviderId.value = p.id; return } } catch {}
    }
  } catch {}
  selectedProviderId.value = 'custom'
}

// ── 服务商切换 ──

const onProviderChange = () => {
  const p = selectedProvider.value
  if (!p || p.id === 'custom') return
  genConfig.base_url = p.baseUrl
  if (p.models.length > 0) genConfig.model = p.models[0]
}

// ── 自定义服务商 ──

const saveAsCustom = async () => {
  const name = prompt('为此服务商命名：')
  if (!name) return
  const id = 'custom_' + Date.now()
  const newProvider = {
    id, name,
    baseUrl: genConfig.base_url,
    models: genConfig.model ? [genConfig.model] : [],
    thinkingMode: 'simple',
    supports: { frequencyPenalty: true, presencePenalty: true }
  }
  customProviders.value.push(newProvider)
  await axios.put('/api/llm-providers', { custom: customProviders.value.map(p => ({ id: p.id, name: p.name, baseUrl: p.baseUrl, models: p.models, supports: p.supports })) })
  selectedProviderId.value = id
}

const deleteCustom = async () => {
  if (!confirm(`确定删除服务商 "${selectedProvider.value?.name}"？`)) return
  customProviders.value = customProviders.value.filter(p => p.id !== selectedProviderId.value)
  await axios.put('/api/llm-providers', { custom: customProviders.value.map(p => ({ id: p.id, name: p.name, baseUrl: p.baseUrl, models: p.models, supports: p.supports })) })
  selectedProviderId.value = 'custom'
}

// ── 保存 ──

const saveConfig = async () => {
  await axios.put('/api/config', {
    llm: {
      api_key: genConfig.api_key,
      base_url: genConfig.base_url,
      model: genConfig.model,
      headers: parseHeaders(headersText.value)
    },
    generation: {
      temperature: genConfig.temperature,
      top_p: genConfig.top_p,
      frequency_penalty: genConfig.frequency_penalty,
      presence_penalty: genConfig.presence_penalty,
      max_tokens: genConfig.max_tokens,
      thinking: genConfig.thinking,
      thinking_budget: genConfig.thinking_budget,
      reasoning_effort: genConfig.reasoning_effort
    }
  })
  alert('配置已保存')
}

// ── UI 配置 ──

const loadUiConfig = () => {
  const saved = localStorage.getItem('uiConfig')
  if (saved) {
    try {
      const parsed = JSON.parse(saved)
      uiConfig.enterKeyBehavior = parsed.enterKeyBehavior || 'newline'
    } catch (e) {}
  }
}

const saveUiConfig = () => {
  localStorage.setItem('uiConfig', JSON.stringify(uiConfig))
  alert('界面设置已保存')
}

onMounted(async () => {
  await fetchProviders()
  fetchModules()
  fetchConfig()
  loadUiConfig()
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

.form-group {
  margin-bottom: 1rem;
}

.provider-row, .model-row {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.provider-row select, .model-row select {
  flex: 1;
}

.provider-row input, .model-row input {
  flex: 1;
}

/* 滑块 */
.slider-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.slider {
  flex: 1;
  height: 6px;
  -webkit-appearance: none;
  appearance: none;
  background: #ddd;
  border-radius: 3px;
  outline: none;
}

.slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #4a90d9;
  cursor: pointer;
}

.slider::-moz-range-thumb {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #4a90d9;
  cursor: pointer;
  border: none;
}

.param-val {
  color: #4a90d9;
  font-weight: 600;
  font-size: 0.85rem;
}

.param-hint {
  color: #999;
  font-size: 0.8rem;
  margin-top: 0.25rem;
}

.param-warn {
  color: #e67e22;
  font-size: 0.8rem;
  margin-top: 0.5rem;
  padding: 0.5rem;
  background: #fef9f0;
  border-radius: 4px;
  border-left: 3px solid #e67e22;
}

/* 自定义请求头 */
.section-toggle {
  display: flex;
  align-items: center;
  user-select: none;
}

.section-toggle label {
  margin: 0;
}

.toggle-arrow {
  color: #999;
  font-size: 0.8rem;
}

.headers-editor textarea {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-family: monospace;
  font-size: 0.85rem;
  resize: vertical;
}

/* 思维链子区域 */
.subsection {
  border-top: 1px solid #eee;
  padding-top: 1rem;
  margin-top: 0.5rem;
}

.subsection h3 {
  font-size: 0.95rem;
  margin-bottom: 0.75rem;
  color: #555;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
}

.checkbox-label input[type="checkbox"] {
  width: 18px;
  height: 18px;
  cursor: pointer;
}

/* 模块列表 */
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
  max-height: 300px;
}

.btn-sm {
  padding: 0.4rem 0.8rem;
  font-size: 0.85rem;
  white-space: nowrap;
}

.btn-danger {
  background: #e74c3c;
  color: white;
  border: 1px solid #c0392b;
}

.btn-danger:hover {
  background: #c0392b;
}
</style>
