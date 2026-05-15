// 分布式 Worker 实现
// 每个 Worker 是独立 async 函数，while 循环轮询自己的队列。
// 不做的事：不推事件到总线、不感知全局状态、不管理其他节点。
// 做的事：检查队列 → 处理对象 → 推到下游 → 检查 stop/pause 信号。

import {
  MeetingConfig, ExpertRole, Granularity, ContainerConfig,
  AgentStopConfig, PipelineObject, ExpertContext, ExpertChatLog,
  WorldBookSummaryConfig, WorldBookSummaryTask, PreprocessConfig
} from '../protocols';
import { createExpert } from '../experts';
import type { BaseExpert } from '../experts/base';
import { addExpertOutput, buildObjectContext, createPipelineObject } from '../models/pipeline-object';
import { AsyncQueue } from '../utils/queue';
import { PipelineEventV2 } from './object-pipeline-engine';
import { runPreprocessPipeline } from './preprocessor';

// ======================== 类型 ========================

export interface NodeWorkerConfig {
  nodeId: string;
  expertId: string;
  role: ExpertRole;
  containerId?: string;
  stopConfig: AgentStopConfig;
  readCategories: ('input' | 'report' | 'chat_log')[];
  isContainer?: boolean;
  children?: string[];
  childrenRoles?: Map<string, ExpertRole>;
  containerConfig?: ContainerConfig;
  worldbookSummaryConfig?: WorldBookSummaryConfig;
  preprocessConfig?: PreprocessConfig;
}

import { WorldBookEntry } from '../protocols';

export interface WorkerSharedState {
  stopRequested: boolean;
  pauseRequested: boolean;
  nodeConfigs: Map<string, NodeWorkerConfig>;
  globalConfig: MeetingConfig;
  feedbackMap: Map<string, string[]>;
  vision: Record<string, string>;
  worldbook: string;
  worldbookEntries: Map<string, WorldBookEntry[]>;
  perNodeWorldBook: Map<string, string>;
  rag: string;
  outputSeq: { value: number };
  worldbookTaskQueue?: AsyncQueue<WorldBookSummaryTask>;
  allObjects: PipelineObject[];  // 管道中所有对象（含预处理等节点动态创建的）
}

export const DEFAULT_STOP_CONFIG: AgentStopConfig = {
  enableStopSignal: true,
  blockEveryNRounds: 0,
  maxRounds: 3,
  onMaxRounds: 'accept_last'
};

export const DEFAULT_READ_CATEGORIES: ('input' | 'report' | 'chat_log')[] = ['input', 'report'];

// ======================== 工具 ========================

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function consumePendingMessage(nodeId: string, state: WorkerSharedState): string | null {
  const msgs = state.feedbackMap.get(nodeId);
  if (msgs && msgs.length > 0) return msgs.shift() || null;
  return null;
}

/** 等待暂停解除 */
async function waitIfPaused(state: WorkerSharedState): Promise<void> {
  while (state.pauseRequested && !state.stopRequested) {
    await sleep(100);
  }
}

/** 端口感知分发 + reject 循环保护 */
async function dispatchToDownstream(
  nodeId: string,
  obj: PipelineObject,
  downstreamQueues: Map<string, AsyncQueue<PipelineObject>>,
  edgePortMap: Map<string, string>
): Promise<void> {
  if (!obj.meta) obj.meta = { rejectCount: 0, maxRejects: 3 };
  if (obj.meta.routePort === 'reject') {
    obj.meta.rejectCount++;
    if (obj.meta.rejectCount > obj.meta.maxRejects) {
      obj.meta.routePort = 'pass';
    }
  }
  const routePort = obj.meta.routePort || 'default';
  for (const [downId, downQueue] of downstreamQueues) {
    const edgePort = edgePortMap.get(downId) || 'default';
    if (edgePort === routePort) {
      await downQueue.enqueue(obj);
    }
  }
}

