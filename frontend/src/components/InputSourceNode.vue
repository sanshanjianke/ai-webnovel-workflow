<template>
  <div class="input-source-node" :class="{ selected: data.selected }">
    <div class="node-header">
      <span class="node-icon">📥</span>
      <span class="node-label">{{ data.label || '输入源' }}</span>
      <span class="node-count" v-if="fileCount > 0">{{ fileCount }}</span>
    </div>
    <div class="node-body">
      <span class="node-hint">{{ fileCount > 0 ? fileCount + ' 个文件' : '空队列' }}</span>
    </div>
    <Handle type="source" :position="Position.Right" id="output" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'

const props = defineProps({
  data: { type: Object, required: true }
})

const fileCount = computed(() => props.data.files ? props.data.files.length : 0)
</script>

<style scoped>
.input-source-node {
  background: #f0fdf4;
  border: 2px solid #22c55e;
  border-radius: 12px;
  padding: 10px 14px;
  min-width: 120px;
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.input-source-node:hover { box-shadow: 0 2px 12px rgba(34, 197, 94, 0.15); }
.input-source-node.selected { border-color: #16a34a; box-shadow: 0 0 0 2px rgba(34, 197, 94, 0.2); }
.node-header { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.node-icon { font-size: 1.2rem; }
.node-label { font-weight: 600; font-size: 0.85rem; color: #166534; }
.node-count { background: #22c55e; color: white; border-radius: 10px; padding: 0 6px; font-size: 0.65rem; font-weight: 600; }
.node-body { display: flex; align-items: center; gap: 6px; }
.node-hint { font-size: 0.7rem; color: #666; }
</style>
