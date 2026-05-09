<template>
  <div class="worldbook-node" :class="{ selected: data.selected }">
    <div class="node-header">
      <span class="node-icon">📖</span>
      <span class="node-label">{{ data.label || '世界书' }}</span>
    </div>
    <div class="node-body">
      <span class="node-book-name">{{ data.bookName || '未命名' }}</span>
      <span class="node-count" v-if="entryCount > 0">{{ entryCount }} 条</span>
      <span class="node-count empty" v-else>空</span>
    </div>
    <Handle type="target" :position="Position.Left" />
    <Handle type="source" :position="Position.Right" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'

const props = defineProps({
  data: { type: Object, required: true },
  selected: { type: Boolean, default: false }
})

const entryCount = computed(() => props.data.entryCount || 0)
</script>

<style scoped>
.worldbook-node {
  background: #f0fdfa;
  border: 2px solid #0ea5e9;
  border-radius: 12px;
  padding: 10px 14px;
  min-width: 140px;
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.worldbook-node:hover {
  border-color: #0284c7;
  box-shadow: 0 2px 12px rgba(14, 165, 233, 0.2);
}
.worldbook-node.selected {
  border-color: #0284c7;
  box-shadow: 0 0 0 2px rgba(14, 165, 233, 0.3);
}
.node-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.node-icon { font-size: 1.2rem; }
.node-label {
  font-weight: 600;
  font-size: 0.85rem;
  color: #0c4a6e;
}
.node-body {
  display: flex;
  align-items: center;
  gap: 8px;
}
.node-book-name {
  font-size: 0.75rem;
  color: #555;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.node-count {
  background: #0ea5e9;
  color: white;
  border-radius: 10px;
  padding: 0 6px;
  font-size: 0.65rem;
  font-weight: 600;
}
.node-count.empty {
  background: #ccc;
}
</style>
