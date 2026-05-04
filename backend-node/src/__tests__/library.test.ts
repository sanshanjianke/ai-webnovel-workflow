// 文档库服务单元测试
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { LibraryManager } from '../services/library';
import { DocSource, DocStatus } from '../protocols';

describe('LibraryManager', () => {
  let tempDir: string;
  let projectPath: string;
  let library: LibraryManager;

  beforeEach(() => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'library-test-'));
    projectPath = path.join(tempDir, 'test_project');
    fs.mkdirSync(projectPath, { recursive: true });
    library = new LibraryManager(projectPath);
  });

  afterEach(() => {
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it('应该初始化目录结构', () => {
    expect(fs.existsSync(path.join(projectPath, 'library'))).toBe(true);
    expect(fs.existsSync(path.join(projectPath, 'library', 'files'))).toBe(true);
    expect(fs.existsSync(path.join(projectPath, 'library', 'manifest.json'))).toBe(true);
  });

  it('应该添加文档', () => {
    const uid = library.addDocument('测试文档', 'l1', { idea: '测试' });
    
    expect(uid).toBeDefined();
    expect(uid.length).toBe(8);
    
    const doc = library.getDocument(uid);
    expect(doc).not.toBeNull();
    expect(doc!.entry.name).toBe('测试文档');
    expect(doc!.entry.layer).toBe('l1');
  });

  it('应该获取文档', () => {
    const uid = library.addDocument('测试文档', 'l1', { idea: '测试' });
    const doc = library.getDocument(uid);
    
    expect(doc).not.toBeNull();
    expect(doc!.entry.uid).toBe(uid);
    expect(doc!.content).toEqual({ idea: '测试' });
  });

  it('应该更新文档元数据', () => {
    const uid = library.addDocument('原名称', 'l1', {});
    const updated = library.updateEntry(uid, { name: '新名称' });
    
    expect(updated).not.toBeNull();
    expect(updated!.name).toBe('新名称');
  });

  it('应该更新文档内容', () => {
    const uid = library.addDocument('测试文档', 'l1', { old: true });
    const success = library.updateContent(uid, { new: true });
    
    expect(success).toBe(true);
    
    const doc = library.getDocument(uid);
    expect(doc!.content).toEqual({ new: true });
  });

  it('应该删除文档', () => {
    const uid = library.addDocument('要删除的文档', 'l1', {});
    const success = library.deleteDocument(uid);
    
    expect(success).toBe(true);
    expect(library.getDocument(uid)).toBeNull();
  });

  it('应该归档文档', () => {
    const uid = library.addDocument('测试文档', 'l1', {});
    const archived = library.archiveDocument(uid, true);
    
    expect(archived).not.toBeNull();
    expect(archived!.status).toBe(DocStatus.ARCHIVED);
    
    // 默认不列出归档文档
    const docs = library.listDocuments();
    expect(docs.length).toBe(0);
    
    // 包含归档文档
    const allDocs = library.listDocuments(undefined, undefined, true);
    expect(allDocs.length).toBe(1);
  });

  it('应该设置活跃文档', () => {
    const uid = library.addDocument('测试文档', 'l1', {});
    const success = library.setActive('l1', uid);
    
    expect(success).toBe(true);
    expect(library.getActive('l1')).toBe(uid);
    
    const activeDoc = library.getActiveDocument('l1');
    expect(activeDoc).not.toBeNull();
    expect(activeDoc!.entry.uid).toBe(uid);
  });

  it('应该按层级列出文档', () => {
    library.addDocument('L1文档', 'l1', {});
    library.addDocument('L2文档', 'l2', {});
    library.addDocument('另一个L1文档', 'l1', {});
    
    const l1Docs = library.listDocuments('l1');
    expect(l1Docs.length).toBe(2);
    
    const l2Docs = library.listDocuments('l2');
    expect(l2Docs.length).toBe(1);
  });

  it('应该创建目录', () => {
    library.createDirectory('/chapters');
    
    // 检查目录是否在manifest中
    const manifestPath = path.join(projectPath, 'library', 'manifest.json');
    const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
    expect(manifest.directories).toContain('/chapters');
  });

  it('应该删除目录', () => {
    library.createDirectory('/temp');
    const success = library.deleteDirectory('/temp');
    expect(success).toBe(true);
  });

  it('不能删除根目录', () => {
    const success = library.deleteDirectory('/');
    expect(success).toBe(false);
  });

  it('应该获取溯源链', () => {
    const parentUid = library.addDocument('父文档', 'l1', {});
    const childUid = library.addDocument('子文档', 'l2', {}, { parentUid });
    
    const chain = library.getProvenanceChain(childUid);
    expect(chain.length).toBe(2);
    expect(chain[0].uid).toBe(childUid);
    expect(chain[1].uid).toBe(parentUid);
  });

  it('应该导入文件', () => {
    const uid = library.importFile('导入的文件', { data: 'test' }, 'json', '/');
    
    expect(uid).toBeDefined();
    
    const doc = library.getDocument(uid);
    expect(doc!.entry.source).toBe(DocSource.IMPORT);
    expect(doc!.entry.layer).toBe('imported');
  });
});
