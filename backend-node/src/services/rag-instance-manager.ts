import * as fs from 'fs';
import * as path from 'path';
import { RAGInstanceConfig, RAGInstanceInfo, RAGRetrieverType, RAGInstanceType, RAGDocument, RetrievedDoc } from '../protocols';

// ============ RAG 实例存储 ============

export class RAGInstanceStore {
  private ragsDir: string;

  constructor(projectPath: string) {
    this.ragsDir = path.join(projectPath, 'rags');
    if (!fs.existsSync(this.ragsDir)) {
      fs.mkdirSync(this.ragsDir, { recursive: true });
    }
    // 迁移旧单例 rag/ → rags/默认实例/
    const oldRagDir = path.join(projectPath, 'rag');
    const defaultDir = path.join(this.ragsDir, '默认实例');
    if (fs.existsSync(oldRagDir) && !fs.existsSync(defaultDir)) {
      this.migrateOldRag(oldRagDir, defaultDir);
    }
    // 确保至少有一个默认实例
    if (this.listInstances().length === 0) {
      this.createInstance('默认实例', 'history', 'keyword');
    }
  }

  private migrateOldRag(oldDir: string, newDir: string): void {
    try {
      fs.mkdirSync(newDir, { recursive: true });
      const indexJson = path.join(oldDir, 'index.json');
      if (fs.existsSync(indexJson)) {
        fs.copyFileSync(indexJson, path.join(newDir, 'documents.json'));
      }
      const config: RAGInstanceConfig = {
        instanceId: '默认实例',
        name: '默认实例',
        type: 'history',
        retrieverType: 'keyword',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      };
      fs.writeFileSync(path.join(newDir, 'instance.json'), JSON.stringify(config, null, 2));
    } catch {}
  }

  // ── 实例 CRUD ──

  listInstances(): RAGInstanceInfo[] {
    const instances: RAGInstanceInfo[] = [];
    if (!fs.existsSync(this.ragsDir)) return instances;

    for (const dir of fs.readdirSync(this.ragsDir)) {
      const instPath = path.join(this.ragsDir, dir);
      const configPath = path.join(instPath, 'instance.json');
      if (!fs.statSync(instPath).isDirectory()) continue;
      if (!fs.existsSync(configPath)) continue;

      try {
        const config: RAGInstanceConfig = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
        const docCount = this.getDocumentCount(config.instanceId);
        instances.push({
          instanceId: config.instanceId,
          name: config.name,
          type: config.type,
          retrieverType: config.retrieverType,
          documentCount: docCount,
          description: config.description,
          createdAt: config.createdAt,
          updatedAt: config.updatedAt
        });
      } catch {}
    }

    return instances.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
  }

  getInstance(instanceId: string): RAGInstanceConfig | null {
    const configPath = path.join(this.ragsDir, instanceId, 'instance.json');
    if (!fs.existsSync(configPath)) return null;
    try {
      return JSON.parse(fs.readFileSync(configPath, 'utf-8'));
    } catch {
      return null;
    }
  }

