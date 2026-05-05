// 会议引擎 - 核心实现
import { 
  MeetingConfig, ExpertConfig, ContainerConfig, 
  ExpertOpinion, ExpertRole, Granularity,
  MeetingOutput, Sequence, Character,
  ExpertContext, ExpertChunk
} from '../protocols';
import { createExpert } from '../experts';
import type { BaseExpert } from '../experts/base';
import { AsyncQueue } from '../utils/queue';

interface SpeakerEntry {
  expertId: string;
  role: ExpertRole;
  containerId?: string;
}

export interface MeetingEvent {
  type: string;
  data: Record<string, unknown>;
}

export class MeetingEngine {
  private config: MeetingConfig;
  private experts: Map<string, BaseExpert> = new Map();
  private meetingHistory: ExpertOpinion[] = [];
  private roundIdx: number = 0;
  private speechCount: number = 0;
  private state: 'idle' | 'running' | 'paused' | 'completed' | 'stopped' = 'idle';
  private forceNextExpert: string | null = null;
  private stopRequested: boolean = false;
  
  // 容器状态
  private containerMap: Map<string, ContainerConfig> = new Map();
  private expertContainers: Map<string, string> = new Map();
  private containerHistories: Map<string, ExpertOpinion[]> = new Map();
  private containerRounds: Map<string, number> = new Map();
  private containerExitRequested: Set<string> = new Set();

  constructor(config: MeetingConfig) {
    this.config = config;
    this.initContainers();
  }

  private initContainers(): void {
    this.containerMap.clear();
    this.expertContainers.clear();
    this.containerHistories.clear();
    this.containerRounds.clear();
    this.containerExitRequested.clear();

    for (const container of this.config.containers || []) {
      this.containerMap.set(container.containerId, container);
      this.containerHistories.set(container.containerId, []);
      this.containerRounds.set(container.containerId, 0);
      
      for (const childId of container.children || []) {
        this.expertContainers.set(childId, container.containerId);
      }
    }
  }

  private getExpertUniqueId(expertId: string, role: ExpertRole): string {
    return `${expertId}_${role}`;
  }

  private getExpert(expertId: string, role: ExpertRole): BaseExpert {
    const cacheKey = this.getExpertUniqueId(expertId, role);
    
    if (!this.experts.has(cacheKey)) {
      const expert = createExpert(expertId, role, this.config.granularity);
      this.experts.set(cacheKey, expert);
    }
    
    return this.experts.get(cacheKey)!;
  }

  private buildSpeakerPool(): SpeakerEntry[] {
    const pool: SpeakerEntry[] = [];
    
    for (const expertConfig of this.config.experts) {
      const containerId = this.expertContainers.get(
        this.getExpertUniqueId(expertConfig.expertId, expertConfig.role)
      );
      
      pool.push({
        expertId: expertConfig.expertId,
        role: expertConfig.role,
        containerId: containerId
      });
    }
    
    return pool;
  }

  private detectMention(text: string, containerId?: string): string | null {
    const mentionRegex = /@([^\s,，。！？…\n]{1,20})/g;
    const matches = text.matchAll(mentionRegex);
    
    const expertNames = new Map<string, string>();
    for (const ec of this.config.experts) {
      const expert = this.getExpert(ec.expertId, ec.role);
      expertNames.set(expert.expertType, ec.expertId);
      expertNames.set(ec.expertId, ec.expertId);
    }

    for (const match of matches) {
      const name = match[1];
      const targetId = expertNames.get(name);
      
      if (!targetId) continue;
      
      // 如果在容器内，只匹配同容器专家
      if (containerId) {
        const targetContainer = this.expertContainers.get(
          this.getExpertUniqueId(targetId, ExpertRole.MAIN)
        );
        if (targetContainer !== containerId) continue;
      }
      
      return targetId;
    }
    
    return null;
  }

  private shouldExit(): boolean {
    if (this.stopRequested) return true;
    if (this.config.maxSpeeches && this.speechCount >= this.config.maxSpeeches) return true;
    return false;
  }

