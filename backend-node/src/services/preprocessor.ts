// 预处理核心模块
// 阶段管线：原始文本 → [替换/清洗] → [拆分] → [窗口合并] → N 个 TextSegment
// 支持三种自定义代码语言：JavaScript（进程内）、Python、Perl（CLI 子进程）

import { TextSegment, StageConfig, PreprocessConfig } from '../protocols';
import { spawn } from 'child_process';
import { tmpdir } from 'os';
import { join } from 'path';
import { writeFileSync, unlinkSync, existsSync } from 'fs';
import { randomUUID } from 'crypto';

// ======================== 正则预设 ========================

export interface RegexPreset {
  label: string;
  pattern: string;
  hint: string;
}

export const REGEX_PRESETS: Record<string, RegexPreset> = {
  cn_chapter: {
    label: '中文网文（第X章）',
    pattern: '(?:^|\\n)\\s*第[零一二三四五六七八九十百千万\\d]+章[^\\n]*',
    hint: '匹配 第一章、第123章、第十一章 标题 等'
  },
  cn_section: {
    label: '中文网文（第X节）',
    pattern: '(?:^|\\n)\\s*第[零一二三四五六七八九十百千万\\d]+节[^\\n]*',
    hint: '匹配 第一节、第12节 等'
  },
  cn_volume_chapter: {
    label: '中文网文（第X卷第Y章）',
    pattern: '(?:^|\\n)\\s*第[零一二三四五六七八九十百千万\\d]+卷[^\\n]*第[零一二三四五六七八九十百千万\\d]+章[^\\n]*',
    hint: '匹配 第三卷第5章 等'
  },
  en_chapter: {
    label: '英文小说（Chapter X）',
    pattern: '(?:^|\\n)\\s*(?:Chapter|CH|Ch\\.?)\\s*\\d+[^\\n]*',
    hint: '匹配 Chapter 1、CH 23、Ch.5 等'
  },
  en_part: {
    label: '英文小说（Part X）',
    pattern: '(?:^|\\n)\\s*(?:Part|PART)\\s*[IVX\\d]+[^\\n]*',
    hint: '匹配 Part I、PART 3 等'
  },
  double_newline: {
    label: '双换行分隔（通用）',
    pattern: '(?:^|\\n)\\n{2,}',
    hint: '按段落间距拆分，适用于无章节标记的文本'
  },
  custom: {
    label: '自定义正则',
    pattern: '',
    hint: '输入你自己的正则表达式'
  }
};

// ======================== 环境检测 ========================

export interface RuntimeInfo {
  available: boolean;
  cmd?: string;
  error?: string;
}

export async function detectAvailableRuntimes(): Promise<Record<string, RuntimeInfo>> {
  const result: Record<string, RuntimeInfo> = {
    javascript: { available: true },
    python: { available: false },
    perl: { available: false }
  };

  for (const cmd of ['python3', 'python']) {
    try {
      await execAsync(`${cmd} --version`);
      result.python = { available: true, cmd };
      break;
    } catch {}
  }

  try {
    await execAsync('perl -MJSON -e "print decode_json(q/[1]/)->[0]"');
    result.perl = { available: true, cmd: 'perl' };
  } catch {
    // Perl or JSON.pm not available
    try {
      await execAsync('perl --version');
      result.perl = { available: false, cmd: 'perl', error: 'JSON 模块未安装，请执行: cpan JSON' };
    } catch {}
  }

  return result;
}

function execAsync(cmd: string): Promise<{ stdout: string; stderr: string }> {
  return new Promise((resolve, reject) => {
    const proc = spawn('sh', ['-c', cmd], { stdio: ['pipe', 'pipe', 'pipe'] });
    let stdout = '';
    let stderr = '';
    proc.stdout.on('data', (d: Buffer) => { stdout += d.toString(); });
    proc.stderr.on('data', (d: Buffer) => { stderr += d.toString(); });
    proc.on('close', (code) => {
      if (code === 0) resolve({ stdout, stderr });
      else reject(new Error(stderr || `exit code ${code}`));
    });
    proc.on('error', reject);
  });
}

// ======================== 阶段接口 ========================

interface PreprocessStage {
  name: string;
  execute(segments: TextSegment[], config: Record<string, any>): TextSegment[];
}

// ======================== 内置阶段实现 ========================

