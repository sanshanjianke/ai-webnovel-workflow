// 流水线引擎 - 真正的生产者-消费者模式
import { 
  MeetingConfig, ExpertConfig, ContainerConfig, 
  ExpertOpinion, ExpertRole, Granularity,
  PipelineOutput, ExpertContext
} from '../protocols';
import { createExpert } from '../experts';
import type { BaseExpert } from '../experts/base';
import { AsyncQueue } from '../utils/queue';

interface PipelineNode {
  id: string;
  expertId: string;
  role: ExpertRole;
  containerId?: string;
  upstream: string[];
  downstream: string[];
}

interface FileTask {
  index: number;
  total: number;
  content: Record<string, string>;
  upstreamOutputs?: Record<string, string>;
  isLastFile?: boolean;
}

export interface PipelineEvent {
  type: string;
  data: Record<string, unknown>;
}

export class PipelineEngine {
  private config: MeetingConfig;
  private nodes: Map<string, PipelineNode> = new Map();
  private nodeQueues: Map<string, AsyncQueue<FileTask>> = new Map();
  private totalSpeeches: number = 0;
  private state: 'idle' | 'running' | 'completed' | 'stopped' = 'idle';
  private stopRequested: boolean = false;
  private eventQueue: AsyncQueue<PipelineEvent> = new AsyncQueue();
  private nodeOutputs: Map<string, string> = new Map();
  private completedConsumers: Set<string> = new Set();
  private totalFiles: number = 0;
  private processedFiles: number = 0;

  constructor(config: MeetingConfig) {
    this.config = config;
    this.buildGraph();
  }