/** 为指定节点解析世界书文本 */
/** 获取指定书的条目文本，按上下文关键词过滤 */
function resolveWorldbook(nodeId: string, contextTokens: string[], state: WorkerSharedState): string {
  const boundBookId = state.perNodeWorldBook.get(nodeId);
  let entries: WorldBookEntry[] = [];

  if (boundBookId && state.worldbookEntries.has(boundBookId)) {
    entries = state.worldbookEntries.get(boundBookId)!;
  } else {
    for (const bookEntries of state.worldbookEntries.values()) {
      entries.push(...bookEntries);
    }
  }

  if (entries.length === 0) return state.worldbook;

  // 按 group 分组（用于互斥选择）
  const groups = new Map<string, WorldBookEntry[]>();
  const ungrouped: WorldBookEntry[] = [];

  const active: WorldBookEntry[] = [];
  for (const entry of entries) {
    if (entry.disable) continue;
    if (entry.constant) { active.push(entry); continue; }

    // 关键词匹配（支持 caseSensitive / matchWholeWords）
    const primaryHit = entry.keys.some(key =>
      matchKeyword(key, contextTokens, entry.caseSensitive || false, entry.matchWholeWords || false)
    );
    if (!primaryHit) continue;

    // secondaryKeys + selectiveLogic
    if (entry.selective !== false && entry.secondaryKeys && entry.secondaryKeys.length > 0) {
      const logic = entry.selectiveLogic || 'AND_ANY';
      const secondaryHit = (sk: string) =>
        contextTokens.some(t => matchKeyword(sk, [t], entry.caseSensitive || false, entry.matchWholeWords || false));

      if (logic === 'AND_ALL' && !entry.secondaryKeys.every(sk => secondaryHit(sk))) continue;
      if (logic === 'NOT_ALL' && entry.secondaryKeys.every(sk => secondaryHit(sk))) continue;
      if (logic === 'NOT_ANY' && entry.secondaryKeys.some(sk => secondaryHit(sk))) continue;
    }

    // probability 概率检查
    const prob = entry.probability ?? 100;
    if (prob < 100 && Math.random() * 100 > prob) continue;

    // 有 group 的先分组，后面做互斥选择
    if (entry.group) {
      if (!groups.has(entry.group)) groups.set(entry.group, []);
      groups.get(entry.group)!.push(entry);
    } else {
      ungrouped.push(entry);
    }
  }

  // 每组选一个（按 groupWeight 加权随机）
  for (const [, groupEntries] of groups) {
    if (groupEntries.length === 1) {
      active.push(groupEntries[0]);
    } else {
      const totalWeight = groupEntries.reduce((sum, e) => sum + (e.groupWeight || 100), 0);
      let roll = Math.random() * totalWeight;
      for (const e of groupEntries) {
        roll -= (e.groupWeight || 100);
        if (roll <= 0) { active.push(e); break; }
      }
    }
  }
  active.push(...ungrouped);

  // 排序：先按 position 分组，再按 priority 降序
  const posOrder: Record<string, number> = {
    'before_char': 0, 'an_top': 0, 'em_top': 0,
    'at_depth': 1,
    'after_char': 2, 'an_bottom': 2, 'em_bottom': 2
  };
  active.sort((a, b) => {
    const pa = posOrder[a.position || 'before_char'] ?? 1;
    const pb = posOrder[b.position || 'before_char'] ?? 1;
    if (pa !== pb) return pa - pb;
    return (b.priority || 0) - (a.priority || 0);
  });

  return active.map(e => `${e.keys?.[0] || e.id}: ${e.content}`).join('\n') || state.worldbook;
}

/** 关键词匹配（支持大小写敏感和全词匹配） */
function matchKeyword(key: string, tokens: string[], caseSensitive: boolean, wholeWords: boolean): boolean {
  if (wholeWords) {
    const flags = caseSensitive ? 'g' : 'gi';
    const escaped = key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const re = new RegExp(`\\b${escaped}\\b`, flags);
    return tokens.some(t => re.test(t));
  }
  return tokens.some(t => {
    if (caseSensitive) return t.includes(key);
    return t.toLowerCase().includes(key.toLowerCase());
  });
}

// ======================== 处理函数（产生 SSE 事件，通过 emit 回调交出） ========================

