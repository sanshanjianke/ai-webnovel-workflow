// L1 种子层路由
import { Express, Request, Response } from 'express';
import * as fs from 'fs';
import * as path from 'path';
import { getProjectManager } from '../services/project-manager';
import { getLLM } from '../services/llm';
import { VisionDocument } from '../protocols';
import { SSEWriter } from '../utils/sse';

const L1_PROMPT = `你是一位创作顾问，帮助用户梳理创意愿景，产出清晰的故事种子文档。

请根据用户提供的以下信息，生成一份结构化的《故事愿景文档》：

用户输入：
{user_input}

请按以下格式输出：

# 故事愿景文档

## 核心梗
[一句话概括故事核心创意]

## 阅读契约
- 目标读者：[男频/女频/年龄层]
- 核心爽点：[装逼/升级/恋爱/悬疑等]
- 风格基调：[轻松/暗黑/热血/治愈等]

## 粗略大纲
1. 开篇：[...]
2. 发展：[...]
3. 高潮：[...]
4. 结局：[...]

## 核心设定
- 世界观：[...]
- 主角人设：[...]
- 金手指/核心道具：[...]

## 热点/潮流元素（如有）
- 热点：[...]
- 融合方式：[...]
- 时效性评估：[...]

## 预期字数
[长篇/中篇/短篇，预估字数]

注意：
- 不评判创意好坏，只负责结构化
- 如果用户信息不足，根据上下文合理补充
- 输出要简洁，不超过500字`;

