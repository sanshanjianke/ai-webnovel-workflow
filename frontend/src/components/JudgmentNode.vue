<template>
  <div class="judgment-node" :class="{ selected: data.selected, running: data.running, done: data.done, rejected: data.verdict === 'reject' }">
    <Handle type="target" :position="Position.Left" id="input" />
    <div class="node-header">
      <span class="node-icon">⚖️</span>
      <span class="node-label">{{ data.label || '判断' }}</span>
    </div>
    <div class="node-body">
      <span class="node-status" v-if="data.running">⏳ 审核中...</span>
      <span class="node-status pass" v-else-if="data.done && data.verdict === 'pass'">✅ 通过</span>
      <span class="node-status reject" v-else-if="data.done && data.verdict === 'reject'">❌ 打回</span>
      <span class="node-hint" v-else>等待输入</span>
      <div class="node-meta" v-if="data.maxRejects !== undefined">
        <span class="meta-label">最大打回: {{ data.maxRejects }}次</span>
      </div>
      <div class="node-meta" v-if="data.reason">
        <span class="meta-reason" :title="data.reason">{{ truncate(data.reason, 40) }}</span>
      </div>
    </div>
    <Handle type="source" :position="Position.Right" id="pass" class="handle-pass" />
    <Handle type="source" :position="Position.Bottom" id="reject" class="handle-reject" />
  </div>
</template>

<script setup>
import { Handle, Position } from '@vue-flow/core'

defineProps({
  data: { type: Object, required: true }
})

function truncate(text, maxLen) {
  if (!text) return ''
  return text.length <= maxLen ? text : text.slice(0, maxLen) + '...'
}
</script>

<style scoped>
.judgment-node {
  background: #fefce8;
  border: 2px solid #a16207;
  border-radius: 8px;
  border-top: 4px solid #a16207;
  padding: 10px 14px;
  min-width: 140px;
  max-width: 200px;
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s;
  outline: none;
}
.judgment-node::before {
  content: '';
  position: absolute;
  top: 4px; left: 50%;
  transform: translateX(-50%) rotate(45deg);
  width: 10px; height: 10px;
  background: #a16207;
  border-radius: 2px;
}
.judgment-node:hover { box-shadow: 0 2px 12px rgba(161, 98, 7, 0.2); }
.judgment-node.selected { border-color: #854d0e; box-shadow: 0 0 0 2px rgba(161, 98, 7, 0.25); }
.judgment-node.running { border-color: #3b82f6; border-top-color: #3b82f6; background: #eff6ff; }
.judgment-node.running::before { background: #3b82f6; }
.judgment-node.done { border-color: #22c55e; border-top-color: #22c55e; background: #f0fdf4; }
.judgment-node.done::before { background: #22c55e; }
.judgment-node.rejected { border-color: #ef4444; border-top-color: #ef4444; background: #fef2f2; }
.judgment-node.rejected::before { background: #ef4444; }
.node-header { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; margin-top: 4px; }
.node-icon { font-size: 1.2rem; }
.node-label { font-weight: 600; font-size: 0.8rem; color: #713f12; }
.judgment-node.running .node-label { color: #1e40af; }
.judgment-node.done .node-label { color: #166534; }
.judgment-node.rejected .node-label { color: #991b1b; }
.node-body { display: flex; flex-direction: column; gap: 4px; }
.node-status { font-size: 0.7rem; color: #a16207; font-weight: 500; }
.node-status.pass { color: #22c55e; }
.node-status.reject { color: #ef4444; }
.node-hint { font-size: 0.65rem; color: #888; }
.node-meta { margin-top: 2px; }
.meta-label { font-size: 0.6rem; color: #888; }
.meta-reason { font-size: 0.65rem; color: #6b7280; display: block; }

.handle-pass { background: #22c55e !important; border-color: #16a34a !important; }
.handle-reject { background: #ef4444 !important; border-color: #dc2626 !important; }
</style>
