// 世界书服务
import * as fs from 'fs';
import * as path from 'path';
import * as crypto from 'crypto';
import { WorldBook, WorldBookEntry, WorldBookInfo, WorldBookCollection, CommitRecord, SelectiveLogic } from '../protocols';

// ── 单书文件存储 ──

export class STStyleWorldBook implements WorldBook {
  protected filePath: string;
  protected commitsPath: string;
  protected entries: Map<string, WorldBookEntry> = new Map();
  protected commits: CommitRecord[] = [];
  protected bookName: string;
  protected bookId: string;
  protected createdAt: string;

  constructor(filePath: string) {
    // 向后兼容：如果是目录则拼接 worldbook.json
    if (!filePath.endsWith('.json')) {
      this.filePath = path.join(filePath, 'worldbook.json');
    } else {
      this.filePath = filePath;
    }
    this.commitsPath = this.filePath.replace(/\.json$/, '_commits.json');
    this.bookName = path.basename(this.filePath, '.json');
    this.bookId = this.bookName;
    this.createdAt = '';
    this.load();
  }

  // ── 持久化 ──

  protected load(): void {
    if (fs.existsSync(this.filePath)) {
      const data = JSON.parse(fs.readFileSync(this.filePath, 'utf-8'));
      if (data.entries) {
        for (const [id, entry] of Object.entries(data.entries)) {
          this.entries.set(id, entry as WorldBookEntry);
        }
      }
      this.bookName = data.name || this.bookName;
      this.createdAt = data.createdAt || '';
    }

    if (fs.existsSync(this.commitsPath)) {
      this.commits = JSON.parse(fs.readFileSync(this.commitsPath, 'utf-8'));
    }
  }

  protected save(): void {
    const data = {
      name: this.bookName,
      createdAt: this.createdAt || new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      entries: Object.fromEntries(this.entries)
    };
    const dir = path.dirname(this.filePath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(this.filePath, JSON.stringify(data, null, 2), 'utf-8');
  }

  protected saveCommits(): void {
    fs.writeFileSync(this.commitsPath, JSON.stringify(this.commits, null, 2), 'utf-8');
  }

  // ── 查询 ──

  getInfo(): WorldBookInfo {
    return {
      bookId: this.bookId,
      name: this.bookName,
      entryCount: this.entries.size,
      createdAt: this.createdAt || '',
      updatedAt: new Date().toISOString()
    };
  }

  setName(name: string): void {
    this.bookName = name;
    this.save();
  }

  getActiveEntries(contextTokens: string[]): WorldBookEntry[] {
    const result: WorldBookEntry[] = [];

    for (const entry of this.entries.values()) {
      if (entry.disable) continue;

      // 常驻条目直接加入
      if (entry.constant) {
        result.push(entry);
        continue;
      }

      // 检查主触发词
      const primaryHit = entry.keys.some(key =>
        contextTokens.some(token => this.matchKey(key, token, entry))
      );

      if (!primaryHit) continue;

      // 选择性逻辑
      if (entry.selective !== false && entry.secondaryKeys && entry.secondaryKeys.length > 0) {
        const logic = entry.selectiveLogic || SelectiveLogic.AND_ANY;
        const secondaryHit = (sk: string) =>
          contextTokens.some(token => this.matchKey(sk, token, entry));

        if (logic === SelectiveLogic.AND_ALL && !entry.secondaryKeys.every(sk => secondaryHit(sk))) continue;
        if (logic === SelectiveLogic.NOT_ALL && entry.secondaryKeys.every(sk => secondaryHit(sk))) continue;
        if (logic === SelectiveLogic.NOT_ANY && entry.secondaryKeys.some(sk => secondaryHit(sk))) continue;
        // AND_ANY: primary matched already, no additional check needed
      }

      result.push(entry);
    }

    // 按优先级排序
    result.sort((a, b) => (b.priority || 0) - (a.priority || 0));
    return result;
  }

  private matchKey(key: string, token: string, entry: WorldBookEntry): boolean {
    const cs = entry.caseSensitive || false;
    if (entry.matchWholeWords) {
      const re = new RegExp(`\\b${this.escapeRegex(key)}\\b`, cs ? 'g' : 'gi');
      return re.test(token);
    }
    if (!cs) {
      return token.toLowerCase().includes(key.toLowerCase());
    }
    return token.includes(key);
  }

  private escapeRegex(s: string): string {
    return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  getEntry(entryId: string): WorldBookEntry | null {
    return this.entries.get(entryId) || null;
  }

  listAllEntries(): WorldBookEntry[] {
    return Array.from(this.entries.values());
  }

  // ── 变更 ──

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

  // ── 版本管理 ──

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
    throw new Error('Revert not implemented');
  }
}

// ── 多书管理 ──

export class WorldBookStore implements WorldBookCollection {
  private booksDir: string;
  private defaultBook: STStyleWorldBook;

