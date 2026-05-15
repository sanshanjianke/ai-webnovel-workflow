// 预处理模块单元测试
import { describe, it, expect } from 'vitest';
import {
  REGEX_PRESETS, getStageExecutor,
  runPreprocessPipeline, testRegex,
  detectAvailableRuntimes
} from '../services/preprocessor';
import type { StageConfig, TextSegment } from '../protocols';

// ======================== 正则预设 ========================

describe('REGEX_PRESETS', () => {
  it('应该包含中文网文章节预设', () => {
    expect(REGEX_PRESETS.cn_chapter).toBeDefined();
    const re = new RegExp(REGEX_PRESETS.cn_chapter.pattern, 'gm');
    const text = '第一章 穿越\n内容...\n第二章 觉醒\n内容...';
    const matches = [...text.matchAll(re)];
    expect(matches).toHaveLength(2);
  });

  it('中文网文章节正则应该匹配数字和中文数字', () => {
    const p = REGEX_PRESETS.cn_chapter.pattern;
    // 每次用新 regex，避免 g 标志的 lastIndex 残留
    expect(new RegExp(p, 'gm').test('第123章 标题')).toBe(true);
    expect(new RegExp(p, 'gm').test('第十章 决战')).toBe(true);
    expect(new RegExp(p, 'gm').test('第一百二十三章 突破')).toBe(true);
  });

  it('中文网文节正则应该匹配节标题', () => {
    const p = REGEX_PRESETS.cn_section.pattern;
    expect(new RegExp(p, 'gm').test('第一节 入门')).toBe(true);
    expect(new RegExp(p, 'gm').test('第5节 进阶')).toBe(true);
  });

  it('英文小说章节正则应该匹配 Chapter', () => {
    const p = REGEX_PRESETS.en_chapter.pattern;
    expect(new RegExp(p, 'gm').test('Chapter 1 The Beginning')).toBe(true);
    expect(new RegExp(p, 'gm').test('CH 23 The End')).toBe(true);
    expect(new RegExp(p, 'gm').test('Ch.5 Middle')).toBe(true);
  });
});

// ======================== 阶段执行器 ========================

describe('阶段注册表', () => {
  it('应该能找到所有内置阶段类型', () => {
    const types = ['replace', 'split_regex', 'split_token', 'split_lines', 'window_group', 'custom'];
    for (const t of types) {
      expect(() => getStageExecutor(t)).not.toThrow();
    }
  });

  it('未知类型应该抛出异常', () => {
    expect(() => getStageExecutor('unknown')).toThrow('Unknown stage type');
  });
});

// ======================== RegexReplaceStage ========================

describe('RegexReplaceStage', () => {
  it('应该替换匹配的文本', () => {
    const stage = getStageExecutor('replace');
    const segments: TextSegment[] = [{
      content: '本文由xxx.com提供\n第一章 开始',
      meta: { index: 0, charCount: 0 }
    }];
    const result = stage.execute(segments, {
      pattern: '本文由.*提供\\n?',
      replacement: '',
      flags: 'g'
    });
    expect(result[0].content).toBe('第一章 开始');
  });

  it('空 pattern 应原样返回', () => {
    const stage = getStageExecutor('replace');
    const segments: TextSegment[] = [{
      content: '保持不变',
      meta: { index: 0, charCount: 5 }
    }];
    const result = stage.execute(segments, { pattern: '' });
    expect(result[0].content).toBe('保持不变');
  });
});

// ======================== RegexSplitStage ========================

describe('RegexSplitStage', () => {
  it('应该按中文网文章节拆分', () => {
    const stage = getStageExecutor('split_regex');
    const text = '第一章 穿越\n主角醒来发现自己穿越了。\n第二章 觉醒\n他发现自己有系统。';
    const segments: TextSegment[] = [{
      content: text,
      meta: { index: 0, charCount: text.length }
    }];

    const result = stage.execute(segments, {
      preset: 'cn_chapter',
      includeSeparator: true
    });

    expect(result.length).toBeGreaterThanOrEqual(2);
  });

  it('应该提取章节号', () => {
    const stage = getStageExecutor('split_regex');
    const text = '第1章 开始\n内容1\n第2章 发展\n内容2\n第3章 高潮\n内容3';
    const segments: TextSegment[] = [{
      content: text,
      meta: { index: 0, charCount: text.length }
    }];

    const result = stage.execute(segments, {
      preset: 'cn_chapter',
      includeSeparator: true
    });

    const numbers = result.map(s => s.meta.chapterNumber).filter(Boolean);
    expect(numbers).toContain(1);
    expect(numbers).toContain(2);
    expect(numbers).toContain(3);
  });

  it('英文小说章节拆分', () => {
    const stage = getStageExecutor('split_regex');
    const text = 'Chapter 1 Start\nContent 1\nChapter 2 Middle\nContent 2';
    const segments: TextSegment[] = [{
      content: text,
      meta: { index: 0, charCount: text.length }
    }];

    const result = stage.execute(segments, {
      preset: 'en_chapter',
      includeSeparator: true
    });

    expect(result.length).toBeGreaterThanOrEqual(2);
  });
});