  createInstance(name: string, type: RAGInstanceType, retrieverType: RAGRetrieverType, options?: Partial<RAGInstanceConfig>): RAGInstanceInfo {
    const instanceId = name.replace(/[^a-zA-Z0-9一-鿿_-]/g, '_').slice(0, 64) || 'instance';
    let finalId = instanceId;
    let counter = 1;
    while (fs.existsSync(path.join(this.ragsDir, finalId))) {
      finalId = `${instanceId}_${counter}`;
      counter++;
    }

    const now = new Date().toISOString();
    const config: RAGInstanceConfig = {
      instanceId: finalId,
      name,
      type,
      retrieverType,
      embeddingModel: retrieverType !== 'keyword' ? (options?.embeddingModel || 'text-embedding-v3') : undefined,
      slicingDimensions: retrieverType !== 'keyword' ? (options?.slicingDimensions || ['plot', 'character', 'emotion', 'function']) : undefined,
      enhancementEnabled: retrieverType === 'hybrid' ? (options?.enhancementEnabled ?? true) : undefined,
      maxResults: options?.maxResults || 5,
      maxInjectionTokens: options?.maxInjectionTokens || 2000,
      vectorWeight: retrieverType === 'hybrid' ? (options?.vectorWeight ?? 0.6) : (retrieverType === 'vector' ? 1.0 : undefined),
      keywordWeight: retrieverType === 'hybrid' ? (options?.keywordWeight ?? 0.4) : (retrieverType === 'keyword' ? 1.0 : undefined),
      threshold: options?.threshold || 0.2,
      autoIndex: options?.autoIndex ?? (retrieverType !== 'keyword'),
      createdAt: now,
      updatedAt: now
    };

    const instDir = path.join(this.ragsDir, finalId);
    fs.mkdirSync(instDir, { recursive: true });
    fs.writeFileSync(path.join(instDir, 'instance.json'), JSON.stringify(config, null, 2));
    fs.writeFileSync(path.join(instDir, 'documents.json'), JSON.stringify([], null, 2));
    if (retrieverType !== 'keyword') {
      fs.mkdirSync(path.join(instDir, 'slices'), { recursive: true });
    }

    return {
      instanceId: finalId,
      name,
      type,
      retrieverType,
      documentCount: 0,
      createdAt: now,
      updatedAt: now
    };
  }

  updateInstance(instanceId: string, updates: Partial<RAGInstanceConfig>): boolean {
    const configPath = path.join(this.ragsDir, instanceId, 'instance.json');
    if (!fs.existsSync(configPath)) return false;

    const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
    Object.assign(config, updates, { updatedAt: new Date().toISOString() });
    fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
    return true;
  }

  deleteInstance(instanceId: string): boolean {
    const instDir = path.join(this.ragsDir, instanceId);
    if (!fs.existsSync(instDir)) return false;
    fs.rmSync(instDir, { recursive: true });
    return true;
  }

  // ── 文档管理（keyword 使用，hybrid/vector 也存一份摘要） ──

  private getDocumentCount(instanceId: string): number {
    try {
      const docsPath = path.join(this.ragsDir, instanceId, 'documents.json');
      if (!fs.existsSync(docsPath)) return 0;
      return JSON.parse(fs.readFileSync(docsPath, 'utf-8')).length;
    } catch { return 0; }
  }

  getDocuments(instanceId: string): RAGDocument[] {
    try {
      const docsPath = path.join(this.ragsDir, instanceId, 'documents.json');
      if (!fs.existsSync(docsPath)) return [];
      return JSON.parse(fs.readFileSync(docsPath, 'utf-8'));
    } catch { return []; }
  }

  addDocuments(instanceId: string, documents: RAGDocument[]): number {
    const docs = this.getDocuments(instanceId);
    const existingIds = new Set(docs.map(d => d.id));
    let added = 0;
    for (const doc of documents) {
      if (!existingIds.has(doc.id)) {
        docs.push(doc);
        existingIds.add(doc.id);
        added++;
      }
    }
    const docsPath = path.join(this.ragsDir, instanceId, 'documents.json');
    fs.writeFileSync(docsPath, JSON.stringify(docs, null, 2));
    return added;
  }

  deleteDocuments(instanceId: string, ids: string[]): number {
    let docs = this.getDocuments(instanceId);
    const before = docs.length;
    docs = docs.filter(d => !ids.includes(d.id));
    const docsPath = path.join(this.ragsDir, instanceId, 'documents.json');
    fs.writeFileSync(docsPath, JSON.stringify(docs, null, 2));
    return before - docs.length;
  }

  clearDocuments(instanceId: string): void {
    const docsPath = path.join(this.ragsDir, instanceId, 'documents.json');
    fs.writeFileSync(docsPath, JSON.stringify([], null, 2));
  }

  getSlicesDir(instanceId: string): string {
    return path.join(this.ragsDir, instanceId, 'slices');
  }

  // ── 检索日志 ──

