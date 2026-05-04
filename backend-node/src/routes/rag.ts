// RAG 检索路由
import { Express, Request, Response } from 'express';
import * as path from 'path';
import { getProjectManager } from '../services/project-manager';
import { SimpleVectorRetriever } from '../services/rag';
import { RAGDocument } from '../protocols';

export function registerRAGRoutes(app: Express): void {
  const pm = getProjectManager();

  function getRetriever(projectId: string): SimpleVectorRetriever {
    const project = pm.getProject(projectId);
    if (!project) {
      throw new Error('Project not found');
    }
    const ragPath = path.join(project.path, 'rag');
    return new SimpleVectorRetriever(ragPath);
  }

  // 语义搜索
  app.post('/api/projects/:projectId/rag/search', async (req: Request, res: Response) => {
    try {
      const retriever = getRetriever(req.params.projectId);
      const { query, k = 5 } = req.body;
      const results = await retriever.retrieve(query, k);
      res.json({ query, results });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // 索引文档
  app.post('/api/projects/:projectId/rag/index', async (req: Request, res: Response) => {
    try {
      const retriever = getRetriever(req.params.projectId);
      const { documents } = req.body;
      
      const docs: RAGDocument[] = documents.map((d: Record<string, unknown>) => ({
        id: d.id as string,
        content: d.content as string,
        metadata: (d.metadata as Record<string, unknown>) || {}
      }));

      await retriever.index(docs);
      res.json({ status: 'indexed', count: docs.length });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // 统计信息
  app.get('/api/projects/:projectId/rag/stats', async (req: Request, res: Response) => {
    try {
      const retriever = getRetriever(req.params.projectId);
      const count = await retriever.count();
      res.json({ count });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });
}
