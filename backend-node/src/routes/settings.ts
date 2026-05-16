// 系统设置路由
import { Express, Request, Response } from 'express';
import * as fs from 'fs';
import * as path from 'path';
import { getConfig, saveConfig } from '../config';
import { listExperts } from '../experts';
import { LLMProviderPreset } from '../protocols';

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

export function registerSettingsRoutes(app: Express): void {
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
    // 深合并 llm 字段，避免丢失 primary/embedding 等未在前端显示的字段
    if (req.body.llm && typeof req.body.llm === 'object') {
      updated.llm = { ...config.llm, ...req.body.llm };
    }
    if (req.body.generation && typeof req.body.generation === 'object') {
      updated.generation = { ...config.generation, ...req.body.generation };
    }
    saveConfig(updated);
    res.json({ status: 'updated' });
  });
}
