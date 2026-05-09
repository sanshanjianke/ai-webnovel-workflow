<template>
  <div class="rag-icon-node" :class="{ selected: selected }">
    <div class="rag-icon-header">
      <span class="rag-icon">🔍</span>
      <span class="rag-label">{{ data.label || 'RAG' }}</span>
      <span class="observer-badge" title="检索节点">📚</span>
    </div>
    <div class="rag-icon-body">
      <span class="rag-target">{{ data.targetInstance || '默认实例' }}</span>
    </div>
    <div class="rag-icon-footer">
      <span class="rag-hint">双击打开管理页</span>
    </div>
  </div>
</template>

<script setup>
defineProps({
  data: { type: Object, required: true },
  selected: { type: Boolean, default: false }
})
</script>

<style scoped>
.rag-icon-node {
  background: rgba(255, 248, 240, 0.5);
  border: 2px dashed #e67e22;
  border-radius: 12px;
  padding: 8px 14px;
  min-width: 150px;
  font-size: 13px;
  cursor: pointer;
}
.rag-icon-node.selected { border-color: #3498db; box-shadow: 0 0 0 2px rgba(52,152,219,0.3); }
.rag-icon-node:hover { border-color: #d35400; }
.rag-icon-header { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
.rag-icon { font-size: 18px; }
.rag-label { font-weight: 600; color: #2c3e50; flex: 1; }
.observer-badge { font-size: 12px; opacity: 0.7; }
.rag-icon-body { padding: 2px 0; }
.rag-target { color: #7f8c8d; font-size: 11px; }
.rag-icon-footer { margin-top: 4px; padding-top: 4px; border-top: 1px dashed #ddd; }
.rag-hint { color: #bdc3c7; font-size: 10px; }
</style>
