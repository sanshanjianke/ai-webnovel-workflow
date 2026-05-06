// LLM 调用模块
import { getConfig } from '../config';
import { LLMProvider, LLMOptions, LLMChunk } from '../protocols';

export class OpenAICompatLLM implements LLMProvider {
  private apiKey: string;
  private baseUrl: string;
  private model: string;

  constructor(apiKey?: string, baseUrl?: string, model?: string) {
    const config = getConfig();
    this.apiKey = apiKey || config.llm.apiKey;
    this.baseUrl = baseUrl || config.llm.baseUrl;
    this.model = model || config.llm.model || 'GLM-5';
  }

  async invoke(prompt: string, options: LLMOptions = {}): Promise<string> {
    const url = `${this.baseUrl.replace(/\/$/, '')}/chat/completions`;
    
    const body: Record<string, unknown> = {
      model: options.model || this.model,
      messages: [{ role: 'user', content: prompt }],
      temperature: options.temperature ?? 0.7,
      max_tokens: options.maxTokens ?? 16384
    };

    // 启用 think 模式
    if (options.thinking) {
      body.thinking = {
        type: 'enabled',
        budget_tokens: options.thinkingBudget || 10000
      };
    }

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.apiKey}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(body)
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`LLM API error: ${response.status} - ${error}`);
    }

    const data = await response.json() as Record<string, unknown>;
    const choices = data.choices as Array<Record<string, unknown>>;
    const message = choices[0].message as Record<string, unknown>;
    return message.content as string;
  }

  async *stream(prompt: string, options: LLMOptions = {}): AsyncGenerator<LLMChunk> {
    const url = `${this.baseUrl.replace(/\/$/, '')}/chat/completions`;
    
    const body: Record<string, unknown> = {
      model: options.model || this.model,
      messages: [{ role: 'user', content: prompt }],
      temperature: options.temperature ?? 0.7,
      max_tokens: options.maxTokens ?? 16384,
      stream: true
    };

    // 启用 think 模式
    if (options.thinking) {
      body.thinking = {
        type: 'enabled',
        budget_tokens: options.thinkingBudget || 10000
      };
    }

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.apiKey}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(body)
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`LLM API error: ${response.status} - ${error}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('No response body');
    }

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || !trimmed.startsWith('data: ')) continue;
        
        const data = trimmed.slice(6);
        if (data === '[DONE]') return;

        try {
          const parsed = JSON.parse(data) as Record<string, unknown>;
          const choices = parsed.choices as Array<Record<string, unknown>> | undefined;
          const delta = choices?.[0]?.delta as Record<string, unknown> | undefined;
          
          // GLM/DeepSeek 使用 reasoning_content 字段
          const reasoning = delta?.reasoning_content;
          if (reasoning) {
            yield { type: 'thinking', content: reasoning as string };
          }
          
          const content = delta?.content;
          if (content) {
            yield { type: 'content', content: content as string };
          }
        } catch {
          // 忽略解析错误
        }
      }
    }
  }
}

// 模拟 LLM（用于测试）
export class MockLLM implements LLMProvider {
  private response: string;

  constructor(response?: string) {
    this.response = response || this.defaultResponse();
  }

  async invoke(prompt: string): Promise<string> {
    return this.response;
  }

  async *stream(prompt: string): AsyncGenerator<LLMChunk> {
    const words = this.response.split(/\s+/);
    for (const word of words) {
      yield { type: 'content', content: word + ' ' };
      await new Promise(resolve => setTimeout(resolve, 10));
    }
  }

  private defaultResponse(): string {
    return `# 故事愿景文档

## 核心梗
主角穿越到修真世界，带着现代AI系统，用科技思维改变修真界。

## 阅读契约
- 目标读者：男频，18-35岁
- 核心爽点：装逼打脸、系统升级、科技碾压
- 风格基调：轻松热血

## 粗略大纲
1. 开篇：主角穿越，激活AI系统，发现自己身处修真宗门
2. 发展：利用AI分析功法，快速突破，引起注意
3. 高潮：宗门大比，主角以科技思维碾压传统修士
4. 结局：主角成为宗门核心弟子，开启新的征程

## 核心设定
- 世界观：修真世界，等级森严，强者为尊
- 主角人设：理工男，理性思维，不按常理出牌
- 金手指/核心道具：AI系统，可分析功法、预测对手招式

## 热点/潮流元素（如有）
- 热点：AI技术热潮
- 融合方式：将AI思维融入修真体系
- 时效性评估：长期有效，科技是永恒话题

## 预期字数
长篇，预计200万字`;
  }
}

// LLM 工厂
let _llmInstance: LLMProvider | null = null;

export function getLLM(): LLMProvider {
  if (!_llmInstance) {
    const config = getConfig();
    if (config.llm.primary === 'mock') {
      _llmInstance = new MockLLM();
    } else {
      _llmInstance = new OpenAICompatLLM();
    }
  }
  return _llmInstance;
}

export function setLLM(llm: LLMProvider): void {
  _llmInstance = llm;
}

export function resetLLM(): void {
  _llmInstance = null;
}