  private buildGraph(): void {
    for (const ec of this.config.experts) {
      const nodeId = ec.nodeId || ec.expertId;
      const key = ec.containerId || nodeId;
      
      if (!this.nodes.has(key)) {
        this.nodes.set(key, {
          id: key,
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
          if (!sourceNode.downstream.includes(target)) {
            sourceNode.downstream.push(target);
          }
          if (!targetNode.upstream.includes(source)) {
            targetNode.upstream.push(source);
          }
        }
      }
    }

    for (const nodeId of this.nodes.keys()) {
      this.nodeQueues.set(nodeId, new AsyncQueue<FileTask>());
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

  private async processNodeConsumer(nodeId: string): Promise<void> {
    const node = this.nodes.get(nodeId);
    if (!node) return;

    const queue = this.nodeQueues.get(nodeId);
    if (!queue) return;

    let emptyCount = 0;

    while (!this.stopRequested) {
      // 检查队列是否有任务
      if (queue.isEmpty()) {
        emptyCount++;
        
        // 检查是否所有上游都已完成
        const allUpstreamDone = node.upstream.every(upId => this.completedConsumers.has(upId));
        
        // 如果所有上游完成且队列为空，再等待一段时间确保没有新任务
        // 对于根节点（没有上游），需要等待更长时间确保下游节点收到所有任务
        const waitThreshold = node.upstream.length === 0 ? 200 : 50;
        if (allUpstreamDone && emptyCount > waitThreshold) {
          break;
        }
        
        // 等待一下再检查
        await new Promise(resolve => setTimeout(resolve, 100));
        continue;
      }

      emptyCount = 0;
      const task = queue.dequeueSync();
      if (!task) {
        continue;
      }

      this.totalSpeeches++;

      const expertStartEvent = {
        type: 'expert_start',
        data: {
          expertId: node.expertId,
          expertType: createExpert(node.expertId, node.role, this.config.granularity).expertType,
          role: node.role,
          nodeId,
          fileIndex: task.index,
          fileTotal: task.total,
          speechCount: this.totalSpeeches
        }
      };
      this.eventQueue.enqueue(expertStartEvent);

      const context: ExpertContext = {
        vision: task.content,
        worldbook: '',
        rag: '',
        history: [],
        customPrompt: task.upstreamOutputs 
          ? `上游节点产出：\n${Object.entries(task.upstreamOutputs).map(([k, v]) => `### ${k}\n${v}`).join('\n\n---\n\n')}`
          : undefined
      };

      const expert = createExpert(node.expertId, node.role, this.config.granularity);
      let fullContent = '';

      for await (const chunk of expert.speakStream(context)) {
          if (chunk.type === '__done__') {
            this.eventQueue.enqueue({
              type: 'expert_speak',
              data: {
                type: 'expert',
                expertId: node.expertId,
                expertType: expert.expertType,
                role: node.role,
                content: fullContent,
                nodeId,
                fileIndex: task.index,
                speechCount: this.totalSpeeches
              }
            });
        } else {
          fullContent += chunk.content || '';
          this.eventQueue.enqueue({
            type: 'expert_chunk',
            data: {
              chunkType: chunk.type,
              content: chunk.content,
              expertId: node.expertId,
              nodeId,
              fileIndex: task.index
            }
          });
        }
      }

      // 保存节点输出
      this.nodeOutputs.set(`${nodeId}_${task.index}`, fullContent);

      // 把产出传递给下游节点
      for (const downstreamId of node.downstream) {
        const downstreamQueue = this.nodeQueues.get(downstreamId);
        if (downstreamQueue) {
          await downstreamQueue.enqueue({
            index: task.index,
            total: task.total,
            content: task.content,
            upstreamOutputs: {
              ...task.upstreamOutputs,
              [nodeId]: fullContent
            }
          });
        }
      }

      this.processedFiles++;
    }

    this.completedConsumers.add(nodeId);
  }

  async *processQueue(
    files: Array<{ index: number; content: Record<string, string> }>,
    contextInput: Record<string, string>,
    worldbookText: string = '',
    ragContext: string = ''
  ): AsyncGenerator<PipelineEvent> {
    this.state = 'running';
    this.totalSpeeches = 0;
    this.stopRequested = false;
    this.nodeOutputs.clear();
    this.completedConsumers.clear();
    this.totalFiles = files.length;
    this.processedFiles = 0;

    const rootNodes = Array.from(this.nodes.values()).filter(n => n.upstream.length === 0);
    
    if (rootNodes.length === 0) {
      yield {
        type: 'error',
        data: { message: '没有找到根节点' }
      };
      return;
    }

    // 启动所有节点的消费者（不等待完成）
    const consumerPromises: Promise<void>[] = [];
    for (const nodeId of this.nodes.keys()) {
      const promise = this.processNodeConsumer(nodeId);
      consumerPromises.push(promise);
    }

    // 只为根节点发送队列初始化事件
    for (const rootNode of rootNodes) {
      const fileNames = files.map((_, i) => `文件${i + 1}`);
      yield {
        type: 'queue_init',
        data: { 
          nodeId: rootNode.id,
          expertId: rootNode.expertId,
          total: files.length, 
          fileNames: fileNames
        }
      };
    }

    // 把文件分发到根节点
    for (const file of files) {
      if (this.stopRequested) break;

      for (const rootNode of rootNodes) {
        const queue = this.nodeQueues.get(rootNode.id);
        if (queue) {
          await queue.enqueue({
            index: file.index,
            total: files.length,
            content: file.content
          });
        }
      }
    }

    // 消费事件队列
    while (!this.stopRequested) {
      try {
        const event = await Promise.race([
          this.eventQueue.dequeue(),
          new Promise<null>((resolve) => setTimeout(() => resolve(null), 500))
        ]);
        
        if (event) {
          yield event;
        }
        
        // 检查是否所有任务完成
        const allConsumersDone = this.completedConsumers.size >= this.nodes.size;
        
        if (allConsumersDone && this.eventQueue.isEmpty()) {
          break;
        }
      } catch (e) {
        break;
      }
    }

    // 收集输出 - 只收集叶子节点（没有下游的节点）
    const leafNodes = Array.from(this.nodes.values())
      .filter(n => n.downstream.length === 0)
      .map(n => n.id);
    
    const nodeOutputs: Record<string, Record<number, string>> = {};
    for (const [key, content] of this.nodeOutputs) {
      const parts = key.split('_');
      const nodeId = parts[0];
      const fileIndex = parseInt(parts[1]) || 0;
      
      // 只收集叶子节点的输出
      if (!leafNodes.includes(nodeId)) continue;
      
      if (!nodeOutputs[nodeId]) {
        nodeOutputs[nodeId] = {};
      }
      nodeOutputs[nodeId][fileIndex] = content;
    }

    // 生成摘要 - 每个节点的每个文件单独显示
    const meetingSummary = Object.entries(nodeOutputs)
      .map(([nodeId, files]) => {
        const fileEntries = Object.entries(files)
          .sort(([a], [b]) => parseInt(a) - parseInt(b))
          .map(([idx, content]) => `### 文件${parseInt(idx) + 1}\n${content}`)
          .join('\n\n');
        return `## ${nodeId}\n${fileEntries}`;
      })
      .join('\n\n---\n\n');

    // 为了兼容下载功能，将输出格式转换为按节点-文件索引存储
    const flatOutputs: Record<string, string> = {};
    for (const [nodeId, files] of Object.entries(nodeOutputs)) {
      for (const [idx, content] of Object.entries(files)) {
        flatOutputs[`${nodeId}_file${parseInt(idx) + 1}`] = content;
      }
    }

    this.state = 'completed';

    yield {
      type: 'queue_complete',
      data: { total: files.length }
    };

    yield {
      type: 'pipeline_complete',
      data: {
        output: {
          nodeOutputs: flatOutputs,
          totalSpeeches: this.totalSpeeches,
          meetingSummary
        }
      }
    };
  }

  stop(): void {
    this.stopRequested = true;
    this.state = 'stopped';
    
    for (const queue of this.nodeQueues.values()) {
      queue.clear();
    }
    this.eventQueue.clear();
  }

  getState(): string {
    return this.state;
  }

  getTotalSpeeches(): number {
    return this.totalSpeeches;
  }
}
