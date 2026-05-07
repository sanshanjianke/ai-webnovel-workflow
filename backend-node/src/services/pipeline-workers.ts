// 分布式 Worker 实现
// 每个 Worker 是独立 async 函数，while 循环轮询自己的队列。
// 不做的事：不推事件到总线、不感知全局状态、不管理其他节点。
// 做的事：检查队列 → 处理对象 → 推到下游 → 检查 stop/pause 信号。

import {
  MeetingConfig, ExpertRole, Granularity, ContainerConfig,
  AgentStopConfig, PipelineObject, ExpertContext, ExpertChatLog
} from '../protocols';
import { createExpert } from '../experts';
import type { BaseExpert } from '../experts/base';
import { addExpertOutput, buildObjectContext } from '../models/pipeline-object';
import { AsyncQueue } from '../utils/queue';
import { PipelineEventV2 } from './object-pipeline-engine';

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
}

export interface WorkerSharedState {
  stopRequested: boolean;
  pauseRequested: boolean;
  nodeConfigs: Map<string, NodeWorkerConfig>;
  globalConfig: MeetingConfig;
  feedbackMap: Map<string, string[]>;
  vision: Record<string, string>;
  worldbook: string;
  rag: string;
  outputSeq: { value: number };
}

export const DEFAULT_STOP_CONFIG: AgentStopConfig = {
  enableTagStop: true,
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
    worldbook: state.worldbook,
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
      }

      if (agentEvent.type === 'agent_complete') {
        const report = (agentEvent.data.report as string) || '';
        const chatLog = agentEvent.data.chatLog as ExpertChatLog;
        state.outputSeq.value++;
        addExpertOutput(obj, expert.expertId, expert.expertType, report, chatLog, state.outputSeq.value);
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
        worldbook: state.worldbook,
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

    roundNum++;
  }

  // 持久化群聊产出
  for (const expertId of children) {
    const role = childrenRoles.get(expertId) || ExpertRole.MAIN;
    const expert = createExpert(expertId, role, state.globalConfig.granularity);
    const mySpeeches = groupChatLog.rounds
      .flatMap(r => r.speeches)
      .filter(s => s.expertId === expertId);

    const finalContent = mySpeeches.map(s => s.content).join('\n\n---\n\n');
    const report = finalContent || '';

    const chatLog: ExpertChatLog = {
      expertId,
      expertType: expert.expertType,
      objectId: obj.id,
      reportFile: `${expert.expertType}_群聊报告.md`,
      startedAt: new Date().toISOString(),
      completedAt: new Date().toISOString(),
      rounds: groupChatLog.rounds.map(r => ({
        round: r.round,
        messages: r.speeches
          .filter(s => s.expertId === expertId)
          .map(s => ({
            role: 'assistant' as const,
            thinking: s.thinking,
            content: s.content,
            timestamp: s.timestamp
          })),
        completedAt: new Date().toISOString()
      }))
    };

    addExpertOutput(obj, expertId, expert.expertType, report, chatLog, state.outputSeq.value);
    state.outputSeq.value++;
  }

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
  initialObjects: PipelineObject[]
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
  state: WorkerSharedState
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

    for (const [, downQueue] of downstreamQueues) {
      await downQueue.enqueue(obj);
    }
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

    obj.status = 'running';
    obj.currentNodeId = nodeId;

    await processGroupChatNode(nodeId, obj, emit, state);

    if ((obj.status as string) !== 'failed') {
      obj.status = 'completed';
      obj.completedAt = new Date().toISOString();
    }

    for (const [, downQueue] of downstreamQueues) {
      await downQueue.enqueue(obj);
    }
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
