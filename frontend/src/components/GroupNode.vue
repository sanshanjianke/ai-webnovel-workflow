<template>
  <div class="container-node" :style="containerStyle">
    <div class="container-header">
      <span class="container-icon">{{ data.icon || '📦' }}</span>
      <span class="container-label">{{ data.name || '容器' }}</span>
      <div class="container-tags">
        <span v-if="data.chat_mode === 'group'" class="tag tag-chat">群聊</span>
        <span v-if="data.concurrency === 'parallel'" class="tag tag-para">并行</span>
        <span v-if="(data.repeat || 1) > 1" class="tag tag-loop">{{ data.repeat }}轮</span>
        <span v-if="data.summarizer !== 'off'" class="tag tag-sum">总结</span>
      </div>
      <button class="container-resize" @mousedown.stop="startResize" title="拖拽调整大小">⟲</button>
    </div>
    <div class="container-body">
      <slot />
      <div v-if="children.length === 0" class="container-empty">拖拽专家到这里</div>
      <div v-else class="container-children-list">
        <span v-for="(child, idx) in children" :key="idx" class="container-child-tag">{{ child }}</span>
      </div>
    </div>
    <Handle type="target" :position="Position.Left" class="container-handle-in" />
    <Handle type="source" :position="Position.Right" class="container-handle-out" />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'

const props = defineProps({
  data: { type: Object, required: true },
  selected: { type: Boolean }
})

const children = computed(() => props.data.children || [])
const width = ref(props.data.width || 500)
const height = ref(props.data.height || 280)

const containerStyle = computed(() => ({
  width: `${width.value}px`,
  minHeight: `${height.value}px`,
  borderColor: props.selected ? '#3498db' : (props.data.borderColor || '#9b59b6'),
  background: props.data.background || 'rgba(240, 240, 255, 0.3)'
}))

function startResize(e) {
  const startX = e.clientX
  const startY = e.clientY
  const startW = width.value
  const startH = height.value

  function onMove(ev) {
    width.value = Math.max(300, startW + (ev.clientX - startX))
    height.value = Math.max(150, startH + (ev.clientY - startY))
    if (props.data.onResize) props.data.onResize({ width: width.value, height: height.value })
  }
  function onUp() {
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
  }
  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
}
</script>

<style scoped>
.container-node {
  border: 2px dashed #9b59b6;
  border-radius: 12px;
  position: relative;
  padding-top: 32px;
}
.container-header {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 32px;
  background: rgba(240, 240, 255, 0.95);
  border-radius: 10px 10px 0 0;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 10px;
  font-size: 0.75rem;
  color: #555;
  border-bottom: 1px solid #e0d8f0;
}
.container-icon { font-size: 0.9rem; }
.container-label { font-weight: 700; color: #7b1fa2; }
.container-tags { display: flex; gap: 3px; margin-left: 4px; }
.tag {
  font-size: 0.6rem;
  padding: 1px 5px;
  border-radius: 8px;
  white-space: nowrap;
}
.tag-chat { background: #e8f5e9; color: #2e7d32; }
.tag-para { background: #fff3e0; color: #e65100; }
.tag-loop { background: #e3f2fd; color: #1565c0; }
.tag-sum { background: #fce4ec; color: #c62828; }
.container-resize {
  position: absolute;
  right: 2px;
  background: none;
  border: none;
  cursor: se-resize;
  font-size: 0.8rem;
  color: #bbb;
  padding: 2px 4px;
}
.container-resize:hover { color: #888; }
.container-body {
  min-height: 60px;
  padding: 8px;
  position: relative;
}
.container-empty {
  color: rgba(0,0,0,0.08);
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
.container-children-list {
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
.container-child-tag {
  font-size: 0.7rem;
  color: rgba(0,0,0,0.18);
  background: rgba(0,0,0,0.03);
  padding: 2px 8px;
  border-radius: 10px;
  white-space: nowrap;
}
.container-handle-in { width: 10px; height: 10px; background: #9b59b6; border: 2px solid white; }
.container-handle-out { width: 10px; height: 10px; background: #9b59b6; border: 2px solid white; }
</style>
