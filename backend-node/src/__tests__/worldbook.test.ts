// 世界书服务单元测试
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { STStyleWorldBook } from '../services/worldbook';
import { WorldBookEntry } from '../protocols';

describe('STStyleWorldBook', () => {
  let tempDir: string;
  let worldbook: STStyleWorldBook;

  beforeEach(() => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'worldbook-test-'));
    worldbook = new STStyleWorldBook(tempDir);
  });

  afterEach(() => {
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  const createTestEntry = (id: string, keys: string[]): WorldBookEntry => ({
    id,
    keys,
    content: `这是${id}的内容`,
    priority: 10
  });

  it('应该创建条目', () => {
    const entry = createTestEntry('char_001', ['主角', '张三']);
    worldbook.createEntry(entry);
    
    const retrieved = worldbook.getEntry('char_001');
    expect(retrieved).not.toBeNull();
    expect(retrieved!.id).toBe('char_001');
    expect(retrieved!.keys).toEqual(['主角', '张三']);
  });

  it('应该列出所有条目', () => {
    worldbook.createEntry(createTestEntry('char_001', ['主角']));
    worldbook.createEntry(createTestEntry('char_002', ['反派']));
    worldbook.createEntry(createTestEntry('item_001', ['宝剑']));
    
    const entries = worldbook.listAllEntries();
    expect(entries.length).toBe(3);
  });

  it('应该更新条目', () => {
    worldbook.createEntry(createTestEntry('char_001', ['主角']));
    worldbook.updateEntry('char_001', { content: '更新后的内容' });
    
    const entry = worldbook.getEntry('char_001');
    expect(entry!.content).toBe('更新后的内容');
  });

  it('应该删除条目', () => {
    worldbook.createEntry(createTestEntry('char_001', ['主角']));
    worldbook.deleteEntry('char_001');
    
    expect(worldbook.getEntry('char_001')).toBeNull();
  });

  it('应该根据触发词获取活跃条目', () => {
    worldbook.createEntry(createTestEntry('char_001', ['主角', '张三']));
    worldbook.createEntry(createTestEntry('char_002', ['反派', '李四']));
    worldbook.createEntry(createTestEntry('item_001', ['宝剑']));
    
    const entries = worldbook.getActiveEntries(['张三拿起了宝剑']);
    expect(entries.length).toBe(2);
    expect(entries.map(e => e.id)).toContain('char_001');
    expect(entries.map(e => e.id)).toContain('item_001');
  });

  it('常驻条目应该总是返回', () => {
    worldbook.createEntry({
      ...createTestEntry('world_001', ['世界观']),
      constant: true
    });
    worldbook.createEntry(createTestEntry('char_001', ['主角']));
    
    const entries = worldbook.getActiveEntries(['无关内容']);
    expect(entries.length).toBe(1);
    expect(entries[0].id).toBe('world_001');
  });

  it('应该按优先级排序', () => {
    worldbook.createEntry({
      ...createTestEntry('low', ['低']),
      priority: 5
    });
    worldbook.createEntry({
      ...createTestEntry('high', ['高']),
      priority: 20
    });
    
    const entries = worldbook.getActiveEntries(['低和高']);
    expect(entries[0].id).toBe('high');
    expect(entries[1].id).toBe('low');
  });

  it('应该提交版本', () => {
    worldbook.createEntry(createTestEntry('char_001', ['主角']));
    const hash = worldbook.commit('初始提交');
    
    expect(hash).toBeDefined();
    expect(hash.length).toBe(12);
    
    const commits = worldbook.listCommits();
    expect(commits.length).toBe(1);
    expect(commits[0].message).toBe('初始提交');
  });

  it('应该持久化数据', () => {
    worldbook.createEntry(createTestEntry('char_001', ['主角']));
    
    // 重新加载
    const worldbook2 = new STStyleWorldBook(tempDir);
    const entry = worldbook2.getEntry('char_001');
    
    expect(entry).not.toBeNull();
    expect(entry!.id).toBe('char_001');
  });
});
