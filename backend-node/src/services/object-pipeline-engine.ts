// 对象管道引擎 v2 — 分布式 Worker 模型
// 每个节点是独立 async 函数，while 轮询自己的队列。
// 引擎只管：建 Worker、收集事件、yield 给 SSE、stop/pause/checkpoint。
import {
  MeetingConfig, ExpertRole, Granularity, ContainerConfig,
  AgentStopConfig, PipelineObject
} from '../protocols';
import { AsyncQueue } from '../utils/queue';
import { CheckpointState, saveCheckpoint, deleteCheckpoint } from './recovery-manager';
import {
  WorkerSharedState, NodeWorkerConfig,
  DEFAULT_STOP_CONFIG, DEFAULT_READ_CATEGORIES,
  inputSourceWorker, expertWorker, groupChatWorker, outputWorker
} from './pipeline-workers';

// ======================== 事件类型 ========================

export interface PipelineEventV2 {
  type: string;
  data: Record<string, unknown>;
}

// ======================== 内部图节点 ========================

interface InternalNode {
  id: string;
  type: 'input' | 'expert' | 'group_chat' | 'output';
  expertId: string;
  role: ExpertRole;
  containerId?: string;
  upstream: string[];
  downstream: string[];
  isContainer?: boolean;
  children?: string[];
  containerConfig?: ContainerConfig;
  childrenRoles?: Map<string, ExpertRole>;
}

// ======================== 引擎类 ========================

export class ObjectPipelineEngine {
  private config: MeetingConfig;
  private nodes: Map<string, InternalNode> = new Map();
  private agentConfigs: Map<string, AgentStopConfig> = new Map();
  private readConfigs: Map<string, ('input' | 'report' | 'chat_log')[]> = new Map();
  private state: 'idle' | 'running' | 'completed' | 'stopped' = 'idle';
  private stopRequested: boolean = false;
  private pendingFeedback: Map<string, string[]> = new Map();
  private activeQueues: Map<string, AsyncQueue<PipelineObject>> | null = null;
  private activeSharedState: WorkerSharedState | null = null;
  private activeEventBus: AsyncQueue<PipelineEventV2> | null = null;
  meetingId: string = '';
  checkpointDir: string = '';

  constructor(config: MeetingConfig) {
    this.config = config;
    this.buildGraph();
  }

  // ======================== 公开 API ========================

  injectFeedback(nodeId: string, message: string): void {
    if (!this.pendingFeedback.has(nodeId)) {
      this.pendingFeedback.set(nodeId, []);
    }
    this.pendingFeedback.get(nodeId)!.push(message);
  }

  setAgentConfig(nodeId: string, config: AgentStopConfig): void {
    this.agentConfigs.set(nodeId, config);
  }

  setReadConfig(nodeId: string, categories: ('input' | 'report' | 'chat_log')[]): void {
    this.readConfigs.set(nodeId, categories);
  }

  stop(): void {
    this.stopRequested = true;
    this.state = 'stopped';
    if (this.activeSharedState) {
      this.activeSharedState.stopRequested = true;
    }
    if (this.activeEventBus) {
      try { this.activeEventBus.close(); } catch {}
    }
    if (this.activeQueues) {
      for (const q of this.activeQueues.values()) {
        try { q.close(); } catch {}
      }
    }
  }

  getState(): string {
    return this.state;
  }

  // ======================== 图构建 ========================

