<template>
  <div class="expert-node" :class="`expert-${data.role}`">
    <div class="node-header">
      <span class="node-icon">{{ icon }}</span>
      <span class="node-label">{{ data.label }}</span>
    </div>
    <div class="node-body">
      <span class="node-role">{{ roleLabel }}</span>
    </div>
    <Handle type="target" :position="Position.Left" />
    <Handle type="source" :position="Position.Right" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'

const props = defineProps({
  data: { type: Object, required: true }
})

const icons = {
  '资深作者': '📕',
  '读者代表': '📙',
  '剧情架构师': '🏛',
  '人物设计师': '🎭',
  '网络编辑': '💼'
}

const icon = computed(() => icons[props.data.label] || '📄')

const roleLabels = {
  main: '主导',
  review: '审核',
  supplement: '补充'
}

const roleLabel = computed(() => roleLabels[props.data.role] || props.data.role)
</script>

<style scoped>
.expert-node {
  background: white;
  border: 2px solid #e0e0e0;
  border-radius: 12px;
  padding: 10px 14px;
  min-width: 140px;
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.expert-node:hover {
  border-color: #3498db;
  box-shadow: 0 2px 12px rgba(52, 152, 219, 0.15);
}
.expert-node.expert-main { border-left: 4px solid #e74c3c; }
.expert-node.expert-review { border-left: 4px solid #f39c12; }
.expert-node.expert-supplement { border-left: 4px solid #3498db; }

.node-header {
  display: flex;
  align-items: center;
  gap: 6px;
}
.node-icon { font-size: 1.1rem; }
.node-label {
  font-weight: 600;
  font-size: 0.9rem;
  color: #333;
}
.node-body { margin-top: 4px; }
.node-role {
  font-size: 0.75rem;
  color: #888;
  background: #f5f5f5;
  padding: 2px 8px;
  border-radius: 4px;
}
</style>
