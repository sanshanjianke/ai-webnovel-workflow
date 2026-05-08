// 文档库服务
import * as fs from 'fs';
import * as path from 'path';
import * as crypto from 'crypto';
import { DocEntry, DocSource, DocStatus, LibraryManifest } from '../protocols';

export class LibraryManager {
  private projectPath: string;
  private libraryPath: string;
  private manifestPath: string;
  private filesPath: string;
  private manifest!: LibraryManifest;

  constructor(projectPath: string) {
    this.projectPath = projectPath;
    this.libraryPath = path.join(projectPath, 'library');
    this.manifestPath = path.join(this.libraryPath, 'manifest.json');
    this.filesPath = path.join(this.libraryPath, 'files');
    this.init();
  }

  private init(): void {
    fs.mkdirSync(this.libraryPath, { recursive: true });
    fs.mkdirSync(this.filesPath, { recursive: true });
    this.loadManifest();
    this.migrateOldOutputs();
  }

  private loadManifest(): void {
    if (fs.existsSync(this.manifestPath)) {
      this.manifest = JSON.parse(fs.readFileSync(this.manifestPath, 'utf-8'));
      // 确保 activeDocs 存在
      if (!this.manifest.activeDocs) {
        this.manifest.activeDocs = {};
      }
    } else {
      this.manifest = {
        projectId: path.basename(this.projectPath),
        directories: ['/'],
        documents: [],
        activeDocs: {},
        updatedAt: new Date().toISOString()
      };
      this.saveManifest();
    }
  }

  private saveManifest(): void {
    this.manifest.updatedAt = new Date().toISOString();
    fs.writeFileSync(this.manifestPath, JSON.stringify(this.manifest, null, 2), 'utf-8');
  }

  private migrateOldOutputs(): void {
    const migratedMarker = path.join(this.projectPath, 'outputs', '.migrated');
    if (fs.existsSync(migratedMarker)) return;

    const outputsPath = path.join(this.projectPath, 'outputs');
    if (!fs.existsSync(outputsPath)) return;

    const oldFiles: Record<string, [string, string]> = {
      'l1_vision.json': ['l1', 'L1 愿景'],
      'l2_outline.json': ['l2', 'L2 大纲']
    };

    for (const [filename, [layer, prefix]] of Object.entries(oldFiles)) {
      const oldPath = path.join(outputsPath, filename);
      if (fs.existsSync(oldPath)) {
        const content = JSON.parse(fs.readFileSync(oldPath, 'utf-8'));
        const wordCount = this.countWords(content);

        const entry: DocEntry = {
          uid: crypto.randomBytes(4).toString('hex'),
          name: `${prefix} — 迁移自旧版`,
          layer,
          source: DocSource.GENERATE,
          wordCount,
          status: DocStatus.ACTIVE,
          createdAt: new Date().toISOString()
        };

        this.manifest.documents.push(entry);
        this.saveFile(entry.uid, content);
        this.manifest.activeDocs[layer] = entry.uid;
      }
    }

    this.saveManifest();
    fs.writeFileSync(migratedMarker, '', 'utf-8');
  }

  private countWords(content: unknown): number {
    const text = typeof content === 'string' ? content : JSON.stringify(content);
    return text.replace(/\s/g, '').length;
  }

  private saveFile(uid: string, content: unknown): void {
    const filePath = path.join(this.filesPath, `${uid}.json`);
    fs.writeFileSync(filePath, JSON.stringify(content, null, 2), 'utf-8');
  }

  private loadFile(uid: string): unknown | null {
    const filePath = path.join(this.filesPath, `${uid}.json`);
    if (!fs.existsSync(filePath)) return null;
    return JSON.parse(fs.readFileSync(filePath, 'utf-8'));
  }

  private deleteFile(uid: string): void {
    const filePath = path.join(this.filesPath, `${uid}.json`);
    if (fs.existsSync(filePath)) {
      fs.unlinkSync(filePath);
    }
  }

  addDocument(
    name: string,
    layer: string,
    content: unknown,
    options: {
      source?: DocSource;
      parentUid?: string;
      directory?: string;
      tags?: string[];
      status?: DocStatus;
      checkpoint?: Record<string, unknown>;
    } = {}
  ): string {
    const uid = crypto.randomBytes(4).toString('hex');
    const wordCount = this.countWords(content);

    const entry: DocEntry = {
      uid,
      name,
      layer,
      source: options.source || DocSource.GENERATE,
      parentUid: options.parentUid,
      directory: options.directory || '/',
      tags: options.tags || [],
      createdAt: new Date().toISOString(),
      wordCount,
      status: options.status || DocStatus.ACTIVE,
      checkpoint: options.checkpoint
    };

    this.manifest.documents.push(entry);
    this.saveFile(uid, content);
    this.saveManifest();

    return uid;
  }

