// 专家基类
import { Expert, ExpertContext, ExpertOpinion, ExpertChunk, ExpertRole, Granularity } from '../protocols';
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

    for await (const chunk of llm.stream(prompt, { temperature })) {
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
}
