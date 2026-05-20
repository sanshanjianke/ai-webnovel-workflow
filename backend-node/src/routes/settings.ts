// 系统设置路由
import { Express, Request, Response } from 'express';
import * as fs from 'fs';
import * as path from 'path';
import { getConfig, saveConfig } from '../config';
import { listExperts } from '../experts';
import { resetLLM } from '../services/llm';
import { LLMProviderPreset, EmbeddingProviderPreset } from '../protocols';

// 项目根目录：从 CWD 或 __dirname 推算（支持 tsx/node 直接运行和 dist 编译运行）
const PROJECT_ROOT = (() => {
  const cwd = process.cwd();
  // 编译运行：dist/routes/settings.js → 往上 3 层
  // tsx 运行：src/routes/settings.ts → 往上 3 层
  // CWD 通常是 backend-node/，往上 1 层即项目根
  const fromCwd = path.resolve(cwd, '..');
  if (fs.existsSync(path.join(fromCwd, 'data', 'llm-providers.json'))) return fromCwd;
  const fromDir = path.resolve(__dirname, '../../..');
  if (fs.existsSync(path.join(fromDir, 'data', 'llm-providers.json'))) return fromDir;
  return fromCwd; // fallback
})();

// 加载内置服务商预设
function loadBuiltinProviders(): LLMProviderPreset[] {
  const presetPath = path.join(PROJECT_ROOT, 'data', 'llm-providers.json');
  if (fs.existsSync(presetPath)) {
    return JSON.parse(fs.readFileSync(presetPath, 'utf-8'));
  }
  return [];
}

function loadBuiltinEmbeddingProviders(): EmbeddingProviderPreset[] {
  const presetPath = path.join(PROJECT_ROOT, 'data', 'embedding-providers.json');
  if (fs.existsSync(presetPath)) {
    return JSON.parse(fs.readFileSync(presetPath, 'utf-8'));
  }
  return [];
}

