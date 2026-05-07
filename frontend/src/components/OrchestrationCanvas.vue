<template>
  <div class="orchestration-page">
    <div class="preset-bar">
      <button 
        v-for="p in presets" :key="p.key"
        :class="['preset-btn', { active: activePreset === p.key }]"
        @click="loadPreset(p.key)"
      >
        {{ p.label }}
      </button>
    </div>

    <div class="canvas-layout">
      <!-- ── 左侧工具箱 ── -->
      <div class="toolbox">
        <div class="toolbox-section" :class="{ collapsed: !builtinOpen }" @click="builtinOpen = !builtinOpen">
          <span class="section-arrow">{{ builtinOpen ? '▾' : '▸' }}</span>
          <h4>默认专家</h4>
        </div>
        <div v-show="builtinOpen">
          <div v-for="(expert, id) in availableExperts" :key="id"
            class="toolbox-item"
            draggable="true"
            @dragstart="onDragStart($event, id, expert)"
            @contextmenu.prevent.stop="showExpertContext($event, id, expert, true)"
          >
            <span class="expert-icon">{{ expert.icon }}</span>
            <div class="expert-info">
              <span class="expert-name">{{ expert.label }}</span>
              <span class="expert-desc">{{ expert.desc }}</span>
            </div>
          </div>
        </div>

        <div class="toolbox-section" :class="{ collapsed: !customOpen }" @click="customOpen = !customOpen">
          <span class="section-arrow">{{ customOpen ? '▾' : '▸' }}</span>
          <h4>自定义专家</h4>
        </div>
        <div v-show="customOpen">
          <div v-for="(expert, id) in customExperts" :key="id"
            class="toolbox-item custom-item"
            draggable="true"
            @dragstart="onDragStart($event, id, expert)"
            @contextmenu.prevent.stop="showExpertContext($event, id, expert, false)"
          >
            <span class="expert-icon">{{ expert.icon }}</span>
            <div class="expert-info">
              <span class="expert-name">{{ expert.label }}</span>
              <span class="expert-desc">{{ expert.desc }}</span>
            </div>
            <button class="btn-delete-expert" @click.stop="deleteCustomExpert(id)" title="删除">×</button>
          </div>
          <div v-if="Object.keys(customExperts).length === 0" class="hint" style="padding:6px 10px;">
            暂无自定义专家
          </div>
          <div style="display:flex;gap:4px;margin:4px 2px;">
            <button class="btn-create-expert" @click="showCreateModal = true">+ 创建</button>
            <button class="btn-create-expert" @click="triggerImportExpert">+ 导入</button>
          </div>
          <input ref="importInput" type="file" accept=".json,.yaml,.yml" @change="handleImportExpert" style="display:none" />
        </div>
      </div>

      <!-- ── 画布 ── -->
      <div class="canvas-area" 
        @drop="onDrop" 
        @dragover="onDragOver"
        @dragenter="onDragEnterCanvas"
        @dragleave="onDragLeaveCanvas"
        :class="{ 'drag-over-canvas': draggingOverCanvas }"
      >
        <VueFlow
          v-model:nodes="nodes"
          v-model:edges="edges"
          :node-types="nodeTypes"
          :default-viewport="{ x: 0, y: 0, zoom: 1 }"
          fit-view-on-init
          @node-click="onNodeClick"
          @node-double-click="onNodeDoubleClick"
          @node-context-menu="onNodeContextMenu"
          @pane-click="onPaneClick"
          @edge-click="onEdgeClick"
          @connect="onConnect"
          class="flow-canvas"
        >
          <Background :gap="20" />
          <Controls position="bottom-right" />
        </VueFlow>
        <div class="floating-toolbar">
          <span class="toolbar-label">工具</span>
          <span class="toolbar-sep"></span>
          <button class="toolbar-btn" @click="addContainer" title="群聊（多专家同时讨论）">📦</button>
          <button class="toolbar-btn" @click="addPlaceholder('worldbook')" title="世界书节点">📖</button>
          <button class="toolbar-btn" @click="addPlaceholder('rag')" title="RAG节点">🔍</button>
          <button class="toolbar-btn" @click="addPlaceholder('splitter')" title="章节拆分师">✂️</button>
          <span class="toolbar-sep"></span>
          <button class="toolbar-btn" @click="addInputSource" title="输入源节点（队列.md文件）">📥</button>
          <button class="toolbar-btn" @click="addOutput" title="输出节点（收集结果）">📤</button>
          <button class="toolbar-btn" @click="saveDesign" :disabled="!projectId || saveStatus === 'saving'" :title="saveStatus === 'saved' ? '已保存' : saveStatus === 'error' ? '保存失败' : '保存到文档库'">
            {{ saveStatus === 'saving' ? '⏳' : saveStatus === 'saved' ? '✅' : saveStatus === 'error' ? '❌' : '💾' }}
          </button>
        </div>
      </div>

      <!-- ── 右侧面板：容器配置 ── -->
      <div class="config-panel" v-if="selectedNode && selectedNode.type === 'container'">
        <div class="panel-header-row">
          <h4>群聊配置</h4>
          <button class="btn-back" @click="selectedNode = null">← 返回</button>
        </div>
        <div class="config-field">
          <label>名称</label>
          <input v-model="containerCfg.name" @change="onContainerChange" />
        </div>
        <div class="config-field">
          <label>并发方式</label>
          <select v-model="containerCfg.concurrency" @change="onContainerChange">
            <option value="serial">串行（一次一个）</option>
            <option value="parallel">并行（可同时）</option>
          </select>
        </div>
        <div class="config-field">
          <label>发言方式</label>
          <select v-model="containerCfg.speaking_mode" @change="onContainerChange">
            <option value="ordered">顺序循环（按连线）</option>
            <option value="mention_driven">提及驱动（互相 @）</option>
          </select>
        </div>
        <div class="config-field">
          <label>重复次数（1=不循环，提及驱动模式忽略此项）</label>
          <input v-model.number="containerCfg.repeat" type="number" min="1" max="100" @change="onContainerChange" :disabled="containerCfg.speaking_mode === 'mention_driven'" />
        </div>

        <div class="config-field">
          <label>中断模式（覆盖容器内专家）</label>
          <select v-model="containerCfg.interrupt_mode" @change="onContainerChange">
            <option :value="null">不覆盖</option>
            <option value="auto">全自动</option>
            <option value="every_n_msgs">每 N 楼暂停</option>
            <option value="every_n_tokens">每 N token 暂停</option>
            <option value="on_mention">@ 主编时暂停</option>
          </select>
        </div>
        <div class="config-field" v-if="containerCfg.interrupt_mode && containerCfg.interrupt_mode !== 'auto' && containerCfg.interrupt_mode !== 'on_mention'">
          <label>阈值</label>
          <input v-model.number="containerCfg.interrupt_threshold" type="number" min="1" max="1000" @change="onContainerChange" />
        </div>

        <div class="config-section">
          <label class="section-label">退出条件</label>
        </div>
        <div class="config-field">
          <label>退出方式</label>
          <select v-model="containerCfg.exit_mode" @change="onContainerChange" >
            <option value="manual">手动</option>
            <option value="consensus">全部赞同</option>
            <option value="ratio">多数赞同</option>
            <option value="gatekeeper">门禁专家</option>
          </select>
        </div>
        <div class="config-field" v-if="containerCfg.exit_mode === 'ratio'">
          <label>赞同比例 ({{ (containerCfg.exit_ratio * 100).toFixed(0) }}%)</label>
          <input v-model.number="containerCfg.exit_ratio" type="range" min="0.1" max="1" step="0.1" @change="onContainerChange"  />
        </div>
        <div class="config-field" v-if="containerCfg.exit_mode === 'gatekeeper'">
          <label>门禁专家</label>
          <select v-model="containerCfg.exit_gatekeeper" @change="onContainerChange" >
            <option :value="null">---</option>
            <option v-for="child in containerChildren" :key="child" :value="child">{{ child }}</option>
          </select>
        </div>
        <div class="config-field">
          <label>最大发言次数（0=不限）</label>
          <input v-model.number="containerCfg.exit_max_speeches" type="number" min="0" max="500" @change="onContainerChange"  />
        </div>

        <div class="config-section">
          <label class="section-label">上下文深度（可选，以先触达为准）</label>
        </div>
        <div class="config-field config-inline">
          <label class="checkbox-label">
            <input type="checkbox" v-model="containerCfg.use_layers" @change="onContainerChange" />
            按楼层
          </label>
          <input v-if="containerCfg.use_layers" v-model.number="containerCfg.context_layers" type="number" min="1" max="50" placeholder="层数" @change="onContainerChange" style="width:70px;margin-left:8px;" />
        </div>
        <div class="config-field config-inline">
          <label class="checkbox-label">
            <input type="checkbox" v-model="containerCfg.use_tokens" @change="onContainerChange" />
            按 token
          </label>
          <input v-if="containerCfg.use_tokens" v-model.number="containerCfg.context_tokens" type="number" min="1000" max="1000000" step="10000" placeholder="token数" @change="onContainerChange" style="width:100px;margin-left:8px;" />
        </div>

        <div class="config-section">
          <label class="section-label">数据绑定（暂留接口）</label>
        </div>
        <div class="config-field">
          <label>世界书（逗号分隔）</label>
          <input v-model="containerCfg.worldbook_bindings" placeholder="核心设定, 角色追踪" @change="onContainerChange" />
        </div>
        <div class="config-field">
          <label>RAG（逗号分隔）</label>
          <input v-model="containerCfg.rag_bindings" placeholder="历史回顾, 技法参考" @change="onContainerChange" />
        </div>

        <div class="config-actions">
          <button class="btn btn-danger btn-sm" @click="removeNode">删除容器</button>
        </div>
      </div>

      <!-- ── 右侧面板：专家节点配置 ── -->
      <div class="config-panel" v-else-if="selectedNode && selectedNode.type === 'expert'">
        <div class="panel-header-row">
          <h4>节点配置</h4>
          <button class="btn-back" @click="selectedNode = null" title="返回会议配置">← 返回</button>
        </div>
        <div class="config-field">
          <label>专家</label>
          <div class="expert-label-row">
            <span class="expert-icon">{{ getExpertIcon(selectedNode) }}</span>
            <strong>{{ selectedNode.data.label }}</strong>
            <span v-if="selectedNode.data.isPlaceholder" class="placeholder-badge">占位</span>
            <span v-if="nodeTriggers.worldbook" class="trigger-icon" title="世界书查询">📖</span>
            <span v-if="nodeTriggers.rag" class="trigger-icon" title="RAG检索">🔍</span>
          </div>
        </div>
        <div class="config-field">
          <label>角色</label>
          <select v-model="selectedNode.data.role" @change="onConfigChange">
            <option value="main">主导 (main)</option>
            <option value="review">审核 (review)</option>
            <option value="supplement">补充 (supplement)</option>
          </select>
        </div>
        <div class="config-field">
          <label>世界书查询</label>
          <select :value="nodeTriggers.worldbook" @change="setTrigger('worldbook', $event.target.value)" class="trigger-select-wb">
            <option value="off">关闭</option>
            <option value="manual">手动</option>
            <option value="auto">自动（发言前注入）</option>
          </select>
        </div>
        <div class="config-field">
          <label>RAG 检索</label>
          <select :value="nodeTriggers.rag" @change="setTrigger('rag', $event.target.value)" class="trigger-select-rag">
            <option value="off">关闭</option>
            <option value="manual">手动</option>
            <option value="auto">自动（发言前注入）</option>
          </select>
        </div>
        <div class="config-field">
          <label>自定义 prompt</label>
          <textarea v-model="customPrompt" placeholder="可选，额外指令" rows="3" @change="onConfigChange"></textarea>
        </div>
        <div class="config-field">
          <label>中断模式</label>
          <select :value="selectedNode.data.interrupt_mode || 'every_n_msgs'" @change="setInterrupt('mode', $event.target.value)">
            <option value="auto">全自动（不暂停）</option>
            <option value="every_n_msgs">每 N 楼暂停</option>
            <option value="every_n_tokens">每 N token 暂停</option>
            <option value="on_mention">专家 @ 主编时暂停</option>
          </select>
        </div>
        <div class="config-field" v-if="(selectedNode.data.interrupt_mode || 'every_n_msgs') !== 'auto' && (selectedNode.data.interrupt_mode || 'every_n_msgs') !== 'on_mention'">
          <label>阈值</label>
          <input :value="selectedNode.data.interrupt_threshold || 1" @change="setInterrupt('threshold', $event.target.value)" type="number" min="1" max="1000" />
        </div>
        <!-- Agent 迭代配置 (仅 pipeline_version=2 时生效) -->
        <div class="config-section">
          <label class="section-label">Agent 迭代配置 (v2)</label>
        </div>
        <div class="config-field config-inline">
          <label class="checkbox-label">
            <input type="checkbox" v-model="agentTagStop" @change="onAgentConfigChange" />
            标签中止 (&lt;stop&gt;)
          </label>
        </div>
        <div class="config-field">
          <label>最大轮数</label>
          <input v-model.number="agentMaxRounds" type="number" min="1" max="10" @change="onAgentConfigChange" />
        </div>
        <div class="config-field">
          <label>超出轮数行为</label>
          <select v-model="agentOnMaxRounds" @change="onAgentConfigChange">
            <option value="accept_last">接受最后一轮</option>
            <option value="pick_best">选择最高分轮次</option>
          </select>
        </div>
        <div class="config-field">
          <label>每 N 轮阻塞等待用户</label>
          <input v-model.number="agentBlockEveryNRounds" type="number" min="0" max="10" @change="onAgentConfigChange" />
          <small v-if="agentBlockEveryNRounds > 0">每 {{ agentBlockEveryNRounds }} 轮暂停，等待用户反馈</small>
          <small v-else>0 = 不阻塞</small>
        </div>
        <div class="config-section">
          <label class="section-label">上下文读取</label>
        </div>
        <div class="config-field config-inline">
          <label class="checkbox-label">
            <input type="checkbox" v-model="agentReadInput" @change="onAgentConfigChange" />
            输入文件
          </label>
          <label class="checkbox-label" style="margin-left:12px;">
            <input type="checkbox" v-model="agentReadReport" @change="onAgentConfigChange" />
            上游报告
          </label>
          <label class="checkbox-label" style="margin-left:12px;">
            <input type="checkbox" v-model="agentReadChatLog" @change="onAgentConfigChange" />
            聊天记录
          </label>
        </div>
        <div class="config-actions">
          <button class="btn btn-danger btn-sm" @click="removeNode">删除节点</button>
        </div>
      </div>

      <!-- ── 右侧面板：输入源队列 ── -->
      <div class="config-panel" v-else-if="selectedNode && selectedNode.type === 'inputSource'"
        @dragover.prevent="onQueueDragOver"
        @dragleave="onQueueDragLeave"
        @drop.stop.prevent="onQueueDrop"
        :class="{ 'drag-over': queueDragOver }">
        <div class="panel-header-row">
          <h4>📥 输入源队列</h4>
          <button class="btn-back" @click="selectedNode = null; showQueuePanel = false">← 返回</button>
        </div>
        <div class="queue-actions">
          <input ref="fileInput" type="file" multiple @change="onFilesSelected" style="display:none" />
          <button class="btn btn-sm" @click="$refs.fileInput.click()">+ 添加文件</button>
          <button class="btn btn-sm" @click="selectedNode.data.files = []" :disabled="!selectedNode.data.files || selectedNode.data.files.length === 0">清空</button>
          <button class="btn btn-sm" @click="addTextAsFile">📝 粘贴</button>
        </div>
        <div class="queue-list" v-if="selectedNode.data.files && selectedNode.data.files.length > 0">
          <div v-for="(f, i) in selectedNode.data.files" :key="i" class="queue-item">
            <span class="queue-idx">{{ i + 1 }}</span>
            <span class="queue-name">{{ f.name }}</span>
            <span class="queue-size">{{ (f.content.length / 1000).toFixed(1) }}KB</span>
            <button class="btn-x" @click="selectedNode.data.files.splice(i, 1)" title="移除">✕</button>
          </div>
        </div>
        <div class="queue-hint" v-else>添加 .md 文件，或将文档库文件拖拽到此处</div>
        <div class="config-actions">
          <button class="btn btn-danger btn-sm" @click="removeNode">删除节点</button>
        </div>
      </div>

      <!-- ── 右侧面板：输出节点 ── -->
      <div class="config-panel" v-else-if="selectedNode && selectedNode.type === 'output'">
        <div class="panel-header-row">
          <h4>📤 输出节点</h4>
          <button class="btn-back" @click="selectedNode = null">← 返回</button>
        </div>
        <div class="config-field">
          <label>状态</label>
          <div v-if="selectedNode.data.running" style="color: #3b82f6; font-weight: 600;">⏳ 运行中...</div>
          <div v-else-if="selectedNode.data.done" style="color: #22c55e; font-weight: 600;">✅ 已完成</div>
          <div v-else style="color: #999;">等待输入</div>
        </div>
        <div class="config-field" v-if="selectedNode.data.done">
          <label>操作</label>
          <div style="display: flex; flex-direction: column; gap: 6px;">
            <button class="btn btn-sm btn-primary" @click="openNodeChatTab(selectedNode)">打开聊天窗口查看结果</button>
            <button class="btn btn-sm" @click="downloadOutput">📥 下载文件</button>
            <button class="btn btn-sm" @click="transferToLibrary">📚 转移到文档库</button>
          </div>
        </div>
        <div class="config-actions">
          <button class="btn btn-danger btn-sm" @click="removeNode">删除节点</button>
        </div>
      </div>

      <!-- ── 右侧面板：会议总配置 ── -->
      <div class="config-panel" v-else>
        <h4>当前配置</h4>
        <div class="meeting-settings">
          <div class="config-field">
            <label>会议名称</label>
            <input v-model="meetingName" placeholder="专家会议" />
          </div>
        </div>
        <button 
          v-if="!props.isRunning"
          class="btn btn-run btn-primary" 
          @click="runMeeting" 
          :disabled="orderedNodes.length === 0"
        >
          开始流程
        </button>
        <template v-else>
          <button class="btn btn-run" :class="props.isPaused ? 'btn-primary' : 'btn-warning'" @click="togglePause">
            {{ props.isPaused ? '▶ 继续' : '⏸ 暂停' }}
          </button>
          <button class="btn btn-outline btn-danger" style="width:100%; margin-top:6px;" @click="stopMeeting">
            ⏹ 中止
          </button>
        </template>
        <button class="btn btn-outline btn-clear" @click="clearCanvas">清空画布</button>
      </div>
    </div>

    <!-- ── 创建自定义专家模态框 ── -->
    <div v-if="showCreateModal" class="modal-overlay" @click.self="showCreateModal = false">
      <div class="modal-content card">
        <h2>创建自定义专家</h2>
        <div class="form-group">
          <label>专家 ID（英文，如 my_expert）</label>
          <input v-model="newExpert.id" placeholder="my_expert" />
        </div>
        <div class="form-group">
          <label>名称</label>
          <input v-model="newExpert.name" placeholder="打脸检测师" />
        </div>
        <div class="form-group">
          <label>图标（emoji）</label>
          <input v-model="newExpert.icon" placeholder="📄" maxlength="4" />
        </div>
        <div class="form-group">
          <label>描述</label>
          <input v-model="newExpert.description" placeholder="检查打脸密度是否达标" />
        </div>
        <div class="form-group">
          <label>Prompt 模板</label>
          <div class="vars-hint">
            可用变量: <code>{vision}</code> <code>{worldbook}</code> <code>{author_proposal}</code> 
            <code>{reader_opinion}</code> <code>{user_feedback}</code> <code>{history}</code> <code>{custom_prompt}</code>
          </div>
          <textarea v-model="newExpert.prompt_template" placeholder="你是XXX专家，负责...&#10;&#10;故事愿景：{vision}&#10;&#10;请分析..." rows="10"></textarea>
        </div>
        <div class="modal-actions">
          <button class="btn btn-primary" @click="createCustomExpert" :disabled="!newExpert.id || !newExpert.name">创建</button>
          <button class="btn" @click="showCreateModal = false">取消</button>
        </div>
      </div>
    </div>

    <!-- ── 专家右键菜单 ── -->
    <div v-if="expertCtx.show" class="context-menu" :style="{ top: expertCtx.y + 'px', left: expertCtx.x + 'px' }" @click.stop>
      <div class="menu-items">
        <div @click="viewExpert">查看详情</div>
        <template v-if="!expertCtx.isBuiltin">
          <div @click="editExpert">编辑</div>
          <div class="menu-danger" @click="deleteCtxExpert">删除</div>
        </template>
      </div>
    </div>

    <!-- ── 画布节点右键菜单 ── -->
    <div v-if="nodeCtx.show" class="context-menu" :style="{ top: nodeCtx.y + 'px', left: nodeCtx.x + 'px' }" @click.stop>
      <div class="menu-items">
        <div @click="openChatNewWindow">打开聊天窗口</div>
      </div>
    </div>

    <!-- ── 查看专家弹窗 ── -->
    <div v-if="showViewExpert" class="modal-overlay" @click.self="showViewExpert = false">
      <div class="modal-content card">
        <h2>{{ viewExpertData.icon }} {{ viewExpertData.name }}</h2>
        <p class="expert-desc-label">{{ viewExpertData.desc }}</p>
        <div class="form-group">
          <label>ID</label>
          <input :value="viewExpertData.id" disabled />
        </div>
        <div class="form-group">
          <label>Prompt 模板</label>
          <pre class="expert-prompt-preview">{{ viewExpertData.prompt }}</pre>
        </div>
        <div class="modal-actions">
          <button class="btn" @click="showViewExpert = false">关闭</button>
        </div>
      </div>
    </div>

    <!-- ── 编辑专家弹窗 ── -->
    <div v-if="showEditExpert" class="modal-overlay" @click.self="showEditExpert = false">
      <div class="modal-content card">
        <h2>编辑专家</h2>
        <div class="form-group">
          <label>名称</label>
          <input v-model="editExpertData.name" />
        </div>
        <div class="form-group">
          <label>图标</label>
          <input v-model="editExpertData.icon" maxlength="4" />
        </div>
        <div class="form-group">
          <label>描述</label>
          <input v-model="editExpertData.description" />
        </div>
        <div class="form-group">
          <label>Prompt 模板</label>
          <textarea v-model="editExpertData.prompt_template" rows="8"></textarea>
        </div>
        <div class="modal-actions">
          <button class="btn btn-primary" @click="saveEditExpert">保存</button>
          <button class="btn" @click="showEditExpert = false">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, markRaw, onMounted, onUnmounted, watch } from 'vue'
import { VueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import axios from 'axios'

import ExpertNode from './ExpertNode.vue'
import GroupNode from './GroupNode.vue'
import InputSourceNode from './InputSourceNode.vue'
import OutputNode from './OutputNode.vue'
import JSZip from 'jszip'
import { saveAs } from 'file-saver'

const emit = defineEmits(['run', 'stop', 'toggle-pause'])
const props = defineProps({
  projectId: { type: String, default: '' },
  isRunning: { type: Boolean, default: false },
  isPaused: { type: Boolean, default: false },
  pipelineOutput: { type: Object, default: null }
})

const nodeTypes = { expert: markRaw(ExpertNode), container: markRaw(GroupNode), inputSource: markRaw(InputSourceNode), output: markRaw(OutputNode) }

const nodes = ref([])
const edges = ref([])
const selectedNode = ref(null)
const activePreset = ref('custom')
const builtinOpen = ref(true)
const customOpen = ref(true)

const meetingName = ref('专家会议')
const saveStatus = ref('')
const loadStatus = ref('')
const draggingOverCanvas = ref(false)
const showCreateModal = ref(false)
const customPrompt = ref('')
const importInput = ref(null)

// Agent 迭代配置 (v2)
const agentTagStop = ref(true)
const agentMaxRounds = ref(3)
const agentOnMaxRounds = ref('accept_last')
const agentBlockEveryNRounds = ref(0)
const agentReadInput = ref(true)
const agentReadReport = ref(true)
const agentReadChatLog = ref(false)

const customExperts = ref({})

// ── 输入源队列 ──
const showQueuePanel = ref(false)
const queueFiles = ref([])
const fileInput = ref(null)
const queueDragOver = ref(false)

function onFilesSelected(event) {
  const files = event.target.files
  if (!selectedNode.value || selectedNode.value.type !== 'inputSource') return
  if (!selectedNode.value.data.files) selectedNode.value.data.files = []
  for (const f of files) {
    const reader = new FileReader()
    reader.onload = (e) => {
      selectedNode.value.data.files.push({ name: f.name, content: e.target.result })
    }
    reader.readAsText(f)
  }
  event.target.value = ''
}

function addTextAsFile() {
  if (!selectedNode.value || selectedNode.value.type !== 'inputSource') return
  if (!selectedNode.value.data.files) selectedNode.value.data.files = []
  const text = prompt('粘贴 .md 文本内容：')
  if (text && text.trim()) {
    const name = '粘贴文本_' + (selectedNode.value.data.files.length + 1) + '.md'
    selectedNode.value.data.files.push({ name, content: text.trim() })
  }
}

function updateInputSourceHighlight() {
  if (selectedNode.value && selectedNode.value.type === 'inputSource') {
    selectedNode.value.data.selected = true
  }
}

const newExpert = reactive({
  id: '',
  name: '',
  icon: '📄',
  description: '',
  prompt_template: ''
})

const expertCtx = reactive({ show: false, x: 0, y: 0, id: '', data: null, isBuiltin: true })
const nodeCtx = reactive({ show: false, x: 0, y: 0, nodeId: '', type: '', nodeData: null })
const showViewExpert = ref(false)
const viewExpertData = reactive({ id: '', name: '', icon: '', desc: '', prompt: '' })
const showEditExpert = ref(false)
const editExpertData = reactive({ id: '', name: '', icon: '', description: '', prompt_template: '' })

const containerCfg = reactive({
  name: '容器', concurrency: 'serial', speaking_mode: 'ordered',
  use_layers: false, context_layers: null,
  use_tokens: false, context_tokens: null,
      repeat: 1, interrupt_mode: null, interrupt_threshold: 1,
  exit_mode: 'manual', exit_ratio: 0.6, exit_gatekeeper: null, exit_max_speeches: 20,
  worldbook_bindings: '', rag_bindings: ''
})

const containerChildren = computed(() => {
  if (!selectedNode.value || selectedNode.value.type !== 'container') return []
  return selectedNode.value.data.children || []
})

let nodeCounter = 0

const availableExperts = {
  senior_author_v1: { label: '资深作者', icon: '📕', desc: '方向/市场判断' },
  reader_representative_v1: { label: '读者代表', icon: '📙', desc: '体验审核' },
  plot_architect_v1: { label: '剧情架构师', icon: '🏛', desc: '逻辑/功能拆解' },
  character_designer_v1: { label: '人物设计师', icon: '🎭', desc: 'OOC/行动元' },
  web_editor_v1: { label: '网络编辑', icon: '💼', desc: '爽点/毒点' },
  chapter_splitter_v1: { label: '章节拆分师', icon: '✂️', desc: '卷纲→章节目录' },
  discussion_summarizer_v1: { label: '讨论总结师', icon: '📋', desc: '提炼共识/标注分歧' }
}

const presets = [
  { key: 'quick_review', label: '快速审核' },
  { key: 'volume_planning', label: '卷纲规划' },
  { key: 'chapter_design', label: '章纲设计' },
  { key: 'custom', label: '自定义' }
]

const presetConfigs = {
  quick_review: {
    meeting_name: '快速审核',
    experts: [{ expert_id: 'web_editor_v1', role: 'main' }]
  },
  volume_planning: {
    meeting_name: '卷纲编排',
    experts: [
      { expert_id: 'senior_author_v1', role: 'main' },
      { expert_id: 'reader_representative_v1', role: 'review' },
      { expert_id: 'senior_author_v1', role: 'supplement' }
    ]
  },
  chapter_design: {
    meeting_name: '章纲设计',
    experts: [
      { expert_id: 'plot_architect_v1', role: 'main' },
      { expert_id: 'web_editor_v1', role: 'review' },
      { expert_id: 'character_designer_v1', role: 'supplement' }
    ]
  }
}

function getAllExperts() {
  return { ...availableExperts, ...customExperts.value }
}

onMounted(() => {
  fetchCustomExperts()
  document.addEventListener('click', hideExpertContext)
  document.addEventListener('click', hideNodeCtx)
})

onUnmounted(() => {
  document.removeEventListener('click', hideExpertContext)
  document.removeEventListener('click', hideNodeCtx)
})

async function fetchCustomExperts() {
  try {
    const params = props.projectId ? `?projectId=${encodeURIComponent(props.projectId)}` : ''
    const res = await axios.get(`/api/experts${params}`)
    customExperts.value = res.data.custom_experts || {}
  } catch (e) { console.warn('Failed to fetch custom experts:', e) }
}

async function saveDesign() {
  saveStatus.value = 'saving'
  try {
    const design = {
      meeting_name: meetingName.value,
      nodes: nodes.value.map(n => ({
        id: n.id, type: n.type, position: n.position,
        parentNode: n.parentNode || null,
        style: n.style || {},
        data: { ...n.data }
      })),
      edges: edges.value.map(e => ({
        id: e.id, source: e.source, target: e.target, animated: true
      }))
    }
    const now = new Date()
    const ts = `${String(now.getFullYear()).slice(-2)}_${now.getMonth() + 1}_${now.getDate()}_${String(now.getHours()).padStart(2, '0')}${String(now.getMinutes()).padStart(2, '0')}`
    const name = `${meetingName.value || '未命名'} — ${ts}`
    const res = await axios.post(`/api/projects/${props.projectId}/library`, {
      name, layer: 'orchestration', content: design, source: 'generate',
      directory: '/', tags: ['编排', meetingName.value]
    })
    await axios.put(`/api/projects/${props.projectId}/library/active/orchestration`, { uid: res.data.uid })
    window.postMessage({ type: 'library-refresh' }, '*')
    saveStatus.value = 'saved'
    setTimeout(() => { saveStatus.value = '' }, 2000)
  } catch (e) {
    saveStatus.value = 'error'
    console.warn('Save design failed:', e)
    setTimeout(() => { saveStatus.value = '' }, 3000)
  }
}

async function createCustomExpert() {
  if (!newExpert.id || !newExpert.name) return
  try {
    const payload = {
      id: newExpert.id,
      name: newExpert.name,
      icon: newExpert.icon,
      description: newExpert.description,
      prompt_template: newExpert.prompt_template
    }
    const apiParams = props.projectId ? `?projectId=${encodeURIComponent(props.projectId)}` : ''
    await axios.post(`/api/experts/custom${apiParams}`, payload)
    await fetchCustomExperts()
    showCreateModal.value = false
    Object.assign(newExpert, { id: '', name: '', icon: '📄', description: '', prompt_template: '' })
  } catch (e) {
    console.error('Create expert failed:', e)
    alert(e.response?.data?.detail || '创建失败')
  }
}

async function deleteCustomExpert(id) {
  if (!confirm('确定删除此自定义专家？')) return
  try {
    const dParams = props.projectId ? `?projectId=${encodeURIComponent(props.projectId)}` : ''
    await axios.delete(`/api/experts/custom/${id}${dParams}`)
    await fetchCustomExperts()
  } catch (e) { alert('删除失败') }
}

// ── 专家右键菜单 ──

function showExpertContext(event, id, expert, isBuiltin) {
  expertCtx.show = true
  expertCtx.x = event.clientX
  expertCtx.y = event.clientY
  expertCtx.id = id
  expertCtx.data = expert
  expertCtx.isBuiltin = isBuiltin
}

function hideExpertContext() {
  expertCtx.show = false
}

async function viewExpert() {
  hideExpertContext()
  const id = expertCtx.id
  try {
    const promptParams = props.projectId ? `?projectId=${encodeURIComponent(props.projectId)}` : ''
    const res = await axios.get(`/api/experts/${id}/prompt${promptParams}`)
    viewExpertData.id = id
    viewExpertData.name = expertCtx.data.label
    viewExpertData.icon = expertCtx.data.icon
    viewExpertData.desc = expertCtx.data.desc
    viewExpertData.prompt = res.data.prompt || '（无 prompt 内容）'
  } catch (e) {
    viewExpertData.id = id
    viewExpertData.name = expertCtx.data.label
    viewExpertData.icon = expertCtx.data.icon
    viewExpertData.desc = expertCtx.data.desc
    viewExpertData.prompt = '（无法获取 prompt）'
  }
  showViewExpert.value = true
}

async function editExpert() {
  hideExpertContext()
  const id = expertCtx.id
  try {
    const promptParams = props.projectId ? `?projectId=${encodeURIComponent(props.projectId)}` : ''
    const res = await axios.get(`/api/experts/${id}/prompt${promptParams}`)
    const infoParams = props.projectId ? `?projectId=${encodeURIComponent(props.projectId)}` : ''
    const info = (await axios.get(`/api/experts${infoParams}`)).data.custom_experts[id] || {}
    editExpertData.id = id
    editExpertData.name = info.label || expertCtx.data.label
    editExpertData.icon = info.icon || expertCtx.data.icon
    editExpertData.description = info.desc || ''
    editExpertData.prompt_template = res.data.prompt || ''
    showEditExpert.value = true
  } catch (e) { console.error('Edit expert failed:', e) }
}

async function saveEditExpert() {
  const fn = `data/user/custom_experts/${editExpertData.id}.json`
  const payload = {
    id: editExpertData.id,
    name: editExpertData.name,
    icon: editExpertData.icon,
    description: editExpertData.description,
    prompt_template: editExpertData.prompt_template
  }
  // Update via reload: delete old registration, write file, re-register
  try {
    const delParams = props.projectId ? `?projectId=${encodeURIComponent(props.projectId)}` : ''
    await axios.delete(`/api/experts/custom/${editExpertData.id}${delParams}`)
    const apiParams = props.projectId ? `?projectId=${encodeURIComponent(props.projectId)}` : ''
    await axios.post(`/api/experts/custom${apiParams}`, payload)
    await fetchCustomExperts()
    showEditExpert.value = false
  } catch (e) {
    console.error('Save expert failed:', e)
    alert('保存失败')
  }
}

function deleteCtxExpert() {
  hideExpertContext()
  deleteCustomExpert(expertCtx.id)
}

function triggerImportExpert() {
  importInput.value?.click()
}

async function handleImportExpert(event) {
  const file = event.target.files?.[0]
  if (!file) return
  try {
    const text = await file.text()
    let data
    if (file.name.endsWith('.json')) {
      data = JSON.parse(text)
    } else {
      // rough yaml parse: just split key: value
      data = {}
      for (const line of text.split('\n')) {
        const m = line.match(/^(\w+):\s*(.+)/)
        if (m) data[m[1]] = m[2].trim()
      }
    }
    if (!data.id || !data.name) { alert('导入文件需包含 id 和 name'); return }
    data.prompt_template = data.prompt_template || data.prompt || ''
    data.icon = data.icon || '📄'
    data.description = data.description || ''
    await axios.post('/api/experts/custom', data)
    await fetchCustomExperts()
  } catch (e) {
    console.error('Import expert failed:', e)
    alert('导入失败：' + (e.response?.data?.detail || e.message))
  }
  event.target.value = ''
}

function loadPreset(key) {
  activePreset.value = key
  if (key === 'custom') { clearCanvas(); return }
  const preset = presetConfigs[key]
  if (!preset) return
  meetingName.value = preset.meeting_name
  nodes.value = []; edges.value = []; nodeCounter = 0
  const allExperts = getAllExperts()
  let prevId = null
  for (const exp of preset.experts) {
    const expert = allExperts[exp.expert_id]
    if (!expert) continue
    const id = `node_${++nodeCounter}`
    nodes.value.push({
      id, type: 'expert', position: { x: nodeCounter * 200, y: 200 },
      data: { label: expert.label, role: exp.role, expertId: exp.expert_id, customPrompt: '' },
      style: { zIndex: 5 }
    })
    if (prevId) {
      edges.value.push({ id: `edge_${prevId}_${id}`, source: prevId, target: id, animated: true })
    }
    prevId = id
  }
}

function onDragStart(event, expertId, expert) {
  event.dataTransfer.setData('application/json', JSON.stringify({ expertId, label: expert.label, icon: expert.icon }))
  event.dataTransfer.effectAllowed = 'move'
}

function onDragOver(event) { event.preventDefault(); event.dataTransfer.dropEffect = 'move' }

function onDrop(event) {
  event.preventDefault()
  draggingOverCanvas.value = false
  const raw = event.dataTransfer.getData('application/json')
  if (!raw) return
  const data = JSON.parse(raw)

  // 编排设计文档 → 加载设计
  if (data.layer === 'orchestration' && data.uid) {
    loadDesignByUid(data.uid)
    return
  }

  if (!data.expertId) return
  const canvasEl = event.target.closest('.vue-flow')
  if (!canvasEl) return
  const rect = canvasEl.getBoundingClientRect()
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top
  const id = `node_${++nodeCounter}`
  nodes.value.push({
    id, type: 'expert', position: { x, y },
    data: { label: data.label, role: 'main', expertId: data.expertId, customPrompt: '' },
    style: { zIndex: 5 }
  })
}

function onDragEnterCanvas(event) { event.preventDefault(); draggingOverCanvas.value = true }
function onDragLeaveCanvas(event) {
  if (!event.currentTarget.contains(event.relatedTarget)) draggingOverCanvas.value = false
}

async function loadDesignByUid(uid) {
  loadStatus.value = 'loading'
  try {
    const res = await axios.get(`/api/projects/${props.projectId}/library/${uid}`)
    const { content } = res.data
    if (!content || !content.nodes) { loadStatus.value = 'empty'; setTimeout(() => { loadStatus.value = '' }, 2000); return }
    loadStatus.value = 'loaded'; setTimeout(() => { loadStatus.value = '' }, 2000)
    meetingName.value = content.meeting_name || '专家会议'
    nodes.value = content.nodes.map(n => ({
      id: n.id, type: n.type || 'expert', position: n.position,
      parentNode: n.parentNode || null,
      style: n.style || (n.type === 'expert' ? { zIndex: 5 } : { zIndex: 0 }),
      data: { ...n.data }
    }))
    edges.value = content.edges.map(e => ({ id: e.id, source: e.source, target: e.target, animated: true }))
    nodeCounter = nodes.value.length
    activePreset.value = 'custom'
    selectedNode.value = null
  } catch (e) {
    loadStatus.value = 'error'; console.warn('Load design failed:', e)
    setTimeout(() => { loadStatus.value = '' }, 3000)
  }
}

function onConnect(connection) {
  edges.value.push({ id: `edge_${connection.source}_${connection.target}`, source: connection.source, target: connection.target, animated: true })
}

function onEdgeClick({ edge }) { edges.value = edges.value.filter(e => e.id !== edge.id) }

function removeNode() {
  if (!selectedNode.value) return
  const id = selectedNode.value.id
  nodes.value = nodes.value.filter(n => n.id !== id)
  edges.value = edges.value.filter(e => e.source !== id && e.target !== id)
  selectedNode.value = null
}

function onConfigChange() {
  if (selectedNode.value) {
    selectedNode.value.data.customPrompt = customPrompt.value
  }
}

function onAgentConfigChange() {
  if (!selectedNode.value || selectedNode.value.type !== 'expert') return
  selectedNode.value.data.agentTagStop = agentTagStop.value
  selectedNode.value.data.agentMaxRounds = agentMaxRounds.value
  selectedNode.value.data.agentOnMaxRounds = agentOnMaxRounds.value
  selectedNode.value.data.agentBlockEveryNRounds = agentBlockEveryNRounds.value
  selectedNode.value.data.agentReadInput = agentReadInput.value
  selectedNode.value.data.agentReadReport = agentReadReport.value
  selectedNode.value.data.agentReadChatLog = agentReadChatLog.value
}

const nodeTriggers = computed(() => {
  if (!selectedNode.value || !selectedNode.value.data) return { worldbook: 'off', rag: 'off' }
  const t = selectedNode.value.data.triggers || {}
  return { worldbook: t.worldbook || 'off', rag: t.rag || 'off' }
})

function setTrigger(field, value) {
  if (selectedNode.value && selectedNode.value.type === 'expert') {
    if (!selectedNode.value.data.triggers) selectedNode.value.data.triggers = {}
    selectedNode.value.data.triggers[field] = value
  }
}

function setInterrupt(field, value) {
  if (selectedNode.value && selectedNode.value.type === 'expert') {
    if (field === 'mode') selectedNode.value.data.interrupt_mode = value
    if (field === 'threshold') selectedNode.value.data.interrupt_threshold = parseInt(value) || 1
  }
}

function getExpertIcon(node) {
  if (!node || !node.data) return '📄'
  const icons = { '资深作者': '📕', '读者代表': '📙', '剧情架构师': '🏛', '人物设计师': '🎭', '网络编辑': '💼' }
  return icons[node.data.label] || '📄'
}

function getExpertLabel(id) {
  const labels = { senior_author_v1: '资深作者', reader_representative_v1: '读者代表', plot_architect_v1: '剧情架构师', character_designer_v1: '人物设计师', web_editor_v1: '网络编辑', chapter_splitter_v1: '章节拆分师', discussion_summarizer_v1: '讨论总结师' }
  return labels[id] || id
}

// ── 容器配置 ──

function onContainerChange() {
  if (selectedNode.value && selectedNode.value.type === 'container') {
    selectedNode.value.data.name = containerCfg.name
    selectedNode.value.data.label = containerCfg.name
    selectedNode.value.data.concurrency = containerCfg.concurrency
    selectedNode.value.data.speaking_mode = containerCfg.speaking_mode
    selectedNode.value.data.context_layers = containerCfg.use_layers ? (containerCfg.context_layers || 3) : null
    selectedNode.value.data.context_tokens = containerCfg.use_tokens ? (containerCfg.context_tokens || 100000) : null
    selectedNode.value.data.repeat = containerCfg.repeat
    selectedNode.value.data.interrupt_mode = containerCfg.interrupt_mode
    selectedNode.value.data.interrupt_threshold = containerCfg.interrupt_threshold
    selectedNode.value.data.exit_mode = containerCfg.exit_mode
    selectedNode.value.data.exit_ratio = containerCfg.exit_ratio
    selectedNode.value.data.exit_gatekeeper = containerCfg.exit_gatekeeper
    selectedNode.value.data.exit_max_speeches = containerCfg.exit_max_speeches
    selectedNode.value.data.worldbook_bindings = containerCfg.worldbook_bindings
      .split(',').map(s => s.trim()).filter(Boolean)
    selectedNode.value.data.rag_bindings = containerCfg.rag_bindings
      .split(',').map(s => s.trim()).filter(Boolean)
    updateContainerChildren()
  }
}

function loadContainerConfig(node) {
  containerCfg.name = node.data.name || node.data.label || '群聊'
  containerCfg.concurrency = node.data.concurrency || 'serial'
  containerCfg.speaking_mode = node.data.speaking_mode || 'ordered'
  containerCfg.use_layers = node.data.context_layers != null
  containerCfg.context_layers = node.data.context_layers ?? null
  containerCfg.use_tokens = node.data.context_tokens != null
  containerCfg.context_tokens = node.data.context_tokens ?? null
  containerCfg.repeat = node.data.repeat || 1
  containerCfg.interrupt_mode = node.data.interrupt_mode ?? null
  containerCfg.interrupt_threshold = node.data.interrupt_threshold || 1
  containerCfg.exit_mode = node.data.exit_mode || 'manual'
  containerCfg.exit_ratio = node.data.exit_ratio ?? 0.6
  containerCfg.exit_gatekeeper = node.data.exit_gatekeeper ?? null
  containerCfg.exit_max_speeches = node.data.exit_max_speeches ?? 20
  containerCfg.worldbook_bindings = (node.data.worldbook_bindings || []).join(', ')
  containerCfg.rag_bindings = (node.data.rag_bindings || []).join(', ')
}

// ── 发言顺序计算 ──

const orderedNodes = computed(() => {
  const expertNodes = nodes.value.filter(n => n.type === 'expert')
  if (edges.value.length === 0) return expertNodes.map(n => {
    const container = nodes.value.find(c => c.type === 'container' && c.id === n.parentNode)
    return { ...n, containerName: container ? container.data.name : null }
  })

  const inDegree = {}, outEdges = {}, nodeMap = {}
  for (const n of expertNodes) { nodeMap[n.id] = n; inDegree[n.id] = 0; outEdges[n.id] = [] }
  for (const e of edges.value) {
    if (!nodeMap[e.source] || !nodeMap[e.target]) continue
    inDegree[e.target] = (inDegree[e.target] || 0) + 1
    outEdges[e.source] = (outEdges[e.source] || []).concat(e.target)
  }

  const queue = expertNodes.filter(n => (inDegree[n.id] || 0) === 0)
  const result = []
  while (queue.length > 0) {
    const level = [...queue]
    queue.length = 0
    for (const current of level) {
      const container = nodes.value.find(n => n.id === current.parentNode && n.type === 'container')
      const isMentionDriven = container && container.data.speaking_mode === 'mention_driven'
      const repeat = isMentionDriven ? 1 : (container ? (container.data.repeat || 1) : 1)
      const containerName = container ? container.data.name : null
      for (let i = 0; i < repeat; i++) {
        result.push({ ...current, containerName, loopIteration: repeat > 1 ? i + 1 : 0 })
      }
    }
    for (const current of level) {
      for (const target of (outEdges[current.id] || [])) {
        inDegree[target]--
        if (inDegree[target] === 0) queue.push(nodeMap[target])
      }
    }
  }
  return result.length >= expertNodes.length ? result : expertNodes.map(n => {
    const container = nodes.value.find(c => c.type === 'container' && c.id === n.parentNode)
    return { ...n, containerName: container ? container.data.name : null }
  })
})

function buildAgentConfigs() {
  const configs = {}
  const expertNodes = nodes.value.filter(n => n.type === 'expert')
  for (const node of expertNodes) {
    const readCategories = []
    if (node.data.agentReadInput !== false) readCategories.push('input')
    if (node.data.agentReadReport !== false) readCategories.push('report')
    if (node.data.agentReadChatLog) readCategories.push('chat_log')

    configs[node.id] = {
      stopConfig: {
        enableTagStop: node.data.agentTagStop !== undefined ? node.data.agentTagStop : true,
        blockEveryNRounds: node.data.agentBlockEveryNRounds || 0,
        maxRounds: node.data.agentMaxRounds || 3,
        onMaxRounds: node.data.agentOnMaxRounds || 'accept_last'
      },
      readCategories: readCategories.length > 0 ? readCategories : ['input', 'report']
    }
  }
  return configs
}

function runMeeting() {
  // 检查是否有输入源
  const inputFiles = inputSourceFiles()
  if (inputFiles.length === 0) {
    alert('请先添加输入源文件！\n\n点击工具栏的 📥 按钮添加输入源节点，然后拖入 .md 文件。')
    return
  }

  // 更新输出节点状态为运行中
  const outputNodes = nodes.value.filter(n => n.type === 'output')
  outputNodes.forEach(n => {
    n.data.running = true
    n.data.done = false
  })

  const experts = orderedNodes.value.map(node => ({
    expert_id: node.data.expertId,
    node_id: node.id,
    role: node.data.role || 'main',
    custom_prompt: node.data.customPrompt || null,
    container_id: node.parentNode || null,
    interrupt_mode: node.data.interrupt_mode || 'every_n_msgs',
    interrupt_threshold: node.data.interrupt_threshold || 1,
    loop_iteration: node.loopIteration || 0
  }))

  const containers = nodes.value
    .filter(n => n.type === 'container')
    .map(n => ({
      container_id: n.id,
      name: n.data.name || n.data.label || '容器',
      concurrency: n.data.concurrency || 'serial',
      speaking_mode: n.data.speaking_mode || 'ordered',
      context_layers: n.data.context_layers ?? null,
      context_tokens: n.data.context_tokens ?? null,
      repeat: n.data.repeat || 1,
      interrupt_mode: n.data.interrupt_mode ?? null,
      interrupt_threshold: n.data.interrupt_threshold || 1,
      exit_mode: n.data.exit_mode || 'manual',
      exit_ratio: n.data.exit_ratio ?? 0.6,
      exit_gatekeeper: n.data.exit_gatekeeper ?? null,
      exit_max_speeches: n.data.exit_max_speeches ?? 20,
      worldbook_bindings: n.data.worldbook_bindings || [],
      rag_bindings: n.data.rag_bindings || [],
      mention_isolation: n.data.mention_isolation !== false,
      children: n.data.children || [],
      edges: edges.value
        .filter(e => {
          const srcIn = (n.data.children || []).includes(e.source)
          const tgtIn = (n.data.children || []).includes(e.target)
          return srcIn || tgtIn || e.source === n.id || e.target === n.id
        })
        .map(e => ({ source: e.source, target: e.target }))
    }))

  emit('run', {
    meeting_name: meetingName.value,
    pipeline: true,
    pipeline_version: 2,
    experts,
    containers,
    queue_files: inputSourceFiles(),
    agent_configs: buildAgentConfigs(),
    edges: edges.value.filter(e => {
      const isInterContainer = nodes.value.some(n => 
        (n.type === 'container' && (e.source === n.id || e.target === n.id || 
         (n.data.children || []).includes(e.source) || (n.data.children || []).includes(e.target)))
      )
      return !isInterContainer
    }).map(e => ({ source: e.source, target: e.target }))
  })
}

function togglePause() {
  emit('toggle-pause')
}

function stopMeeting() {
  emit('stop')
}

function clearCanvas() {
  nodes.value = []; edges.value = []; selectedNode.value = null
  nodeCounter = 0; activePreset.value = 'custom'
}

function inputSourceFiles() {
  const srcNode = nodes.value.find(n => n.type === 'inputSource')
  if (srcNode && srcNode.data.files && srcNode.data.files.length > 0) {
    return srcNode.data.files.map(f => ({ name: f.name, content: f.content }))
  }
  return []
}

function onQueueDragOver(event) {
  event.dataTransfer.dropEffect = 'move'
  queueDragOver.value = true
}

function onQueueDragLeave(event) {
  if (!event.currentTarget.contains(event.relatedTarget)) {
    queueDragOver.value = false
  }
}

async function onQueueDrop(event) {
  queueDragOver.value = false
  const raw = event.dataTransfer.getData('application/json')
  if (!raw) { console.warn('Queue drop: no JSON'); return }
  let data
  try { data = JSON.parse(raw) } catch (e) { console.warn('Queue drop: bad JSON'); return }
  if (!data.uid || !data.name) { console.warn('Queue drop: no uid/name', data); return }
  if (!selectedNode.value || selectedNode.value.type !== 'inputSource') return
  if (!selectedNode.value.data.files) selectedNode.value.data.files = []
  if (selectedNode.value.data.files.some(f => f.uid === data.uid)) return
  // 加载内容
  try {
    const res = await axios.get(`/api/projects/${props.projectId}/library/${data.uid}`)
    const content = res.data.content
    const text = typeof content === 'string' ? content : (content.content || JSON.stringify(content, null, 2))
    selectedNode.value.data.files.push({ name: data.name, content: text, uid: data.uid })
  } catch (e) { console.error('Failed to load document:', e) }
}

// ── 容器子节点同步 ──

function updateContainerChildren() {
  const map = {}
  for (const n of nodes.value) {
    if (n.type === 'expert' && n.parentNode) {
      if (!map[n.parentNode]) map[n.parentNode] = []
      map[n.parentNode].push(n.data.label)
    }
  }
  for (const n of nodes.value) {
    if (n.type === 'container') {
      const labels = map[n.id] || []
      n.data.children = [...new Set(labels)]
    }
  }
}

watch(() => nodes.value.length, () => { updateContainerChildren() })
watch(() => nodes.value.map(n => n.parentNode).join(','), () => { updateContainerChildren() }, { immediate: true })

// 监听isRunning变化，更新输出节点状态
watch(() => props.isRunning, (running) => {
  const outputNodes = nodes.value.filter(n => n.type === 'output')
  outputNodes.forEach(n => {
    n.data.running = running
    if (!running) {
      n.data.done = true
    }
  })
})

// 监听pipelineOutput变化，将文件数据传递给输出节点
watch(() => props.pipelineOutput, (output) => {
  if (!output) return

  const nodeOutputs = output.node_outputs || output.nodeOutputs
  if (!nodeOutputs || Object.keys(nodeOutputs).length === 0) return

  // 查找输出节点
  const outputNodes = nodes.value.filter(n => n.type === 'output')
  if (outputNodes.length === 0) return

  // 将输出文件组织为数组格式
  const files = Object.entries(nodeOutputs).map(([key, content]) => ({
    name: `${key}.md`,
    content: content
  }))

  // 将文件设置到输出节点的data中
  outputNodes.forEach(n => {
    n.data.files = files
    n.data.done = true
    n.data.running = false
  })

  console.log('[OrchestrationCanvas] Files set to output nodes:', files)
}, { immediate: true, deep: true })

// ── 占位节点 ──

function addPlaceholder(type) {
  const configs = {
    worldbook: { label: '世界书', icon: '📖', expertId: '__worldbook__', desc: '设定查询/更新' },
    rag: { label: 'RAG检索', icon: '🔍', expertId: '__rag__', desc: '历史/技法检索' },
    splitter: { label: '章节拆分师', icon: '✂️', expertId: 'chapter_splitter_v1', desc: '卷纲→章节' }
  }
  const cfg = configs[type]; if (!cfg) return
  const id = `node_${++nodeCounter}`
  nodes.value.push({
    id, type: 'expert', position: { x: 100 + nodeCounter * 80, y: 300 + nodeCounter * 30 },
    data: { label: cfg.label, role: 'main', expertId: cfg.expertId, customPrompt: '', isPlaceholder: type !== 'splitter', triggers: {} },
    style: { zIndex: 5 }
  })
}

function addContainer() {
  const id = `container_${++nodeCounter}`
  nodes.value.push({
    id, type: 'container', position: { x: 250, y: 180 },
    data: {
      name: '群聊', label: '群聊', icon: '👥',
      concurrency: 'serial', speaking_mode: 'ordered',
      repeat: 1, children: [], edges: [],
      context_layers: null, context_tokens: null,
      interrupt_mode: null, interrupt_threshold: 1,
      exit_mode: 'manual', exit_ratio: 0.6, exit_gatekeeper: null, exit_max_speeches: 20,
      worldbook_bindings: [], rag_bindings: [],
    },
    style: { width: 280, zIndex: 4 }
  })
}

function addInputSource() {
  const id = `input_${++nodeCounter}`
  nodes.value.push({
    id, type: 'inputSource', position: { x: 100, y: 300 },
    data: { label: '输入源', files: [], selected: false },
    style: { zIndex: 5 }
  })
  updateInputSourceHighlight()
}

function addOutput() {
  const id = `output_${++nodeCounter}`
  nodes.value.push({
    id, type: 'output', position: { x: 800, y: 300 },
    data: { label: '输出', running: false, done: false, selected: false },
    style: { zIndex: 5 }
  })
}

function onNodeClick({ node }) {
  selectedNode.value = node
  if (node.type === 'expert') {
    customPrompt.value = node.data.customPrompt || ''
    agentTagStop.value = node.data.agentTagStop !== undefined ? node.data.agentTagStop : true
    agentMaxRounds.value = node.data.agentMaxRounds || 3
    agentOnMaxRounds.value = node.data.agentOnMaxRounds || 'accept_last'
    agentBlockEveryNRounds.value = node.data.agentBlockEveryNRounds || 0
    agentReadInput.value = node.data.agentReadInput !== undefined ? node.data.agentReadInput : true
    agentReadReport.value = node.data.agentReadReport !== undefined ? node.data.agentReadReport : true
    agentReadChatLog.value = node.data.agentReadChatLog || false
  } else if (node.type === 'container') {
    loadContainerConfig(node)
  } else if (node.type === 'inputSource') {
    showQueuePanel.value = true
  } else if (node.type === 'output') {
    // 输出节点单击时只选中，显示属性面板
  }
}

function onPaneClick() {
  selectedNode.value = null
  showQueuePanel.value = false
}

function onNodeDoubleClick({ node }) {
  openNodeChatTab(node)
}

function openNodeChatTab(node) {
  // 输出节点打开输出页面
  if (node.type === 'output') {
    window.open(`/output?projectId=${encodeURIComponent(props.projectId || '')}`, '_blank')
    return
  }

  let params = `projectId=${encodeURIComponent(props.projectId || '')}&nodeType=${encodeURIComponent(node.type)}`
  if (node.type === 'container') {
    params += `&containerId=${encodeURIComponent(node.id)}&name=${encodeURIComponent(node.data.name || '容器')}`
  } else if (node.type === 'expert') {
    const eid = node.data.expertId
    const label = getExpertLabel(eid) || eid
    params += `&expertId=${encodeURIComponent(eid)}&name=${encodeURIComponent(label)}`
    if (node.parentNode) params += `&containerId=${encodeURIComponent(node.parentNode)}`
  } else if (node.type === 'inputSource') {
    params += `&name=${encodeURIComponent(node.data.label || '输入源')}`
  }
  window.open(`/chat-popup?${params}`, '_blank')
}

function onNodeContextMenu({ event, node }) {
  event.preventDefault()
  nodeCtx.show = true
  nodeCtx.x = event.clientX
  nodeCtx.y = event.clientY
  nodeCtx.nodeId = node.id
  nodeCtx.type = node.type
  nodeCtx.nodeData = node.data
}

function openChatNewWindow() {
  const n = nodeCtx
  let params = `projectId=${encodeURIComponent(props.projectId || '')}`
  if (n.type === 'container') {
    const c = nodes.value.find(x => x.id === n.nodeId)
    const name = c?.data?.name || '容器'
    params += `&containerId=${encodeURIComponent(n.nodeId)}&name=${encodeURIComponent(name)}`
  } else if (n.type === 'output') {
    params += `&expertId=output&name=${encodeURIComponent(n.nodeData?.label || '输出')}`
  } else {
    const eid = n.nodeData?.expertId
    const label = getExpertLabel(eid) || eid
    params += `&expertId=${encodeURIComponent(eid)}&name=${encodeURIComponent(label)}`
    const expertNode = nodes.value.find(x => x.id === n.nodeId)
    if (expertNode?.parentNode) params += `&containerId=${encodeURIComponent(expertNode.parentNode)}`
  }
  window.open(`/chat-popup?${params}`, '_blank')
  nodeCtx.show = false
}

function openChatInline() {
  // 统一为新窗口打开
  openChatNewWindow()
}

function hideNodeCtx() { nodeCtx.show = false }

async function downloadOutput() {
  if (!props.pipelineOutput) {
    alert('没有可下载的输出数据')
    return
  }

  // 支持驼峰和下划线两种字段名
  const nodeOutputs = props.pipelineOutput.node_outputs || props.pipelineOutput.nodeOutputs
  if (!nodeOutputs) {
    alert('没有可下载的输出数据')
    return
  }

  const keys = Object.keys(nodeOutputs)

  if (keys.length === 0) {
    alert('没有可下载的输出数据')
    return
  }

  if (keys.length === 1) {
    // 单个文件直接下载
    const content = nodeOutputs[keys[0]]
    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
    saveAs(blob, `${keys[0]}.md`)
  } else {
    // 多个文件打包为zip
    const zip = new JSZip()
    for (const [nodeId, content] of Object.entries(nodeOutputs)) {
      zip.file(`${nodeId}.md`, content)
    }
    const blob = await zip.generateAsync({ type: 'blob' })
    saveAs(blob, 'pipeline_output.zip')
  }
}

async function transferToLibrary() {
  if (!props.pipelineOutput || !props.pipelineOutput.node_outputs) {
    alert('没有可转移的输出数据')
    return
  }

  if (!props.projectId) {
    alert('未关联项目，无法转移到文档库')
    return
  }

  const nodeOutputs = props.pipelineOutput.node_outputs
  const keys = Object.keys(nodeOutputs)

  if (keys.length === 0) {
    alert('没有可转移的输出数据')
    return
  }

  try {
    if (keys.length === 1) {
      const content = nodeOutputs[keys[0]]
      await axios.post(`/api/projects/${props.projectId}/library/import`, {
        name: `${keys[0]}.md`,
        content,
        format: 'markdown',
        directory: '/管道输出'
      })
      alert('已转移到文档库')
    } else {
      for (const [nodeId, content] of Object.entries(nodeOutputs)) {
        await axios.post(`/api/projects/${props.projectId}/library/import`, {
          name: `${nodeId}.md`,
          content,
          format: 'markdown',
          directory: '/管道输出'
        })
      }
      alert('已转移到文档库')
    }
    // 刷新文档库侧边栏
    window.postMessage({ type: 'library-refresh' }, window.location.origin)
  } catch (err) {
    console.error('转移到文档库失败:', err)
    alert('转移到文档库失败: ' + (err.response?.data?.error || err.message))
  }
}
</script>

<style scoped>
.orchestration-page {
  height: calc(100vh - 42px);
  display: flex;
  flex-direction: column;
  background: #f5f5f5;
}

.preset-bar {
  display: flex; gap: 8px; padding: 10px 16px;
  background: white; border-bottom: 1px solid #e0e0e0;
}
.preset-btn {
  padding: 6px 16px; border: 1px solid #ddd; border-radius: 6px;
  background: white; cursor: pointer; font-size: 0.875rem; transition: all 0.2s;
}
.preset-btn:hover { background: #f0f7ff; border-color: #3498db; }
.preset-btn.active { background: #3498db; color: white; border-color: #3498db; }

.floating-toolbar {
  position: absolute; top: 12px; left: 50%; transform: translateX(-50%);
  display: flex; align-items: center; gap: 2px; padding: 6px 12px;
  background: #fff; border: 1px solid #d0d0d0; border-radius: 10px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.12); z-index: 10;
}
.toolbar-label { font-size: 0.7rem; color: #999; font-weight: 600; letter-spacing: 0.05em; }
.floating-toolbar .toolbar-sep { width: 1px; height: 20px; background: #ddd; margin: 0 4px; }
.toolbar-btn {
  width: 32px; height: 32px; border: 1px solid transparent; border-radius: 6px;
  background: transparent; cursor: pointer; font-size: 1.1rem;
  display: flex; align-items: center; justify-content: center; transition: all 0.15s;
}
.toolbar-btn:hover { background: #f0f7ff; border-color: #3498db; }
.toolbar-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.canvas-layout { flex: 1; display: flex; overflow: hidden; }

.toolbox { width: 190px; background: white; border-right: 1px solid #e0e0e0; padding: 4px; overflow-y: auto; display: flex; flex-direction: column; }
.toolbox-section { display: flex; align-items: center; gap: 4px; padding: 8px 8px 6px 8px; cursor: pointer; user-select: none; border-radius: 4px; }
.toolbox-section:hover { background: #f5f5f5; }
.toolbox-section.collapsed { margin-bottom: 2px; }
.toolbox-section h4 { font-size: 0.75rem; color: #999; margin: 0; text-transform: uppercase; letter-spacing: 0.05em; }
.section-arrow { font-size: 0.7rem; color: #bbb; width: 12px; }
.toolbox-item { display: flex; align-items: center; gap: 8px; padding: 10px; border-radius: 8px; cursor: grab; transition: background 0.2s; margin-bottom: 4px; border: 1px solid transparent; }
.toolbox-item:hover { background: #f0f7ff; border-color: #d0e3f7; }
.toolbox-item:active { cursor: grabbing; }
.custom-item { position: relative; }
.btn-delete-expert { position: absolute; top: 4px; right: 4px; width: 18px; height: 18px; border: none; background: rgba(0,0,0,0.1); border-radius: 50%; cursor: pointer; font-size: 0.7rem; color: #999; display: flex; align-items: center; justify-content: center; opacity: 0; transition: opacity 0.2s; }
.custom-item:hover .btn-delete-expert { opacity: 1; }
.btn-delete-expert:hover { background: #e74c3c; color: white; }
.expert-icon { font-size: 1.3rem; }
.expert-info { flex: 1; }
.expert-name { font-size: 0.85rem; font-weight: 600; display: block; }
.expert-desc { font-size: 0.7rem; color: #999; }
.btn-create-expert { width: calc(100% - 4px); margin: 8px 2px; padding: 8px; border: 1px dashed #ccc; border-radius: 6px; background: transparent; cursor: pointer; font-size: 0.8rem; color: #888; transition: all 0.2s; }
.btn-create-expert:hover { border-color: #3498db; color: #3498db; background: #f0f7ff; }

.canvas-area { flex: 1; position: relative; transition: background 0.2s; border-radius: 4px; }
.canvas-area.drag-over-canvas { background: rgba(52, 152, 219, 0.08); box-shadow: inset 0 0 0 2px #3498db; }
.flow-canvas { width: 100%; height: 100%; }
/* 修复输出节点边框问题 */
.flow-canvas :deep(.vue-flow__node-output) { border: none !important; outline: none !important; box-shadow: none !important; background: transparent !important; padding: 0 !important; }
.flow-canvas :deep(.vue-flow__node-output.selected) { box-shadow: none !important; }

.config-panel { width: 280px; background: white; border-left: 1px solid #e0e0e0; padding: 14px; overflow-y: auto; }
.config-panel h4 { font-size: 0.85rem; color: #666; margin: 0; padding-bottom: 6px; border-bottom: 1px solid #eee; }
.panel-header-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.panel-header-row h4 { border: none; padding: 0; margin: 0; }
.btn-back { padding: 2px 8px; border: 1px solid #ddd; border-radius: 4px; background: white; cursor: pointer; font-size: 0.75rem; color: #3498db; transition: all 0.15s; }
.btn-back:hover { background: #f0f7ff; border-color: #3498db; }
.config-field { margin-bottom: 10px; }
.config-field label { display: block; font-size: 0.75rem; color: #888; margin-bottom: 4px; }
.checkbox-label { display: flex; align-items: center; gap: 6px; cursor: pointer; font-size: 0.8rem; }
.checkbox-label input { width: auto; }
.config-field input, .config-field select, .config-field textarea { width: 100%; padding: 6px 8px; border: 1px solid #ddd; border-radius: 4px; font-size: 0.85rem; }
.config-field textarea { resize: vertical; font-family: inherit; }
.config-field strong { font-size: 0.85rem; }
.expert-label-row { display: flex; align-items: center; gap: 6px; }
.placeholder-badge { font-size: 0.65rem; background: #f0f0f0; color: #999; padding: 1px 6px; border-radius: 4px; }
.trigger-icon { font-size: 0.9rem; margin-left: 2px; }
.order-list { margin-top: 8px; }
.order-item { display: flex; align-items: center; gap: 6px; padding: 6px 8px; border-radius: 4px; background: #f8f9fa; margin-bottom: 4px; font-size: 0.8rem; }
.order-num { background: #3498db; color: white; border-radius: 50%; width: 20px; height: 20px; display: flex; align-items: center; justify-content: center; font-size: 0.7rem; }
.order-label { font-weight: 600; }
.order-role { color: #999; font-size: 0.7rem; }
.order-container { color: #9b59b6; font-size: 0.65rem; background: #f5f0ff; padding: 1px 6px; border-radius: 4px; }
.hint { font-size: 0.8rem; color: #999; font-style: italic; padding: 12px 0; }

.btn { padding: 0.5rem 1rem; border: 1px solid #ddd; border-radius: 4px; cursor: pointer; font-size: 0.875rem; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: #3498db; color: white; border-color: #3498db; }
.btn-danger { background: #e74c3c; color: white; border-color: #e74c3c; }
.btn-outline { background: white; color: #666; }
.btn-sm { padding: 4px 10px; font-size: 0.8rem; }
.btn-run { width: 100%; margin-top: 14px; padding: 10px; font-size: 0.95rem; }
.btn-running { background: #27ae60; color: white; border-color: #27ae60; cursor: not-allowed; }
.btn-clear { width: 100%; margin-top: 6px; padding: 8px; font-size: 0.85rem; }
.config-actions { margin-top: 10px; }
.config-section { margin: 12px 0 6px 0; }
.section-label { font-size: 0.7rem; color: #888; font-weight: 600; text-transform: uppercase; }
.config-inline { display: flex; align-items: center; gap: 6px; }
.config-inline label { margin-bottom: 0 !important; }

.modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 999; }
.modal-content { width: 520px; max-width: 90vw; max-height: 85vh; overflow-y: auto; background: white; padding: 1.5rem; border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.2); }
.modal-content h2 { margin: 0 0 1rem 0; font-size: 1.2rem; }
.form-group { margin-bottom: 1rem; }
.form-group label { display: block; font-size: 0.8rem; color: #666; margin-bottom: 4px; font-weight: 500; }
.form-group input, .form-group textarea { width: 100%; padding: 8px 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 0.9rem; font-family: inherit; }
.form-group textarea { resize: vertical; min-height: 120px; font-family: 'Courier New', monospace; font-size: 0.85rem; }
.vars-hint { font-size: 0.7rem; color: #999; margin-bottom: 6px; line-height: 1.5; }
.vars-hint code { background: #f0f0f0; padding: 1px 5px; border-radius: 3px; font-size: 0.7rem; }
.modal-actions { display: flex; gap: 8px; margin-top: 1rem; }
.modal-actions .btn { flex: 1; }

.context-menu {
  position: fixed;
  background: white;
  border: 1px solid #ddd;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
  z-index: 1000;
  min-width: 120px;
}
.menu-items > div {
  padding: 0.5rem 0.75rem;
  cursor: pointer;
  font-size: 0.875rem;
}
.menu-items > div:hover { background: #f0f0f0; }
.menu-danger { color: #e74c3c; }
.expert-desc-label { color: #666; font-size: 0.85rem; margin: 0 0 1rem 0; }
.expert-prompt-preview {
  background: #f8f9fa; padding: 0.75rem; border-radius: 4px;
  font-family: monospace; font-size: 0.8rem; white-space: pre-wrap;
  max-height: 200px; overflow-y: auto; margin: 0;
}

/* ── 输入源队列（在右侧配置面板内）─── */
.queue-actions { display: flex; gap: 8px; margin: 8px 0; }
.queue-list { display: flex; flex-direction: column; gap: 4px; }
.queue-item { display: flex; align-items: center; gap: 8px; padding: 6px 8px; background: #f8f9fa; border-radius: 6px; font-size: 0.85rem; }
.queue-idx { background: #3498db; color: white; width: 22px; height: 22px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.7rem; font-weight: 600; flex-shrink: 0; }
.queue-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.queue-size { color: #999; font-size: 0.75rem; flex-shrink: 0; }
.queue-hint { color: #999; font-size: 0.85rem; text-align: center; padding: 1rem; }
.btn-x { width: 22px; height: 22px; border: none; background: transparent; cursor: pointer; color: #999; font-size: 0.9rem; border-radius: 50%; }
.btn-x:hover { background: #fee; color: #e74c3c; }
.panel-header-row { display: flex; justify-content: space-between; align-items: center; }
.panel-header-row h4 { margin: 0; font-size: 0.9rem; }
.config-panel.drag-over { border: 2px dashed #22c55e; background: #f0fdf4; }
</style>
