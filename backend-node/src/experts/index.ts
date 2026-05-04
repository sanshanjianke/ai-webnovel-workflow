// 7 位专家实现
import { BaseExpert } from './base';
import { ExpertRole, Granularity, ExpertContext } from '../protocols';

// ============ 资深作者 ============
export class SeniorAuthor extends BaseExpert {
  expertId = 'senior_author_v1';
  expertType = '资深作者';

  buildPrompt(context: ExpertContext) {
    const visionText = this.formatVision(context.vision);
    const worldbook = context.worldbook || '暂无';
    const readerOpinion = context.history?.find(op => op.expertType === '读者代表')?.content || '';
    const userFeedback = context.userFeedback || '';
    const history = this.formatHistory(context.history);
    const customPrompt = context.customPrompt || '';
    const granularityContext = this.getGranularityContext();

    const prompt = `你是资深网文作者，有丰富的商业写作经验。

${this.getRoleInstruction()}

${granularityContext}

你的核心职责：
- 判断方向是否符合市场和读者预期
- 预警毒点和商业风险
- 给出专业建议

故事愿景：
${visionText}

世界书设定：
${worldbook}

${history ? `已有讨论：\n${history}` : ''}
${readerOpinion ? `读者代表意见：${readerOpinion}` : ''}
${userFeedback ? `用户反馈：${userFeedback}` : ''}
${customPrompt ? `自定义指令：${customPrompt}` : ''}

请发言。保持简洁专业，用作者视角。`;

    return { prompt, temperature: 0.8 };
  }

  extractSuggestions(content: string): string[] {
    const suggestions: string[] = [];
    const lines = content.split('\n');
    
    for (const line of lines) {
      const trimmed = line.trim();
      if (this.granularity === Granularity.VOLUME && (trimmed.startsWith('卷') || trimmed.includes('卷'))) {
        suggestions.push(trimmed);
      } else if (this.granularity === Granularity.CHAPTER && trimmed.includes('第') && trimmed.includes('章')) {
        suggestions.push(trimmed);
      } else if (trimmed.startsWith('场景') || trimmed.startsWith('**场景')) {
        suggestions.push(trimmed);
      }
    }
    
    return suggestions;
  }
}

// ============ 读者代表 ============
export class ReaderRepresentative extends BaseExpert {
  expertId = 'reader_representative_v1';
  expertType = '读者代表';

  buildPrompt(context: ExpertContext) {
    const visionText = this.formatVision(context.vision);
    const authorProposal = context.history?.find(op => 
      ['资深作者', '剧情架构师', '章节拆分师'].includes(op.expertType)
    )?.content || '';
    const history = this.formatHistory(context.history, 150);
    const customPrompt = context.customPrompt || '';
    const granularityContext = this.getGranularityContext();

    const prompt = `你是读者代表，站在普通网文读者角度审视作品。

你的职责：
- 模拟读者情绪："看到这里我会觉得..."
- 检测疲劳："连续X章都是同一场景，读者会疲劳"
- 质疑方向："为什么主角不去做XXX？读者会觉得不合理"
- 预测反应："如果这样写，读者可能会骂/弃书"

**重要约束**：
- 只表达读者会怎么感受，不说"应该怎么写"
- 必须以读者口吻发言："我看到第XX章的时候会觉得..."
- 不负责解决方案

${granularityContext}

故事愿景：
${visionText}

${authorProposal ? `作者方案：${authorProposal}` : ''}
${history ? `已有讨论：\n${history}` : ''}
${customPrompt ? `自定义指令：${customPrompt}` : ''}

请从读者角度发表意见。指出可能的问题点，但不要给出解决方案。
保持简洁，列出2-4个关键意见。`;

    return { prompt, temperature: 0.8 };
  }

  extractSuggestions(content: string): string[] {
    const suggestions: string[] = [];
    if (content.includes('疲劳')) suggestions.push('检测到节奏疲劳风险');
    if (content.includes('不合理') || content.includes('困惑')) suggestions.push('检测到逻辑疑问');
    if (content.includes('弃书') || content.includes('骂')) suggestions.push('检测到严重劝退风险');
    return suggestions;
  }
}

// ============ 剧情架构师 ============
export class PlotArchitect extends BaseExpert {
  expertId = 'plot_architect_v1';
  expertType = '剧情架构师';

