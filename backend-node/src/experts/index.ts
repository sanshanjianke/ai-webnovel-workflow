// 专家系统 — JSON 定义 + ConfigurableExpert + 工厂
import { BaseExpert } from './base';
import {
  ExpertRole, Granularity, ExpertContext,
  ExpertDefinition, AgentStopConfig, AgentContext
} from '../protocols';
import { expertLoader } from '../services/expert-loader';

// ============ ConfigurableExpert ============

export class ConfigurableExpert extends BaseExpert {
  expertId: string;
  expertType: string;
  private definition: ExpertDefinition;

  constructor(definition: ExpertDefinition, role: ExpertRole = ExpertRole.MAIN, granularity: Granularity = Granularity.CHAPTER) {
    super(role, granularity);
    this.definition = definition;
    this.expertId = definition.expertId;
    this.expertType = definition.expertType;
  }

  get icon(): string { return this.definition.icon; }
  get description(): string { return this.definition.description; }
  get agentDefaults(): AgentStopConfig { return { ...this.definition.agent_defaults }; }

  buildPrompt(context: ExpertContext): { prompt: string; temperature: number } {
    const def = this.definition;
    let prompt = def.prompt_template;

    // 模板变量替换
    prompt = prompt.replace(/\{role_instruction\}/g, def.role_instructions[this.role] || '');
    prompt = prompt.replace(/\{granularity_context\}/g, def.granularity_contexts[this.granularity] || '');

    // vision
    const vision = context.vision || {};
    const visionText = Object.entries(vision)
      .filter(([_, v]) => v)
      .map(([k, v]) => `- ${k}: ${v}`)
      .join('\n');
    prompt = prompt.replace(/\{vision\}/g, visionText || '未提供愿景文档');

    // worldbook
    prompt = prompt.replace(/\{worldbook\}/g, context.worldbook || '暂无');

    // 上游产出 - 从 history 中提取
    const authorProposal = context.history?.find(op =>
      ['资深作者', '剧情架构师', '章节拆分师'].includes(op.expertType)
    )?.content || '';
    prompt = prompt.replace(/\{author_proposal\}/g, authorProposal ? `作者方案：\n${authorProposal}` : '');

    const readerOpinion = context.history?.find(op =>
      op.expertType === '读者代表'
    )?.content || '';
    prompt = prompt.replace(/\{reader_opinion\}/g, readerOpinion ? `读者代表意见：\n${readerOpinion}` : '');

    // history
    const history = context.history && context.history.length > 0
      ? context.history.slice(-3).map(op =>
          `[${op.expertType}] ${op.content.slice(0, 200)}...`
        ).join('\n')
      : '';
    prompt = prompt.replace(/\{history\}/g, history ? `已有讨论：\n${history}` : '');

    // container context
    prompt = prompt.replace(/\{container_context\}/g, context.containerContext || '');

    // user feedback
    prompt = prompt.replace(/\{user_feedback\}/g, context.userFeedback || '');

    // custom prompt
    prompt = prompt.replace(/\{custom_prompt\}/g, context.customPrompt ? `自定义指令：\n${context.customPrompt}` : '');

    return { prompt, temperature: def.temperature };
  }

  extractSuggestions(content: string): string[] {
    const suggestions: string[] = [];
    const patterns = this.definition.suggestion_patterns;

    if (!patterns || patterns.length === 0) return suggestions;

    const lines = content.split('\n');
    for (const line of lines) {
      const trimmed = line.trim();
      for (const pattern of patterns) {
        try {
          const regex = new RegExp(pattern, 'i');
          if (regex.test(trimmed)) {
            suggestions.push(trimmed);
            break;
          }
        } catch {
          // 无效正则，跳过
        }
      }
    }

    return suggestions;
  }
}

// ============ 工厂（签名不变） ============

export function createExpert(id: string, role: ExpertRole, granularity: Granularity, projectPath?: string): BaseExpert {
  const def = expertLoader.getExpert(id, projectPath);
  if (!def) {
    throw new Error(`Expert not found: ${id}`);
  }
  return new ConfigurableExpert(def, role, granularity);
}

export function listExperts(projectPath?: string): string[] {
  return expertLoader.listExperts(projectPath).map(e => e.id);
}

// ============ 兼容旧注册 API ============

export { BaseExpert } from './base';
