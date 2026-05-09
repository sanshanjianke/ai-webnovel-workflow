<template>
  <div
    class="tag-library"
    :class="{ collapsed: isCollapsed }"
    :style="{ width: isCollapsed ? '40px' : '220px' }"
  >
    <div class="taglib-header">
      <span v-if="!isCollapsed" class="taglib-title">标签库</span>
      <button class="btn-toggle" @click="toggleCollapse">
        {{ isCollapsed ? '◀' : '▶' }}
      </button>
    </div>

    <div v-if="!isCollapsed" class="taglib-body">
      <!-- 搜索 -->
      <div class="taglib-search">
        <input
          v-model="searchQuery"
          type="text"
          class="search-input"
          placeholder="搜索标签..."
        />
      </div>

      <!-- 流派过滤 -->
      <div class="taglib-filter">
        <select v-model="genreFilter" class="filter-select">
          <option value="">全部流派</option>
          <option v-for="g in allGenres" :key="g" :value="g">{{ g }}</option>
        </select>
      </div>

      <!-- 分类树 -->
      <div class="taglib-tree">
        <div v-for="cat in filteredCategories" :key="cat.name" class="tag-category">
          <div class="category-header" @click="toggleCategory(cat.name)">
            <span class="category-icon">{{ expandedCats.has(cat.name) ? '▼' : '▶' }}</span>
            <span class="category-label">{{ cat.label }}</span>
            <span class="category-count">{{ cat.tags.length }}</span>
          </div>
          <div v-if="expandedCats.has(cat.name)" class="category-tags">
            <div
              v-for="tag in cat.tags"
              :key="tag.tagId"
              class="tag-item"
              :class="{ selected: selectedTag?.tagId === tag.tagId }"
              :style="{ borderLeftColor: categoryColor(cat.name) }"
              @click="selectTag(tag)"
              draggable="true"
              @dragstart="onDragStart($event, tag)"
            >
              <span class="tag-item-label">{{ tag.效果标签 || tag.tagId }}</span>
              <span class="tag-usage" v-if="tag.usageCount">{{ tag.usageCount }}</span>
            </div>
            <div v-if="cat.tags.length === 0" class="empty-cat">暂无标签</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 标签详情弹窗 -->
    <div v-if="tagDetail" class="tag-detail-overlay" @click.self="tagDetail = null">
      <div class="tag-detail-card">
        <div class="detail-header">
          <span class="detail-title">{{ tagDetail.效果标签 || tagDetail.tagId }}</span>
          <button class="btn-close" @click="tagDetail = null">✕</button>
        </div>
        <div class="detail-body">
          <div class="detail-row">
            <span class="detail-label">分类</span>
            <span class="detail-value">{{ tagDetail.category }}</span>
          </div>
          <div class="detail-row" v-if="tagDetail.genre?.length">
            <span class="detail-label">适用流派</span>
            <span class="detail-value">{{ tagDetail.genre.join('、') }}</span>
          </div>
          <div class="detail-row" v-if="tagDetail.叙事指令">
            <span class="detail-label">叙事指令</span>
            <div class="detail-narrative">
              <div v-if="tagDetail.叙事指令.视角">视角：{{ tagDetail.叙事指令.视角 }}</div>
              <div v-if="tagDetail.叙事指令.节奏">节奏：{{ tagDetail.叙事指令.节奏 }}</div>
              <div v-if="tagDetail.叙事指令.话语模式">话语模式：{{ tagDetail.叙事指令.话语模式 }}</div>
            </div>
          </div>
          <div class="detail-row" v-if="tagDetail.理由">
            <span class="detail-label">理由</span>
            <span class="detail-value">{{ tagDetail.理由 }}</span>
          </div>
          <div class="detail-row" v-if="tagDetail.关联网文概念?.length">
            <span class="detail-label">关联概念</span>
            <span class="detail-value">{{ tagDetail.关联网文概念.join('、') }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const isCollapsed = ref(false)
defineExpose({ isCollapsed })
const searchQuery = ref('')
const genreFilter = ref('')
const expandedCats = ref(new Set(['情节', '人物', '叙事', '爽点']))
const selectedTag = ref(null)
const tagDetail = ref(null)
const allTags = ref([])

const categoryMeta = {
  '情节': { label: '情节', icon: '📖' },
  '人物': { label: '人物', icon: '🎭' },
  '叙事': { label: '叙事', icon: '👁' },
  '爽点': { label: '爽点', icon: '⚡' }
}

const categoryColor = (cat) => {
  const colors = { '情节': '#3498db', '人物': '#2ecc71', '叙事': '#9b59b6', '爽点': '#e67e22' }
  return colors[cat] || '#999'
}

const allGenres = computed(() => {
  const genres = new Set()
  for (const t of allTags.value) {
    if (t.genre) for (const g of t.genre) genres.add(g)
  }
  return [...genres].sort()
})

const filteredCategories = computed(() => {
  const q = searchQuery.value.toLowerCase()
  const gf = genreFilter.value
  const cats = {}
  for (const cat of Object.keys(categoryMeta)) {
    cats[cat] = []
  }
  for (const tag of allTags.value) {
    const cat = tag.category
    if (!cats[cat]) cats[cat] = []
    // genre filter
    if (gf && (!tag.genre || !tag.genre.includes(gf))) continue
    // search filter
    if (q) {
      const haystack = [
        tag.tagId, tag.效果标签, tag.理由,
        ...(tag.关联网文概念 || [])
      ].join(' ').toLowerCase()
      if (!haystack.includes(q)) continue
    }
    cats[cat].push(tag)
  }
  return Object.entries(cats).map(([name, tags]) => ({
    name,
    label: categoryMeta[name]?.label || name,
    tags
  }))
})

function toggleCollapse() {
  isCollapsed.value = !isCollapsed.value
}

function toggleCategory(name) {
  const s = new Set(expandedCats.value)
  if (s.has(name)) s.delete(name)
  else s.add(name)
  expandedCats.value = s
}

function selectTag(tag) {
  selectedTag.value = tag
  tagDetail.value = tag
}

function onDragStart(event, tag) {
  event.dataTransfer.setData('application/tag', JSON.stringify(tag))
  event.dataTransfer.effectAllowed = 'copy'
}

async function fetchTags() {
  try {
    const res = await axios.get('/api/tags')
    allTags.value = res.data.tags || []
  } catch (err) {
    // 加载内置默认数据
    allTags.value = getDefaultTags()
  }
}

function getDefaultTags() {
  return [
    { tagId: '功能:转折', category: '情节', genre: ['无限流', '系统文'], '效果标签': '功能标签-转折', '叙事指令': { '视角': '全知视角（概述）', '节奏': '快速叙事（概叙）', '话语模式': '叙述者话语主导' }, '理由': '功能性序列标注', '关联网文概念': ['起承转合', '情节点'] },
    { tagId: '序列:高潮', category: '情节', genre: ['无限流', '穿越流'], '效果标签': '序列-高潮', '叙事指令': { '视角': '内聚焦（主角视角）', '节奏': '慢速叙事（场景）', '话语模式': '多种话语混合' }, '理由': '情绪集中释放点', '关联网文概念': ['高潮', '爽点密度'] },
    { tagId: '行动元:对手', category: '人物', genre: [], '效果标签': '行动元标签-对手', '叙事指令': { '视角': '外聚焦（行为描写）', '节奏': '中速', '话语模式': '对话+动作' }, '理由': '明确对手行动元', '关联网文概念': ['对立关系', '冲突动力'] },
    { tagId: '原型:导师', category: '人物', genre: ['穿越流', '重生流'], '效果标签': '原型-导师', '叙事指令': { '视角': '全知视角', '节奏': '慢速（场景）', '话语模式': '叙述者话语+对话' }, '理由': '导师角色出场', '关联网文概念': ['导师原型', '知识传递'] },
    { tagId: '视角:内聚焦', category: '叙事', genre: [], '效果标签': '视角-内聚焦', '叙事指令': { '视角': '内聚焦（主角视角）', '节奏': '中速', '话语模式': '叙述者话语+自由间接引语' }, '理由': '读者代入主角', '关联网文概念': ['内聚焦', '代入感'] },
    { tagId: '节奏:加速', category: '叙事', genre: [], '效果标签': '节奏-加速', '叙事指令': { '视角': '全知视角', '节奏': '快速叙事（概叙）', '话语模式': '叙述者话语主导' }, '理由': '过渡段落', '关联网文概念': ['节奏控制', '叙事速度'] },
    { tagId: '装逼打脸:压抑', category: '爽点', genre: ['无限流', '系统文'], '效果标签': '装逼打脸-压抑阶段', '叙事指令': { '视角': '内聚焦（反派/路人）', '节奏': '慢速叙事（场景）', '话语模式': '大量对话+环境描写' }, '理由': '通过无知者视角制造信息差', '关联网文概念': ['欲扬先抑', '期待感悬置', '信息差'] },
    { tagId: '期待感:钩子', category: '爽点', genre: [], '效果标签': '期待感-钩子', '叙事指令': { '视角': '内聚焦（主角）', '节奏': '中速', '话语模式': '叙述者话语+自由间接引语' }, '理由': '章末悬念', '关联网文概念': ['期待感', '章末钩子'] }
  ]
}

onMounted(() => {
  fetchTags()
})
</script>

<style scoped>
.tag-library {
  display: flex;
  flex-direction: column;
  background: #fafafa;
  border-left: 1px solid #e0e0e0;
  height: 100%;
  transition: width 0.2s;
  flex-shrink: 0;
  overflow: hidden;
}
.tag-library.collapsed {
  height: auto;
}

.taglib-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border-bottom: 1px solid #e0e0e0;
  background: white;
  flex-shrink: 0;
}

