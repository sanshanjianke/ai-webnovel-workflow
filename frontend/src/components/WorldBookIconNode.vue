<template>
  <div class="worldbook-icon-node" :class="{ selected: selected }">
    <div class="wb-icon-header">
      <span class="wb-icon">📖</span>
      <span class="wb-label">{{ data.label || '世界书管理员' }}</span>
      <span class="observer-badge" title="观察者模式 — 不参与数据流">👁</span>
    </div>
    <div class="wb-icon-body">
      <span class="wb-target-book">{{ data.targetBookName || '默认世界书' }}</span>
    </div>
    <div class="wb-icon-footer">
      <span class="wb-hint">双击打开管理窗</span>
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
.worldbook-icon-node {
  background: rgba(240, 240, 255, 0.5);
  border: 2px dashed #9b59b6;
  border-radius: 12px;
  padding: 8px 14px;
  min-width: 160px;
  font-size: 13px;
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.worldbook-icon-node.selected {
  border-color: #3498db;
  box-shadow: 0 0 0 2px rgba(52, 152, 219, 0.3);
}
.worldbook-icon-node:hover {
  border-color: #8e44ad;
}
.wb-icon-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}
.wb-icon {
  font-size: 18px;
}
.wb-label {
  font-weight: 600;
  color: #2c3e50;
  flex: 1;
}
.observer-badge {
  font-size: 12px;
  opacity: 0.7;
}
.wb-icon-body {
  padding: 2px 0;
}
.wb-target-book {
  color: #7f8c8d;
  font-size: 11px;
}
.wb-icon-footer {
  margin-top: 4px;
  padding-top: 4px;
  border-top: 1px dashed #ddd;
}
.wb-hint {
  color: #bdc3c7;
  font-size: 10px;
}
</style>