class RegexReplaceStage implements PreprocessStage {
  name = 'RegexReplace';

  execute(segments: TextSegment[], config: Record<string, any>): TextSegment[] {
    const pattern = config.pattern as string;
    const replacement = config.replacement as string || '';
    const flags = config.flags as string || 'g';

    if (!pattern) return segments;

    const re = new RegExp(pattern, flags);
    return segments.map(s => ({
      content: s.content.replace(re, replacement),
      meta: { ...s.meta, charCount: s.content.length }
    }));
  }
}

class RegexSplitStage implements PreprocessStage {
  name = 'RegexSplit';

  execute(segments: TextSegment[], config: Record<string, any>): TextSegment[] {
    const preset = config.preset as string;
    let pattern = config.pattern as string;

    // 若有预设，优先用预设
    if (preset && preset !== 'custom' && REGEX_PRESETS[preset]) {
      pattern = REGEX_PRESETS[preset].pattern;
    }

    if (!pattern) return segments;

    const includeSeparator = config.includeSeparator !== false;
    const result: TextSegment[] = [];

    for (const s of segments) {
      const re = new RegExp(pattern, 'gm');
      const matches: { index: number; length: number; text: string }[] = [];
      let m: RegExpExecArray | null;
      while ((m = re.exec(s.content)) !== null) {
        matches.push({ index: m.index, length: m[0].length, text: m[0] });
      }

      if (matches.length === 0) {
        result.push(s);
        continue;
      }

      // 第一段：第一个匹配之前的内容
      if (matches[0].index > 0) {
        const firstContent = s.content.slice(0, matches[0].index).trim();
        if (firstContent) {
          result.push({
            content: firstContent,
            meta: { ...s.meta, index: 0, chapterNumber: 0, title: this.extractTitle(matches[0].text) }
          });
        }
      }

      // 中间各段
      for (let i = 0; i < matches.length; i++) {
        const start = matches[i].index + (includeSeparator ? 0 : matches[i].length);
        const end = i + 1 < matches.length ? matches[i + 1].index : s.content.length;
        let content = s.content.slice(start, end).trim();
        if (includeSeparator && i > 0) {
          // separator already included at start
        }
        if (!content && includeSeparator) {
          content = matches[i].text;
        }
        if (content) {
          const cn = this.extractNumber(matches[i].text);
          result.push({
            content: (includeSeparator ? '' : '') + content,
            meta: {
              ...s.meta,
              index: i,
              chapterNumber: cn,
              title: this.extractTitle(matches[i].text)
            }
          });
        }
      }
    }

    return result.length > 0 ? result : segments;
  }

  private extractNumber(text: string): number | undefined {
    const m = text.match(/\d+/);
    return m ? parseInt(m[0], 10) : undefined;
  }

  private extractTitle(text: string): string {
    return text.replace(/^\s+/, '').trim();
  }
}

class TokenSplitStage implements PreprocessStage {
  name = 'TokenSplit';

  execute(segments: TextSegment[], config: Record<string, any>): TextSegment[] {
    const maxTokens = config.maxTokens as number || 3000;
    const overlap = config.overlap as number || 200;

    const result: TextSegment[] = [];
    for (const s of segments) {
      const chars = [...s.content];
      const chunkSize = maxTokens; // 1 char ≈ 1 token for Chinese
      const step = chunkSize - overlap;

      if (chars.length <= chunkSize) {
        result.push(s);
        continue;
      }

      let i = 0;
      while (i < chars.length) {
        const chunk = chars.slice(i, i + chunkSize).join('');
        if (chunk.trim()) {
          result.push({
            content: chunk,
            meta: { ...s.meta, index: result.length, charCount: chunk.length }
          });
        }
        i += step;
      }
    }

    return result.length > 0 ? result : segments;
  }
}

class LineSplitStage implements PreprocessStage {
  name = 'LineSplit';

  execute(segments: TextSegment[], config: Record<string, any>): TextSegment[] {
    const maxLines = config.maxLines as number || 100;
    const overlap = config.overlap as number || 0;

    const result: TextSegment[] = [];
    for (const s of segments) {
      const lines = s.content.split('\n');

      if (lines.length <= maxLines) {
        result.push(s);
        continue;
      }

      let i = 0;
      while (i < lines.length) {
        const chunk = lines.slice(i, i + maxLines).join('\n');
        if (chunk.trim()) {
          result.push({
            content: chunk,
            meta: { ...s.meta, index: result.length, charCount: chunk.length }
          });
        }
        i += maxLines - overlap;
      }
    }

    return result.length > 0 ? result : segments;
  }
}