  constructor(projectPath: string) {
    this.booksDir = path.join(projectPath, 'worldbooks');
    const defaultPath = path.join(projectPath, 'worldbook.json');

    // 向后兼容：如果存在旧 worldbook.json，迁移到 worldbooks/default.json
    if (fs.existsSync(defaultPath) && !fs.existsSync(this.booksDir)) {
      fs.mkdirSync(this.booksDir, { recursive: true });
      const defaultNewPath = path.join(this.booksDir, 'default.json');
      fs.copyFileSync(defaultPath, defaultNewPath);
      // 保留旧文件做向后兼容
    }

    if (!fs.existsSync(this.booksDir)) {
      fs.mkdirSync(this.booksDir, { recursive: true });
    }

    // 确保默认书存在
    const defaultBookPath = path.join(this.booksDir, 'default.json');
    if (!fs.existsSync(defaultBookPath)) {
      fs.writeFileSync(defaultBookPath, JSON.stringify({
        name: '默认世界书',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        entries: {}
      }, null, 2), 'utf-8');
    }

    this.defaultBook = new STStyleWorldBook(defaultBookPath);
  }

  listBooks(): WorldBookInfo[] {
    const books: WorldBookInfo[] = [];
    if (!fs.existsSync(this.booksDir)) return books;

    for (const file of fs.readdirSync(this.booksDir)) {
      if (!file.endsWith('.json') || file.endsWith('_commits.json')) continue;
      const filePath = path.join(this.booksDir, file);
      try {
        const data = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
        const bookId = file.replace('.json', '');
        books.push({
          bookId,
          name: data.name || bookId,
          entryCount: Object.keys(data.entries || {}).length,
          createdAt: data.createdAt || '',
          updatedAt: data.updatedAt || ''
        });
      } catch { /* skip corrupted */ }
    }

    return books.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
  }

  createBook(name: string): WorldBookInfo {
    const now = new Date().toISOString();
    // sanitize bookId from name
    const bookId = name.replace(/[^a-zA-Z0-9一-鿿_-]/g, '_').slice(0, 64) || 'book';
    const filePath = path.join(this.booksDir, `${bookId}.json`);

    // 去重
    let finalId = bookId;
    let counter = 1;
    while (fs.existsSync(path.join(this.booksDir, `${finalId}.json`))) {
      finalId = `${bookId}_${counter}`;
      counter++;
    }

    const data = {
      name,
      createdAt: now,
      updatedAt: now,
      entries: {}
    };
    fs.writeFileSync(path.join(this.booksDir, `${finalId}.json`), JSON.stringify(data, null, 2), 'utf-8');

    return {
      bookId: finalId,
      name,
      entryCount: 0,
      createdAt: now,
      updatedAt: now
    };
  }

  deleteBook(bookId: string): boolean {
    if (bookId === 'default') return false; // 默认书不可删除
    const filePath = path.join(this.booksDir, `${bookId}.json`);
    const commitsPath = path.join(this.booksDir, `${bookId}_commits.json`);
    let deleted = false;
    if (fs.existsSync(filePath)) { fs.unlinkSync(filePath); deleted = true; }
    if (fs.existsSync(commitsPath)) { fs.unlinkSync(commitsPath); }
    return deleted;
  }

  getBook(bookId: string): WorldBook | null {
    const filePath = path.join(this.booksDir, `${bookId}.json`);
    if (!fs.existsSync(filePath)) return null;
    return new STStyleWorldBook(filePath);
  }

  getDefaultBook(): WorldBook {
    return this.defaultBook;
  }
}

// ── 世界书管理 Agent ──

export class WorldBookManager {
  private worldbook: WorldBook;

  constructor(worldbook: WorldBook) {
    this.worldbook = worldbook;
  }

  async processSequence(sequenceContent: string, sequenceId: string): Promise<Record<string, unknown>> {
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