// ======================== TokenSplitStage ========================

describe('TokenSplitStage', () => {
  it('应该按 token 数拆分长文本', () => {
    const stage = getStageExecutor('split_token');
    const longText = 'a'.repeat(5000);
    const segments: TextSegment[] = [{
      content: longText,
      meta: { index: 0, charCount: longText.length }
    }];

    const result = stage.execute(segments, {
      maxTokens: 1000,
      overlap: 100
    });

    expect(result.length).toBeGreaterThan(1);
    // 每块不超过 maxTokens（最后一块可能更短）
    for (const s of result) {
      expect(s.content.length).toBeLessThanOrEqual(1000);
    }
  });

  it('短文本不应拆分', () => {
    const stage = getStageExecutor('split_token');
    const segments: TextSegment[] = [{
      content: '短文本',
      meta: { index: 0, charCount: 3 }
    }];

    const result = stage.execute(segments, {
      maxTokens: 1000,
      overlap: 100
    });

    expect(result).toHaveLength(1);
  });
});

// ======================== LineSplitStage ========================

describe('LineSplitStage', () => {
  it('应该按行数拆分', () => {
    const stage = getStageExecutor('split_lines');
    const lines = Array.from({ length: 250 }, (_, i) => `这是第${i + 1}行`);
    const segments: TextSegment[] = [{
      content: lines.join('\n'),
      meta: { index: 0, charCount: 0 }
    }];

    const result = stage.execute(segments, {
      maxLines: 100,
      overlap: 0
    });

    expect(result.length).toBe(3); // 250 行 / 100 = 3 块
  });
});

// ======================== WindowGroupStage ========================

describe('WindowGroupStage', () => {
  it('应该按 groupSize 和上下文窗口合并', () => {
    const stage = getStageExecutor('window_group');
    const segments: TextSegment[] = Array.from({ length: 20 }, (_, i) => ({
      content: `块${i + 1}的内容`,
      meta: { index: i, title: `第${i + 1}章`, charCount: 10 }
    }));

    const result = stage.execute(segments, {
      groupSize: 5,
      contextBefore: 2,
      contextAfter: 2
    });

    // 20 个块 / 5 groupSize = 4 组
    expect(result.length).toBe(4);

    // 第一组: 块1-7 (主: 1-5, 前文: 0, 后文: 6-7)
    expect(result[0].meta.mainStart).toBe(0);
    expect(result[0].meta.mainEnd).toBe(5);
    expect(result[0].meta.windowStart).toBe(0);
    expect(result[0].meta.windowEnd).toBe(7);

    // 最后一组: 块16-20 (主: 16-20, 前文: 14-15, 后文: 0)
    const last = result[result.length - 1];
    expect(last.meta.mainStart).toBe(15);
    expect(last.meta.mainEnd).toBe(20);
  });

  it('少于 groupSize 的块不应合并', () => {
    const stage = getStageExecutor('window_group');
    const segments: TextSegment[] = Array.from({ length: 3 }, (_, i) => ({
      content: `块${i + 1}`,
      meta: { index: i, charCount: 2 }
    }));

    const result = stage.execute(segments, {
      groupSize: 5,
      contextBefore: 2,
      contextAfter: 2
    });

    expect(result).toHaveLength(3);
  });

  it('每组内容应包含窗口范围内所有块', () => {
    const stage = getStageExecutor('window_group');
    const segments: TextSegment[] = Array.from({ length: 10 }, (_, i) => ({
      content: `CHUNK_${i + 1}`,
      meta: { index: i, title: `第${i + 1}章`, charCount: 8 }
    }));

    const result = stage.execute(segments, {
      groupSize: 3,
      contextBefore: 1,
      contextAfter: 1
    });

    // 第一组应包含块1-4
    expect(result[0].content).toContain('CHUNK_1');
    expect(result[0].content).toContain('CHUNK_2');
    expect(result[0].content).toContain('CHUNK_3');
    expect(result[0].content).toContain('CHUNK_4');
  });
});