class WindowGroupStage implements PreprocessStage {
  name = 'WindowGroup';

  execute(segments: TextSegment[], config: Record<string, any>): TextSegment[] {
    const groupSize = config.groupSize as number || 5;       // n: 主单元块数
    const contextBefore = config.contextBefore as number || 2; // i: 前文上下文
    const contextAfter = config.contextAfter as number || 2;   // i: 后文上下文

    if (segments.length <= groupSize) return segments;

    const result: TextSegment[] = [];
    let groupIndex = 0;

    // 滑动步长 = groupSize
    for (let start = 0; start < segments.length; start += groupSize) {
      const windowStart = Math.max(0, start - contextBefore);
      const windowEnd = Math.min(segments.length, start + groupSize + contextAfter);

      const windowSegments = segments.slice(windowStart, windowEnd);
      const mainStart = start - windowStart;
      const mainEnd = mainStart + Math.min(groupSize, segments.length - start);

      const combinedContent = windowSegments.map((seg, i) => {
        const label = i >= mainStart && i < mainEnd ? '★' : ' ';
        const title = seg.meta.title || `块${seg.meta.index + 1}`;
        return `<!-- ${label} ${title} -->\n${seg.content}`;
      }).join('\n\n');

      const mainSegments = segments.slice(start, Math.min(start + groupSize, segments.length));
      const mainTitles = mainSegments.map(s => s.meta.title || `块${s.meta.index + 1}`);

      result.push({
        content: combinedContent,
        meta: {
          index: groupIndex,
          groupIndex,
          windowStart,
          windowEnd,
          mainStart: start,
          mainEnd: Math.min(start + groupSize, segments.length),
          contextBefore: windowStart < start ? contextBefore : start,
          contextAfter: windowEnd > start + groupSize ? contextAfter : (windowEnd - start - groupSize),
          titles: mainTitles,
          charCount: combinedContent.length
        }
      });
      groupIndex++;
    }

    return result;
  }
}

class CustomStage implements PreprocessStage {
  name = 'Custom';

  execute(segments: TextSegment[], config: Record<string, any>): TextSegment[] {
    const language = (config.language as string) || 'javascript';
    const customCode = config.customCode as string;

    if (!customCode || !customCode.trim()) return segments;

    if (language === 'javascript') {
      return this.executeJavaScript(segments, customCode);
    }
    // Python and Perl are async but this interface is sync.
    // For now, JS is the primary path. Python/Perl custom stages are
    // executed via the async wrapper in preprocessorWorker.
    throw new Error(`Custom stage language "${language}" requires async execution. Use JS for sync pipelines.`);
  }

  private executeJavaScript(segments: TextSegment[], code: string): TextSegment[] {
    const utils = {
      segment: (content: string, meta?: Record<string, any>) => ({
        content,
        meta: { index: 0, charCount: content.length, ...meta }
      }),
      regex: (pattern: string, text: string): string[] => {
        const re = new RegExp(pattern, 'g');
        const results: string[] = [];
        let m: RegExpExecArray | null;
        while ((m = re.exec(text)) !== null) {
          results.push(m[0]);
        }
        return results;
      },
      countTokens: (text: string): number => text.length
    };

    const fn = new Function('segments', 'utils', code);
    const result = fn(segments, utils);

    if (!Array.isArray(result)) {
      throw new Error('Custom JS stage must return an array of TextSegment objects');
    }

    return result;
  }
}

// ======================== 异步自定义阶段 (Python/Perl) ========================

