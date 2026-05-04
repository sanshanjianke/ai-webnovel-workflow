// RAG 检索服务
import { RAGRetriever, RAGDocument, RetrievedDoc } from '../protocols';

// 简单的内存向量检索（生产环境应使用 ChromaDB）
export class SimpleVectorRetriever implements RAGRetriever {
  private documents: Map<string, RAGDocument> = new Map();
  private persistDir?: string;

  constructor(persistDir?: string) {
    this.persistDir = persistDir;
    if (persistDir) {
      this.loadFromDisk();
    }
  }

  private loadFromDisk(): void {
    if (!this.persistDir) return;
    
    const indexPath = `${this.persistDir}/index.json`;
    try {
      const fs = require('fs');
      if (fs.existsSync(indexPath)) {
        const data = JSON.parse(fs.readFileSync(indexPath, 'utf-8'));
        for (const doc of data) {
          this.documents.set(doc.id, doc);
        }
      }
    } catch {
      // 忽略加载错误
    }
  }

  private saveToDisk(): void {
    if (!this.persistDir) return;
    
    const fs = require('fs');
    const path = require('path');
    
    const dir = path.dirname(this.persistDir);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }

    const data = Array.from(this.documents.values());
    fs.writeFileSync(`${this.persistDir}/index.json`, JSON.stringify(data, null, 2));
  }

  async retrieve(query: string, k: number = 5): Promise<RetrievedDoc[]> {
    const results: RetrievedDoc[] = [];
    const queryLower = query.toLowerCase();

    for (const doc of this.documents.values()) {
      // 简单的关键词匹配（生产环境应使用向量相似度）
      const contentLower = doc.content.toLowerCase();
      let score = 0;

      // 计算匹配分数
      const queryWords = queryLower.split(/\s+/);
      for (const word of queryWords) {
        if (contentLower.includes(word)) {
          score += 1;
        }
      }

      // 归一化分数
      score = score / queryWords.length;

      if (score > 0) {
        results.push({
          id: doc.id,
          content: doc.content,
          score,
          metadata: doc.metadata
        });
      }
    }

    // 按分数排序，返回 top k
    results.sort((a, b) => b.score - a.score);
    return results.slice(0, k);
  }

  async index(documents: RAGDocument[]): Promise<void> {
    for (const doc of documents) {
      this.documents.set(doc.id, doc);
    }
    this.saveToDisk();
  }

  async delete(ids: string[]): Promise<void> {
    for (const id of ids) {
      this.documents.delete(id);
    }
    this.saveToDisk();
  }

  async count(): Promise<number> {
    return this.documents.size;
  }
}

// RAG 工厂
export function createRAGRetriever(type: string, persistDir?: string): RAGRetriever {
  switch (type) {
    case 'simple_vector':
    default:
      return new SimpleVectorRetriever(persistDir);
  }
}