// ======================== 管线执行器 ========================

describe('runPreprocessPipeline', () => {
  it('空阶段列表应原样返回', async () => {
    const result = await runPreprocessPipeline('hello world', []);
    expect(result).toHaveLength(1);
    expect(result[0].content).toBe('hello world');
  });

  it('替换+拆分的完整流程', async () => {
    const stages: StageConfig[] = [
      {
        id: 's1', type: 'replace', enabled: true, label: '清理',
        config: { pattern: '广告内容\\n?', replacement: '', flags: 'g' }
      },
      {
        id: 's2', type: 'split_regex', enabled: true, label: '拆分',
        config: { preset: 'cn_chapter', includeSeparator: true }
      }
    ];

    const text = '广告内容\n第1章 开始\n正文内容1\n第2章 发展\n正文内容2';
    const result = await runPreprocessPipeline(text, stages);

    expect(result.length).toBe(2);
    expect(result[0].content).not.toContain('广告内容');
    expect(result[0].meta.chapterNumber).toBe(1);
    expect(result[1].meta.chapterNumber).toBe(2);
  });

  it('禁用的阶段应跳过', async () => {
    const stages: StageConfig[] = [
      {
        id: 's1', type: 'replace', enabled: false, label: '清理',
        config: { pattern: '广告', replacement: '', flags: 'g' }
      }
    ];

    const text = '广告内容保留';
    const result = await runPreprocessPipeline(text, stages);

    expect(result[0].content).toContain('广告内容保留');
  });

  it('窗口合并的完整流程', async () => {
    const stages: StageConfig[] = [
      {
        id: 's1', type: 'split_regex', enabled: true, label: '拆分',
        config: { preset: 'cn_chapter', includeSeparator: true }
      },
      {
        id: 's2', type: 'window_group', enabled: true, label: '合并',
        config: { groupSize: 2, contextBefore: 1, contextAfter: 1 }
      }
    ];

    let text = '';
    for (let i = 1; i <= 6; i++) {
      text += `第${i}章 标题${i}\n这是第${i}章的内容。\n\n`;
    }

    const result = await runPreprocessPipeline(text, stages);

    // 6 章 / groupSize 2 = 3 组
    expect(result.length).toBe(3);
  });
});

// ======================== 正则测试工具 ========================

describe('testRegex', () => {
  it('应该统计匹配数', () => {
    const text = '第1章\n第2章\n第3章\n';
    const result = testRegex(REGEX_PRESETS.cn_chapter.pattern, text);
    expect(result.matchCount).toBe(3);
    expect(result.matches).toHaveLength(3);
  });

  it('无匹配时应返回 0', () => {
    const text = '没有章节标题的普通文本';
    const result = testRegex(REGEX_PRESETS.cn_chapter.pattern, text);
    expect(result.matchCount).toBe(0);
  });
});

// ======================== 环境检测 ========================

describe('detectAvailableRuntimes', () => {
  it('JavaScript 应该始终可用', async () => {
    const runtimes = await detectAvailableRuntimes();
    expect(runtimes.javascript.available).toBe(true);
  });

  it('应该返回所有三种语言的检测结果', async () => {
    const runtimes = await detectAvailableRuntimes();
    expect(runtimes).toHaveProperty('javascript');
    expect(runtimes).toHaveProperty('python');
    expect(runtimes).toHaveProperty('perl');
  });
});

// ======================== Custom JS Stage ========================

describe('CustomStage (JavaScript)', () => {
  it('应该执行用户自定义 JS 代码', () => {
    const stage = getStageExecutor('custom');
    const segments: TextSegment[] = [{
      content: 'A,B,C',
      meta: { index: 0, charCount: 5 }
    }];

    const result = stage.execute(segments, {
      language: 'javascript',
      customCode: `
        return segments.flatMap(s => {
          return s.content.split(',').filter(p => p).map((part, i) =>
            utils.segment(part.trim(), { ...s.meta, partIndex: i })
          );
        });
      `
    });

    expect(result).toHaveLength(3);
    expect(result[0].content).toBe('A');
    expect(result[1].content).toBe('B');
    expect(result[2].content).toBe('C');
  });

  it('空代码应原样返回', () => {
    const stage = getStageExecutor('custom');
    const segments: TextSegment[] = [{
      content: 'test',
      meta: { index: 0, charCount: 4 }
    }];

    const result = stage.execute(segments, {
      language: 'javascript',
      customCode: ''
    });

    expect(result).toHaveLength(1);
    expect(result[0].content).toBe('test');
  });
});