export async function executeCustomStageAsync(
  segments: TextSegment[],
  config: Record<string, any>
): Promise<TextSegment[]> {
  const language = (config.language as string) || 'javascript';
  const customCode = config.customCode as string;

  if (!customCode || !customCode.trim()) return segments;
  if (language === 'javascript') {
    return new CustomStage().execute(segments, config);
  }

  const inputJson = JSON.stringify({ segments, config });
  const tmpFile = join(tmpdir(), `preprocess_${randomUUID()}.${language === 'python' ? 'py' : 'pl'}`);

  let script: string;
  let cmd: string;
  let args: string[];

  if (language === 'python') {
    script = buildPythonScript(customCode);
    cmd = 'python3';
    args = [tmpFile];
  } else if (language === 'perl') {
    script = buildPerlScript(customCode);
    cmd = 'perl';
    args = [tmpFile];
  } else {
    return segments;
  }

  writeFileSync(tmpFile, script, 'utf-8');

  try {
    const result = await executeScript(cmd, args, inputJson);
    return result;
  } finally {
    try { unlinkSync(tmpFile); } catch {}
  }
}

function executeScript(cmd: string, args: string[], inputJson: string): Promise<TextSegment[]> {
  return new Promise((resolve, reject) => {
    const proc = spawn(cmd, args, {
      stdio: ['pipe', 'pipe', 'pipe'],
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
    });

    let stdout = '';
    let stderr = '';
    let stdoutSize = 0;
    const MAX_STDOUT = 50 * 1024 * 1024; // 50MB

    const timer = setTimeout(() => {
      proc.kill('SIGKILL');
      reject(new Error(`Custom script timed out after 30s`));
    }, 30000);

    proc.stdout.on('data', (chunk: Buffer) => {
      stdoutSize += chunk.length;
      if (stdoutSize > MAX_STDOUT) {
        proc.kill('SIGKILL');
        reject(new Error(`stdout exceeded ${MAX_STDOUT / 1024 / 1024}MB limit`));
        return;
      }
      stdout += chunk.toString();
    });

    proc.stderr.on('data', (chunk: Buffer) => {
      stderr += chunk.toString();
    });

    proc.on('close', (code) => {
      clearTimeout(timer);
      if (code !== 0) {
        reject(new Error(`Script exited with code ${code}: ${stderr.slice(0, 500)}`));
        return;
      }
      try {
        const parsed = JSON.parse(stdout);
        if (!parsed.segments || !Array.isArray(parsed.segments)) {
          reject(new Error(`Invalid script output: missing "segments" array`));
          return;
        }
        resolve(parsed.segments as TextSegment[]);
      } catch (e: any) {
        reject(new Error(`Failed to parse script JSON output: ${e.message}. stderr: ${stderr.slice(0, 200)}`));
      }
    });

    proc.on('error', (err) => {
      clearTimeout(timer);
      reject(new Error(`Failed to spawn ${cmd}: ${err.message}`));
    });

    proc.stdin.write(inputJson);
    proc.stdin.end();
  });
}

function buildPythonScript(userCode: string): string {
  return `import json, sys, re

# ═══ 辅助函数 ═══
def segment(content, meta=None):
    m = meta.copy() if meta else {}
    m['charCount'] = len(content)
    return {'content': content, 'meta': m}

def regex_match(pattern, text):
    return [m.group() for m in re.finditer(pattern, text)]

def count_tokens(text):
    return len(text)
# ═══ 辅助函数结束 ═══

def main():
    raw = sys.stdin.buffer.read()
    data = json.loads(raw.decode('utf-8'))
    segments = data['segments']
    config = data['config']

    # ═══════ 用户代码开始 ═══════
${indentCode(userCode, 4)}
    # ═══════ 用户代码结束 ═══════

    output = json.dumps({'segments': result}, ensure_ascii=False)
    sys.stdout.buffer.write(output.encode('utf-8'))

if __name__ == '__main__':
    main()
`;
}

function buildPerlScript(userCode: string): string {
  return `use strict;
use warnings;
use utf8;
binmode(STDIN, ':utf8');
binmode(STDOUT, ':utf8');

my $json_ok = eval { require JSON; JSON->import(qw(decode_json encode_json)); 1 };
die "Perl JSON module not installed. Run: cpan JSON\\n" unless $json_ok;

# ═══ 辅助函数 ═══
sub segment {
    my ($content, $meta) = @_;
    $meta //= {};
    $meta->{charCount} = length($content);
    return { content => $content, meta => $meta };
}

sub count_tokens {
    return length(shift);
}
# ═══ 辅助函数结束 ═══

my $json_text = do { local $/; <STDIN> };
my $data = decode_json($json_text);
my $segments = $data->{segments};
my $config = $data->{config};

# ═══════ 用户代码开始 ═══════
${userCode}
# ═══════ 用户代码结束 ═══════

print encode_json({ segments => \\@result });
`;
}

