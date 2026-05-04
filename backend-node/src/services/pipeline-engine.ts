// 流水线引擎 - 实现真正的生产者-消费者模式
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
  nodeOutputs: Map<string, string>;
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

  constructor(config: MeetingConfig) {
    this.config = config;
    this.buildGraph();
  }

  private buildGraph(): void {
    // 构建节点图
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

    // 构建边
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

    // 为每个节点创建队列
    for (const nodeId of this.nodes.keys()) {
      this.nodeQueues.set(nodeId, new AsyncQueue<FileTask>());
    }
  }

  private findNodeKey(vueId: string): string | null {
    // 先直接查找
    if (this.nodes.has(vueId)) return vueId;
    
    // 查找 containerId 匹配
    for (const [key, node] of this.nodes) {
      if (node.containerId === vueId) return key;
    }
    
    // 查找 expertId 匹配
    for (const ec of this.config.experts) {
      if (ec.nodeId === vueId || ec.expertId === vueId) {
        return ec.containerId || ec.nodeId || ec.expertId;
      }
    }
    
    return null;
  }

  private getTopologicalOrder(): string[][] {
    const inDegree = new Map<string, number>();
    const outEdges = new Map<string, string[]>();

    // 初始化
    for (const nodeId of this.nodes.keys()) {
      inDegree.set(nodeId, 0);
      outEdges.set(nodeId, []);
    }

    // 计算入度和出边
    for (const node of this.nodes.values()) {
      for (const downstream of node.downstream) {
        inDegree.set(downstream, (inDegree.get(downstream) || 0) + 1);
        outEdges.get(node.id)?.push(downstream);
      }
    }

    // 拓扑排序（层级分组）
    const levels: string[][] = [];
    let queue = Array.from(this.nodes.keys()).filter(id => (inDegree.get(id) || 0) === 0);

    while (queue.length > 0) {
      levels.push([...queue]);
      
      const nextQueue: string[] = [];
      for (const nodeId of queue) {
        for (const downstream of outEdges.get(nodeId) || []) {
          const newDegree = (inDegree.get(downstream) || 1) - 1;
          inDegree.set(downstream, newDegree);
          if (newDegree === 0) {
            nextQueue.push(downstream);
          }
        }
      }
      queue = nextQueue;
    }

    return levels;
  }

  // 主运行方法 - 处理单个文件
  async *processFile(
    fileTask: FileTask,
    contextInput: Record<string, string>,
    worldbookText: string = '',
    ragContext: string = ''
  ): AsyncGenerator<PipelineEvent> {
    const levels = this.getTopologicalOrder();
    
    yield {
      type: 'level_start',
      data: {
        level: 1,
        totalLevels: levels.length,
        nodes: levels[0] || [],
        fileIndex: fileTask.index
      }
    };

    for (let levelIdx = 0; levelIdx < levels.length; levelIdx++) {
      const level = levels[levelIdx];
      
      yield {
        type: 'level_start',
        data: {
          level: levelIdx + 1,
          totalLevels: levels.length,
          nodes: level,
          fileIndex: fileTask.index
        }
      };

      // 并行处理同一层级的节点
      const levelPromises = level.map(async (nodeId) => {
        const node = this.nodes.get(nodeId);
        if (!node) return;

        // 收集上游输出
        const upstreamOutputs: string[] = [];
        for (const upstreamId of node.upstream) {
          const upstreamOutput = fileTask.nodeOutputs.get(upstreamId);
          if (upstreamOutput) {
            upstreamOutputs.push(upstreamOutput);
          }
        }

        // 构建上下文
        const context: ExpertContext = {
          vision: contextInput,
          worldbook: worldbookText,
          rag: ragContext,
          history: [],
          customPrompt: upstreamOutputs.length > 0 
            ? `上游节点产出：\n${upstreamOutputs.join('\n\n---\n\n')}`
            : undefined
        };

        // 判断是容器还是单独专家
        const container = this.config.containers?.find(c => c.containerId === nodeId);
        
        if (container) {
          // 容器处理
          return this.processContainer(container, context, fileTask, nodeId);
        } else {
          // 单独专家处理
          return this.processSingleExpert(node, context, fileTask, nodeId);
        }
      });

      // 等待当前层级所有节点完成
      const results = await Promise.all(levelPromises);
      
      // 收集输出
      for (const result of results) {
        if (result) {
          fileTask.nodeOutputs.set(result.nodeId, result.content);
        }
      }

      yield {
        type: 'level_complete',
        data: {
          level: levelIdx + 1,
          fileIndex: fileTask.index
        }
      };
    }
  }

  private async processContainer(
    container: ContainerConfig,
    context: ExpertContext,
    fileTask: FileTask,
    nodeId: string
  ): Promise<{ nodeId: string; content: string }> {
    const outputParts: string[] = [];
    const children = container.children || [];

    for (const childId of children) {
      const expertConfig = this.config.experts.find(ec => 
        (ec.containerId || ec.nodeId || ec.expertId) === childId
      );
      
      if (!expertConfig) continue;

      const expert = createExpert(expertConfig.expertId, expertConfig.role, this.config.granularity);
      this.totalSpeeches++;

      const opinion = await expert.speak(context);
      outputParts.push(`### ${expert.expertType}\n${opinion.content}`);
    }

    return {
      nodeId,
      content: outputParts.join('\n\n')
    };
  }

  private async processSingleExpert(
    node: PipelineNode,
    context: ExpertContext,
    fileTask: FileTask,
    nodeId: string
  ): Promise<{ nodeId: string; content: string }> {
    const expert = createExpert(node.expertId, node.role, this.config.granularity);
    this.totalSpeeches++;

    const opinion = await expert.speak(context);
    
    return {
      nodeId,
      content: opinion.content
    };
  }

  // 处理文件队列
  async *processQueue(
    files: Array<{ index: number; content: Record<string, string> }>,
    contextInput: Record<string, string>,
    worldbookText: string = '',
    ragContext: string = ''
  ): AsyncGenerator<PipelineEvent> {
    this.state = 'running';
    this.totalSpeeches = 0;

    yield {
      type: 'queue_start',
      data: { total: files.length }
    };

    const allOutputs: Map<string, string>[] = [];

    for (const file of files) {
      if (this.stopRequested) {
        yield {
          type: 'pipeline_stopped',
          data: { reason: 'user_stopped' }
        };
        break;
      }

      yield {
        type: 'queue_item_start',
        data: { index: file.index, total: files.length }
      };

      const fileTask: FileTask = {
        index: file.index,
        total: files.length,
        content: file.content,
        nodeOutputs: new Map()
      };

      // 处理单个文件
      for await (const event of this.processFile(fileTask, contextInput, worldbookText, ragContext)) {
        yield event;
      }

      allOutputs.push(fileTask.nodeOutputs);

      yield {
        type: 'queue_item_complete',
        data: { index: file.index, total: files.length }
      };
    }

    // 汇总输出
    const nodeOutputs: Record<string, string> = {};
    for (const outputs of allOutputs) {
      for (const [nodeId, content] of outputs) {
        if (!nodeOutputs[nodeId]) {
          nodeOutputs[nodeId] = '';
        }
        nodeOutputs[nodeId] += '\n\n' + content;
      }
    }

    const meetingSummary = Object.entries(nodeOutputs)
      .map(([nodeId, content]) => `## ${nodeId}\n${content}`)
      .join('\n\n---\n\n');

    this.state = 'completed';

    yield {
      type: 'queue_complete',
      data: { total: files.length }
    };

    yield {
      type: 'pipeline_complete',
      data: {
        output: {
          nodeOutputs,
          totalSpeeches: this.totalSpeeches,
          meetingSummary
        }
      }
    };
  }

  stop(): void {
    this.stopRequested = true;
    this.state = 'stopped';
  }

  getState(): string {
    return this.state;
  }

  getTotalSpeeches(): number {
    return this.totalSpeeches;
  }
}