  private buildGraph(): void {
    const expertToContainer = new Map<string, string>();
    for (const ec of this.config.experts) {
      if (ec.containerId) expertToContainer.set(ec.expertId, ec.containerId);
    }

    for (const cc of this.config.containers || []) {
      const containerId = cc.containerId;
      const children = [...(cc.children || [])];
      for (const ec of this.config.experts) {
        if (ec.containerId === containerId && !children.includes(ec.expertId)) {
          children.push(ec.expertId);
        }
      }

      const childrenRoles = new Map<string, ExpertRole>();
      for (const childId of children) {
        const ec = this.config.experts.find(e => e.expertId === childId);
        childrenRoles.set(childId, ec?.role || ExpertRole.MAIN);
      }

      this.nodes.set(containerId, {
        id: containerId,
        type: 'group_chat',
        expertId: '',
        role: ExpertRole.MAIN,
        upstream: [],
        downstream: [],
        isContainer: true,
        children,
        containerConfig: cc,
        childrenRoles
      });
    }

    for (const ec of this.config.experts) {
      const nodeId = ec.nodeId || ec.expertId;
      const key = ec.containerId || nodeId;
      if (ec.containerId && this.nodes.has(ec.containerId)) continue;

      if (!this.nodes.has(key)) {
        this.nodes.set(key, {
          id: key,
          type: 'expert',
          expertId: ec.expertId,
          role: ec.role,
          containerId: ec.containerId,
          upstream: [],
          downstream: []
        });
      }
    }

    for (const edge of this.config.edges || []) {
      const source = this.findNodeKey(edge.source);
      const target = this.findNodeKey(edge.target);
      if (source && target) {
        const sourceNode = this.nodes.get(source);
        const targetNode = this.nodes.get(target);
        if (sourceNode && targetNode) {
          if (!sourceNode.downstream.includes(target)) sourceNode.downstream.push(target);
          if (!targetNode.upstream.includes(source)) targetNode.upstream.push(source);
        }
      }
    }

    const inputId = '__input_source__';
    if (!this.nodes.has(inputId)) {
      const roots = [...this.nodes.values()].filter(n => n.upstream.length === 0 && n.id !== inputId);
      this.nodes.set(inputId, {
        id: inputId, type: 'input', expertId: '', role: ExpertRole.MAIN,
        upstream: [], downstream: roots.map(r => r.id)
      });
      for (const root of roots) {
        if (!root.upstream.includes(inputId)) root.upstream.push(inputId);
      }
    }

    const outputId = '__output__';
    if (!this.nodes.has(outputId)) {
      const leaves = [...this.nodes.values()].filter(
        n => n.downstream.length === 0 && n.id !== outputId && n.id !== inputId
      );
      this.nodes.set(outputId, {
        id: outputId, type: 'output', expertId: '', role: ExpertRole.MAIN,
        upstream: leaves.map(l => l.id), downstream: []
      });
      for (const leaf of leaves) {
        if (!leaf.downstream.includes(outputId)) leaf.downstream.push(outputId);
      }
    }

    const inputNode = this.nodes.get(inputId);
    if (inputNode && inputNode.downstream.includes(outputId) && inputNode.downstream.length > 1) {
      inputNode.downstream = inputNode.downstream.filter(id => id !== outputId);
    }
  }

  private findNodeKey(vueId: string): string | null {
    if (this.nodes.has(vueId)) return vueId;
    for (const [key, node] of this.nodes) {
      if (node.containerId === vueId) return key;
    }
    for (const ec of this.config.experts) {
      if (ec.nodeId === vueId || ec.expertId === vueId) {
        return ec.containerId || ec.nodeId || ec.expertId;
      }
    }
    return null;
  }

  // ======================== 分布式处理入口 ========================

