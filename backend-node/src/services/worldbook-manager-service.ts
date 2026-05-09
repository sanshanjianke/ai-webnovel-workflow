import { WorldBookSummaryTask, WorldBookAction, WorldBookEntry } from '../protocols';
import { WorldBook } from '../protocols';
import { buildSummarizerPrompt, parseAnalysisResponse } from './worldbook-summarizer';
import { getLLM } from './llm';
import { WorldBookStore } from './worldbook';
import * as fs from 'fs';
import * as path from 'path';

export interface WBManagerEvent {
  type: string;
  data: Record<string, unknown>;
}

export class WorldBookManagerService {
  private projectPath: string;
  private eventEmitter: (event: WBManagerEvent) => void;
  private pendingActions: Map<string, WorldBookAction[]> = new Map();

  constructor(projectPath: string, eventEmitter: (event: WBManagerEvent) => void) {
    this.projectPath = projectPath;
    this.eventEmitter = eventEmitter;
  }

  async processTask(task: WorldBookSummaryTask): Promise<WorldBookAction[]> {
    this.eventEmitter({
      type: 'worldbook_task_queued',
      data: { taskId: task.taskId, nodeId: task.nodeId, nodeType: task.nodeType, objectId: task.objectId, objectName: task.objectName, triggeredBy: task.triggeredBy, timestamp: task.timestamp }
    });

    this.eventEmitter({
      type: 'worldbook_analyze_start',
      data: { taskId: task.taskId, nodeId: task.nodeId, objectId: task.objectId, bookId: task.targetBookId, chatContentLength: task.chatContent.length }
    });

    const store = new WorldBookStore(this.projectPath);
    const worldbook = task.targetBookId
      ? store.getBook(task.targetBookId)
      : store.getDefaultBook();

    if (!worldbook) {
      this.eventEmitter({
        type: 'worldbook_task_complete',
        data: { taskId: task.taskId, nodeId: task.nodeId, error: `Book not found: ${task.targetBookId}`, totalActions: 0, appliedCount: 0 }
      });
      return [];
    }

    const prompt = buildSummarizerPrompt(task);
    const llm = getLLM();

    let rawResponse = '';
    try {
      rawResponse = await llm.invoke(prompt, { temperature: 0.3, maxTokens: 4096 });
    } catch (err: any) {
      this.eventEmitter({
        type: 'worldbook_task_complete',
        data: { taskId: task.taskId, nodeId: task.nodeId, error: `LLM error: ${err.message}`, totalActions: 0, appliedCount: 0 }
      });
      return [];
    }

    const result = parseAnalysisResponse(rawResponse);

    const createCount = result.actions.filter(a => a.action === 'create').length;
    const updateCount = result.actions.filter(a => a.action === 'update').length;
    const mergeCount = result.actions.filter(a => a.action === 'merge').length;
    const skipCount = result.actions.filter(a => a.action === 'skip').length;

    this.eventEmitter({
      type: 'worldbook_actions_ready',
      data: {
        taskId: task.taskId, actions: result.actions, summary: result.summary,
        totalActions: result.actions.length, createCount, updateCount, mergeCount, skipCount,
        confidence: result.confidence
      }
    });

    const mode = task.summaryConfig.operationMode || 'semi_auto';

    if (mode === 'auto') {
      let appliedCount = 0;
      for (const action of result.actions) {
        if (action.action === 'skip') continue;
        this.applyAction(action, worldbook);
        action.status = 'applied';
        appliedCount++;
        this.eventEmitter({
          type: 'worldbook_action_applied',
          data: { taskId: task.taskId, actionId: action.actionId, actionType: action.action, keys: action.keys, bookId: task.targetBookId }
        });
      }

      this.eventEmitter({
        type: 'worldbook_task_complete',
        data: { taskId: task.taskId, nodeId: task.nodeId, totalActions: result.actions.length, appliedCount, skippedCount: skipCount, mode: 'auto' }
      });
    } else if (mode === 'semi_auto') {
      this.pendingActions.set(task.taskId, result.actions.filter(a => a.action !== 'skip'));
    }

    return result.actions;
  }

  applyAction(action: WorldBookAction, worldbook: WorldBook): void {
    switch (action.action) {
      case 'create': {
        const id = `wb_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
        worldbook.createEntry({
          id,
          keys: action.keys,
          content: action.content,
          priority: action.priority || 5,
          group: action.group || '',
          comment: action.reason || ''
        } as WorldBookEntry);
        break;
      }
      case 'update': {
        if (!action.targetEntryId) return;
        worldbook.updateEntry(action.targetEntryId, {
          keys: action.keys,
          content: action.content,
          comment: action.reason
        } as Partial<WorldBookEntry>);
        break;
      }
      case 'merge': {
        if (!action.mergeFromIds || action.mergeFromIds.length < 2) return;
        const mergedContent = action.content;
        const newId = `wb_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
        worldbook.createEntry({
          id: newId,
          keys: action.keys,
          content: mergedContent,
          priority: action.priority || 5,
          group: action.group || '',
          comment: `合并自: ${action.mergeFromIds.join(', ')}`
        } as WorldBookEntry);
        for (const oldId of action.mergeFromIds) {
          try { worldbook.deleteEntry(oldId); } catch {}
        }
        break;
      }
      case 'skip':
        break;
    }
  }

  confirmAction(taskId: string, actionId: string, modifiedContent?: string, modifiedKeys?: string[]): boolean {
    const actions = this.pendingActions.get(taskId);
    if (!actions) return false;

    const action = actions.find(a => a.actionId === actionId);
    if (!action) return false;

    const store = new WorldBookStore(this.projectPath);
    // Use the task's target book — we need to find it from the pending store
    // For now, use default book as fallback
    const worldbook = store.getDefaultBook();

    if (modifiedContent !== undefined) {
      action.content = modifiedContent;
      action.status = 'modified';
    } else {
      action.status = 'applied';
    }
    if (modifiedKeys !== undefined) {
      action.keys = modifiedKeys;
    }

    if (action.action !== 'skip') {
      this.applyAction(action, worldbook);
    }

    this.eventEmitter({
      type: 'worldbook_action_applied',
      data: { taskId, actionId, actionType: action.action, keys: action.keys, bookId: 'default' }
    });

    return true;
  }

  rejectAction(taskId: string, actionId: string): boolean {
    const actions = this.pendingActions.get(taskId);
    if (!actions) return false;

    const action = actions.find(a => a.actionId === actionId);
    if (!action) return false;

    action.status = 'rejected';
    return true;
  }

  getPendingActions(taskId: string): WorldBookAction[] {
    return this.pendingActions.get(taskId) || [];
  }

  clearPendingActions(taskId: string): void {
    this.pendingActions.delete(taskId);
  }
}
