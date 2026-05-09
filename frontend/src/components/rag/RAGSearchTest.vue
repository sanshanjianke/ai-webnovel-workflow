<template>
  <div class="rag-search-test">
    <div class="search-row">
      <input v-model="query" placeholder="输入查询文本..." @keyup.enter="doSearch" />
      <button class="btn btn-primary btn-sm" @click="doSearch" :disabled="!query">🔍 检索</button>
    </div>

    <div class="search-options" v-if="retrieverType !== 'keyword'">
      <span class="opt-label">维度：</span>
      <label><input type="checkbox" v-model="dims.plot" /> plot</label>
      <label><input type="checkbox" v-model="dims.character" /> character</label>
      <label><input type="checkbox" v-model="dims.emotion" /> emotion</label>
      <label><input type="checkbox" v-model="dims.function" /> function</label>
      <span class="opt-sep">|</span>
      <label>返回 <input type="number" v-model.number="k" min="1" max="20" style="width:50px" /> 条</label>
    </div>

    <div v-if="results.length > 0" class="results-area">
      <p class="result-summary">结果 ({{ results.length }} 条，耗时 {{ duration }}ms)：</p>
      <div v-for="(r, i) in results" :key="r.id || i" class="result-item" @click="selected = r">
        <div class="result-header">
          <span class="result-rank">#{{ i + 1 }}</span>
          <span class="result-score">score:{{ r.score.toFixed(3) }}</span>
          <span class="result-id">{{ r.id }}</span>
          <span class="result-words" v-if="r.metadata?.matchedWords?.length">
            命中：{{ r.metadata.matchedWords.join(', ') }}
          </span>
        </div>
        <div class="result-content">{{ (r.content || '').slice(0, 200) }}{{ (r.content || '').length > 200 ? '...' : '' }}</div>
      </div>
    </div>
    <p v-if="searched && results.length === 0" class="hint">无结果</p>

    <!-- 切片详情（仅 hybrid/vector） -->
    <div v-if="selected && retrieverType !== 'keyword'" class="slice-detail">
      <h4>切片详情 — {{ selected.id }}</h4>
      <p><strong>得分：</strong>{{ selected.score.toFixed(3) }}</p>
      <p><strong>关键词：</strong>{{ (selected.metadata?.matchedWords || []).join(', ') || '-' }}</p>
      <div class="slice-full-content">{{ selected.content }}</div>
      <div v-if="selected.metadata?.tags?.length" class="slice-meta">
        <strong>标签：</strong>{{ selected.metadata.tags.join(', ') }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import axios from 'axios'

const props = defineProps({
  instanceId: String,
  projectId: String,
  retrieverType: { type: String, default: 'keyword' }
})

const query = ref('')
const k = ref(5)
const dims = ref({ plot: true, character: true, emotion: true, function: true })
const results = ref([])
const duration = ref(0)
const searched = ref(false)
const selected = ref(null)

async function doSearch() {
  if (!query.value) return
  try {
    const res = await axios.post(`/api/projects/${props.projectId}/rags/${props.instanceId}/search`, {
      query: query.value, k: k.value
    })
    results.value = res.data.results || []
    duration.value = res.data.duration || 0
    searched.value = true
    selected.value = null
  } catch (e) { console.error('search', e) }
}
</script>

<style scoped>
.rag-search-test { }
.search-row { display: flex; gap: 8px; margin-bottom: 12px; }
.search-row input { flex: 1; padding: 8px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; }
.search-options { display: flex; gap: 12px; align-items: center; margin-bottom: 12px; font-size: 13px; }
.search-options label { display: flex; align-items: center; gap: 3px; cursor: pointer; }
.opt-label { font-weight: 600; }
.opt-sep { color: #ddd; }
.result-summary { font-size: 13px; color: #666; margin-bottom: 8px; }
.result-item { padding: 10px; margin-bottom: 6px; border: 1px solid #eee; border-radius: 6px; cursor: pointer; transition: background 0.15s; }
.result-item:hover { background: #f0f7ff; }
.result-header { display: flex; gap: 12px; align-items: center; margin-bottom: 4px; font-size: 12px; }
.result-rank { font-weight: 700; color: #3498db; }
.result-score { background: #e8f5e9; color: #27ae60; padding: 1px 6px; border-radius: 3px; font-weight: 600; }
.result-id { color: #888; }
.result-words { color: #e67e22; }
.result-content { font-size: 13px; color: #555; line-height: 1.6; }
.slice-detail { margin-top: 16px; padding: 12px; background: #fafafa; border-radius: 8px; border: 1px solid #eee; }
.slice-detail h4 { margin-top: 0; }
.slice-full-content { white-space: pre-wrap; font-size: 13px; line-height: 1.8; color: #333; max-height: 400px; overflow-y: auto; padding: 8px; background: #fff; border-radius: 4px; }
.slice-meta { margin-top: 8px; font-size: 12px; color: #888; }

.btn { padding: 6px 14px; border: 1px solid #ddd; border-radius: 6px; background: #fff; cursor: pointer; font-size: 13px; }
.btn-primary { background: #3498db; color: #fff; border-color: #3498db; }
.btn-sm { padding: 4px 10px; font-size: 12px; }
.hint { color: #999; font-size: 13px; }
</style>