.taglib-title {
  font-size: 0.8rem;
  font-weight: 600;
  color: #555;
}

.btn-toggle {
  width: 24px;
  height: 24px;
  border: none;
  background: #f0f0f0;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.7rem;
  color: #666;
  display: flex;
  align-items: center;
  justify-content: center;
}

.taglib-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.taglib-search {
  padding: 6px 8px;
  flex-shrink: 0;
}

.search-input {
  width: 100%;
  padding: 4px 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 0.75rem;
  outline: none;
  box-sizing: border-box;
}

.search-input:focus {
  border-color: #3498db;
}

.taglib-filter {
  padding: 0 8px 6px;
  flex-shrink: 0;
}

.filter-select {
  width: 100%;
  padding: 3px 6px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 0.72rem;
  background: white;
  outline: none;
}

.taglib-tree {
  flex: 1;
  overflow-y: auto;
  padding: 0 4px 8px;
}

.tag-category {
  margin-bottom: 2px;
}

.category-header {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 5px 6px;
  cursor: pointer;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
  color: #555;
}

.category-header:hover {
  background: #f0f0f0;
}

.category-icon {
  font-size: 0.6rem;
  width: 12px;
}

.category-label {
  flex: 1;
}

.category-count {
  font-size: 0.65rem;
  color: #999;
  background: #eee;
  padding: 0 5px;
  border-radius: 8px;
}

