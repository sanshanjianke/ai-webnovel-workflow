<template>
  <div class="output-node" :class="{ selected: data.selected, running: data.running, done: data.done }">
    <div class="node-header">
      <span class="node-icon">📤</span>
      <span class="node-label">{{ data.label || '输出' }}</span>
    </div>
    <div class="node-body">
      <span class="node-status" v-if="data.running">⏳ 运行中...</span>
      <span class="node-status done" v-else-if="data.done">✅ 完成</span>
      <span class="node-hint" v-else>等待输入</span>
    </div>
    <Handle type="target" :position="Position.Left" id="input" />
  </div>
</template>

<script setup>
import { Handle, Position } from '@vue-flow/core'

const props = defineProps({
  data: { type: Object, required: true }
})
</script>

<style scoped>
.output-node {
  background: #fffbeb;
  border: 2px solid #f59e0b;
  border-radius: 12px;
  padding: 10px 14px;
  min-width: 120px;
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s;
  outline: none;
  box-shadow: none;
}
.output-node:hover { box-shadow: 0 2px 12px rgba(245, 158, 11, 0.15); }
.output-node.selected { border-color: #d97706; box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.2); }
.output-node.running { border-color: #3b82f6; background: #eff6ff; }
.output-node.done { border-color: #22c55e; background: #f0fdf4; }
.node-header { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.node-icon { font-size: 1.2rem; }
.node-label { font-weight: 600; font-size: 0.85rem; color: #92400e; }
.output-node.running .node-label { color: #1e40af; }
.output-node.done .node-label { color: #166534; }
.node-body { display: flex; align-items: center; gap: 6px; }
.node-status { font-size: 0.7rem; color: #3b82f6; font-weight: 500; }
.node-status.done { color: #22c55e; }
.node-hint { font-size: 0.7rem; color: #666; }
</style>