async function processAgentNode(
  nodeId: string,
  obj: PipelineObject,
  expert: BaseExpert,
  stopConfig: AgentStopConfig,
  readCategories: ('input' | 'report' | 'chat_log')[],
  emit: (event: PipelineEventV2) => void,
  state: WorkerSharedState
): Promise<void> {
  const containerContext = buildObjectContext(obj, readCategories);

  const context: ExpertContext = {
    vision: state.vision,
    worldbook: resolveWorldbook(nodeId, (containerContext || '').split(/\s+/).filter(Boolean), state),
    rag: state.rag,
    containerContext,
    history: []
  };

  emit({
    type: 'agent_start',
    data: {
      expertId: expert.expertId,
      expertType: expert.expertType,
      role: expert['role'] || ExpertRole.MAIN,
      nodeId,
      objectId: obj.id,
      objectName: obj.name,
      stopConfig,
      files: obj.files.map(f => ({ path: f.path, category: f.category, producer: f.producer, content: f.content }))
    }
  });

  try {
    for await (const agentEvent of expert.iterate(context, stopConfig, undefined, undefined,
      () => consumePendingMessage(nodeId, state))) {
      await waitIfPaused(state);
      if (state.stopRequested) break;

      emit({
        type: agentEvent.type,
        data: {
          ...agentEvent.data,
          nodeId,
          objectId: obj.id,
          objectName: obj.name
        }
      });

      if (agentEvent.type === 'agent_round_complete') {
        // 每轮完成后发一次 object_progress，让前端文件队列即时更新
        const roundReport = (agentEvent.data.report as string) || '';
        const currentFiles = [
          ...obj.files.map(f => ({ path: f.path, category: f.category, producer: f.producer, content: f.content })),
        ];
        if (roundReport) {
          currentFiles.push({ path: `${expert.expertType}意见.md`, category: 'report', producer: expert.expertId, content: roundReport });
        }
        emit({
          type: 'object_progress',
          data: { objectId: obj.id, objectName: obj.name, nodeId, totalFiles: currentFiles.length, files: currentFiles }
        });

        // 世界书总结触发（per_round）
        tryEnqueueWorldBookTask(nodeId, obj, state, expert.expertId, 'agent_round_complete', roundReport);
      }

      if (agentEvent.type === 'agent_complete') {
        const report = (agentEvent.data.report as string) || '';
        const chatLog = agentEvent.data.chatLog as ExpertChatLog;
        state.outputSeq.value++;
        addExpertOutput(obj, expert.expertId, expert.expertType, report, chatLog, state.outputSeq.value);

        // 世界书总结触发（per_node）
        const fullContent = chatLog?.rounds?.map(r =>
          r.messages?.filter(m => m.role === 'assistant').map(m => m.content).join('\n') || ''
        ).join('\n') || report;
        tryEnqueueWorldBookTask(nodeId, obj, state, expert.expertId, 'agent_complete', fullContent);
      }
    }
  } catch (err) {
    emit({
      type: 'agent_error',
      data: { nodeId, objectId: obj.id, error: String(err) }
    });
    obj.status = 'failed';
  }

  // Worker 处理完当前对象，发最新的文件列表
  emit({
    type: 'object_progress',
    data: {
      objectId: obj.id,
      objectName: obj.name,
      nodeId,
      totalFiles: obj.files.length,
      files: obj.files.map(f => ({ path: f.path, category: f.category, producer: f.producer, content: f.content }))
    }
  });
}

