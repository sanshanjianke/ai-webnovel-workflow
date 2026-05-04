// 世界书服务
import * as fs from 'fs';
import * as path from 'path';
import * as crypto from 'crypto';
import { WorldBook, WorldBookEntry, CommitRecord } from '../protocols';

export class STStyleWorldBook implements WorldBook {
  private projectPath: string;
  private worldbookPath: string;
  private commitsPath: string;
  private entries: Map<string, WorldBookEntry> = new Map();
  private commits: CommitRecord[] = [];

  constructor(projectPath: string) {
    this.projectPath = projectPath;
    this.worldbookPath = path.join(projectPath, 'worldbook.json');
    this.commitsPath = path.join(projectPath, 'commits.json');
    this.load();
  }

  private load(): void {
    if (fs.existsSync(this.worldbookPath)) {
      const data = JSON.parse(fs.readFileSync(this.worldbookPath, 'utf-8'));
      for (const [id, entry] of Object.entries(data.entries || {})) {
        this.entries.set(id, entry as WorldBookEntry);
      }
    }

    if (fs.existsSync(this.commitsPath)) {
      this.commits = JSON.parse(fs.readFileSync(this.commitsPath, 'utf-8'));
    }
  }

  private save(): void {
    const data = {
      entries: Object.fromEntries(this.entries)
    };
    fs.writeFileSync(this.worldbookPath, JSON.stringify(data, null, 2), 'utf-8');
  }

  private saveCommits(): void {
    fs.writeFileSync(this.commitsPath, JSON.stringify(this.commits, null, 2), 'utf-8');
  }

  getActiveEntries(contextTokens: string[]): WorldBookEntry[] {
    const result: WorldBookEntry[] = [];

    for (const entry of this.entries.values()) {
      // 常驻条目直接加入
      if (entry.constant) {
        result.push(entry);
        continue;
      }

      // 检查触发词
      for (const key of entry.keys) {
        if (contextTokens.some(token => token.includes(key))) {
          if (entry.secondaryKeys && entry.secondaryKeys.length > 0) {
            if (entry.secondaryKeys.some(sk => contextTokens.some(token => token.includes(sk)))) {
              result.push(entry);
              break;
            }
          } else {
            result.push(entry);
            break;
          }
        }
      }
    }

    // 按优先级排序
    result.sort((a, b) => (b.priority || 0) - (a.priority || 0));
    return result;
  }

  getEntry(entryId: string): WorldBookEntry | null {
    return this.entries.get(entryId) || null;
  }

  updateEntry(entryId: string, data: Partial<WorldBookEntry>): void {
    const entry = this.entries.get(entryId);
    if (entry) {
      this.entries.set(entryId, { ...entry, ...data });
      this.save();
    }
  }

  createEntry(entry: WorldBookEntry): void {
    this.entries.set(entry.id, entry);
    this.save();
  }

  deleteEntry(entryId: string): void {
    this.entries.delete(entryId);
    this.save();
  }

  listAllEntries(): WorldBookEntry[] {
    return Array.from(this.entries.values());
  }

  commit(message: string): string {
    const content = JSON.stringify(Object.fromEntries(this.entries));
    const hash = crypto.createHash('sha256').update(content).digest('hex').slice(0, 12);

    const commitRecord: CommitRecord = {
      hash,
      message,
      timestamp: new Date().toISOString(),
      entryCount: this.entries.size
    };

    this.commits.push(commitRecord);
    this.saveCommits();
    return hash;
  }

  listCommits(): CommitRecord[] {
    return [...this.commits];
  }

  revert(commitHash: string): void {
    // 简化实现：暂不支持回滚
    throw new Error('Revert not implemented');
  }
}

// 世界书管理 Agent
export class WorldBookManager {
  private worldbook: STStyleWorldBook;

  constructor(worldbook: STStyleWorldBook) {
    this.worldbook = worldbook;
  }

  async processSequence(sequenceContent: string, sequenceId: string): Promise<Record<string, unknown>> {
    // 简化实现：提取变化并更新世界书
    // 实际应该调用 LLM 分析
    return {
      newCharacters: [],
      updatedCharacters: [],
      newForeshadowing: [],
      resolvedForeshadowing: [],
      stateChanges: [],
      conflicts: []
    };
  }

  getConflicts(changes: Record<string, unknown>): unknown[] {
    return (changes.conflicts as unknown[]) || [];
  }
}
