<template>
  <table v-if="docs.length > 0" class="doc-table">
    <thead><tr><th>ID</th><th>内容</th><th>标签</th><th>操作</th></tr></thead>
    <tbody>
      <tr v-for="doc in docs" :key="doc.id">
        <td>{{ doc.id }}</td>
        <td class="content-cell">{{ (doc.content || '').slice(0, 120) }}{{ (doc.content || '').length > 120 ? '...' : '' }}</td>
        <td>{{ (doc.metadata?.tags || []).join(', ') }}</td>
        <td><button class="btn btn-sm" @click="$emit('delete', doc.id)">✕</button></td>
      </tr>
    </tbody>
  </table>
  <p v-else class="hint">暂无索引文档</p>
</template>

<script setup>
defineProps({ docs: { type: Array, default: () => [] } })
defineEmits(['delete'])
</script>

<style scoped>
.doc-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.doc-table th { text-align: left; padding: 6px 8px; border-bottom: 2px solid #eee; background: #fafafa; }
.doc-table td { padding: 6px 8px; border-bottom: 1px solid #f0f0f0; }
.content-cell { max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.btn { padding: 6px 14px; border: 1px solid #ddd; border-radius: 6px; background: #fff; cursor: pointer; font-size: 13px; }
.btn-sm { padding: 4px 10px; font-size: 12px; }
.hint { color: #999; font-size: 13px; }
</style>
