<template>
  <div class="rag-search-log">
    <div class="log-toolbar">
      <span>共 {{ entries.length }} 条检索记录</span>
      <button class="btn btn-sm" @click="loadLog">🔄 刷新</button>
    </div>
    <div v-if="entries.length === 0" class="hint">暂无检索记录</div>
    <div v-for="entry in entries" :key="entry.id" class="log-entry">
      <div class="log-time">{{ formatTime(entry.timestamp) }}</div>
      <div class="log-query">"{{ entry.query }}"</div>
      <div class="log-meta">
        <span>{{ entry.resultsCount }} 条结果</span>
        <span>top={{ entry.topScore?.toFixed?.(3) || entry.topScore }}</span>
        <span>{{ entry.duration }}ms</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import axios from 'axios'

const props = defineProps({
  instanceId: String,
  projectId: String
})

const entries = ref([])

function formatTime(ts) {
  if (!ts) return ''
  return new Date(ts).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

async function loadLog() {
  try {
    const res = await axios.get(`/api/projects/${props.projectId}/rags/${props.instanceId}/log?limit=50`)
    entries.value = res.data.entries || []
  } catch {}
}

onMounted(loadLog)
watch(() => props.instanceId, loadLog)
</script>

<style scoped>
.rag-search-log { }
.log-toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; font-size: 13px; }
.log-entry { padding: 8px; margin-bottom: 4px; border-bottom: 1px solid #f0f0f0; font-size: 13px; }
.log-time { color: #999; font-size: 11px; }
.log-query { color: #2c3e50; font-weight: 500; margin: 2px 0; }
.log-meta { display: flex; gap: 12px; font-size: 11px; color: #888; }

.btn { padding: 6px 14px; border: 1px solid #ddd; border-radius: 6px; background: #fff; cursor: pointer; font-size: 13px; }
.btn-sm { padding: 4px 10px; font-size: 12px; }
.hint { color: #999; font-size: 13px; }
</style>
