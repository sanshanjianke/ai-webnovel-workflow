// 项目管理路由
import { Express, Request, Response } from 'express';
import { getProjectManager } from '../services/project-manager';

export function registerProjectRoutes(app: Express): void {
  const pm = getProjectManager();

  // 列出所有项目
  app.get('/api/projects', (req: Request, res: Response) => {
    const projects = pm.listProjects();
    res.json(projects.map(p => ({
      id: p.id,
      config: p.config
    })));
  });

  // 创建项目
  app.post('/api/projects', (req: Request, res: Response) => {
    const { name, description, genre, targetPlatform, drivingMode } = req.body;
    
    if (!name) {
      return res.status(400).json({ error: 'Name is required' });
    }

    const project = pm.createProject(name, {
      description,
      genre,
      targetPlatform,
      drivingMode
    });

    res.json({ id: project.id, config: project.config });
  });

  // 获取项目详情
  app.get('/api/projects/:projectId', (req: Request, res: Response) => {
    const project = pm.getProject(req.params.projectId);
    if (!project) {
      return res.status(404).json({ error: 'Project not found' });
    }
    res.json({ id: project.id, config: project.config });
  });

  // 更新项目
  app.put('/api/projects/:projectId', (req: Request, res: Response) => {
    const project = pm.updateProject(req.params.projectId, req.body);
    if (!project) {
      return res.status(404).json({ error: 'Project not found' });
    }
    res.json({ id: project.id, config: project.config });
  });

  // 删除项目
  app.delete('/api/projects/:projectId', (req: Request, res: Response) => {
    const success = pm.deleteProject(req.params.projectId);
    if (!success) {
      return res.status(404).json({ error: 'Project not found' });
    }
    res.json({ status: 'deleted' });
  });
}