export function registerSettingsRoutes(app: Express): void {
  // 测试 LLM 连通性
  app.post('/api/llm/test', async (req: Request, res: Response) => {
    try {
      const { llm: llmConfig, generation: genConfig } = req.body;

      const baseUrl = llmConfig?.base_url || getConfig().llm.baseUrl;
      const apiKey = llmConfig?.api_key || getConfig().llm.apiKey;
      const model = llmConfig?.model || getConfig().llm.model || 'GLM-5';

      if (!apiKey) {
        res.json({ success: false, error: '未配置 API Key' });
        return;
      }
      if (!baseUrl) {
        res.json({ success: false, error: '未配置 Base URL' });
        return;
      }

      const response = await fetch(`${baseUrl.replace(/\/$/, '')}/chat/completions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${apiKey}`,
          ...(llmConfig?.headers || {}),
        },
        body: JSON.stringify({
          model,
          messages: [{ role: 'user', content: '你好，请回复"连接成功"。' }],
          max_tokens: 50,
          temperature: 0,
          ...(genConfig?.thinking ? { thinking: { type: 'enabled' } } : {}),
        }),
        signal: AbortSignal.timeout(30000),
      });

      if (!response.ok) {
        const errText = await response.text();
        let errMsg = `HTTP ${response.status}`;
        try {
          const errJson = JSON.parse(errText);
          errMsg = errJson.error?.message || errJson.message || errMsg;
        } catch {}
        res.json({ success: false, error: errMsg, detail: errText });
        return;
      }

      const data = await response.json() as Record<string, unknown>;
      const choices = data.choices as Array<Record<string, unknown>>;
      const content = (choices?.[0]?.message as Record<string, unknown>)?.content as string || '';

      res.json({
        success: true,
        model: data.model || model,
        reply: content.slice(0, 200),
        usage: data.usage || null,
      });
    } catch (err: any) {
      const message = err.name === 'TimeoutError' || err.name === 'AbortError'
        ? '连接超时（30 秒）'
        : err.message || String(err);
      res.json({ success: false, error: message });
    }
  });

  // 测试 Embedding 连通性
  app.post('/api/embedding/test', async (req: Request, res: Response) => {
    try {
      const { model, api_key, base_url } = req.body;
      const resolvedBaseUrl = base_url || getConfig().llm.baseUrl;
      const resolvedApiKey = api_key || getConfig().llm.apiKey;
      const resolvedModel = model || 'text-embedding-v3';

      if (!resolvedApiKey) {
        res.json({ success: false, error: '未配置 API Key（LLM 和 Embedding 均为空）' });
        return;
      }

      const response = await fetch(`${resolvedBaseUrl.replace(/\/$/, '')}/embeddings`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${resolvedApiKey}`,
        },
        body: JSON.stringify({
          model: resolvedModel,
          input: '连接测试',
        }),
        signal: AbortSignal.timeout(30000),
      });

      if (!response.ok) {
        const errText = await response.text();
        let errMsg = `HTTP ${response.status}`;
        try {
          const errJson = JSON.parse(errText);
          errMsg = errJson.error?.message || errJson.message || errMsg;
        } catch {}
        res.json({ success: false, error: errMsg, detail: errText });
        return;
      }

      const data = await response.json() as Record<string, unknown>;
      const embData = (data.data as Array<Record<string, unknown>>)?.[0];
      const embedding = embData?.embedding as number[] | undefined;

      res.json({
        success: true,
        model: data.model || resolvedModel,
        dimensions: embedding ? embedding.length : 0,
        usage: data.usage || null,
      });
    } catch (err: any) {
      const message = err.name === 'TimeoutError' || err.name === 'AbortError'
        ? '连接超时（30 秒）'
        : err.message || String(err);
      res.json({ success: false, error: message });
    }
  });

  // 获取 LLM 服务商预设（内置 + 用户自定义）
  app.get('/api/llm-providers', (req: Request, res: Response) => {
    const builtin = loadBuiltinProviders();
    const config = getConfig();
    const custom = config.llm_providers?.custom || [];
    res.json({ builtin, custom });
  });

  // 保存用户自定义服务商
  app.put('/api/llm-providers', (req: Request, res: Response) => {
    const config = getConfig();
    const updated = {
      ...config,
      llm_providers: { custom: req.body.custom || [] }
    };
    saveConfig(updated);
    res.json({ status: 'updated' });
  });

  // 获取 Embedding 服务商预设（内置 + 用户自定义）
  app.get('/api/embedding-providers', (req: Request, res: Response) => {
    const builtin = loadBuiltinEmbeddingProviders();
    const config = getConfig();
    const custom = config.embedding_providers?.custom || [];
    res.json({ builtin, custom });
  });

  // 保存用户自定义 Embedding 服务商
  app.put('/api/embedding-providers', (req: Request, res: Response) => {
    const config = getConfig();
    const updated = {
      ...config,
      embedding_providers: { custom: req.body.custom || [] }
    };
    saveConfig(updated);
    res.json({ status: 'updated' });
  });

  // 获取模块列表
  app.get('/api/modules', (req: Request, res: Response) => {
    res.json({
      llm: ['openai_compat', 'mock'],
      rag: ['simple_vector'],
      worldbook: ['st_style'],
      expert: listExperts()
    });
  });

  // 获取配置
  app.get('/api/config', (req: Request, res: Response) => {
    const config = getConfig();
    // 隐藏敏感信息
    const safeConfig = {
      ...config,
      llm: {
        ...config.llm,
        apiKey: config.llm.apiKey ? '***' : ''
      }
    };
    res.json(safeConfig);
  });

  // 更新配置
  app.put('/api/config', (req: Request, res: Response) => {
    const config = getConfig();
    const updated = { ...config };
    // 深合并 llm 字段，避免丢失 primary 等未在前端显示的字段
    // 同时规范化前端 snake_case → 后端 camelCase，防止 yaml 中出现重复字段
    const normLLM = (body: Record<string, unknown>) => {
      const n = { ...body } as Record<string, unknown>;
      if (n.api_key) { n.apiKey = n.api_key; delete n.api_key; }
      if (n.base_url) { n.baseUrl = n.base_url; delete n.base_url; }
      return n;
    };
    const normGen = (body: Record<string, unknown>) => {
      const n = { ...body } as Record<string, unknown>;
      if (n.top_p !== undefined) { n.topP = n.top_p; delete n.top_p; }
      if (n.frequency_penalty !== undefined) { n.frequencyPenalty = n.frequency_penalty; delete n.frequency_penalty; }
      if (n.presence_penalty !== undefined) { n.presencePenalty = n.presence_penalty; delete n.presence_penalty; }
      if (n.max_tokens !== undefined) { n.maxTokens = n.max_tokens; delete n.max_tokens; }
      if (n.thinking_budget !== undefined) { n.thinkingBudget = n.thinking_budget; delete n.thinking_budget; }
      if (n.reasoning_effort !== undefined) { n.reasoningEffort = n.reasoning_effort; delete n.reasoning_effort; }
      return n;
    };

    if (req.body.llm && typeof req.body.llm === 'object') {
      updated.llm = { ...config.llm, ...normLLM(req.body.llm) };
    }
    if (req.body.embedding && typeof req.body.embedding === 'object') {
      updated.embedding = { ...config.embedding, ...normLLM(req.body.embedding) };
    }
    if (req.body.generation && typeof req.body.generation === 'object') {
      updated.generation = { ...config.generation, ...normGen(req.body.generation) };
    }
    saveConfig(updated);
    resetLLM();
    res.json({ status: 'updated' });
  });
}