  buildPrompt(context: ExpertContext) {
    const visionText = this.formatVision(context.vision);
    const volumePlan = context.history?.find(op => op.expertType === '资深作者')?.content || '';
    const worldbook = context.worldbook || '';
    const history = this.formatHistory(context.history);
    const customPrompt = context.customPrompt || '';
    const granularityContext = this.getGranularityContext();

    const prompt = `你是剧情架构师，专注于故事结构和逻辑推演。

${this.getRoleInstruction()}

${granularityContext}

你的核心概念：
- 功能：叙事的最小单位（铺垫/转折/阻碍/回收等）
- 序列：功能组成的完整叙事句子
- 情节：序列的组织（链状/嵌入/并列）

检查要点：
- 因果闭环：每个转折是否有铺垫？
- 序列完整：起承转合是否齐全？
- 逻辑漏洞：有无未解释的跳跃？

故事愿景：
${visionText}

${volumePlan ? `卷纲：${volumePlan}` : ''}
${worldbook ? `世界书：${worldbook}` : ''}
${history ? `讨论历史：\n${history}` : ''}
${customPrompt ? `自定义指令：${customPrompt}` : ''}

请发言。用结构化方式呈现你的分析。`;

    return { prompt, temperature: 0.7 };
  }

  extractSuggestions(content: string): string[] {
    const suggestions: string[] = [];
    const lines = content.split('\n');
    
    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed.includes('第') && trimmed.includes('章')) {
        suggestions.push(trimmed);
      } else if (trimmed.includes('序列') || trimmed.includes('功能')) {
        suggestions.push(trimmed);
      }
    }
    
    return suggestions;
  }
}

// ============ 人物设计师 ============
export class CharacterDesigner extends BaseExpert {
  expertId = 'character_designer_v1';
  expertType = '人物设计师';

  buildPrompt(context: ExpertContext) {
    const visionText = this.formatVision(context.vision);
    const volumePlan = context.history?.find(op => op.expertType === '资深作者')?.content || '';
    const history = this.formatHistory(context.history, 150);
    const customPrompt = context.customPrompt || '';
    const granularityContext = this.getGranularityContext();

    const prompt = `你是人物设计师，专注于角色塑造和行为合理性。

${this.getRoleInstruction()}

${granularityContext}

你的核心概念：
- 行动元：主体/客体/发送者/接收者/帮助者/敌对者
- 扁形/圆形人物：功能性配角 vs 成长型主角
- 人设一致性：角色的行为是否符合其性格设定？

检查要点：
- 行动元分配是否清晰？
- 人物行为是否有动机支撑？
- 是否存在OOC（人物崩坏）？
- 关系变化是否合理？

故事愿景：
${visionText}

${volumePlan ? `卷纲：${volumePlan}` : ''}
${history ? `讨论历史：\n${history}` : ''}
${customPrompt ? `自定义指令：${customPrompt}` : ''}

请发言。关注人物层面的合理性。`;

    return { prompt, temperature: 0.7 };
  }

  extractSuggestions(content: string): string[] {
    const suggestions: string[] = [];
    if (content.includes('人物') || content.includes('角色')) {
      suggestions.push('包含人物分析');
    }
    return suggestions;
  }
}

// ============ 网络编辑 ============
export class WebEditor extends BaseExpert {
  expertId = 'web_editor_v1';
  expertType = '网络编辑';

  buildPrompt(context: ExpertContext) {
    const visionText = this.formatVision(context.vision);
    const volumePlan = context.history?.find(op => op.expertType === '资深作者')?.content || '';
    const history = this.formatHistory(context.history, 150);
    const customPrompt = context.customPrompt || '';
    const granularityContext = this.getGranularityContext();

    const prompt = `你是网络编辑，专注于商业效果和读者体验。

${this.getRoleInstruction()}

${granularityContext}

你的核心概念：
- 爽点公式：压抑-释放、期待感悬置、欲扬先抑
- 黄金三章：开篇必须成立的冲突/悬念
- 毒点规避：圣母、降智、节奏拖沓

检查要点：
- 爽点密度是否达标？
- 情绪曲线是否合理？
- 是否存在劝退风险？
- 商业卖点是否突出？

故事愿景：
${visionText}

${volumePlan ? `卷纲：${volumePlan}` : ''}
${history ? `讨论历史：\n${history}` : ''}
${customPrompt ? `自定义指令：${customPrompt}` : ''}

请发言。从市场和读者角度评估。`;

    return { prompt, temperature: 0.7 };
  }

  extractSuggestions(content: string): string[] {
    const suggestions: string[] = [];
    if (content.includes('爽点')) suggestions.push('包含爽点分析');
    if (content.includes('毒点') || content.includes('劝退')) suggestions.push('检测到毒点风险');
    if (content.includes('节奏')) suggestions.push('包含节奏建议');
    return suggestions;
  }
}

// ============ 章节拆分师 ============
export class ChapterSplitter extends BaseExpert {
  expertId = 'chapter_splitter_v1';
  expertType = '章节拆分师';