  getSearchLog(instanceId: string, limit: number = 50): Record<string, unknown>[] {
    try {
      const logPath = path.join(this.ragsDir, instanceId, 'search_log.json');
      if (!fs.existsSync(logPath)) return [];
      const entries = JSON.parse(fs.readFileSync(logPath, 'utf-8'));
      return entries.slice(0, limit);
    } catch { return []; }
  }

  appendSearchLog(instanceId: string, entry: Record<string, unknown>): void {
    try {
      const logPath = path.join(this.ragsDir, instanceId, 'search_log.json');
      let entries: Record<string, unknown>[] = [];
      if (fs.existsSync(logPath)) {
        entries = JSON.parse(fs.readFileSync(logPath, 'utf-8'));
      }
      entries.unshift({ ...entry, id: `log_${Date.now()}`, timestamp: new Date().toISOString() });
      if (entries.length > 200) entries = entries.slice(0, 200);
      fs.writeFileSync(logPath, JSON.stringify(entries, null, 2));
    } catch {}
  }

  // ── 导入导出 ──

  exportInstance(instanceId: string): Record<string, unknown> | null {
    const config = this.getInstance(instanceId);
    if (!config) return null;
    return {
      config,
      documents: this.getDocuments(instanceId),
      searchLog: this.getSearchLog(instanceId, 1000)
    };
  }

  importInstance(data: Record<string, unknown>): RAGInstanceInfo | null {
    const config = data.config as RAGInstanceConfig;
    if (!config || !config.name) return null;

    const info = this.createInstance(
      config.name,
      config.type || 'custom',
      config.retrieverType || 'keyword',
      config
    );

    const docs = data.documents as RAGDocument[];
    if (docs && docs.length > 0) {
      this.addDocuments(info.instanceId, docs);
    }

    return info;
  }
}

// ============ 关键词检索 ============

export class KeywordRetriever {
  private store: RAGInstanceStore;
  private instanceId: string;

  constructor(store: RAGInstanceStore, instanceId: string) {
    this.store = store;
    this.instanceId = instanceId;
  }

  retrieve(query: string, k: number = 5): RetrievedDoc[] {
    const docs = this.store.getDocuments(this.instanceId);
    const results: RetrievedDoc[] = [];
    const queryLower = query.toLowerCase();
    const queryWords = queryLower.split(/\s+/).filter(w => w.length > 0);

    for (const doc of docs) {
      const contentLower = doc.content.toLowerCase();
      let score = 0;
      const matchedWords: string[] = [];

      for (const word of queryWords) {
        if (contentLower.includes(word)) {
          score += 1;
          matchedWords.push(word);
        }
      }

      score = queryWords.length > 0 ? score / queryWords.length : 0;
      const config = this.store.getInstance(this.instanceId);
      const threshold = config?.threshold || 0.1;

      if (score >= threshold) {
        results.push({
          id: doc.id,
          content: doc.content,
          score,
          metadata: { ...doc.metadata, matchedWords }
        });
      }
    }

    results.sort((a, b) => b.score - a.score);
    return results.slice(0, k);
  }

  async index(documents: RAGDocument[]): Promise<void> {
    this.store.addDocuments(this.instanceId, documents);
  }

  async count(): Promise<number> {
    return this.store.getDocuments(this.instanceId).length;
  }
}

// ============ 检索器工厂 ============

export function createRetrieverForInstance(store: RAGInstanceStore, instanceId: string): KeywordRetriever | null {
  const config = store.getInstance(instanceId);
  if (!config) return null;

  switch (config.retrieverType) {
    case 'keyword':
      return new KeywordRetriever(store, instanceId);
    case 'hybrid':
      // 降级为 keyword 直到 ChromaDB 集成完成
      return new KeywordRetriever(store, instanceId);
    case 'vector':
      // 降级为 keyword 直到 ChromaDB 集成完成
      return new KeywordRetriever(store, instanceId);
    default:
      return new KeywordRetriever(store, instanceId);
  }
}
