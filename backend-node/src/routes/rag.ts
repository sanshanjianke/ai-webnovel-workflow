// RAG 检索路由 — 多实例管理 + 检索 + 索引
import { Express, Request, Response } from 'express';
import * as path from 'path';
import { getProjectManager } from '../services/project-manager';
import { RAGInstanceStore, KeywordRetriever, createRetrieverForInstance } from '../services/rag-instance-manager';
import { RAGDocument, RAGInstanceType, RAGRetrieverType } from '../protocols';

export function registerRAGRoutes(app: Express): void {
  const pm = getProjectManager();

  function getStore(projectId: string): RAGInstanceStore {
    const project = pm.getProject(projectId);
    if (!project) throw new Error('Project not found');
    return new RAGInstanceStore(project.path);
  }

  // ======================== 实例管理 ========================

  // 列出所有实例
  app.get('/api/projects/:projectId/rags', (req: Request, res: Response) => {
    try {
      const store = getStore(req.params.projectId);
      res.json({ instances: store.listInstances() });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // 创建实例
  app.post('/api/projects/:projectId/rags', (req: Request, res: Response) => {
    try {
      const store = getStore(req.params.projectId);
      const { name, type = 'custom', retrieverType = 'keyword', ...options } = req.body;
      if (!name) return res.status(400).json({ error: 'name is required' });
      const info = store.createInstance(name, type as RAGInstanceType, retrieverType as RAGRetrieverType, options);
      res.json({ instance: info });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // 获取实例详情
  app.get('/api/projects/:projectId/rags/:instanceId', (req: Request, res: Response) => {
    try {
      const store = getStore(req.params.projectId);
      const config = store.getInstance(req.params.instanceId);
      if (!config) return res.status(404).json({ error: 'Instance not found' });
      const docCount = store.getDocuments(req.params.instanceId).length;
      res.json({ instance: config, documentCount: docCount });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // 更新实例配置
  app.put('/api/projects/:projectId/rags/:instanceId', (req: Request, res: Response) => {
    try {
      const store = getStore(req.params.projectId);
      const ok = store.updateInstance(req.params.instanceId, req.body);
      if (!ok) return res.status(404).json({ error: 'Instance not found' });
      res.json({ status: 'updated' });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // 删除实例
  app.delete('/api/projects/:projectId/rags/:instanceId', (req: Request, res: Response) => {
    try {
      const store = getStore(req.params.projectId);
      const ok = store.deleteInstance(req.params.instanceId);
      if (!ok) return res.status(404).json({ error: 'Instance not found' });
      res.json({ status: 'deleted' });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // 导出实例
  app.get('/api/projects/:projectId/rags/:instanceId/export', (req: Request, res: Response) => {
    try {
      const store = getStore(req.params.projectId);
      const data = store.exportInstance(req.params.instanceId);
      if (!data) return res.status(404).json({ error: 'Instance not found' });
      res.json(data);
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // 导入实例
  app.post('/api/projects/:projectId/rags/import', (req: Request, res: Response) => {
    try {
      const store = getStore(req.params.projectId);
      const info = store.importInstance(req.body);
      if (!info) return res.status(400).json({ error: 'Invalid import data' });
      res.json({ instance: info });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // ======================== 文档管理（keyword 实例） ========================

  // 列出文档
  app.get('/api/projects/:projectId/rags/:instanceId/documents', (req: Request, res: Response) => {
    try {
      const store = getStore(req.params.projectId);
      const docs = store.getDocuments(req.params.instanceId);
      res.json({ documents: docs, count: docs.length });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // 添加文档
  app.post('/api/projects/:projectId/rags/:instanceId/documents', (req: Request, res: Response) => {
    try {
      const store = getStore(req.params.projectId);
      const { documents } = req.body;
      if (!Array.isArray(documents)) return res.status(400).json({ error: 'documents array is required' });
      const docs: RAGDocument[] = documents.map((d: Record<string, unknown>) => ({
        id: (d.id as string) || `doc_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
        content: (d.content as string) || '',
        metadata: (d.metadata as Record<string, unknown>) || {}
      }));
      const added = store.addDocuments(req.params.instanceId, docs);
      res.json({ status: 'added', count: added });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // 删除文档
  app.delete('/api/projects/:projectId/rags/:instanceId/documents', (req: Request, res: Response) => {
    try {
      const store = getStore(req.params.projectId);
      const { ids } = req.body;
      if (!Array.isArray(ids)) return res.status(400).json({ error: 'ids array is required' });
      const deleted = store.deleteDocuments(req.params.instanceId, ids);
      res.json({ status: 'deleted', count: deleted });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // 清空文档
  app.delete('/api/projects/:projectId/rags/:instanceId/documents/all', (req: Request, res: Response) => {
    try {
      const store = getStore(req.params.projectId);
      store.clearDocuments(req.params.instanceId);
      res.json({ status: 'cleared' });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // ======================== 检索 ========================

  // 检索（自动使用实例配置的检索器）
  app.post('/api/projects/:projectId/rags/:instanceId/search', (req: Request, res: Response) => {
    try {
      const store = getStore(req.params.projectId);
      const retriever = createRetrieverForInstance(store, req.params.instanceId);
      if (!retriever) return res.status(404).json({ error: 'Instance not found or unsupported retriever type' });

      const { query, k = 5 } = req.body;
      if (!query) return res.status(400).json({ error: 'query is required' });

      const startTime = Date.now();
      const results = retriever.retrieve(query, k);
      const duration = Date.now() - startTime;

      // 记录检索日志
      store.appendSearchLog(req.params.instanceId, {
        query, resultsCount: results.length, topScore: results[0]?.score || 0, duration
      });

      res.json({ query, results, duration });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // 索引文档（兼容旧 API）
  app.post('/api/projects/:projectId/rags/:instanceId/index', async (req: Request, res: Response) => {
    try {
      const store = getStore(req.params.projectId);
      const { documents } = req.body;
      if (!Array.isArray(documents)) return res.status(400).json({ error: 'documents array is required' });

      const docs: RAGDocument[] = documents.map((d: Record<string, unknown>) => ({
        id: (d.id as string) || `doc_${Date.now()}`,
        content: (d.content as string) || '',
        metadata: (d.metadata as Record<string, unknown>) || {}
      }));
      const added = store.addDocuments(req.params.instanceId, docs);
      res.json({ status: 'indexed', count: added });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // 检索日志
  app.get('/api/projects/:projectId/rags/:instanceId/log', (req: Request, res: Response) => {
    try {
      const store = getStore(req.params.projectId);
      const limit = parseInt(req.query.limit as string) || 50;
      const entries = store.getSearchLog(req.params.instanceId, limit);
      res.json({ entries });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // ======================== 旧 API（向后兼容，操作默认实例） ========================

  app.post('/api/projects/:projectId/rag/search', async (req: Request, res: Response) => {
    try {
      const store = getStore(req.params.projectId);
      const retriever = createRetrieverForInstance(store, '默认实例');
      if (!retriever) return res.status(404).json({ error: 'Default instance not found' });
      const { query, k = 5 } = req.body;
      const results = retriever.retrieve(query, k);
      res.json({ query, results });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  app.post('/api/projects/:projectId/rag/index', async (req: Request, res: Response) => {
    try {
      const store = getStore(req.params.projectId);
      const { documents } = req.body;
      const docs: RAGDocument[] = (documents || []).map((d: Record<string, unknown>) => ({
        id: d.id as string,
        content: d.content as string,
        metadata: (d.metadata as Record<string, unknown>) || {}
      }));
      const added = store.addDocuments('默认实例', docs);
      res.json({ status: 'indexed', count: added });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  app.get('/api/projects/:projectId/rag/stats', async (req: Request, res: Response) => {
    try {
      const store = getStore(req.params.projectId);
      const instances = store.listInstances();
      const count = instances.reduce((sum, i) => sum + i.documentCount, 0);
      res.json({ count, instanceCount: instances.length, instances });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });
}
