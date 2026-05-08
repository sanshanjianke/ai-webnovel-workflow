<template>
  <div class="container-node" :style="containerStyle">
    <div class="container-header">
      <span class="container-icon">{{ data.icon || '📦' }}</span>
      <span class="container-label">{{ data.name || '容器' }}</span>
      <div class="container-tags">
        <span v-if="data.concurrency === 'parallel'" class="tag tag-para">并行</span>
        <span v-if="data.speaking_mode === 'mention_driven'" class="tag tag-mention">@驱动</span>
        <span v-if="data.context_layers != null" class="tag tag-depth">{{ data.context_layers }}层</span>
        <span v-if="data.context_tokens != null" class="tag tag-depth">{{ (data.context_tokens / 1000).toFixed(0) }}K</span>
        <span v-if="(data.repeat || 1) > 1 && data.speaking_mode !== 'mention_driven'" class="tag tag-loop">{{ data.repeat }}轮</span>
      </div>
      <button class="container-resize" @mousedown.stop="startResize" title="拖拽调整大小">⟲</button>
    </div>
    <div
      class="container-body"
      :class="{ 'clickable-body': hasPendingExpert }"
      @click="onClickBody"
      :title="hasPendingExpert ? '点击添加选中的专家' : '先在左侧选择专家'"
    >
      <slot />
      <div v-if="experts.length === 0" class="container-empty-placeholder">
        <span>{{ hasPendingExpert ? '点击这里添加专家' : '在左侧选择专家后点击这里' }}</span>
      </div>
      <div v-else class="container-expert-cards">
        <div v-for="(expert, idx) in experts" :key="idx" class="expert-card">
          <span class="expert-card-num">{{ idx + 1 }}</span>
          <span class="expert-card-icon">{{ expert.icon || '📄' }}</span>
          <span class="expert-card-label">{{ expert.label }}</span>
          <span class="expert-card-role">{{ roleLabel(expert.role) }}</span>
          <button class="expert-card-remove" @click.stop="removeExpert(idx)" title="移除此专家">×</button>
        </div>
      </div>
    </div>
    <Handle type="target" :position="Position.Left" class="container-handle-in" />
    <Handle type="source" :position="Position.Right" class="container-handle-out" />
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { Handle, Position } from '@vue-flow/core'

const props = defineProps({
  data: { type: Object, required: true },
  selected: { type: Boolean }
})

const experts = computed(() => props.data.experts || [])
const hasPendingExpert = computed(() => !!(props.data._pendingExpert))

const defaultW = props.data.width || 500
const defaultH = props.data.height || 280
const width = ref(defaultW)
const height = ref(defaultH)

watch(experts, () => {
  const autoH = 180 + experts.value.length * 62
  if (experts.value.length > 0) {
    height.value = Math.max(defaultH, autoH)
    if (props.data.onResize) props.data.onResize({ width: width.value, height: height.value })
  }
}, { deep: true })

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

function onClickBody() {
  if (props.data.onClickBody) props.data.onClickBody()
}

function removeExpert(index) {
  if (props.data.onRemoveExpert) {
    props.data.onRemoveExpert(index)
  }
}

function roleLabel(role) {
  const labels = { main: '主导', review: '审核', supplement: '补充' }
  return labels[role] || role
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
.tag-mention { background: #e0f2f1; color: #00695c; }
.tag-depth { background: #ede7f6; color: #4527a0; }
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

/* 拖放目标区域 */
.container-body {
  min-height: 60px;
  padding: 8px;
  position: relative;
  transition: background 0.2s, box-shadow 0.2s;
  border-radius: 0 0 10px 10px;
}
.container-body.clickable-body {
  cursor: pointer;
  background: rgba(52, 152, 219, 0.04);
  box-shadow: inset 0 0 0 2px rgba(52, 152, 219, 0.25);
}
.container-body.clickable-body:hover {
  background: rgba(52, 152, 219, 0.1);
  box-shadow: inset 0 0 0 2px #3498db;
}

/* 空状态 */
.container-empty-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 60px;
  color: rgba(0, 0, 0, 0.12);
  font-size: 0.85rem;
  user-select: none;
  pointer-events: none;
}

/* 专家卡片垂直排列 */
.container-expert-cards {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 4px 0;
}
.expert-card {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid #e8e0f0;
  border-radius: 8px;
  font-size: 0.8rem;
  transition: box-shadow 0.15s;
}
.expert-card:hover {
  box-shadow: 0 2px 8px rgba(155, 89, 182, 0.12);
}
.expert-card-num {
  background: #9b59b6;
  color: white;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.7rem;
  font-weight: 700;
  flex-shrink: 0;
}
.expert-card-icon {
  font-size: 1rem;
  flex-shrink: 0;
}
.expert-card-label {
  font-weight: 600;
  color: #333;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.expert-card-role {
  font-size: 0.65rem;
  color: #888;
  background: #f5f5f5;
  padding: 1px 6px;
  border-radius: 4px;
  flex-shrink: 0;
}
.expert-card-remove {
  width: 20px;
  height: 20px;
  border: none;
  background: transparent;
  cursor: pointer;
  color: #bbb;
  font-size: 1rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.15s;
}
.expert-card-remove:hover {
  background: #fee;
  color: #e74c3c;
}

/* handles */
.container-handle-in { width: 10px; height: 10px; background: #9b59b6; border: 2px solid white; }
.container-handle-out { width: 10px; height: 10px; background: #9b59b6; border: 2px solid white; }
</style>
