// 系统设置路由
import { Express, Request, Response } from 'express';
import { getConfig, saveConfig } from '../config';
import { listExperts } from '../experts';

export function registerSettingsRoutes(app: Express): void {
  // 获取模块列表
  app.get('/api/modules', (req: Request, res: Response) => {
    res.json({
      llm: ['openai_compat', 'mock'],
      rag: ['simple_vector'],
      worldbook: ['st_style'],
      l1: ['guided_form'],
      l3: ['mapping_compiler'],
      l4: ['constrained_renderer'],
      expert: listExperts(),
      meeting_protocol: ['editor_reader', 'plot_driven', 'character_driven', 'market_driven']
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
    const updated = { ...config, ...req.body };
    saveConfig(updated);
    res.json({ status: 'updated' });
  });

  // 获取 L3 标签
  app.get('/api/tags/l3', (req: Request, res: Response) => {
    // 空桩
    res.json({});
  });

  // 获取 L4 标签
  app.get('/api/tags/l4', (req: Request, res: Response) => {
    // 空桩
    res.json({});
  });
}