  private formatOutput(): MeetingOutput {
    const sequences: Sequence[] = [];
    const characters: Character[] = [];
    const worldNotes: string[] = [];
    const suggestions: string[] = [];

    // 提取主发言人的建议
    for (const opinion of this.meetingHistory) {
      if (opinion.role === ExpertRole.MAIN) {
        for (const suggestion of opinion.suggestions) {
          if (suggestion.includes('卷') || suggestion.includes('章') || suggestion.includes('序列')) {
            sequences.push({
              name: suggestion,
              description: opinion.content.slice(0, 200)
            });
          }
        }
      }
      suggestions.push(...opinion.suggestions);
    }

    const meetingSummary = this.meetingHistory.map(op => 
      `### ${op.expertType} (${op.role})\n\n${op.content}`
    ).join('\n\n---\n\n');

    return {
      meetingName: this.config.meetingName,
      granularity: this.config.granularity,
      sequences,
      characters,
      worldNotes,
      meetingSummary,
      suggestions,
      totalRounds: this.roundIdx,
      totalSpeeches: this.speechCount
    };
  }

  // 主运行方法 - 异步生成器
  async *run(
    contextInput: Record<string, string>,
    worldbookText: string = '',
    ragContext: string = '',
    humanFeedback?: () => Promise<{ action: string; message?: string; expertId?: string } | null>
  ): AsyncGenerator<MeetingEvent> {
    this.meetingHistory = [];
    this.roundIdx = 0;
    this.speechCount = 0;
    this.state = 'running';
    this.forceNextExpert = null;
    this.stopRequested = false;
    this.initContainers();

    const speakerPool = this.buildSpeakerPool();
    let poolIdx = 0;

    while (!this.shouldExit()) {
      // 判断下一位发言人
      let expertId: string;
      let role: ExpertRole;
      let containerId: string | undefined;

      if (this.forceNextExpert) {
        expertId = this.forceNextExpert;
        role = ExpertRole.SUPPLEMENT;
        containerId = undefined;
        this.forceNextExpert = null;
      } else {
        const entry = speakerPool[poolIdx % speakerPool.length];
        expertId = entry.expertId;
        role = entry.role;
        containerId = entry.containerId;
        poolIdx++;
      }

      // 轮次播报
      if (poolIdx % speakerPool.length === 1) {
        this.roundIdx++;
        yield {
          type: 'round_start',
          data: {
            round: this.roundIdx,
            speechCount: this.speechCount,
            maxSpeeches: this.config.maxSpeeches || 0,
            meetingName: this.config.meetingName
          }
        };
      }

      const expert = this.getExpert(expertId, role);

      // 构建上下文
      const context: ExpertContext = {
        vision: contextInput,
        worldbook: worldbookText,
        rag: ragContext,
        round: this.roundIdx,
        speechCount: this.speechCount,
        history: [...this.meetingHistory],
        containerContext: containerId ? this.buildContainerContext(containerId) : undefined,
        customPrompt: this.getExpertConfig(expertId, role)?.customPrompt
      };

      this.injectHistoryContext(context);

      yield {
        type: 'expert_start',
        data: {
          expertId,
          expertType: expert.expertType,
          role,
          round: this.roundIdx,
          speechCount: this.speechCount,
          containerId
        }
      };

      // 流式发言
      let fullContent = '';
      for await (const chunk of expert.speakStream(context)) {
        if (chunk.type === '__done__') {
          // 发言完成
          const opinion = chunk.opinion!;
          this.meetingHistory.push(opinion);
          this.speechCount++;

          // 记录到容器历史
          if (containerId) {
            this.containerHistories.get(containerId)?.push(opinion);
          }

          // 检测 @提及
          const mentionTarget = this.detectMention(opinion.content, containerId);

          yield {
            type: 'expert_speak',
            data: {
              type: 'expert',
              expertId: opinion.expertId,
              expertType: opinion.expertType,
              role: opinion.role,
              content: opinion.content,
              suggestions: opinion.suggestions,
              speechCount: this.speechCount,
              mention: mentionTarget,
              containerId
            }
          };

          if (mentionTarget) {
            this.forceNextExpert = mentionTarget;
            yield {
              type: 'mention_detected',
              data: { from: opinion.expertType, to: mentionTarget }
            };
          }
        } else {
          // 流式内容
          fullContent += chunk.content;
          yield {
            type: 'expert_chunk',
            data: {
              chunkType: chunk.type,
              content: chunk.content,
              expertId,
              containerId
            }
          };
        }
      }

      // 中断判定
      const shouldPause = this.checkInterrupt(expertId, containerId);
      if (shouldPause && humanFeedback) {
        yield { type: 'waiting_user', data: { speechCount: this.speechCount } };
        
        const feedback = await humanFeedback();
        if (feedback) {
          if (feedback.action === 'stop') {
            this.stopRequested = true;
            this.state = 'stopped';
            break;
          } else if (feedback.action === 'approve') {
            yield { type: 'meeting_complete', data: { reason: 'user_approved' } };
            break;
          } else if (feedback.action === 'modify') {
            context.userFeedback = feedback.message;
          } else if (feedback.action === 'call_expert' && feedback.expertId) {
            this.forceNextExpert = feedback.expertId;
          } else if (feedback.action === 'restart') {
            this.meetingHistory = [];
            this.speechCount = 0;
            this.roundIdx = 0;
            poolIdx = 0;
            yield { type: 'meeting_restarted', data: {} };
          }
        }
      }
    }

    // 会议结束
    const output = this.formatOutput();
    this.state = 'completed';
    yield {
      type: 'output_ready',
      data: {
        output,
        speechCount: this.speechCount,
        rounds: this.roundIdx,
        reason: this.stopRequested ? 'user_stopped' : 'max_rounds'
      }
    };
  }