  async *processQueue(
    objects: PipelineObject[],
    visionInput: Record<string, string>,
    worldbookText: string = '',
    ragContext: string = '',
    resumeFrom?: CheckpointState
  ): AsyncGenerator<PipelineEventV2> {
    this.state = 'running';
    this.stopRequested = false;

    if (this.nodes.size === 0) {
      yield { type: 'error', data: { message: 'No nodes in pipeline graph' } };
      return;
    }

    const inputId = '__input_source__';
    const outputId = '__output__';

    // resume: 跳过已完成对象
    let activeObjects = objects;
    if (resumeFrom) {
      activeObjects = objects.filter(o => o.status !== 'completed');
    }

    // 构建共享状态
    const sharedState: WorkerSharedState = {
      stopRequested: false,
      pauseRequested: false,
      nodeConfigs: new Map(),
      globalConfig: this.config,
      feedbackMap: this.pendingFeedback,
      vision: visionInput,
      worldbook: worldbookText,
      rag: ragContext,
      outputSeq: { value: resumeFrom?.outputSeq || 0 }
    };
    this.activeSharedState = sharedState;

    // 为每个节点创建队列
    const queues = new Map<string, AsyncQueue<PipelineObject>>();
    for (const [nodeId] of this.nodes) {
      queues.set(nodeId, new AsyncQueue<PipelineObject>());
    }
    this.activeQueues = queues;

    // 构建下游映射
    const downstreamMap = new Map<string, Map<string, AsyncQueue<PipelineObject>>>();
    for (const [nodeId] of this.nodes) {
      downstreamMap.set(nodeId, new Map());
    }
    for (const [nodeId, node] of this.nodes) {
      for (const downId of node.downstream) {
        const toQueue = queues.get(downId);
        if (toQueue) downstreamMap.get(nodeId)!.set(downId, toQueue);
      }
    }

    // 填充 node configs
    for (const [nodeId, node] of this.nodes) {
      sharedState.nodeConfigs.set(nodeId, {
        nodeId,
        expertId: node.expertId,
        role: node.role,
        containerId: node.containerId,
        stopConfig: this.agentConfigs.get(nodeId) || { ...DEFAULT_STOP_CONFIG },
        readCategories: this.readConfigs.get(nodeId) || [...DEFAULT_READ_CATEGORIES],
        isContainer: node.isContainer,
        children: node.children,
        childrenRoles: node.childrenRoles,
        containerConfig: node.containerConfig
      });
    }

    // 事件队列 — emit 回调往里塞，引擎从这取并 yield 给 SSE
    const eventQueue = new AsyncQueue<PipelineEventV2>();
    this.activeEventBus = eventQueue;
    const emit = (event: PipelineEventV2) => {
      eventQueue.enqueue(event).catch(() => {});
    };

    // yield 启动事件
    const allNodeIds = [...this.nodes.keys()].filter(id => id !== inputId && id !== outputId);
    yield {
      type: 'pipeline_start_v2',
      data: {
        meetingId: this.meetingId,
        nodes: allNodeIds,
        totalObjects: activeObjects.length,
        objects: activeObjects.map(o => ({
          id: o.id,
          name: o.name,
          files: o.files.map(f => ({ path: f.path, category: f.category, producer: f.producer }))
        }))
      }
    };

    // 启动所有 Worker（Promise，后台运行）
    const workerPromises: Promise<void>[] = [];
    for (const [nodeId, node] of this.nodes) {
      const inQueue = queues.get(nodeId)!;
      const downQueues = downstreamMap.get(nodeId)!;

      let promise: Promise<void>;
      switch (node.type) {
        case 'input':
          promise = inputSourceWorker(nodeId, inQueue, downQueues, emit, sharedState, activeObjects);
          break;
        case 'expert':
          promise = expertWorker(nodeId, inQueue, downQueues, emit, sharedState);
          break;
        case 'group_chat':
          promise = groupChatWorker(nodeId, inQueue, downQueues, emit, sharedState);
          break;
        case 'output':
          promise = outputWorker(nodeId, inQueue, downQueues, emit, sharedState);
          break;
      }
      workerPromises.push(promise);
    }

    // 消费事件，yield 给 SSE
    let completedCount = 0;
    const workersDone = Promise.all(workerPromises);

    try {
      while (!this.stopRequested && !sharedState.stopRequested) {
        let event: PipelineEventV2;
        try {
          event = await eventQueue.dequeue();
        } catch {
          break;
        }

        yield event;

        if (event.type === 'object_complete') {
          completedCount++;
          if (this.checkpointDir && this.meetingId) {
            try {
              saveCheckpoint(
                this.checkpointDir, this.meetingId, this.meetingId,
                this.config, activeObjects,
                completedCount, [], sharedState.outputSeq.value
              );
            } catch {}
          }

          if (completedCount >= activeObjects.length) {
            // 全部完成，通知 Workers 退出
            sharedState.stopRequested = true;
            for (const q of queues.values()) q.close();
            eventQueue.close();
            break;
          }
        }
      }
    } finally {
      sharedState.stopRequested = true;
      for (const q of queues.values()) {
        try { q.close(); } catch {}
      }
      try { eventQueue.close(); } catch {}
    }

    // 等待 Workers 退出
    try { await workersDone; } catch {}

    this.state = this.stopRequested ? 'stopped' : 'completed';
    this.activeSharedState = null;
    this.activeEventBus = null;
    this.activeQueues = null;

    if (this.state === 'completed' && this.checkpointDir && this.meetingId) {
      deleteCheckpoint(this.checkpointDir, this.meetingId);
    }

    // pipeline_complete — 从对象中提取产出文件
    const nodeOutputs: Record<string, string> = {};
    const reportFiles: string[] = [];
    for (const obj of activeObjects) {
      for (const f of obj.files) {
        if (f.category === 'report' && f.content) {
          const key = f.producer && f.producer !== 'input'
            ? `${obj.name}_${f.producer}_${f.path}`
            : `${obj.name}_${f.path}`;
          nodeOutputs[key] = f.content;
          reportFiles.push(f.path);
        }
      }
    }
    const meetingSummary = activeObjects.map(o =>
      `## ${o.name}\n${o.files.filter(f => f.category === 'report').map(f => f.content).join('\n\n')}`
    ).join('\n\n---\n\n');

    yield {
      type: 'pipeline_complete',
      data: {
        objects: activeObjects.map(o => ({
          id: o.id, name: o.name, status: o.status,
          files: o.files.map(f => ({
            path: f.path, category: f.category, producer: f.producer,
            ...(f.category === 'report' ? { content: f.content } : {})
          }))
        })),
        output: {
          nodeOutputs,
          meetingSummary
        }
      }
    };
  }
}
