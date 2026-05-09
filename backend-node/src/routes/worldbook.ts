// 世界书路由
import { Express, Request, Response } from 'express';
import { getProjectManager } from '../services/project-manager';
import { STStyleWorldBook, WorldBookStore, WorldBookManager } from '../services/worldbook';
import { WorldBookEntry, WorldBook } from '../protocols';

export function registerWorldbookRoutes(app: Express): void {
  const pm = getProjectManager();

  function getDefaultBook(projectId: string): STStyleWorldBook {
    const project = pm.getProject(projectId);
    if (!project) throw new Error('Project not found');
    return new STStyleWorldBook(require('path').join(project.path, 'worldbook.json'));
  }

  function getBookStore(projectId: string): WorldBookStore {
    const project = pm.getProject(projectId);
    if (!project) throw new Error('Project not found');
    return new WorldBookStore(project.path);
  }

  function getBook(projectId: string, bookId: string): WorldBook | null {
    const store = getBookStore(projectId);
    if (bookId === 'default' || bookId === '__default__') {
      return store.getDefaultBook();
    }
    return store.getBook(bookId);
  }

  // ══════════════════════════════════════════════
  // 多书管理
  // ══════════════════════════════════════════════

  app.get('/api/projects/:projectId/worldbooks', (req: Request, res: Response) => {
    try {
      const store = getBookStore(req.params.projectId);
      res.json({ books: store.listBooks() });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  app.post('/api/projects/:projectId/worldbooks', (req: Request, res: Response) => {
    try {
      const store = getBookStore(req.params.projectId);
      const { name } = req.body;
      if (!name || !name.trim()) {
        return res.status(400).json({ error: '书名不能为空' });
      }
      const info = store.createBook(name.trim());
      res.json({ status: 'created', book: info });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  app.delete('/api/projects/:projectId/worldbooks/:bookId', (req: Request, res: Response) => {
    try {
      const store = getBookStore(req.params.projectId);
      const ok = store.deleteBook(req.params.bookId);
      if (!ok) return res.status(404).json({ error: 'Book not found or cannot delete default' });
      res.json({ status: 'deleted' });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // 导出世界书（完整 JSON）
  app.get('/api/projects/:projectId/worldbooks/:bookId/export', (req: Request, res: Response) => {
    try {
      const store = getBookStore(req.params.projectId);
      const wb = req.params.bookId === 'default' ? store.getDefaultBook() : store.getBook(req.params.bookId);
      if (!wb) return res.status(404).json({ error: 'Book not found' });
      const data = {
        name: wb.getInfo().name,
        entryCount: wb.getInfo().entryCount,
        entries: Object.fromEntries(
          wb.listAllEntries().map(e => [e.id, e])
        ),
        exportedAt: new Date().toISOString()
      };
      res.json(data);
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // 导入世界书
  app.post('/api/projects/:projectId/worldbooks/import', (req: Request, res: Response) => {
    try {
      const store = getBookStore(req.params.projectId);
      const { name, entries } = req.body;
      if (!entries) return res.status(400).json({ error: 'Missing entries in import data' });
      const bookName = name || '导入的世界书';
      const info = store.createBook(bookName);
      const wb = store.getBook(info.bookId);
      if (!wb) return res.status(500).json({ error: 'Failed to create book' });
      for (const [id, entry] of Object.entries(entries)) {
        wb.createEntry(entry as any);
      }
      res.json({ status: 'imported', book: { ...info, entryCount: Object.keys(entries).length } });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // ══════════════════════════════════════════════
  // 指定书的条目 CRUD
  // ══════════════════════════════════════════════

  app.get('/api/projects/:projectId/worldbooks/:bookId/entries', (req: Request, res: Response) => {
    try {
      const store = getBookStore(req.params.projectId);
      const wb = req.params.bookId === 'default' ? store.getDefaultBook() : store.getBook(req.params.bookId);
      if (!wb) return res.status(404).json({ error: 'Book not found' });
      res.json({ book: wb.getInfo(), entries: wb.listAllEntries() });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  app.post('/api/projects/:projectId/worldbooks/:bookId/entries', (req: Request, res: Response) => {
    try {
      const store = getBookStore(req.params.projectId);
      const wb = req.params.bookId === 'default' ? store.getDefaultBook() : store.getBook(req.params.bookId);
      if (!wb) return res.status(404).json({ error: 'Book not found' });
      const entry: WorldBookEntry = {
        id: req.body.id || `entry_${Date.now()}`,
        keys: req.body.keys || [],
        content: req.body.content || '',
        secondaryKeys: req.body.secondaryKeys || [],
        constant: req.body.constant || false,
        priority: req.body.priority || 10,
        position: req.body.position || 'before_char',
        disable: req.body.disable || false,
        comment: req.body.comment || '',
        selective: req.body.selective !== false,
        selectiveLogic: req.body.selectiveLogic || 'AND_ANY',
        probability: req.body.probability ?? 100,
        depth: req.body.depth ?? 4,
        group: req.body.group || '',
        groupWeight: req.body.groupWeight ?? 100,
        sticky: req.body.sticky ?? null,
        cooldown: req.body.cooldown ?? null,
        delay: req.body.delay ?? null,
        role: req.body.role || '',
        caseSensitive: req.body.caseSensitive || false,
        matchWholeWords: req.body.matchWholeWords || false,
        excludeRecursion: req.body.excludeRecursion || false,
        preventRecursion: req.body.preventRecursion || false,
        delayUntilRecursion: req.body.delayUntilRecursion ?? 0,
        ignoreBudget: req.body.ignoreBudget || false,
        metadata: req.body.metadata || {}
      };
      wb.createEntry(entry);
      res.json({ status: 'created', entry });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  app.put('/api/projects/:projectId/worldbooks/:bookId/entries/:entryId', (req: Request, res: Response) => {
    try {
      const store = getBookStore(req.params.projectId);
      const wb = req.params.bookId === 'default' ? store.getDefaultBook() : store.getBook(req.params.bookId);
      if (!wb) return res.status(404).json({ error: 'Book not found' });
      wb.updateEntry(req.params.entryId, req.body);
      res.json({ status: 'updated' });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  app.delete('/api/projects/:projectId/worldbooks/:bookId/entries/:entryId', (req: Request, res: Response) => {
    try {
      const store = getBookStore(req.params.projectId);
      const wb = req.params.bookId === 'default' ? store.getDefaultBook() : store.getBook(req.params.bookId);
      if (!wb) return res.status(404).json({ error: 'Book not found' });
      wb.deleteEntry(req.params.entryId);
      res.json({ status: 'deleted' });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // ══════════════════════════════════════════════
  // 旧版 API（向下兼容，操作默认书或旧路径）
  // ══════════════════════════════════════════════

  app.get('/api/projects/:projectId/worldbook', (req: Request, res: Response) => {
    try {
      const store = getBookStore(req.params.projectId);
      const wb = store.getDefaultBook();
      res.json({ book: wb.getInfo(), entries: wb.listAllEntries() });
    } catch (error) {
      res.status(404).json({ error: String(error) });
    }
  });

  app.post('/api/projects/:projectId/worldbook', (req: Request, res: Response) => {
    try {
      const store = getBookStore(req.params.projectId);
      const wb = store.getDefaultBook();
      const entry: WorldBookEntry = {
        id: req.body.id,
        keys: req.body.keys || [],
        content: req.body.content || '',
        secondaryKeys: req.body.secondaryKeys || req.body.secondary_keys || [],
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

  // 提交版本（具体路径必须在 :entryId 前）
  app.post('/api/projects/:projectId/worldbook/commit', (req: Request, res: Response) => {
    try {
      const store = getBookStore(req.params.projectId);
      const wb = store.getDefaultBook();
      const message = req.query.message || req.body.message || 'Manual commit';
      const hash = wb.commit(String(message));
      res.json({ status: 'committed', hash });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // 版本历史
  app.get('/api/projects/:projectId/worldbook/history', (req: Request, res: Response) => {
    try {
      const store = getBookStore(req.params.projectId);
      const wb = store.getDefaultBook();
      res.json({ commits: wb.listCommits() });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // AI 自动处理
  app.post('/api/projects/:projectId/worldbook/process-sequence', async (req: Request, res: Response) => {
    try {
      const store = getBookStore(req.params.projectId);
      const wb = store.getDefaultBook();
      const manager = new WorldBookManager(wb);
      const { sequenceContent, sequenceId } = req.body;
      const changes = await manager.processSequence(sequenceContent, sequenceId);
      const conflicts = manager.getConflicts(changes);
      res.json({ status: 'processed', changes, conflicts });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  app.post('/api/projects/:projectId/worldbook/auto-commit', (req: Request, res: Response) => {
    try {
      const store = getBookStore(req.params.projectId);
      const wb = store.getDefaultBook();
      const message = req.body.message || 'Auto commit after sequence completion';
      const hash = wb.commit(message);
      res.json({ status: 'committed', hash });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // 兼容旧前端 PUT/DELETE /api/projects/:id/worldbook/entry/:entryId
  app.put('/api/projects/:projectId/worldbook/entry/:entryId', (req: Request, res: Response) => {
    try {
      const store = getBookStore(req.params.projectId);
      const wb = store.getDefaultBook();
      wb.updateEntry(req.params.entryId, req.body);
      res.json({ status: 'updated' });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  app.delete('/api/projects/:projectId/worldbook/entry/:entryId', (req: Request, res: Response) => {
    try {
      const store = getBookStore(req.params.projectId);
      const wb = store.getDefaultBook();
      wb.deleteEntry(req.params.entryId);
      res.json({ status: 'deleted' });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // :entryId 参数路由放在最后
  app.get('/api/projects/:projectId/worldbook/:entryId', (req: Request, res: Response) => {
    try {
      const store = getBookStore(req.params.projectId);
      const wb = store.getDefaultBook();
      const entry = wb.getEntry(req.params.entryId);
      if (!entry) return res.status(404).json({ error: 'Entry not found' });
      res.json({ entry });
    } catch (error) {
      res.status(404).json({ error: String(error) });
    }
  });

  app.put('/api/projects/:projectId/worldbook/:entryId', (req: Request, res: Response) => {
    try {
      const store = getBookStore(req.params.projectId);
      const wb = store.getDefaultBook();
      wb.updateEntry(req.params.entryId, req.body);
      res.json({ status: 'updated' });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });
}