  buildPrompt(context: ExpertContext) {
    const visionText = this.formatVision(context.vision);
    const volumePlan = context.history?.find(op => op.expertType === '资深作者')?.content || '';
    const authorProposal = context.history?.find(op => 
      ['资深作者', '剧情架构师'].includes(op.expertType)
    )?.content || '';
    const history = this.formatHistory(context.history, 200);
    const userFeedback = context.userFeedback || '';
    const customPrompt = context.customPrompt || '';

    const prompt = `你是章节拆分师，负责将宏观的卷纲/故事方向拆解为具体的章节列表。

${this.getRoleInstruction()}

你的核心职责：
- 接收卷级方向（如"卷二写秘境探索"），拆解为具体的章节目录
- 每章给出：章号、标题、核心事件、情绪基调、衔接说明
- 控制每章的篇幅范围（建议2000-4000字）
- 确保章与章之间的因果链衔接自然

工作方式：
- 如果已有卷纲，在此基础上展开
- 如果没有卷纲，从故事愿景直接拆分
- 通常每次拆分5-15章的规划

输出格式：
**第X章：章节标题**
- 核心事件：（一句话概括本章发生了什么）
- 情绪基调：XXX → XXX
- 衔接前章：承接XXX
- 衔接后章：铺垫XXX
- 关键人物：XXX
- 视角建议：XXX

故事愿景：
${visionText}

${volumePlan ? `卷纲：${volumePlan}` : ''}
${authorProposal ? `已有方案：${authorProposal}` : ''}
${history ? `讨论历史：\n${history}` : ''}
${userFeedback ? `用户反馈：${userFeedback}` : ''}
${customPrompt ? `自定义指令：${customPrompt}` : ''}

请拆解章节。从当前讨论的阶段开始，依次展开后续章节。`;

    return { prompt, temperature: 0.7 };
  }

  extractSuggestions(content: string): string[] {
    const suggestions: string[] = [];
    const lines = content.split('\n');
    
    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed.includes('第') && trimmed.includes('章') && trimmed.includes('：')) {
        suggestions.push(trimmed);
      }
    }
    
    return suggestions;
  }
}

// ============ 讨论总结师 ============
export class DiscussionSummarizer extends BaseExpert {
  expertId = 'discussion_summarizer_v1';
  expertType = '讨论总结师';

  buildPrompt(context: ExpertContext) {
    const visionText = this.formatVision(context.vision);
    const historyText = context.history?.slice(-6).map(op => 
      `[${op.expertType}] (${op.role})\n${op.content}`
    ).join('\n\n---\n\n') || '';
    const containerContext = context.containerContext || '';
    const userFeedback = context.userFeedback || '';
    const customPrompt = context.customPrompt || '';

    const prompt = `你是讨论总结师，负责在群聊讨论中定期总结和提炼。你的职责不是提出新观点，而是收束已有讨论：

- 提炼共识：哪些观点大家已经达成一致？
- 标注分歧：哪些问题还有不同意见？
- 格式化输出：确保讨论保持在结构化的轨道上

${this.getRoleInstruction()}

故事愿景：
${visionText}

${historyText ? `已有讨论：\n${historyText}` : ''}
${containerContext ? `容器上下文：${containerContext}` : ''}
${userFeedback ? `用户反馈：${userFeedback}` : ''}
${customPrompt ? `自定义指令：${customPrompt}` : ''}

请简洁总结。用「共识」「分歧」「建议」三个小节。每节不超过3句话。`;

    return { prompt, temperature: 0.5 };
  }

  extractSuggestions(content: string): string[] {
    const suggestions: string[] = [];
    if (content.includes('共识')) suggestions.push('包含共识提炼');
    if (content.includes('分歧')) suggestions.push('包含分歧标注');
    return suggestions;
  }
}

// 专家注册表
type ExpertConstructor = new (role: ExpertRole, granularity: Granularity) => BaseExpert;
const expertRegistry = new Map<string, ExpertConstructor>();

export function registerExpert(id: string, expertClass: ExpertConstructor): void {
  expertRegistry.set(id, expertClass);
}

export function getExpertClass(id: string): ExpertConstructor | undefined {
  return expertRegistry.get(id);
}

export function createExpert(id: string, role: ExpertRole, granularity: Granularity): BaseExpert {
  const ExpertClass = expertRegistry.get(id);
  if (!ExpertClass) {
    throw new Error(`Expert not found: ${id}`);
  }
  return new ExpertClass(role, granularity);
}

export function listExperts(): string[] {
  return Array.from(expertRegistry.keys());
}

// 注册内置专家
registerExpert('senior_author_v1', SeniorAuthor);
registerExpert('reader_representative_v1', ReaderRepresentative);
registerExpert('plot_architect_v1', PlotArchitect);
registerExpert('character_designer_v1', CharacterDesigner);
registerExpert('web_editor_v1', WebEditor);
registerExpert('chapter_splitter_v1', ChapterSplitter);
registerExpert('discussion_summarizer_v1', DiscussionSummarizer);
