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

      <!-- 文件列表 -->
      <div v-if="data.files && data.files.length > 0" class="file-list">
        <div class="file-item" v-for="(file, idx) in data.files" :key="idx" :title="file.name">
          <span class="file-icon">📝</span>
          <span class="file-name">{{ truncateName(file.name) }}</span>
        </div>
        <div class="file-count" v-if="data.files.length > 3">
          +{{ data.files.length - 3 }} 个文件
        </div>
      </div>
    </div>
    <Handle type="target" :position="Position.Left" id="input" />
  </div>
</template>

<script setup>
import { Handle, Position } from '@vue-flow/core'

const props = defineProps({
  data: { type: Object, required: true }
})

function truncateName(name, maxLen = 12) {
  if (!name) return ''
  if (name.length <= maxLen) return name
  const ext = name.includes('.') ? name.slice(name.lastIndexOf('.')) : ''
  const base = name.slice(0, name.lastIndexOf('.'))
  return base.slice(0, maxLen - ext.length - 3) + '...' + ext
}
</script>

<style scoped>
.output-node {
  background: #fffbeb;
  border: 2px solid #f59e0b;
  border-radius: 12px;
  padding: 10px 14px;
  min-width: 140px;
  max-width: 180px;
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s;
  outline: none;
  box-shadow: none;
}
.output-node:hover { box-shadow: 0 2px 12px rgba(245, 158, 11, 0.15); }
.output-node.selected { border-color: #d97706; box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.2); }
.output-node.running { border-color: #3b82f6; background: #eff6ff; }
.output-node.done { border-color: #22c55e; background: #f0fdf4; }
.node-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.node-icon { font-size: 1.2rem; }
.node-label { font-weight: 600; font-size: 0.85rem; color: #92400e; }
.output-node.running .node-label { color: #1e40af; }
.output-node.done .node-label { color: #166534; }
.node-body { display: flex; flex-direction: column; gap: 6px; }
.node-status { font-size: 0.7rem; color: #3b82f6; font-weight: 500; }
.node-status.done { color: #22c55e; }
.node-hint { font-size: 0.7rem; color: #666; }

/* 文件列表样式 */
.file-list {
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px dashed #e5e7eb;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.file-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.7rem;
  color: #374151;
  background: rgba(255,255,255,0.6);
  padding: 3px 6px;
  border-radius: 4px;
  overflow: hidden;
}
.file-icon { font-size: 0.8rem; }
.file-name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.file-count {
  font-size: 0.65rem;
  color: #6b7280;
  text-align: center;
  padding: 2px 0;
}
</style>