async function processGroupChatNode(
  nodeId: string,
  obj: PipelineObject,
  emit: (event: PipelineEventV2) => void,
  state: WorkerSharedState
): Promise<void> {
  const nodeConfig = state.nodeConfigs.get(nodeId);
  if (!nodeConfig || !nodeConfig.isContainer) return;

  const cc = nodeConfig.containerConfig!;
  const children = nodeConfig.children || [];
  const childrenRoles = nodeConfig.childrenRoles || new Map();
  const speakingMode = cc.speakingMode || 'ordered';
  const exitMode = cc.exitMode || 'manual';
  const exitRatio = cc.exitRatio || 0.6;
  const exitGatekeeper = cc.exitGatekeeper;
  const exitMaxSpeeches = cc.exitMaxSpeeches || 20;
  const readCategories = nodeConfig.readCategories || [...DEFAULT_READ_CATEGORIES];

  emit({
    type: 'group_chat_start',
    data: {
      nodeId,
      nodeName: cc.name || nodeId,
      members: children,
      speakingMode,
      exitMode,
      objectId: obj.id,
      objectName: obj.name,
      files: obj.files.map(f => ({ path: f.path, category: f.category, producer: f.producer, content: f.content }))
    }
  });

  let totalSpeeches = 0;
  let roundNum = 1;
  const groupChatLog: {
    nodeId: string; nodeName: string; objectId: string;
    rounds: Array<{
      round: number;
      speeches: Array<{
        expertId: string; expertType: string; role: ExpertRole;
        thinking: string; content: string; timestamp: string;
      }>;
    }>;
  } = {
    nodeId,
    nodeName: cc.name || nodeId,
    objectId: obj.id,
    rounds: []
  };

  while (totalSpeeches < exitMaxSpeeches && !state.stopRequested) {
    await waitIfPaused(state);
    if (state.stopRequested) break;

    const roundSpeeches: typeof groupChatLog.rounds[0]['speeches'] = [];

    emit({
      type: 'group_chat_round_start',
      data: { nodeId, round: roundNum, objectId: obj.id, objectName: obj.name }
    });

    const containerCtx = buildObjectContext(obj, readCategories);

    let historySummary = '';
    if (groupChatLog.rounds.length > 0) {
      const prevRound = groupChatLog.rounds[groupChatLog.rounds.length - 1];
      historySummary = prevRound.speeches.map(s =>
        `[${s.expertType}] ${s.content.slice(0, 200)}`
      ).join('\n');
    }

    let speakers: string[];
    if (speakingMode === 'ordered') {
      speakers = [...children];
    } else {
      speakers = [children[0]];
    }

    for (const expertId of speakers) {
      await waitIfPaused(state);
      if (state.stopRequested) break;

      const role = childrenRoles.get(expertId) || ExpertRole.MAIN;
      const expert = createExpert(expertId, role, state.globalConfig.granularity);

      const currentMemberNames = children.filter(id => id !== expertId)
        .map(id => {
          const ec = state.globalConfig.experts.find(e => e.expertId === id);
          return ec?.expertId || id;
        });

      const context: ExpertContext = {
        vision: state.vision,
        worldbook: resolveWorldbook(nodeId, (containerCtx || '').split(/\s+/).filter(Boolean), state),
        rag: state.rag,
        containerContext: [
          containerCtx,
          historySummary ? `## 上轮讨论摘要\n${historySummary}` : '',
          roundSpeeches.length > 0 ? `## 本轮已发言\n${roundSpeeches.map(s =>
            `[${s.expertType}] ${s.content.slice(0, 300)}`
          ).join('\n')}` : '',
          `## 群聊参与者\n${currentMemberNames.join(', ')}。你可以 @ 他们来提问或要求回应。`
        ].filter(Boolean).join('\n\n'),
        history: []
      };

      emit({
        type: 'group_chat_member_start',
        data: { nodeId, expertId, expertType: expert.expertType, role, round: roundNum, objectId: obj.id, objectName: obj.name }
      });

      try {
        let fullContent = '';
        let fullThinking = '';

        for await (const chunk of expert.speakStream(context)) {
          await waitIfPaused(state);
          if (state.stopRequested) break;

          if (chunk.type === 'thinking') {
            fullThinking += chunk.content;
            emit({
              type: 'group_chat_chunk',
              data: { nodeId, expertId, expertType: expert.expertType, chunkType: 'thinking', content: chunk.content, round: roundNum, objectId: obj.id }
            });
          } else if (chunk.type === 'content') {
            fullContent += chunk.content;
            emit({
              type: 'group_chat_chunk',
              data: { nodeId, expertId, expertType: expert.expertType, chunkType: 'content', content: chunk.content, round: roundNum, objectId: obj.id }
            });
          }
        }

        roundSpeeches.push({
          expertId, expertType: expert.expertType, role,
          thinking: fullThinking, content: fullContent,
          timestamp: new Date().toISOString()
        });

        totalSpeeches++;

        emit({
          type: 'group_chat_member_complete',
          data: { nodeId, expertId, expertType: expert.expertType, content: fullContent.slice(0, 300), round: roundNum, objectId: obj.id }
        });
      } catch (err) {
        emit({
          type: 'group_chat_error',
          data: { nodeId, expertId, objectId: obj.id, error: String(err) }
        });
      }
    }

    if (roundSpeeches.length > 0) {
      groupChatLog.rounds.push({ round: roundNum, speeches: roundSpeeches });

      if (exitMode === 'consensus') {
        const allStopped = roundSpeeches.every(s => /<stop>/i.test(s.content));
        if (allStopped) break;
      } else if (exitMode === 'ratio') {
        const stoppedCount = roundSpeeches.filter(s => /<stop>/i.test(s.content)).length;
        if (stoppedCount / children.length >= exitRatio) break;
      } else if (exitMode === 'gatekeeper' && exitGatekeeper) {
        const gkSpeech = roundSpeeches.find(s => s.expertId === exitGatekeeper);
        if (gkSpeech && /<stop>/i.test(gkSpeech.content)) break;
      }
    }

    emit({
      type: 'group_chat_round_complete',
      data: { nodeId, round: roundNum, totalSpeeches, objectId: obj.id }
    });

    // 世界书总结触发（per_round）
    if (roundSpeeches.length > 0) {
      const roundContent = roundSpeeches.map(s => `[${s.expertType}] ${s.content}`).join('\n\n');
      tryEnqueueWorldBookTask(nodeId, obj, state, nodeId, 'group_chat_round_complete', roundContent);
    }

    roundNum++;
  }

  // 持久化群聊产出 — 合并为一份共享报告
  const containerName = cc.name || nodeId;
  const allSpeeches = groupChatLog.rounds.flatMap(r => r.speeches);

  const combinedReport = allSpeeches.length > 0
    ? allSpeeches.map(s => `## ${s.expertType}\n\n${s.content}`).join('\n\n---\n\n')
    : '';

  state.outputSeq.value++;
  obj.files.push({
    path: `${containerName}_群聊_report.md`,
    content: combinedReport,
    producer: nodeId,
    category: 'report'
  });

  obj.files.push({
    path: `${containerName}_群聊_chatlog.json`,
    content: JSON.stringify(groupChatLog, null, 2),
    producer: nodeId,
    category: 'chat_log'
  });

  emit({
    type: 'group_chat_complete',
    data: {
      nodeId,
      nodeName: cc.name || nodeId,
      totalRounds: groupChatLog.rounds.length,
      totalSpeeches,
      objectId: obj.id,
      objectName: obj.name
    }
  });

  // 世界书总结触发（per_node）
  tryEnqueueWorldBookTask(nodeId, obj, state, nodeId, 'group_chat_complete', combinedReport);

  // 群聊 Worker 处理完对象，发最新文件列表
  emit({
    type: 'object_progress',
    data: {
      objectId: obj.id,
      objectName: obj.name,
      nodeId,
      totalFiles: obj.files.length,
      files: obj.files.map(f => ({ path: f.path, category: f.category, producer: f.producer, content: f.content }))
    }
  });
}

