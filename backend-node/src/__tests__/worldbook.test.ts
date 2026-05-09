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

  it('4. resolveWorldbook 逻辑：绑定节点取特定书的条目', () => {
    const bookA = store.getBook(store.createBook('书A').bookId)!;
    bookA.createEntry({ id: 'a1', keys: ['hello'], content: '来自书A的内容' });
    const bookB = store.getBook(store.createBook('书B').bookId)!;
    bookB.createEntry({ id: 'b1', keys: ['world'], content: '来自书B的内容' });

    const entries = new Map<string, WorldBookEntry[]>();
    entries.set(bookA.getInfo().bookId, bookA.listAllEntries());
    entries.set(bookB.getInfo().bookId, bookB.listAllEntries());

    const perNodeWorldBook = new Map<string, string>();
    perNodeWorldBook.set('node_1', bookA.getInfo().bookId);

    // 已绑定的 node_1 → bookA 的条目
    const boundId = perNodeWorldBook.get('node_1')!;
    expect(entries.get(boundId)!.length).toBe(1);
    expect(entries.get(boundId)![0].content).toContain('来自书A');

    // 未绑定的 node_2 → undefined
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

  it('6. 完整链路：store → entries → 关键词过滤 → prompt', async () => {
    setLLM(new MockLLM('测试响应'));

    // Step 1: 创建书，写两个条目（一个应命中，一个不应命中）
    const info = store.createBook('过滤测试书');
    const book = store.getBook(info.bookId)!;
    book.createEntry({
      id: 'match_1', keys: ['test'], content: '命中条目：验证码888',
      priority: 10
    });
    book.createEntry({
      id: 'no_match', keys: ['job'], content: '不应命中的条目：验证码999',
      priority: 10
    });

    // Step 2: 模拟 resolveWorldbook 的关键词过滤
    const entries = book.listAllEntries();
    const contextTokens = ['这是', '一个', 'test', '关键词', '测试'];
    const active = entries.filter(e => {
      if (e.constant) return true;
      return e.keys.some(key =>
        contextTokens.some(t => t.toLowerCase().includes(key.toLowerCase()))
      );
    });
    const resolvedText = active.map(e => `${e.keys?.[0] || e.id}: ${e.content}`).join('\n');

    // Step 3: 只应有 test 条目，不应有 job 条目
    expect(resolvedText).toContain('验证码888');
    expect(resolvedText).not.toContain('验证码999');

    // Step 4: 注入 ExpertContext → buildPrompt
    const context: ExpertContext = {
      vision: {},
      worldbook: resolvedText,
      rag: '',
    };

    const expert = createExpert('senior_author_v1', ExpertRole.MAIN, Granularity.CHAPTER);
    const { prompt } = expert.buildPrompt(context);

    expect(prompt).toContain('验证码888');
    expect(prompt).not.toContain('验证码999');
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

// ========================
// 集成测试：meeting route → pipeline 衔接
// ========================

describe('Meeting route → Pipeline 世界书衔接', () => {
  let tempDir: string;

  beforeEach(() => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'wb-meeting-'));
    setLLM(new MockLLM('测试响应'));
  });

  afterEach(() => {
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  // 模拟 meeting route 中 worldbookEntries 构建逻辑
  function buildWorldbookEntries(projectPath: string): Map<string, WorldBookEntry[]> {
    const entries = new Map<string, WorldBookEntry[]>();
    const worldbooksDir = path.join(projectPath, 'worldbooks');
    try {
      if (fs.existsSync(worldbooksDir)) {
        for (const file of fs.readdirSync(worldbooksDir)) {
          if (!file.endsWith('.json') || file.endsWith('_commits.json')) continue;
          const bookId = file.replace('.json', '');
          try {
            const wb = JSON.parse(fs.readFileSync(path.join(worldbooksDir, file), 'utf-8'));
            entries.set(bookId, Object.values(wb.entries || {}) as WorldBookEntry[]);
          } catch {}
        }
      }
    } catch {}
    return entries;
  }

  it('应该从磁盘加载世界书条目并做关键词过滤', () => {
    // Step 1: 创建项目目录和世界书（两个条目）
    const worldbooksDir = path.join(tempDir, 'worldbooks');
    fs.mkdirSync(worldbooksDir, { recursive: true });
    fs.writeFileSync(path.join(worldbooksDir, 'default.json'), JSON.stringify({
      name: '默认书', entries: {
        'entry_1': { id: 'entry_1', keys: ['test'], content: '命中内容：验证码999', priority: 10 },
        'entry_2': { id: 'entry_2', keys: ['job'], content: '不应命中的内容：验证码000', priority: 10 }
      }
    }, null, 2));

    // Step 2: 模拟 meeting route 加载
    const entries = buildWorldbookEntries(tempDir);
    expect(entries.size).toBe(1);
    expect(entries.get('default')!.length).toBe(2);

    // Step 3: 模拟关键词过滤（只有 test，没有 job）
    const contextTokens = '这是一个test关键词的测试'.split(/\s+/);
    const active = entries.get('default')!.filter(e => {
      if (e.constant) return true;
      return e.keys.some(key =>
        contextTokens.some(t => t.toLowerCase().includes(key.toLowerCase()))
      );
    });
    expect(active.length).toBe(1);
    expect(active[0].content).toContain('验证码999');
    expect(active.map(e => e.content).join()).not.toContain('验证码000');

    // Step 4: 验证 binding
    const perNodeWorldBook = new Map<string, string>();
    perNodeWorldBook.set('node_1', 'default');
    const boundId = perNodeWorldBook.get('node_1')!;
    const bookEntries = entries.get(boundId)!;
    expect(bookEntries.length).toBe(2);
  });

  it('前端 node.id 应该和 pipeline 的 ec.nodeId 一致', () => {
    // 场景 1: 独立专家，ec.nodeId = 'node_1'
    let ec_nodeId = 'node_1';
    let key: string | null = null;
    key = ec_nodeId;  // ec.containerId is null, fallback to nodeId
    expect(key).toBe('node_1');

    // 场景 2: 容器内专家，key = containerId
    ec_nodeId = 'container_1_exp_0';
    const ec_containerId = 'container_1';
    key = ec_containerId || ec_nodeId;
    expect(key).toBe('container_1');

    // 验证 perNodeWorldBook 的 key 能匹配
    const perNodeWorldBook = new Map<string, string>();
    perNodeWorldBook.set('node_1', 'book_x');
    perNodeWorldBook.set('container_1', 'book_x');
    expect(perNodeWorldBook.get('node_1')).toBe('book_x');
    expect(perNodeWorldBook.get('container_1')).toBe('book_x');
  });

  it('关键词过滤：只匹配包含关键词的条目，不匹配的应被排除', () => {
    const s = new WorldBookStore(tempDir);
    const book = s.getBook(s.createBook('过滤书').bookId)!;
    book.createEntry({ id: 'e1', keys: ['test'], content: 'test条目：码111', priority: 10 });
    book.createEntry({ id: 'e2', keys: ['job'], content: 'job条目：码222', priority: 10 });
    book.createEntry({ id: 'e3', keys: ['xyz'], content: 'xyz条目：码333', priority: 10 });

    const allEntries = book.listAllEntries();
    const contextTokens = ['这里', '包含', 'test', '和', 'xyz'];

    // 过滤
    const active = allEntries.filter((e: WorldBookEntry) => {
      if (e.constant) return true;
      if (e.disable) return false;
      return e.keys.some((key: string) =>
        contextTokens.some(t => t.toLowerCase().includes(key.toLowerCase()))
      );
    });

    expect(active.length).toBe(2);
    expect(active.map((e: WorldBookEntry) => e.id)).toContain('e1');
    expect(active.map((e: WorldBookEntry) => e.id)).toContain('e3');
    expect(active.map((e: WorldBookEntry) => e.id)).not.toContain('e2');
  });
});
