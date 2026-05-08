// 专家基类
import {
  Expert, ExpertContext, ExpertOpinion, ExpertChunk,
  ExpertRole, Granularity,
  AgentStopConfig, AgentEvent,
  ExpertChatLog, ExpertRound, ExpertMessage
} from '../protocols';
import { getLLM } from '../services/llm';

export abstract class BaseExpert implements Expert {
  abstract expertId: string;
  abstract expertType: string;
  
  protected role: ExpertRole;
  protected granularity: Granularity;

  constructor(role: ExpertRole = ExpertRole.MAIN, granularity: Granularity = Granularity.CHAPTER) {
    this.role = role;
    this.granularity = granularity;
  }

  abstract buildPrompt(context: ExpertContext): { prompt: string; temperature: number };

  extractSuggestions(content: string): string[] {
    return [];
  }

  async speak(context: ExpertContext): Promise<ExpertOpinion> {
    const { prompt, temperature } = this.buildPrompt(context);
    const llm = getLLM();
    const content = await llm.invoke(prompt, { temperature });
    
    return {
      expertId: this.expertId,
      expertType: this.expertType,
      role: this.role,
      content,
      suggestions: this.extractSuggestions(content)
    };
  }

  async *speakStream(context: ExpertContext): AsyncGenerator<ExpertChunk> {
    const { prompt, temperature } = this.buildPrompt(context);
    const llm = getLLM();
    let fullContent = '';

    for await (const chunk of llm.stream(prompt, { temperature, thinking: true, thinkingBudget: 10000 })) {
      if (chunk.type === 'content') {
        fullContent += chunk.content;
        yield { type: 'content', content: chunk.content };
      } else if (chunk.type === 'thinking') {
        yield { type: 'thinking', content: chunk.content };
      }
    }

    yield {
      type: '__done__',
      content: '',
      opinion: {
        expertId: this.expertId,
        expertType: this.expertType,
        role: this.role,
        content: fullContent,
        suggestions: this.extractSuggestions(fullContent)
      }
    };
  }

  protected formatVision(vision?: Record<string, string>): string {
    if (!vision) return '未提供愿景文档';
    return Object.entries(vision)
      .filter(([_, v]) => v)
      .map(([k, v]) => `- ${k}: ${v}`)
      .join('\n');
  }

  protected formatHistory(history?: ExpertOpinion[], maxChars: number = 200): string {
    if (!history || history.length === 0) return '';
    return history.slice(-3).map(op => 
      `[${op.expertType}] ${op.content.slice(0, maxChars)}...`
    ).join('\n');
  }

  protected getGranularityContext(): string {
    switch (this.granularity) {
      case Granularity.VOLUME:
        return `讨论粒度：卷级
你需要讨论：
- 分卷方案（每卷10-50章）
- 每卷的主线方向和热点
- 卷与卷之间的衔接
- 读者疲劳点预防
输出格式：
**分卷建议**：
卷一：XXX (第1-XX章)
  → 方向说明`;

      case Granularity.CHAPTER:
        return `讨论粒度：章级
你需要讨论：
- 每章的功能序列（铺垫→冲突→转折）
- 情绪曲线设计
- 人物行动元分配
- 爽点/毒点标注
输出格式：
**章节概要**：
第X章：XXX
- 核心事件：...
- 功能链：铺垫→转折→...
- 情绪曲线：压抑→爆发→余韵`;

      case Granularity.SCENE:
        return `讨论粒度：场景级
你需要讨论：
- 场景内的视角切换
- 节奏控制（扩述/概述）
- 话语模式选择
- 细节描写建议
输出格式：
**场景设计**：
场景：XXX
- 视角：外聚焦/内聚焦
- 节奏：慢速扩述
- 关键细节：...`;

      default:
        return '';
    }
  }

  protected getRoleInstruction(): string {
    switch (this.role) {
      case ExpertRole.MAIN:
        return '你是会议的主导者，负责提出方案和方向。';
      case ExpertRole.REVIEW:
        return '你是审核者，负责评估已有方案的可行性。';
      case ExpertRole.SUPPLEMENT:
        return '你是补充者，在主导者发言后补充细节或调整。';
      default:
        return '';
    }
  }

  // ============ Agent 多轮迭代 ============