// ======================== 四种 Worker（简单 async 函数，while 轮询） ========================

/**
 * 输入源 Worker
 */
export async function inputSourceWorker(
  nodeId: string,
  inputQueue: AsyncQueue<PipelineObject>,
  downstreamQueues: Map<string, AsyncQueue<PipelineObject>>,
  emit: (event: PipelineEventV2) => void,
  state: WorkerSharedState,
  initialObjects: PipelineObject[],
  _edgePortMap: Map<string, string> = new Map()
): Promise<void> {
  // 1. 分发初始对象
  for (const obj of initialObjects) {
    if (state.stopRequested) return;
    emit({ type: 'object_init', data: { objectId: obj.id, objectName: obj.name } });
    for (const [, downQueue] of downstreamQueues) {
      await downQueue.enqueue(obj);
    }
  }

  // 2. 轮询运行时注入
  while (!state.stopRequested) {
    await waitIfPaused(state);
    if (state.stopRequested) break;

    const obj = inputQueue.dequeueSync();
    if (!obj) {
      await sleep(1000);
      continue;
    }

    emit({ type: 'object_init', data: { objectId: obj.id, objectName: obj.name } });
    for (const [, downQueue] of downstreamQueues) {
      await downQueue.enqueue(obj);
    }
  }
}

/**
 * 专家 Worker
 */
export async function expertWorker(
  nodeId: string,
  inputQueue: AsyncQueue<PipelineObject>,
  downstreamQueues: Map<string, AsyncQueue<PipelineObject>>,
  emit: (event: PipelineEventV2) => void,
  state: WorkerSharedState,
  edgePortMap: Map<string, string> = new Map()
): Promise<void> {
  const config = state.nodeConfigs.get(nodeId);
  if (!config) return;

  while (!state.stopRequested) {
    await waitIfPaused(state);
    if (state.stopRequested) break;

    const obj = inputQueue.dequeueSync();
    if (!obj) {
      await sleep(1000);
      continue;
    }

    obj.status = 'running';
    obj.currentNodeId = nodeId;

    const expert = createExpert(config.expertId, config.role, state.globalConfig.granularity);
    const stopConfig = config.stopConfig || { ...DEFAULT_STOP_CONFIG };
    const readCategories = config.readCategories || [...DEFAULT_READ_CATEGORIES];

    await processAgentNode(nodeId, obj, expert, stopConfig, readCategories, emit, state);

    if ((obj.status as string) !== 'failed') {
      obj.status = 'completed';
      obj.completedAt = new Date().toISOString();
    }

    await dispatchToDownstream(nodeId, obj, downstreamQueues, edgePortMap);
  }
}

/**
 * 群聊 Worker
 */
