// LLM 服务单元测试
import { describe, it, expect, beforeEach } from 'vitest';
import { MockLLM, setLLM, resetLLM, getLLM } from '../services/llm';

describe('LLM 服务', () => {
  beforeEach(() => {
    resetLLM();
  });

  describe('MockLLM', () => {
    it('应该返回默认响应', async () => {
      const llm = new MockLLM();
      const response = await llm.invoke('测试提示');
      
      expect(response).toContain('故事愿景文档');
      expect(response).toContain('核心梗');
    });

    it('应该返回自定义响应', async () => {
      const llm = new MockLLM('自定义响应');
      const response = await llm.invoke('测试提示');
      
      expect(response).toBe('自定义响应');
    });

    it('应该支持流式输出', async () => {
      const llm = new MockLLM('Hello World');
      const chunks: string[] = [];
      
      for await (const chunk of llm.stream('测试')) {
        chunks.push(chunk.content);
      }
      
      expect(chunks.length).toBeGreaterThan(0);
      expect(chunks.join('')).toContain('Hello');
    });
  });

  describe('LLM 工厂', () => {
    it('应该返回默认 LLM', () => {
      const llm = getLLM();
      expect(llm).toBeDefined();
    });

    it('应该支持设置自定义 LLM', async () => {
      const mockLlm = new MockLLM('自定义');
      setLLM(mockLlm);
      
      const llm = getLLM();
      const response = await llm.invoke('测试');
      expect(response).toBe('自定义');
    });

    it('应该支持重置', () => {
      setLLM(new MockLLM('测试'));
      resetLLM();
      
      // 重置后应该创建新的实例
      const llm = getLLM();
      expect(llm).toBeDefined();
    });
  });
});
