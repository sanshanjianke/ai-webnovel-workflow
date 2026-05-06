<template>
  <div class="round-card" :class="{ streaming: round.streaming }">
    <div class="round-header">
      <span v-if="round.speakerName" class="speaker-icon">{{ round.speakerIcon || '📄' }}</span>
      <span class="round-label">
        <template v-if="round.isGroupChat && round.speakerName">{{ round.speakerName }}</template>
        <template v-else>🔄 第{{ round.round }}轮</template>
      </span>
      <span class="round-time">{{ formatTime(round.startedAt) }}</span>
      <span v-if="round.streaming" class="streaming-badge">流式中...</span>
    </div>

    <div v-for="(msg, mIdx) in round.messages" :key="mIdx">
      <!-- 用户消息气泡 -->
      <div v-if="msg.role === 'user'" class="user-bubble">
        <span class="user-label">💬 用户</span>
        <span class="msg-time">{{ formatTime(msg.timestamp) }}</span>
        <div class="user-content">{{ msg.content }}</div>
      </div>

      <!-- 系统消息（自审视提示词，隐藏） -->
      <div v-else-if="msg.role === 'system'" class="system-msg">
        <details class="system-details">
          <summary>📋 系统提示词</summary>
          <pre class="system-text">{{ msg.content }}</pre>
        </details>
      </div>

      <!-- AI 消息 -->
      <div v-else-if="msg.role === 'assistant'" class="assistant-msg">
        <details v-if="msg.thinking" class="thinking-block" :open="round.streaming">
          <summary>
            💭 思考过程
            <span v-if="round.streaming && !msg.content" class="thinking-indicator">...</span>
          </summary>
          <pre class="thinking-text">{{ msg.thinking }}</pre>
        </details>
        <div class="content-area" v-if="msg.content">
          <div class="content-label">📝 产出</div>
          <div class="content-text" v-html="renderMarkdown(msg.content)"></div>
        </div>
        <div v-if="round.streaming && !msg.content" class="streaming-cursor">▊</div>
      </div>
    </div>

    <div v-if="round.selfScore !== undefined" class="self-score">
      📊 自评: {{ round.selfScore }}/10
    </div>
  </div>
</template>

<script setup>
import MarkdownIt from 'markdown-it'

const md = new MarkdownIt()

const props = defineProps({
  round: {
    type: Object,
    required: true
    // { round, messages: [{ role, content, thinking, timestamp }], selfScore, streaming, startedAt }
  }
})

function formatTime(ts) {
  return ts ? new Date(ts).toLocaleTimeString('zh-CN') : ''
}

function renderMarkdown(text) {
  return text ? md.render(text) : ''
}
</script>

<style scoped>
.round-card {
  background: white;
  border-radius: 8px;
  margin-bottom: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  overflow: hidden;
}
.round-card.streaming {
  border-left: 2px solid #3498db;
}

.round-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 14px;
  background: #f8f9fa;
  border-bottom: 1px solid #eee;
  font-size: 0.85rem;
}
.round-label {
  font-weight: 700;
  color: #2c3e50;
}
.speaker-icon { font-size: 1.1rem; }
.round-time {
  color: #999;
  font-size: 0.75rem;
}
.streaming-badge {
  margin-left: auto;
  font-size: 0.7rem;
  color: #3498db;
  animation: blink 1s infinite;
}

/* User bubble */
.user-bubble {
  margin: 8px 12px;
  padding: 8px 12px;
  background: #e3f2fd;
  border-left: 2px solid #2196f3;
  border-radius: 6px;
  font-size: 0.85rem;
}
.user-label {
  font-weight: 600;
  color: #1565c0;
  margin-right: 8px;
}
.msg-time {
  font-size: 0.7rem;
  color: #999;
}
.user-content {
  margin-top: 4px;
  color: #333;
  line-height: 1.5;
}

/* System message (hidden by default) */
.system-msg {
  margin: 4px 12px;
  font-size: 0.75rem;
}
.system-details summary {
  color: #aaa;
  cursor: pointer;
}
.system-text {
  font-size: 0.7rem;
  color: #999;
  background: #fafafa;
  padding: 6px;
  border-radius: 4px;
  max-height: 120px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

/* Assistant message */
.assistant-msg {
  padding: 8px 14px;
}

.thinking-block {
  margin-bottom: 8px;
  font-size: 0.8rem;
}
.thinking-block summary {
  cursor: pointer;
  color: #7f8c8d;
  font-size: 0.8rem;
  user-select: none;
}
.thinking-indicator {
  animation: blink 0.8s infinite;
  color: #3498db;
}
.thinking-text {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 0.8rem;
  color: #7f8c8d;
  background: #f9f9f9;
  padding: 8px;
  border-radius: 4px;
  margin-top: 4px;
  max-height: 200px;
  overflow-y: auto;
}

.content-label {
  font-size: 0.75rem;
  color: #666;
  margin-bottom: 4px;
  font-weight: 600;
}
.content-text {
  line-height: 1.6;
  font-size: 0.9rem;
  color: #333;
}

.self-score {
  padding: 6px 14px;
  font-size: 0.8rem;
  color: #8e44ad;
  font-weight: 500;
  border-top: 1px dashed #eee;
}

.streaming-cursor {
  display: inline-block;
  padding: 0 14px 8px;
  animation: blink 0.8s infinite;
  color: #3498db;
  font-weight: bold;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
</style>