export async function groupChatWorker(
  nodeId: string,
  inputQueue: AsyncQueue<PipelineObject>,
  downstreamQueues: Map<string, AsyncQueue<PipelineObject>>,
  emit: (event: PipelineEventV2) => void,
  state: WorkerSharedState,
  edgePortMap: Map<string, string> = new Map()
): Promise<void> {
  while (!state.stopRequested) {
    await waitIfPaused(state);
    if (state.stopRequested) break;

    const obj = inputQueue.dequeueSync();
    if (!obj) {
      await sleep(1000);
      continue;
    }

    obj.status = 'running';
    obj.currentNodeId = nodeId;

    await processGroupChatNode(nodeId, obj, emit, state);

    if ((obj.status as string) !== 'failed') {
      obj.status = 'completed';
      obj.completedAt = new Date().toISOString();
    }

    await dispatchToDownstream(nodeId, obj, downstreamQueues, edgePortMap);
  }
}

/**
 * 输出 Worker
 */
export async function outputWorker(
  nodeId: string,
  inputQueue: AsyncQueue<PipelineObject>,
  _downstreamQueues: Map<string, AsyncQueue<PipelineObject>>,
  emit: (event: PipelineEventV2) => void,
  state: WorkerSharedState
): Promise<void> {
  while (!state.stopRequested) {
    await waitIfPaused(state);
    if (state.stopRequested) break;

    const obj = inputQueue.dequeueSync();
    if (!obj) {
      await sleep(1000);
      continue;
    }

    emit({
      type: 'object_complete',
      data: {
        objectId: obj.id,
        objectName: obj.name,
        status: obj.status,
        totalFiles: obj.files.length,
        files: obj.files.map(f => ({
          path: f.path,
          category: f.category,
          producer: f.producer,
          ...(f.category === 'report' ? { content: f.content } : {})
        }))
      }
    });
  }
}

/**
 * 判断节点 Worker
 * 轻量 LLM 调用，判断产出是否合格，设置 routePort。
 */
export async function judgmentWorker(
  nodeId: string,
  inputQueue: AsyncQueue<PipelineObject>,
  downstreamQueues: Map<string, AsyncQueue<PipelineObject>>,
  emit: (event: PipelineEventV2) => void,
  state: WorkerSharedState,
  edgePortMap: Map<string, string> = new Map()
): Promise<void> {
  while (!state.stopRequested) {
    await waitIfPaused(state);
    if (state.stopRequested) break;

    const obj = inputQueue.dequeueSync();
    if (!obj) {
      await sleep(1000);
      continue;
    }

    obj.status = 'running';
    obj.currentNodeId = nodeId;

    emit({
      type: 'judgment_start',
      data: { nodeId, objectId: obj.id, objectName: obj.name }
    });

    try {
      // 构建审核上下文
      const reports = obj.files.filter(f => f.category === 'report');
      const reportText = reports.map(r => r.content).join('\n\n');
      const inputFiles = obj.files.filter(f => f.category === 'input');

      // 调 LLM 判断
      const llm = await import('./llm');
      const provider = llm.getLLM();
      const reviewPrompt = `你是一位严格的审稿编辑。请审查以下产出是否合格。

## 输入文件
${inputFiles.map(f => `### ${f.path}\n${f.content}`).join('\n\n')}

## 专家产出
${reportText || '（无产出）'}

请以 JSON 格式给出判断：{"verdict":"pass"|"reject","reason":"一句话说明理由"}`;

      let verdict: 'pass' | 'reject' = 'pass';
      let reason = 'No LLM configured, defaulting to pass';
      try {
        const response = await provider.invoke(reviewPrompt, { temperature: 0.3 });
        const jsonMatch = response.match(/\{[\s\S]*\}/);
        if (jsonMatch) {
          const result = JSON.parse(jsonMatch[0]);
          verdict = result.verdict === 'reject' ? 'reject' : 'pass';
          reason = result.reason || reason;
        }
      } catch {
        // LLM 调用失败，默认通过
      }

      if (!obj.meta) obj.meta = { rejectCount: 0, maxRejects: 3 };
      obj.meta.routePort = verdict;

      // 将裁决结果写入对象文件，供下载和输出页展示
      const judgmentReport = `# 判断结果\n\n- **裁决**: ${verdict === 'pass' ? '✅ 通过' : '❌ 驳回'}\n- **理由**: ${reason}\n- **驳回次数**: ${obj.meta.rejectCount}\n- **时间**: ${new Date().toISOString()}\n\n## 审核内容\n${inputFiles.map(f => `### ${f.path}\n${f.content.slice(0, 500)}${f.content.length > 500 ? '...' : ''}`).join('\n\n')}`;
      state.outputSeq.value++;
      obj.files.push({
        path: `判断结果_${state.outputSeq.value}.md`,
        content: judgmentReport,
        producer: nodeId,
        category: 'report'
      });

      emit({
        type: 'judgment_complete',
        data: {
          nodeId, objectId: obj.id, objectName: obj.name,
          verdict, reason, rejectCount: obj.meta.rejectCount
        }
      });
    } catch (err: any) {
      const errorReport = `# 判断失败\n\n- **错误**: ${err.message}\n- **时间**: ${new Date().toISOString()}`;
      state.outputSeq.value++;
      obj.files.push({
        path: `判断错误_${state.outputSeq.value}.md`,
        content: errorReport,
        producer: nodeId,
        category: 'report'
      });

      emit({
        type: 'judgment_error',
        data: { nodeId, objectId: obj.id, objectName: obj.name, error: err.message }
      });
      if (!obj.meta) obj.meta = { rejectCount: 0, maxRejects: 3 };
      obj.meta.routePort = 'pass';
    }

    obj.status = 'completed';
    obj.completedAt = new Date().toISOString();

    emit({
      type: 'object_progress',
      data: {
        objectId: obj.id, objectName: obj.name, nodeId,
        totalFiles: obj.files.length,
        files: obj.files.map(f => ({ path: f.path, category: f.category, producer: f.producer, content: f.content }))
      }
    });

    await dispatchToDownstream(nodeId, obj, downstreamQueues, edgePortMap);
  }
}

