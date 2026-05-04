// 文档库路由
import { Express, Request, Response } from 'express';
import { getProjectManager } from '../services/project-manager';
import { getLibraryManager } from '../services/library';
import { DocSource, DocStatus } from '../protocols';

export function registerLibraryRoutes(app: Express): void {
  const pm = getProjectManager();

  function getLibrary(projectId: string) {
    const project = pm.getProject(projectId);
    if (!project) {
      throw new Error('Project not found');
    }
    return getLibraryManager(project.path);
  }

  // 文档树
  app.get('/api/projects/:projectId/library', (req: Request, res: Response) => {
    try {
      const library = getLibrary(req.params.projectId);
      const includeArchived = req.query.includeArchived === 'true';
      const tree = library.getTree(includeArchived);
      res.json({ tree });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // 新增文档
  app.post('/api/projects/:projectId/library', (req: Request, res: Response) => {
    try {
      const library = getLibrary(req.params.projectId);
      const { name, layer, content, source, parentUid, directory, tags } = req.body;
      
      const uid = library.addDocument(name, layer, content, {
        source: source as DocSource,
        parentUid,
        directory,
        tags
      });

      res.json({ uid, status: 'created' });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // 获取文档
  app.get('/api/projects/:projectId/library/:uid', (req: Request, res: Response) => {
    try {
      const library = getLibrary(req.params.projectId);
      const result = library.getDocument(req.params.uid);
      
      if (!result) {
        return res.status(404).json({ error: 'Document not found' });
      }

      res.json(result);
    } catch (error) {
      res.status(404).json({ error: String(error) });
    }
  });

  // 更新文档
  app.put('/api/projects/:projectId/library/:uid', (req: Request, res: Response) => {
    try {
      const library = getLibrary(req.params.projectId);
      const updated = library.updateEntry(req.params.uid, req.body);
      
      if (!updated) {
        return res.status(404).json({ error: 'Document not found' });
      }

      res.json({ status: 'updated', entry: updated });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // 删除文档
  app.delete('/api/projects/:projectId/library/:uid', (req: Request, res: Response) => {
    try {
      const library = getLibrary(req.params.projectId);
      const success = library.deleteDocument(req.params.uid);
      
      if (!success) {
        return res.status(404).json({ error: 'Document not found' });
      }

      res.json({ status: 'deleted' });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // 更新内容
  app.put('/api/projects/:projectId/library/:uid/content', (req: Request, res: Response) => {
    try {
      const library = getLibrary(req.params.projectId);
      const success = library.updateContent(req.params.uid, req.body.content);
      
      if (!success) {
        return res.status(404).json({ error: 'Document not found' });
      }

      res.json({ status: 'updated' });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // 归档
  app.put('/api/projects/:projectId/library/:uid/archive', (req: Request, res: Response) => {
    try {
      const library = getLibrary(req.params.projectId);
      const archive = req.body.archive !== false;
      const entry = library.archiveDocument(req.params.uid, archive);
      
      if (!entry) {
        return res.status(404).json({ error: 'Document not found' });
      }

      res.json({ status: archive ? 'archived' : 'unarchived', entry });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // 导出
  app.get('/api/projects/:projectId/library/:uid/export', (req: Request, res: Response) => {
    try {
      const library = getLibrary(req.params.projectId);
      const result = library.getDocument(req.params.uid);
      
      if (!result) {
        return res.status(404).json({ error: 'Document not found' });
      }

      res.json(result);
    } catch (error) {
      res.status(404).json({ error: String(error) });
    }
  });

  // 活跃文档
  app.get('/api/projects/:projectId/library/active/:layer', (req: Request, res: Response) => {
    try {
      const library = getLibrary(req.params.projectId);
      const result = library.getActiveDocument(req.params.layer);
      
      if (!result) {
        return res.status(404).json({ error: 'No active document for this layer' });
      }

      res.json(result);
    } catch (error) {
      res.status(404).json({ error: String(error) });
    }
  });

  app.put('/api/projects/:projectId/library/active/:layer', (req: Request, res: Response) => {
    try {
      const library = getLibrary(req.params.projectId);
      const { uid } = req.body;
      const success = library.setActive(req.params.layer, uid);
      
      if (!success) {
        return res.status(400).json({ error: 'Invalid document or layer' });
      }

      res.json({ status: 'set' });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // 导入文件
  app.post('/api/projects/:projectId/library/import', (req: Request, res: Response) => {
    try {
      const library = getLibrary(req.params.projectId);
      const { name, content, format, directory, tags } = req.body;
      
      const uid = library.importFile(name, content, format, directory, tags);
      res.json({ uid, status: 'imported' });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // 目录管理
  app.post('/api/projects/:projectId/library/directories', (req: Request, res: Response) => {
    try {
      const library = getLibrary(req.params.projectId);
      const { path } = req.body;
      const success = library.createDirectory(path);
      res.json({ status: success ? 'created' : 'exists' });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  app.delete('/api/projects/:projectId/library/directories', (req: Request, res: Response) => {
    try {
      const library = getLibrary(req.params.projectId);
      const { path } = req.body;
      const success = library.deleteDirectory(path);
      res.json({ status: success ? 'deleted' : 'not_found' });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });
}