.category-tags {
  padding-left: 14px;
}

.tag-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 3px 8px;
  border-left: 3px solid #ccc;
  margin: 1px 0;
  border-radius: 0 4px 4px 0;
  cursor: pointer;
  font-size: 0.72rem;
  background: white;
}

.tag-item:hover {
  background: #e8f4fd;
}

.tag-item.selected {
  background: #d4e9f7;
}

.tag-item-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tag-usage {
  font-size: 0.62rem;
  color: #999;
  margin-left: 4px;
}

.empty-cat {
  font-size: 0.7rem;
  color: #ccc;
  padding: 4px 8px;
  font-style: italic;
}

/* 标签详情弹窗 */
.tag-detail-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  z-index: 500;
  display: flex;
  align-items: center;
  justify-content: center;
}

.tag-detail-card {
  background: white;
  border-radius: 8px;
  width: 360px;
  max-height: 60vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
}

.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid #e0e0e0;
}

.detail-title {
  font-size: 0.9rem;
  font-weight: 600;
}

.btn-close {
  border: none;
  background: none;
  font-size: 1rem;
  cursor: pointer;
  color: #999;
}

.detail-body {
  padding: 12px 16px;
  overflow-y: auto;
  font-size: 0.8rem;
  line-height: 1.6;
}

.detail-row {
  margin-bottom: 10px;
}

.detail-label {
  font-size: 0.7rem;
  color: #999;
  display: block;
  margin-bottom: 2px;
}

.detail-value {
  color: #333;
}

.detail-narrative {
  background: #f8f9fa;
  padding: 6px 10px;
  border-radius: 4px;
  font-size: 0.75rem;
  color: #555;
  line-height: 1.5;
}
</style>
