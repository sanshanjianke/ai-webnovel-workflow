// 世界书服务单元测试
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { STStyleWorldBook, WorldBookStore } from '../services/worldbook';
import { WorldBookEntry, ExpertContext, ExpertRole, Granularity } from '../protocols';
import { createExpert } from '../experts';
import { setLLM, MockLLM } from '../services/llm';

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

// ========================
// 集成测试：世界书注入链路
// ========================

describe('WorldBook 注入链路', () => {
  let tempDir: string;
  let store: WorldBookStore;

  beforeEach(() => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'wb-inject-'));
    store = new WorldBookStore(tempDir);
  });

  afterEach(() => {
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it('1. 创建书 → 写条目 → 读取条目', () => {
    const info = store.createBook('测试书');
    expect(info.bookId).toBeTruthy();
    expect(info.entryCount).toBe(0);

    const book = store.getBook(info.bookId)!;
    book.createEntry({
      id: 'entry_1', keys: ['test', '测试'], content: '测试条目内容：验证码12345',
      priority: 10, constant: false
    });

    const loaded = store.getBook(info.bookId)!;
    expect(loaded.listAllEntries().length).toBe(1);
    expect(loaded.listAllEntries()[0].content).toContain('12345');
  });

  it('2. getActiveEntries 应该匹配关键词', () => {
    const book = store.getBook(store.createBook('匹配书').bookId)!;
    book.createEntry({
      id: 'e1', keys: ['test'], content: '命中内容：数字9527',
      priority: 10
    });
    book.createEntry({
      id: 'e2', keys: ['无关'], content: '不会命中',
      priority: 5
    });

    const active = book.getActiveEntries(['这段文字里包含test关键词']);
    expect(active.length).toBe(1);
    expect(active[0].content).toContain('9527');
  });

  it('3. WorldBookStore 多书不互相干扰', () => {
    const bookA = store.getBook(store.createBook('书A').bookId)!;
    bookA.createEntry({ id: 'a1', keys: ['a'], content: '来自书A' });

    const bookB = store.getBook(store.createBook('书B').bookId)!;
    bookB.createEntry({ id: 'b1', keys: ['b'], content: '来自书B' });

    // 重新加载
    const store2 = new WorldBookStore(tempDir);
    const books = store2.listBooks();
    expect(books.length).toBe(3); // 包括默认书

    const reloadedA = store2.getBook(bookA.getInfo().bookId)!;
    expect(reloadedA.listAllEntries()[0].content).toBe('来自书A');

    const reloadedB = store2.getBook(bookB.getInfo().bookId)!;
    expect(reloadedB.listAllEntries()[0].content).toBe('来自书B');
  });

  it('4. resolveWorldbook 逻辑：绑定节点取特定书，未绑定走回退', () => {
    const worldbookMap = new Map<string, string>();
    const perNodeWorldBook = new Map<string, string>();

    worldbookMap.set('book_a', '书A内容：hello-from-a');
    worldbookMap.set('book_b', '书B内容：hello-from-b');
    perNodeWorldBook.set('node_1', 'book_a');

    // 已绑定的 node_1 → book_a
    const boundId = perNodeWorldBook.get('node_1')!;
    expect(worldbookMap.get(boundId)).toContain('hello-from-a');

    // 未绑定的 node_2 → undefined（fallback）
    expect(perNodeWorldBook.get('node_2')).toBeUndefined();
  });

  it('5. 专家 buildPrompt 应该包含 worldbook 注入文本', async () => {
    setLLM(new MockLLM('测试响应'));

    const context: ExpertContext = {
      vision: {},
      worldbook: 'test: 注入码42',
      rag: '',
    };

    const expert = createExpert('senior_author_v1', ExpertRole.MAIN, Granularity.CHAPTER);
    const { prompt } = expert.buildPrompt(context);

    expect(prompt).toContain('注入码42');
    expect(prompt).not.toContain('暂无');
  });

  it('6. 完整链路：store → entries → map → resolve → prompt', async () => {
    setLLM(new MockLLM('测试响应'));

    // Step 1: 创建书，写条目
    const info = store.createBook('完整链路测试');
    const book = store.getBook(info.bookId)!;
    book.createEntry({
      id: 'full_1', keys: ['test'], content: '链路验证码：888',
      priority: 10
    });

    // Step 2: 构建 worldbookMap（模拟 pipeline 加载）
    const worldbookMap = new Map<string, string>();
    const text = book.listAllEntries()
      .map(e => `${e.keys?.[0] || ''}: ${e.content || ''}`)
      .join('\n');
    worldbookMap.set(info.bookId, text);

    // Step 3: 构建 perNodeWorldBook（模拟前端 binding）
    const perNodeWorldBook = new Map<string, string>();
    perNodeWorldBook.set('node_1', info.bookId);

    // Step 4: resolve
    const boundBookId = perNodeWorldBook.get('node_1')!;
    const resolvedText = worldbookMap.get(boundBookId)!;
    expect(resolvedText).toContain('验证码：888');

    // Step 5: 注入 ExpertContext → buildPrompt
    const context: ExpertContext = {
      vision: {},
      worldbook: resolvedText,
      rag: '',
    };

    const expert = createExpert('senior_author_v1', ExpertRole.MAIN, Granularity.CHAPTER);
    const { prompt } = expert.buildPrompt(context);

    expect(prompt).toContain('验证码：888');
  });

  it('7. 没有 worldbook 时 prompt 显示暂无', async () => {
    setLLM(new MockLLM('测试响应'));

    const context: ExpertContext = {
      vision: {},
      worldbook: '',
      rag: '',
    };

    const expert = createExpert('senior_author_v1', ExpertRole.MAIN, Granularity.CHAPTER);
    const { prompt } = expert.buildPrompt(context);

    expect(prompt).toContain('暂无');
  });
});
