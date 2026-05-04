// RAG 服务单元测试
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { SimpleVectorRetriever } from '../services/rag';

describe('SimpleVectorRetriever', () => {
  let tempDir: string;
  let retriever: SimpleVectorRetriever;

  beforeEach(() => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'rag-test-'));
    retriever = new SimpleVectorRetriever(tempDir);
  });

  afterEach(() => {
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it('应该索引和检索文档', async () => {
    await retriever.index([
      { id: 'doc1', content: '主角是一个穿越者' },
      { id: 'doc2', content: '反派是魔教教主' },
      { id: 'doc3', content: '世界观是修仙世界' }
    ]);
    
    const results = await retriever.retrieve('穿越者');
    expect(results.length).toBeGreaterThan(0);
    expect(results[0].id).toBe('doc1');
  });

  it('应该返回正确的分数', async () => {
    await retriever.index([
      { id: 'doc1', content: '主角张三是一个穿越者' },
      { id: 'doc2', content: '配角李四是一个穿越者' }
    ]);
    
    const results = await retriever.retrieve('张三 穿越者');
    expect(results.length).toBe(2);
    expect(results[0].score).toBeGreaterThan(0);
  });

  it('应该限制返回数量', async () => {
    await retriever.index([
      { id: 'doc1', content: '测试内容1' },
      { id: 'doc2', content: '测试内容2' },
      { id: 'doc3', content: '测试内容3' }
    ]);
    
    const results = await retriever.retrieve('测试', 2);
    expect(results.length).toBeLessThanOrEqual(2);
  });

  it('应该删除文档', async () => {
    await retriever.index([
      { id: 'doc1', content: '要保留的' },
      { id: 'doc2', content: '要删除的' }
    ]);
    
    await retriever.delete(['doc2']);
    
    expect(await retriever.count()).toBe(1);
  });

  it('应该返回正确的数量', async () => {
    expect(await retriever.count()).toBe(0);
    
    await retriever.index([
      { id: 'doc1', content: '文档1' },
      { id: 'doc2', content: '文档2' }
    ]);
    
    expect(await retriever.count()).toBe(2);
  });

  it('应该持久化数据', async () => {
    await retriever.index([
      { id: 'doc1', content: '持久化测试' }
    ]);
    
    // 重新加载
    const retriever2 = new SimpleVectorRetriever(tempDir);
    expect(await retriever2.count()).toBe(1);
    
    const results = await retriever2.retrieve('持久化');
    expect(results.length).toBe(1);
    expect(results[0].id).toBe('doc1');
  });

  it('没有匹配时应该返回空数组', async () => {
    await retriever.index([
      { id: 'doc1', content: '完全无关的内容' }
    ]);
    
    const results = await retriever.retrieve('xyzabc');
    expect(results.length).toBe(0);
  });
});
