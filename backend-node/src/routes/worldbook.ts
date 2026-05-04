// 世界书路由
import { Express, Request, Response } from 'express';
import { getProjectManager } from '../services/project-manager';
import { STStyleWorldBook, WorldBookManager } from '../services/worldbook';
import { WorldBookEntry } from '../protocols';

export function registerWorldbookRoutes(app: Express): void {
  const pm = getProjectManager();

  function getWorldbook(projectId: string): STStyleWorldBook {
    const project = pm.getProject(projectId);
    if (!project) {
      throw new Error('Project not found');
    }
    return new STStyleWorldBook(project.path);
  }

  // 列出所有条目
  app.get('/api/projects/:projectId/worldbook', (req: Request, res: Response) => {
    try {
      const wb = getWorldbook(req.params.projectId);
      const entries = wb.listAllEntries();
      res.json({ entries: entries.map(e => e) });
    } catch (error) {
      res.status(404).json({ error: String(error) });
    }
  });

  // 创建条目
  app.post('/api/projects/:projectId/worldbook', (req: Request, res: Response) => {
    try {
      const wb = getWorldbook(req.params.projectId);
      const entry: WorldBookEntry = {
        id: req.body.id,
        keys: req.body.keys || [],
        content: req.body.content || '',
        secondaryKeys: req.body.secondaryKeys || [],
        constant: req.body.constant || false,
        priority: req.body.priority || 10,
        position: req.body.position || 'before_char',
        metadata: req.body.metadata || {}
      };
      wb.createEntry(entry);
      res.json({ status: 'created', entry });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // 获取条目
  app.get('/api/projects/:projectId/worldbook/:entryId', (req: Request, res: Response) => {
    try {
      const wb = getWorldbook(req.params.projectId);
      const entry = wb.getEntry(req.params.entryId);
      if (!entry) {
        return res.status(404).json({ error: 'Entry not found' });
      }
      res.json({ entry });
    } catch (error) {
      res.status(404).json({ error: String(error) });
    }
  });

  // 更新条目
  app.put('/api/projects/:projectId/worldbook/:entryId', (req: Request, res: Response) => {
    try {
      const wb = getWorldbook(req.params.projectId);
      wb.updateEntry(req.params.entryId, req.body);
      res.json({ status: 'updated' });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // 删除条目
  app.delete('/api/projects/:projectId/worldbook/:entryId', (req: Request, res: Response) => {
    try {
      const wb = getWorldbook(req.params.projectId);
      wb.deleteEntry(req.params.entryId);
      res.json({ status: 'deleted' });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // 提交版本
  app.post('/api/projects/:projectId/worldbook/commit', (req: Request, res: Response) => {
    try {
      const wb = getWorldbook(req.params.projectId);
      const message = req.body.message || 'Manual commit';
      const hash = wb.commit(message);
      res.json({ status: 'committed', hash });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // 版本历史
  app.get('/api/projects/:projectId/worldbook/history', (req: Request, res: Response) => {
    try {
      const wb = getWorldbook(req.params.projectId);
      const commits = wb.listCommits();
      res.json({ commits });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // AI 自动处理
  app.post('/api/projects/:projectId/worldbook/process-sequence', async (req: Request, res: Response) => {
    try {
      const wb = getWorldbook(req.params.projectId);
      const manager = new WorldBookManager(wb);
      const { sequenceContent, sequenceId } = req.body;
      const changes = await manager.processSequence(sequenceContent, sequenceId);
      const conflicts = manager.getConflicts(changes);
      res.json({ status: 'processed', changes, conflicts });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // 自动提交
  app.post('/api/projects/:projectId/worldbook/auto-commit', (req: Request, res: Response) => {
    try {
      const wb = getWorldbook(req.params.projectId);
      const message = req.body.message || 'Auto commit after sequence completion';
      const hash = wb.commit(message);
      res.json({ status: 'committed', hash });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });
}
