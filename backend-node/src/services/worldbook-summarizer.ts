import { WorldBookSummaryTask, WorldBookAction, WorldBookAnalysisResult, WorldBookEntry } from '../protocols';
import crypto from 'crypto';

export function buildSummarizerPrompt(task: WorldBookSummaryTask): string {
  const entriesSummary = summarizeEntriesForPrompt(task.existingEntries);
  const depthHint = getDepthHint(task.summaryConfig.summaryDepth);

  return `你是一位世界书管理员。你的任务是从专家讨论中提取应该记录到世界书的事实信息。

## 当前世界书已有条目
${entriesSummary}

## 本次聊天内容
${task.chatContent}

## 指令
请分析上述聊天内容，提取其中的世界观事实、角色信息、物品/地点描述、伏笔线索等。
对于每条发现，判断它相对于已有条目是"新信息"(create)、"更新已有"(update)、"与已有重复应合并"(merge)还是"无新信息"(skip)。

${depthHint}

输出 JSON（严格格式，不要包裹在 markdown 代码块中）：
{
  "actions": [
    {
      "action": "create",
      "keys": ["触发关键词"],
      "content": "条目正文（第三人称、简明扼要）",
      "reason": "为什么做此操作",
      "priority": 5,
      "group": ""
    }
  ],
  "summary": "一句话总结本次分析了什么",
  "confidence": 0.8
}

update 示例：
{ "action": "update", "targetEntryId": "abc123", "keys": ["新关键词"], "content": "更新后的完整内容", "reason": "..." }

merge 示例：
{ "action": "merge", "mergeFromIds": ["id1", "id2"], "keys": ["合并后关键词"], "content": "合并后的完整内容", "reason": "..." }

注意：
- 只记录事实信息，不要记录专家意见或创作建议
- content 使用第三人称客观描述
- keys 应该是会触发此条目的中文关键词
- 不确定的信息不要录入，宁可 skip
- 每个 action 必须给出 reason`;
}

function getDepthHint(depth: number): string {
  if (depth <= 1) return '总结深度：只提取聊天中明确陈述的显式事实。不要推断。';
  if (depth === 2) return '总结深度：提取显式事实，对明显推论可以做保守记录。';
  if (depth === 3) return '总结深度：提取显式+合理推论，对讨论中隐含的设定做有限推断。';
  if (depth === 4) return '总结深度：广泛提取，包括隐含设定和次要细节。';
  return '总结深度：深度提取，包括隐含设定、次要细节、可预见的未来变化。';
}

export function summarizeEntriesForPrompt(entries: WorldBookEntry[]): string {
  if (!entries || entries.length === 0) return '（空）';
  return entries.map(e => {
    const keys = e.keys?.join(', ') || '';
    const content = (e.content || '').replace(/\n/g, ' ').slice(0, 100);
    return `- [${e.id}] ${keys}: ${content}${e.content?.length > 100 ? '...' : ''}`;
  }).join('\n');
}

export function parseAnalysisResponse(raw: string): WorldBookAnalysisResult {
  try {
    const jsonMatch = raw.match(/\{[\s\S]*\}/);
    if (!jsonMatch) {
      return { actions: [], summary: '解析失败：未找到 JSON', confidence: 0 };
    }

    const parsed = JSON.parse(jsonMatch[0]);
    const actions: WorldBookAction[] = (parsed.actions || []).map((a: Record<string, unknown>) => ({
      actionId: crypto.randomUUID(),
      action: validateAction(a.action as string),
      keys: Array.isArray(a.keys) ? a.keys as string[] : [],
      content: (a.content as string) || '',
      reason: (a.reason as string) || '',
      targetEntryId: a.targetEntryId as string | undefined,
      mergeFromIds: a.mergeFromIds as string[] | undefined,
      priority: (a.priority as number) || 5,
      group: (a.group as string) || '',
      status: 'pending' as const
    }));

    return {
      actions,
      summary: (parsed.summary as string) || '',
      confidence: (parsed.confidence as number) || 0.5
    };
  } catch {
    return { actions: [], summary: `解析异常: ${raw.slice(0, 200)}`, confidence: 0 };
  }
}

function validateAction(a: unknown): WorldBookAction['action'] {
  if (a === 'create' || a === 'update' || a === 'merge' || a === 'skip') return a;
  return 'skip';
}
