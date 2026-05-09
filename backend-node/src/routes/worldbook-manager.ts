import { Express, Request, Response } from 'express';
import { getProjectManager } from '../services/project-manager';
import { WorldBookStore } from '../services/worldbook';
import { WorldBookManagerService } from '../services/worldbook-manager-service';
import { WorldBookSummaryTask, WorldBookSummaryConfig, WorldBookAction } from '../protocols';
import { getLLM } from '../services/llm';
import { buildSummarizerPrompt, parseAnalysisResponse, summarizeEntriesForPrompt } from '../services/worldbook-summarizer';
import { SSEWriter } from '../utils/sse';
import crypto from 'crypto';

// 全局注册表：meetingId → WorldBookManagerService 实例
const managerInstances = new Map<string, WorldBookManagerService>();

export function registerManagerInstance(meetingId: string, manager: WorldBookManagerService): void {
  managerInstances.set(meetingId, manager);
}

export function unregisterManagerInstance(meetingId: string): void {
  managerInstances.delete(meetingId);
}

export function registerWorldBookManagerRoutes(app: Express): void {
  const pm = getProjectManager();

  // 手动触发单次总结
  app.post('/api/projects/:projectId/worldbooks/:bookId/summarize', async (req: Request, res: Response) => {
    try {
      const project = pm.getProject(req.params.projectId);
      if (!project) return res.status(404).json({ error: 'Project not found' });

      const { chatContent, nodeId = 'manual', objectId = 'manual', mode = 'semi_auto' } = req.body;
      if (!chatContent) return res.status(400).json({ error: 'chatContent is required' });

      const store = new WorldBookStore(project.path);
      const worldbook = store.getBook(req.params.bookId) || store.getDefaultBook();
      const existingEntries = worldbook.listAllEntries();

      const task: WorldBookSummaryTask = {
        taskId: `wbt_manual_${Date.now()}`,
        nodeId, nodeType: 'expert', objectId, objectName: '手动触发',
        targetBookId: req.params.bookId,
        summaryConfig: {
          enableWorldBookSummary: true,
          targetBookId: req.params.bookId,
          triggerGranularity: 'per_node',
          summaryDepth: 3,
          operationMode: mode as 'auto' | 'semi_auto' | 'manual'
        },
        chatContent, existingEntries,
        triggeredBy: 'manual', timestamp: new Date().toISOString()
      };

      const prompt = buildSummarizerPrompt(task);
      const llm = getLLM();
      const rawResponse = await llm.invoke(prompt, { temperature: 0.3, maxTokens: 4096 });
      const result = parseAnalysisResponse(rawResponse);

      if (mode === 'auto') {
        for (const action of result.actions) {
          if (action.action === 'skip') continue;
          applyActionToBook(action, worldbook);
          action.status = 'applied';
        }
      }

      res.json({ status: 'completed', actions: result.actions, summary: result.summary });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // SSE 流订阅世界书管理员事件
  app.get('/api/projects/:projectId/worldbooks/manager/stream', (req: Request, res: Response) => {
    const meetingId = req.query.meetingId as string;
    if (!meetingId) return res.status(400).json({ error: 'meetingId is required' });

    const writer = new SSEWriter(res);

    const manager = managerInstances.get(meetingId);
    if (!manager) {
      // 没有活跃的管理员实例，仍然保持连接等待
      // 定期发送心跳直到连接关闭或实例注册
      const interval = setInterval(() => {
        if (writer.isClosed()) { clearInterval(interval); return; }
        const mgr = managerInstances.get(meetingId);
        if (mgr) {
          clearInterval(interval);
          writer.write('connected', { meetingId, status: 'ready' });
        } else {
          writer.write('heartbeat', { meetingId, status: 'waiting' });
        }
      }, 2000);

      req.on('close', () => { clearInterval(interval); writer.close(); });
      return;
    }

    writer.write('connected', { meetingId, status: 'ready' });
    req.on('close', () => writer.close());
  });

  // 确认/拒绝/修改 action（半自动模式）
  app.put('/api/projects/:projectId/worldbooks/:bookId/actions/:actionId', async (req: Request, res: Response) => {
    try {
      const project = pm.getProject(req.params.projectId);
      if (!project) return res.status(404).json({ error: 'Project not found' });

      const { action, modifiedContent, modifiedKeys, taskId } = req.body;
      if (!action || !taskId) return res.status(400).json({ error: 'action and taskId are required' });

      // 在整个注册表中查找有对应 taskId 的 manager
      let found = false;
      for (const [, manager] of managerInstances) {
        const pending = manager.getPendingActions(taskId);
        if (pending.length > 0) {
          if (action === 'confirm' || action === 'modify') {
            found = manager.confirmAction(taskId, req.params.actionId, modifiedContent, modifiedKeys);
          } else if (action === 'reject') {
            found = manager.rejectAction(taskId, req.params.actionId);
          }
          if (found) break;
        }
      }

      if (found) {
        res.json({ status: action === 'reject' ? 'rejected' : (modifiedContent ? 'modified' : 'confirmed'), actionId: req.params.actionId });
      } else {
        res.status(404).json({ error: 'Action or task not found in any active manager' });
      }
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });
}

function applyActionToBook(action: WorldBookAction, worldbook: any): void {
  switch (action.action) {
    case 'create': {
      const id = `wb_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
      worldbook.createEntry({
        id, keys: action.keys, content: action.content,
        priority: action.priority || 5, group: action.group || '',
        comment: action.reason || ''
      });
      break;
    }
    case 'update': {
      if (!action.targetEntryId) return;
      worldbook.updateEntry(action.targetEntryId, { keys: action.keys, content: action.content, comment: action.reason });
      break;
    }
    case 'merge': {
      if (!action.mergeFromIds || action.mergeFromIds.length < 2) return;
      const newId = `wb_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
      worldbook.createEntry({
        id: newId, keys: action.keys, content: action.content,
        priority: action.priority || 5, group: action.group || '',
        comment: `合并自: ${action.mergeFromIds.join(', ')}`
      });
      for (const oldId of action.mergeFromIds) {
        try { worldbook.deleteEntry(oldId); } catch {}
      }
      break;
    }
  }
}