  /**
   * Agent 迭代循环。每轮调用 speakStream()，支持自我审视和停止条件。
   * 新增于 Phase 1 重构，speakStream() 保持不变。
   */
  async *iterate(
    context: ExpertContext,
    stopConfig: AgentStopConfig,
    selfReviewPromptProvider?: () => string,
    onBlocking?: (round: number) => Promise<{ action: string; message?: string } | null>,
    getPendingMessage?: () => string | null
  ): AsyncGenerator<AgentEvent> {
    let finalReport = '';
    let bestScore = 0;
    let bestRound = 0;
    let stopRequested = false;
    let pendingUserMessage: string | null = null;

    const chatLog: ExpertChatLog = {
      expertId: this.expertId,
      expertType: this.expertType,
      objectId: '',
      reportFile: `${this.expertType}意见.md`,
      startedAt: new Date().toISOString(),
      completedAt: null,
      rounds: []
    };

    for (let round = 1; round <= stopConfig.maxRounds; round++) {
      if (stopRequested) break;

      // ---- 阻塞中止检查 ----
      if (stopConfig.blockEveryNRounds > 0 && round > 1 &&
          round % stopConfig.blockEveryNRounds === 0 && onBlocking) {
        yield {
          type: 'agent_waiting_user',
          data: {
            expertId: this.expertId, expertType: this.expertType,
            round, summary: finalReport.slice(0, 500)
          }
        };
        const fb = await onBlocking(round);
        if (fb?.action === 'stop' || fb?.action === 'accept') {
          stopRequested = true;
          break;
        }
        if (fb?.message) {
          pendingUserMessage = fb.message;
        }
      }

      // ---- 检查外部注入的消息 ----
      if (!pendingUserMessage && getPendingMessage) {
        pendingUserMessage = getPendingMessage() || null;
      }
      if (!pendingUserMessage && this._pendingUserMessage) {
        pendingUserMessage = this._pendingUserMessage;
        this._pendingUserMessage = null;
      }

      // ---- 轮次开始事件 ----
      yield {
        type: 'agent_round_start',
        data: {
          expertId: this.expertId, expertType: this.expertType, round
        }
      };

      // ---- 构建本轮上下文 ----
      const roundContext: ExpertContext = {
        ...context,
        round,
        userFeedback: pendingUserMessage || context.userFeedback
      };

      // 第2轮及以后：注入自审视提示词
      if (round > 1 && selfReviewPromptProvider) {
        const prevMessages = chatLog.rounds[round - 2]?.messages || [];
        const prevAssistant = prevMessages.find(m => m.role === 'assistant');
        if (prevAssistant?.content) {
          roundContext.userFeedback = [
            `上一轮你的产出：\n${prevAssistant.content.slice(0, 2000)}\n\n---`,
            selfReviewPromptProvider()
          ].join('\n');
        } else {
          roundContext.userFeedback = selfReviewPromptProvider();
        }
      }

      const messages: ExpertMessage[] = [];

      // System prompt
      if (round > 1) {
        messages.push({
          role: 'system',
          content: selfReviewPromptProvider?.() || '请审视并修正你的意见。',
          timestamp: new Date().toISOString()
        });
      }

      // User message (from blocking)
      if (pendingUserMessage) {
        messages.push({
          role: 'user',
          content: pendingUserMessage,
          timestamp: new Date().toISOString()
        });
        pendingUserMessage = null;
      }

      // ---- 调用 speakStream（复用现有方法） ----
      let fullThinking = '';
      let fullContent = '';

      for await (const chunk of this.speakStream(roundContext)) {
        if (chunk.type === 'thinking') {
          fullThinking += chunk.content;
          yield {
            type: 'agent_chunk',
            data: {
              chunkType: 'thinking', content: chunk.content,
              expertId: this.expertId, round
            }
          };
        } else if (chunk.type === 'content') {
          fullContent += chunk.content;
          yield {
            type: 'agent_chunk',
            data: {
              chunkType: 'content', content: chunk.content,
              expertId: this.expertId, round
            }
          };
        } else if (chunk.type === '__done__') {
          messages.push({
            role: 'assistant',
            thinking: fullThinking,
            content: fullContent,
            timestamp: new Date().toISOString()
          });
        }
      }

      // ---- 提取评分 (for pick_best) ----
      const scoreMatch = fullContent.match(/<score:(\d+)>/i);
      let selfScore: number | undefined;
      if (scoreMatch) {
        selfScore = parseInt(scoreMatch[1]);
        if (selfScore > bestScore) {
          bestScore = selfScore;
          bestRound = round;
        }
      }

      // ---- 保存轮次 ----
      chatLog.rounds.push({
        round,
        messages,
        selfScore,
        completedAt: new Date().toISOString()
      });

      // ---- 提取最终报告 ----
      const currentReport = extractReport(fullContent);
      if (currentReport) {
        finalReport = currentReport;
      }

      // ---- <stop> 标签检测 ----
      if (stopConfig.enableStopSignal && hasStopSignal(fullContent)) {
        yield {
          type: 'agent_round_complete',
          data: {
            expertId: this.expertId, round,
            stoppedBy: 'stop', report: finalReport
          }
        };
        stopRequested = true;
        break;
      }

      // ---- 轮次完成事件 ----
      yield {
        type: 'agent_round_complete',
        data: {
          expertId: this.expertId, round,
          selfScore,
          report: finalReport
        }
      };
    }

    // ---- 最终化：pick_best 模式 ----
    if (stopConfig.onMaxRounds === 'pick_best' && bestRound > 0) {
      const bestRoundData = chatLog.rounds.find(r => r.round === bestRound);
      if (bestRoundData) {
        const bestMsg = bestRoundData.messages.find(m => m.role === 'assistant');
        if (bestMsg?.content) {
          finalReport = extractReport(bestMsg.content);
        }
      }
    }

    chatLog.completedAt = new Date().toISOString();

    // ---- Agent 完成 ----
    yield {
      type: 'agent_complete',
      data: {
        expertId: this.expertId,
        expertType: this.expertType,
        report: finalReport,
        reportFileName: chatLog.reportFile,
        chatLog,
        totalRounds: chatLog.rounds.length
      }
    };
  }

  /**
   * 注入用户消息到下一轮迭代
   */
  private _pendingUserMessage: string | null = null;
  injectUserMessage(message: string): void {
    this._pendingUserMessage = message;
  }
}

// ============ 报告/标签解析工具函数 ============

/**
 * 从 AI 输出中提取 <报告>...</报告> 标签内的内容。
 * 匹配不到时降级返回全部 content。
 * 只扫描 content 部分，忽略 thinking。
 */
export function extractReport(content: string): string {
  const match = content.match(/<报告>([\s\S]*?)<\/报告>/);
  if (match) {
    return match[1].trim();
  }
  return content.trim();
}

/**
 * 检查内容是否包含 <stop> 标签（大小写不敏感）。
 */
export function hasStopSignal(content: string): boolean {
  return /<stop>/i.test(content);
}

/**
 * 从内容中提取自评分 <score:N>
 */
export function extractSelfScore(content: string): number | null {
  const match = content.match(/<score:(\d+)>/i);
  if (match) {
    return parseInt(match[1]);
  }
  return null;
}