/**
 * 预处理 Worker
 * 1→N (expand) 或 N→1 (pack) 分发，取决于 outputMode 配置。
 */
export async function preprocessorWorker(
  nodeId: string,
  inputQueue: AsyncQueue<PipelineObject>,
  downstreamQueues: Map<string, AsyncQueue<PipelineObject>>,
  emit: (event: PipelineEventV2) => void,
  state: WorkerSharedState,
  edgePortMap: Map<string, string> = new Map()
): Promise<void> {
  const config = state.nodeConfigs.get(nodeId);
  const preprocessConfig = config?.preprocessConfig;

  while (!state.stopRequested) {
    await waitIfPaused(state);
    if (state.stopRequested) break;

    const obj = inputQueue.dequeueSync();
    if (!obj) {
      await sleep(1000);
      continue;
    }

    obj.status = 'running';
    obj.currentNodeId = nodeId;

    emit({
      type: 'preprocess_start',
      data: { nodeId, objectId: obj.id, objectName: obj.name, stageCount: preprocessConfig?.stages?.filter(s => s.enabled).length || 0 }
    });

    try {
      // 获取输入文本（合并所有 input 文件）
      const inputText = obj.files
        .filter(f => f.category === 'input')
        .map(f => f.content)
        .join('\n\n');

      // 运行预处理管线
      const stages = preprocessConfig?.stages || [];
      const outputMode = preprocessConfig?.outputMode || 'expand';
      const segments = await runPreprocessPipeline(inputText, stages);

      emit({
        type: 'preprocess_progress',
        data: { nodeId, objectId: obj.id, totalSegments: segments.length, outputMode }
      });

      if (outputMode === 'pack') {
        // ── 归并模式 (N→1)：所有分块打包进一个对象 ──
        const segmentFiles = segments.map((seg, i) => ({
          path: `${seg.meta.title || `chunk_${i + 1}`}.md`,
          content: seg.content
        }));
        const packedObj = createPipelineObject(
          `${obj.name}_预处理结果`,
          segmentFiles
        );
        packedObj.meta = { rejectCount: 0, maxRejects: 3, totalChunks: segments.length, outputMode: 'pack' };
        packedObj.status = 'completed';
        packedObj.completedAt = new Date().toISOString();

        state.allObjects.push(packedObj);

        emit({
          type: 'object_init',
          data: { objectId: packedObj.id, objectName: packedObj.name, totalChunks: segments.length, outputMode: 'pack' }
        });
        for (const [, downQueue] of downstreamQueues) {
          await downQueue.enqueue(packedObj);
        }
      } else {
        // ── 分流模式 (1→N)：每个分块独立为 PipelineObject ──
        // 批量创建对象并一次性发送 objects_init（避免 N 个 event 导致 SSE 背压）
        const chunkObjects: PipelineObject[] = [];
        for (const seg of segments) {
          const chunkObj = createPipelineObject(
            seg.meta.title || `${obj.name}_块${seg.meta.index + 1}`,
            [{ path: `${obj.name}_块${seg.meta.index + 1}.md`, content: seg.content }]
          );
          chunkObj.meta = {
            rejectCount: 0,
            maxRejects: 3,
            chunkIndex: seg.meta.index,
            totalChunks: segments.length,
            outputMode: 'expand'
          };
          chunkObj.status = 'completed';
          chunkObj.completedAt = new Date().toISOString();
          chunkObjects.push(chunkObj);
        }

        // 批量发送一个聚合事件
        emit({
          type: 'objects_init',
          data: {
            count: chunkObjects.length,
            objects: chunkObjects.map(o => ({
              id: o.id, name: o.name, chunkIndex: o.meta?.chunkIndex, totalChunks: o.meta?.totalChunks
            }))
          }
        });

        // 添加到全局对象列表（供 pipeline_complete 收集）
        for (const chunkObj of chunkObjects) {
          state.allObjects.push(chunkObj);
        }

        // 分发到下游
        for (const chunkObj of chunkObjects) {
          for (const [, downQueue] of downstreamQueues) {
            await downQueue.enqueue(chunkObj);
          }
        }
      }
    } catch (err: any) {
      emit({
        type: 'preprocess_error',
        data: { nodeId, objectId: obj.id, objectName: obj.name, error: err.message }
      });
      obj.status = 'failed';
    }

    if ((obj.status as string) !== 'failed') {
      obj.status = 'completed';
      obj.completedAt = new Date().toISOString();
    }
    // 不 dispatch 原始对象——预处理节点消费上游对象，产出新对象到下游
  }
}

