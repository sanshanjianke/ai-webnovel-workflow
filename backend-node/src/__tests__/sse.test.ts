// SSE 工具单元测试
import { describe, it, expect, vi } from 'vitest';
import { sseFormat, sseData } from '../utils/sse';

describe('SSE 工具', () => {
  it('sseFormat 应该生成正确的格式', () => {
    const result = sseFormat('test_event', { key: 'value' });
    expect(result).toBe('event: test_event\ndata: {"key":"value"}\n\n');
  });

  it('sseData 应该生成正确的格式', () => {
    const result = sseData({ type: 'message', content: 'hello' });
    expect(result).toBe('data: {"type":"message","content":"hello"}\n\n');
  });

  it('应该正确处理中文字符', () => {
    const result = sseFormat('test', { message: '你好' });
    expect(result).toContain('"message":"你好"');
  });

  it('应该正确处理特殊字符', () => {
    const result = sseFormat('test', { message: 'hello\nworld' });
    expect(result).toContain('\\n');
  });
});