function indentCode(code: string, spaces: number): string {
  const prefix = ' '.repeat(spaces);
  return code.split('\n').map(line => line ? prefix + line : line).join('\n');
}

// ======================== 阶段注册表 ========================

const stageRegistry = new Map<string, PreprocessStage>();

function registerStage(type: string, stage: PreprocessStage): void {
  stageRegistry.set(type, stage);
}

// 注册内置阶段
registerStage('replace', new RegexReplaceStage());
registerStage('split_regex', new RegexSplitStage());
registerStage('split_token', new TokenSplitStage());
registerStage('split_lines', new LineSplitStage());
registerStage('window_group', new WindowGroupStage());
registerStage('custom', new CustomStage());

export function getStageExecutor(type: string): PreprocessStage {
  const stage = stageRegistry.get(type);
  if (!stage) throw new Error(`Unknown stage type: ${type}`);
  return stage;
}

// ======================== 编码检测 ========================

/**
 * 检测文本是否有足够的中文字符（用于判断编码是否正确）
 */
export function countChineseChars(text: string): number {
  return (text.match(/[一-鿿㐀-䶿]/g) || []).length;
}

/**
 * 自动检测编码：如果 UTF-8 读到中文字符不够，尝试 GBK
 * 返回 { text, encoding }
 */
export function autoDetectEncoding(buffer: Buffer): { text: string; encoding: string } {
  const utf8Text = buffer.toString('utf-8');
  const chineseChars = countChineseChars(utf8Text);

  // 中文文本至少每 100 字节应有 1 个中文字符（粗略估算）
  const minExpected = Math.floor(buffer.length / 200);
  if (chineseChars >= minExpected) {
    return { text: utf8Text, encoding: 'utf-8' };
  }

  // UTF-8 中文太少，尝试 GBK
  try {
    const gbkText = (buffer as any).toString('gbk') as string;
    const gbkChinese = countChineseChars(gbkText);
    if (gbkChinese > chineseChars) {
      return { text: gbkText, encoding: 'gbk' };
    }
  } catch {
    // GBK not supported
  }

  return { text: utf8Text, encoding: 'utf-8' };
}

// ======================== 管线执行器 ========================

export async function runPreprocessPipeline(
  inputText: string,
  stages: StageConfig[]
): Promise<TextSegment[]> {
  let segments: TextSegment[] = [{
    content: inputText,
    meta: { index: 0, charCount: inputText.length }
  }];

  let splitCount = 0;
  for (const stage of stages) {
    if (!stage.enabled) continue;

    const beforeCount = segments.length;
    if (stage.type === 'custom' && stage.language && stage.language !== 'javascript') {
      segments = await executeCustomStageAsync(segments, { ...stage.config, language: stage.language, customCode: stage.customCode });
    } else {
      const executor = getStageExecutor(stage.type);
      segments = executor.execute(segments, stage.config);
    }

    // 跟踪拆分阶段是否生效
    if (stage.type === 'split_regex' || stage.type === 'split_token' || stage.type === 'split_lines') {
      splitCount = segments.length;
    }
  }

  // 重新编号
  segments.forEach((s, i) => { s.meta.index = i; });

  return segments;
}

/**
 * 获取管线执行统计信息（供前端提示用）
 */
export function getPipelineStats(segments: TextSegment[]): {
  totalSegments: number;
  totalChars: number;
  avgCharsPerSegment: number;
  hasSplits: boolean;
} {
  const totalChars = segments.reduce((s, seg) => s + seg.content.length, 0);
  return {
    totalSegments: segments.length,
    totalChars,
    avgCharsPerSegment: segments.length > 0 ? Math.round(totalChars / segments.length) : 0,
    hasSplits: segments.length > 1
  };
}

// ======================== 正则测试工具 ========================

export function testRegex(
  pattern: string,
  sampleText: string
): { matchCount: number; matches: Array<{ index: number; text: string }> } {
  const re = new RegExp(pattern, 'gm');
  const matches: Array<{ index: number; text: string }> = [];
  let m: RegExpExecArray | null;
  while ((m = re.exec(sampleText)) !== null) {
    matches.push({ index: m.index, text: m[0].slice(0, 100) });
  }
  return { matchCount: matches.length, matches };
}