  getDocument(uid: string): { entry: DocEntry; content: unknown } | null {
    const entry = this.manifest.documents.find(e => e.uid === uid);
    if (!entry) return null;

    const content = this.loadFile(uid);
    if (content === null) return null;

    return { entry, content };
  }

  getEntry(uid: string): DocEntry | null {
    return this.manifest.documents.find(e => e.uid === uid) || null;
  }

  updateEntry(uid: string, updates: Partial<DocEntry>): DocEntry | null {
    const index = this.manifest.documents.findIndex(e => e.uid === uid);
    if (index === -1) return null;

    const entry = this.manifest.documents[index];
    const updatedEntry = {
      ...entry,
      ...updates,
      updatedAt: new Date().toISOString()
    };

    this.manifest.documents[index] = updatedEntry;
    this.saveManifest();
    return updatedEntry;
  }

  updateContent(uid: string, content: unknown): boolean {
    const entry = this.getEntry(uid);
    if (!entry) return false;

    this.saveFile(uid, content);
    const wordCount = this.countWords(content);
    this.updateEntry(uid, { wordCount });
    return true;
  }

  deleteDocument(uid: string): boolean {
    const index = this.manifest.documents.findIndex(e => e.uid === uid);
    if (index === -1) return false;

    this.manifest.documents.splice(index, 1);
    this.deleteFile(uid);

    // 清除活跃文档引用
    for (const [layer, activeUid] of Object.entries(this.manifest.activeDocs)) {
      if (activeUid === uid) {
        delete this.manifest.activeDocs[layer];
      }
    }

    this.saveManifest();
    return true;
  }

  archiveDocument(uid: string, archive: boolean = true): DocEntry | null {
    return this.updateEntry(uid, {
      status: archive ? DocStatus.ARCHIVED : DocStatus.ACTIVE
    });
  }

  setActive(layer: string, uid: string): boolean {
    const entry = this.getEntry(uid);
    if (!entry) return false;

    this.manifest.activeDocs[layer] = uid;
    this.saveManifest();
    return true;
  }

  getActive(layer: string): string | null {
    return this.manifest.activeDocs[layer] || null;
  }

  getActiveDocument(layer: string): { entry: DocEntry; content: unknown } | null {
    const uid = this.getActive(layer);
    if (!uid) return null;
    return this.getDocument(uid);
  }

  listDocuments(
    layer?: string,
    directory?: string,
    includeArchived: boolean = false
  ): DocEntry[] {
    return this.manifest.documents.filter(entry => {
      if (layer && entry.layer !== layer) return false;
      if (directory && entry.directory !== directory) return false;
      if (!includeArchived && entry.status === DocStatus.ARCHIVED) return false;
      return true;
    }).sort((a, b) => (b.createdAt || '').localeCompare(a.createdAt || ''));
  }

  getTree(includeArchived: boolean = false): Record<string, DocEntry[]> {
    const tree: Record<string, DocEntry[]> = {};

    for (const entry of this.manifest.documents) {
      if (!includeArchived && entry.status === DocStatus.ARCHIVED) continue;
      
      const dir = entry.directory || '/';
      if (!tree[dir]) tree[dir] = [];
      tree[dir].push(entry);
    }

    return tree;
  }

  createDirectory(path: string): boolean {
    if (!path.startsWith('/')) path = '/' + path;
    if (!this.manifest.directories.includes(path)) {
      this.manifest.directories.push(path);
      this.saveManifest();
      return true;
    }
    return false;
  }

  deleteDirectory(dirPath: string): boolean {
    if (dirPath === '/') return false;
    
    const index = this.manifest.directories.indexOf(dirPath);
    if (index === -1) return false;

    this.manifest.directories.splice(index, 1);

    // 将该目录下的文档移到根目录
    for (const entry of this.manifest.documents) {
      if (entry.directory === dirPath) {
        entry.directory = '/';
      }
    }

    this.saveManifest();
    return true;
  }

  getProvenanceChain(uid: string): DocEntry[] {
    const chain: DocEntry[] = [];
    let current = this.getEntry(uid);

    while (current) {
      chain.push(current);
      if (current.parentUid) {
        current = this.getEntry(current.parentUid);
      } else {
        break;
      }
    }

    return chain;
  }

  importFile(
    name: string,
    content: unknown,
    format: string = 'json',
    directory: string = '/',
    tags?: string[]
  ): string {
    return this.addDocument(name, 'imported', content, {
      source: DocSource.IMPORT,
      directory,
      tags
    });
  }
}

// 单例
const _instances = new Map<string, LibraryManager>();

export function getLibraryManager(projectPath: string): LibraryManager {
  const projectId = path.basename(projectPath);
  if (!_instances.has(projectId)) {
    _instances.set(projectId, new LibraryManager(projectPath));
  }
  return _instances.get(projectId)!;
}