export function registerL1Routes(app: Express): void {
  const pm = getProjectManager();

  // L1 聊天（SSE 流式）
  app.post('/api/projects/:projectId/l1/chat', async (req: Request, res: Response) => {
    const project = pm.getProject(req.params.projectId);
    if (!project) {
      return res.status(404).json({ error: 'Project not found' });
    }

    const { messages = [], currentForm = {} } = req.body;
    const writer = new SSEWriter(res);

    try {
      const llm = getLLM();
      
      // 构建聊天历史
      const chatHistory = messages.map((m: Record<string, string>) => 
        `${m.role === 'user' ? '用户' : 'AI'}: ${m.content}`
      ).join('\n');

      const prompt = `你是创作顾问，帮助用户梳理创意。

当前表单状态：
${JSON.stringify(currentForm, null, 2)}

聊天历史：
${chatHistory}

请继续引导用户完善创意。如果用户提供了新信息，提取关键字段。

回复格式：
1. 自然对话回复
2. 如果提取到字段，用 JSON 格式输出：{"extracted": {"field": "value"}}`;

      let fullContent = '';
      let thinking = '';

      for await (const chunk of llm.stream(prompt)) {
        if (chunk.type === 'thinking') {
          thinking += chunk.content;
          writer.write('thinking', { content: chunk.content });
        } else {
          fullContent += chunk.content;
          writer.write('chunk', { content: chunk.content });
        }
      }

      // 尝试提取字段
      let extracted = {};
      try {
        const jsonMatch = fullContent.match(/\{"extracted":\s*\{[^}]*\}\}/);
        if (jsonMatch) {
          const parsed = JSON.parse(jsonMatch[0]);
          extracted = parsed.extracted || {};
        }
      } catch {}

      writer.write('done', { 
        content: fullContent,
        thinking,
        extracted
      });
    } catch (error) {
      writer.write('error', { message: String(error) });
    } finally {
      writer.close();
    }
  });

  // 生成愿景文档
  app.post('/api/projects/:projectId/l1/generate', async (req: Request, res: Response) => {
    const project = pm.getProject(req.params.projectId);
    if (!project) {
      return res.status(404).json({ error: 'Project not found' });
    }

    try {
      const llm = getLLM();
      const inputText = Object.entries(req.body)
        .filter(([_, v]) => v)
        .map(([k, v]) => `- ${k}: ${v}`)
        .join('\n');

      const prompt = L1_PROMPT.replace('{user_input}', inputText || '用户未提供具体信息');
      const response = await llm.invoke(prompt);

      // 解析响应
      const vision = parseVisionResponse(response, req.body);

      // 保存
      const visionPath = path.join(project.path, 'outputs', 'l1_vision.json');
      fs.mkdirSync(path.dirname(visionPath), { recursive: true });
      fs.writeFileSync(visionPath, JSON.stringify({
        ...vision,
        createdAt: new Date().toISOString()
      }, null, 2), 'utf-8');

      res.json({ status: 'generated', vision });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // 获取愿景文档
  app.get('/api/projects/:projectId/l1/vision', (req: Request, res: Response) => {
    const project = pm.getProject(req.params.projectId);
    if (!project) {
      return res.status(404).json({ error: 'Project not found' });
    }

    const visionPath = path.join(project.path, 'outputs', 'l1_vision.json');
    if (!fs.existsSync(visionPath)) {
      return res.status(404).json({ error: 'Vision not found' });
    }

    const vision = JSON.parse(fs.readFileSync(visionPath, 'utf-8'));
    res.json({ vision });
  });

  // 更新愿景文档
  app.put('/api/projects/:projectId/l1/vision', (req: Request, res: Response) => {
    const project = pm.getProject(req.params.projectId);
    if (!project) {
      return res.status(404).json({ error: 'Project not found' });
    }

    const visionPath = path.join(project.path, 'outputs', 'l1_vision.json');
    fs.mkdirSync(path.dirname(visionPath), { recursive: true });
    fs.writeFileSync(visionPath, JSON.stringify({
      ...req.body,
      updatedAt: new Date().toISOString()
    }, null, 2), 'utf-8');

    res.json({ status: 'updated' });
  });

  // 保存草稿
  app.get('/api/projects/:projectId/l1/draft', (req: Request, res: Response) => {
    const project = pm.getProject(req.params.projectId);
    if (!project) {
      return res.status(404).json({ error: 'Project not found' });
    }

    const draftPath = path.join(project.path, 'outputs', 'l1_draft.json');
    if (fs.existsSync(draftPath)) {
      const draft = JSON.parse(fs.readFileSync(draftPath, 'utf-8'));
      res.json({ draft });
    } else {
      res.json({ draft: {} });
    }
  });

  app.post('/api/projects/:projectId/l1/draft', (req: Request, res: Response) => {
    const project = pm.getProject(req.params.projectId);
    if (!project) {
      return res.status(404).json({ error: 'Project not found' });
    }

    const draftPath = path.join(project.path, 'outputs', 'l1_draft.json');
    fs.mkdirSync(path.dirname(draftPath), { recursive: true });
    fs.writeFileSync(draftPath, JSON.stringify(req.body, null, 2), 'utf-8');

    res.json({ status: 'saved' });
  });

  // 聊天历史
  app.get('/api/projects/:projectId/l1/chat-history', (req: Request, res: Response) => {
    const project = pm.getProject(req.params.projectId);
    if (!project) {
      return res.status(404).json({ error: 'Project not found' });
    }

    const historyPath = path.join(project.path, 'outputs', 'l1_chat_history.json');
    if (fs.existsSync(historyPath)) {
      const history = JSON.parse(fs.readFileSync(historyPath, 'utf-8'));
      res.json({ history });
    } else {
      res.json({ history: [] });
    }
  });

  app.post('/api/projects/:projectId/l1/chat-history', (req: Request, res: Response) => {
    const project = pm.getProject(req.params.projectId);
    if (!project) {
      return res.status(404).json({ error: 'Project not found' });
    }

    const historyPath = path.join(project.path, 'outputs', 'l1_chat_history.json');
    fs.mkdirSync(path.dirname(historyPath), { recursive: true });
    fs.writeFileSync(historyPath, JSON.stringify(req.body, null, 2), 'utf-8');

    res.json({ status: 'saved' });
  });
}

function parseVisionResponse(response: string, originalInput: Record<string, string>): VisionDocument {
  const extractSection = (name: string): string => {
    const regex = new RegExp(`##\\s*${name}[^\\n]*\\n([\\s\\S]*?)(?=##|$)`, 'i');
    const match = response.match(regex);
    return match ? match[1].trim() : '';
  };

  const extractField = (text: string, field: string): string => {
    const lines = text.split('\n');
    for (const line of lines) {
      if (line.includes(field)) {
        const parts = line.split(/[：:]/);
        return parts.length > 1 ? parts[1].trim() : '';
      }
    }
    return '';
  };

  const contract = extractSection('阅读契约');
  const setting = extractSection('核心设定');

  return {
    coreIdea: extractSection('核心梗') || originalInput.idea || '',
    targetReaders: extractField(contract, '目标读者') || originalInput.targetReaders || '',
    coreAppeal: extractField(contract, '核心爽点') || originalInput.coreAppeal || '',
    style: extractField(contract, '风格基调') || originalInput.style || '',
    roughOutline: extractSection('粗略大纲') || originalInput.roughOutline || originalInput.outline || '',
    worldSetting: extractField(setting, '世界观') || originalInput.worldSetting || '',
    protagonist: extractField(setting, '主角人设') || originalInput.protagonist || '',
    goldenFinger: extractField(setting, '金手指') || extractField(setting, '核心道具') || originalInput.goldenFinger || '',
    hotElements: extractSection('热点/潮流元素') || originalInput.hotElements || '',
    expectedLength: extractSection('预期字数') || originalInput.expectedLength || ''
  };
}
