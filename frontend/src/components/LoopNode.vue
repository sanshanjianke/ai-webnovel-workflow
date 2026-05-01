<template>
  <div class="loop-node" :style="loopStyle">
    <div class="loop-header">
      <span class="loop-icon">🔁</span>
      <span class="loop-label">循环 {{ data.count || 3 }} 次</span>
      <span class="loop-info">发言次数 ×{{ data.count || 3 }}</span>
    </div>
    <div class="loop-body">
      <slot />
      <div v-if="children.length === 0" class="loop-empty">拖拽专家到这里</div>
      <div v-else class="loop-children-list">
        <span v-for="(child, idx) in children" :key="idx" class="loop-child-tag">{{ child }}</span>
      </div>
    </div>
    <div class="loop-footer">
      <span>↻ 重复 {{ data.count || 3 }} 次后退出</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  data: { type: Object, required: true },
  selected: { type: Boolean }
})

const children = computed(() => props.data.children || [])
const loopStyle = computed(() => ({
  width: `${props.data.width || 500}px`,
  minHeight: `${props.data.height || 240}px`,
  borderColor: props.selected ? '#27ae60' : '#8bc34a'
}))
</script>

<style scoped>
.loop-node {
  border: 2px solid #8bc34a;
  border-radius: 16px;
  position: relative;
  padding-top: 32px;
  padding-bottom: 24px;
  background: rgba(232, 245, 233, 0.3);
}
.loop-header {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 32px;
  background: rgba(139, 195, 74, 0.15);
  border-radius: 14px 14px 0 0;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 14px;
  font-size: 0.8rem;
  border-bottom: 1px solid #c8e6c9;
}
.loop-icon { font-size: 1rem; }
.loop-label { font-weight: 700; color: #2e7d32; }
.loop-info { color: #888; font-size: 0.7rem; margin-left: auto; }
.loop-body {
  min-height: 60px;
  padding: 10px;
  position: relative;
}
.loop-empty {
  color: rgba(0,0,0,0.10);
  font-size: 0.8rem;
  text-align: center;
  padding: 20px;
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  pointer-events: none;
  user-select: none;
}
.loop-children-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding: 4px;
  position: absolute;
  bottom: 6px;
  left: 8px;
  right: 8px;
  pointer-events: none;
  user-select: none;
}
.loop-child-tag {
  font-size: 0.7rem;
  color: rgba(46, 125, 50, 0.25);
  background: rgba(46, 125, 50, 0.05);
  padding: 2px 8px;
  border-radius: 10px;
  white-space: nowrap;
}
.loop-footer {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 24px;
  background: rgba(139, 195, 74, 0.1);
  border-radius: 0 0 14px 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.65rem;
  color: #999;
  border-top: 1px solid #e8f5e9;
}
</style>