// ======================== 世界书总结触发器 ========================

function tryEnqueueWorldBookTask(
  nodeId: string,
  obj: PipelineObject,
  state: WorkerSharedState,
  producerId: string,
  triggeredBy: string,
  chatContent: string
): void {
  if (!state.worldbookTaskQueue) return;

  const nodeConfig = state.nodeConfigs.get(nodeId);
  if (!nodeConfig?.worldbookSummaryConfig?.enableWorldBookSummary) return;

  const cfg = nodeConfig.worldbookSummaryConfig;
  const shouldTrigger = cfg.triggerGranularity === 'per_round'
    ? triggeredBy.endsWith('round_complete')
    : triggeredBy.endsWith('complete') && !triggeredBy.includes('round');

  if (!shouldTrigger) return;

  const task: WorldBookSummaryTask = {
    taskId: `wbt_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    nodeId,
    nodeType: nodeConfig.isContainer ? 'group_chat' : 'expert',
    objectId: obj.id,
    objectName: obj.name,
    targetBookId: cfg.targetBookId || 'default',
    summaryConfig: cfg,
    chatContent,
    existingEntries: state.worldbookEntries.get(cfg.targetBookId || 'default') || [],
    triggeredBy,
    timestamp: new Date().toISOString()
  };

  state.worldbookTaskQueue.enqueue(task).catch(() => {});
}

// ======================== 世界书观察者 Worker ========================

/**
 * 世界书观察者 Worker — 不参与 PipelineObject 数据流。
 * 监听专用 worldbookTaskQueue，对每个任务调用 WorldBookManagerService 分析聊天内容并更新世界书条目。
 */
export async function worldbookObserverWorker(
  _nodeId: string,
  _inputQueue: AsyncQueue<PipelineObject>,
  _downstreamQueues: Map<string, AsyncQueue<PipelineObject>>,
  emit: (event: PipelineEventV2) => void,
  state: WorkerSharedState
): Promise<void> {
  const taskQueue = state.worldbookTaskQueue;
  if (!taskQueue) return;

  // lazy import to avoid circular dependency
  const { WorldBookManagerService } = await import('./worldbook-manager-service');

  // 需要 projectPath 来构造 WorldBookManagerService
  // 从 globalConfig 或 state 中获取 — 暂时硬编码从 data/projects 推导
  const projectPath = (state as any)._projectPath as string || '';

  const wbEventEmitter = (event: { type: string; data: Record<string, unknown> }) => {
    emit(event as PipelineEventV2);
  };

  const manager = new WorldBookManagerService(projectPath, wbEventEmitter);

  while (!state.stopRequested) {
    await new Promise<void>(resolve => {
      const check = () => {
        if (state.stopRequested) { resolve(); return; }
        resolve();
      };
      setTimeout(check, 100);
    });
    if (state.stopRequested) break;

    const task = taskQueue.dequeueSync();
    if (!task) {
      await sleep(1000);
      continue;
    }

    try {
      await manager.processTask(task);
    } catch (err: any) {
      emit({
        type: 'worldbook_task_complete',
        data: { taskId: task.taskId, nodeId: task.nodeId, error: `Manager error: ${err.message}`, totalActions: 0, appliedCount: 0 }
      });
    }
  }
}
