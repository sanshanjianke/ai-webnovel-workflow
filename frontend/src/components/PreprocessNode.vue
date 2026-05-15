<template>
  <div class="preprocess-node" :class="{ selected: data.selected }">
    <div class="node-header">
      <span class="node-icon">✂️</span>
      <span class="node-label">{{ data.label || '预处理' }}</span>
      <span class="node-count" v-if="stageCount > 0">{{ stageCount }}</span>
    </div>
    <div class="node-body">
      <span class="node-hint">{{ hintText }}</span>
    </div>
    <Handle type="target" :position="Position.Left" id="input" />
    <Handle type="source" :position="Position.Right" id="output" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'

const props = defineProps({
  data: { type: Object, required: true }
})

const stageCount = computed(() => {
  const stages = props.data.preprocessConfig?.stages
  return stages ? stages.filter(s => s.enabled !== false).length : 0
})

const hintText = computed(() => {
  const mode = props.data.preprocessConfig?.outputMode
  const modeLabel = mode === 'pack' ? '归并' : '分流'
  return stageCount.value > 0 ? `${stageCount.value} 阶段 · ${modeLabel}` : '空管线'
})
</script>

<style scoped>
.preprocess-node {
  background: #fff7ed;
  border: 2px solid #f97316;
  border-radius: 12px;
  padding: 10px 14px;
  min-width: 130px;
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.preprocess-node:hover { box-shadow: 0 2px 12px rgba(249, 115, 22, 0.15); }
.preprocess-node.selected { border-color: #ea580c; box-shadow: 0 0 0 2px rgba(249, 115, 22, 0.2); }
.node-header { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.node-icon { font-size: 1.2rem; }
.node-label { font-weight: 600; font-size: 0.85rem; color: #9a3412; }
.node-count { background: #f97316; color: white; border-radius: 10px; padding: 0 6px; font-size: 0.65rem; font-weight: 600; }
.node-body { display: flex; align-items: center; gap: 6px; }
.node-hint { font-size: 0.7rem; color: #666; }
</style>