  private buildContainerContext(containerId: string): string {
    const container = this.containerMap.get(containerId);
    if (!container) return '';

    let context = `\n[你在容器「${container.name || containerId}」中，并发模式: ${container.concurrency || 'serial'}]`;
    
    const history = this.containerHistories.get(containerId) || [];
    if (history.length > 0) {
      const recent = history.slice(-10);
      const histText = recent.map(op => 
        `[${op.expertType}] ${op.content.slice(0, 200)}...`
      ).join('\n');
      context += `\n\n容器内讨论历史:\n${histText}`;
    }

    return context;
  }

  private injectHistoryContext(context: ExpertContext): void {
    const history = context.history || [];
    
    for (let i = history.length - 1; i >= 0; i--) {
      const op = history[i];
      
      if (['资深作者', '剧情架构师', '章节拆分师'].includes(op.expertType) && !context.customPrompt?.includes('author_proposal')) {
        // 注入作者方案
        context.customPrompt = (context.customPrompt || '') + `\n\n作者方案：${op.content.slice(0, 500)}`;
        break;
      }
    }
  }

  private getExpertConfig(expertId: string, role: ExpertRole): ExpertConfig | undefined {
    return this.config.experts.find(ec => 
      ec.expertId === expertId && ec.role === role
    ) || this.config.experts.find(ec => ec.expertId === expertId);
  }

  private checkInterrupt(expertId: string, containerId?: string): boolean {
    const expertConfig = this.getExpertConfig(expertId, ExpertRole.MAIN);
    const interruptMode = expertConfig?.interruptMode || 'every_n_msgs';
    const threshold = expertConfig?.interruptThreshold || 1;

    if (interruptMode === 'auto') return false;
    if (interruptMode === 'every_n_msgs') {
      return this.speechCount % threshold === 0;
    }
    
    return false;
  }

  getState(): string {
    return this.state;
  }

  getSpeechCount(): number {
    return this.speechCount;
  }

  getRound(): number {
    return this.roundIdx;
  }
}
