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

  // 获取默认提示词
  app.get('/api/projects/:projectId/l1/prompt', (req: Request, res: Response) => {
    const formParts: string[] = [];
    // 返回模板，用 {field} 占位
    const promptTemplate = `你是一位创作顾问，帮助用户梳理创意愿景，产出清晰的故事种子文档。

用户提供的信息：
{user_input}

请根据以上信息，生成一份完整的《故事愿景文档》。要求：
1. 直接输出文档内容，不要有多余的解释
2. 使用 markdown 格式
3. 包含以下部分：核心梗、阅读契约、粗略大纲、核心设定、热点元素、预期字数
4. 内容要具体、有指导意义，不要泛泛而谈
5. 如果用户信息不足，合理补充但要符合用户意图`;

    res.json({ prompt: promptTemplate });
  });

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
      
      // 读取愿景文档（如果存在）
      let visionContent = '';
      const visionPath = path.join(project.path, 'outputs', 'l1_vision.json');
      if (fs.existsSync(visionPath)) {
        try {
          const visionData = JSON.parse(fs.readFileSync(visionPath, 'utf-8'));
          visionContent = visionData.content || JSON.stringify(visionData, null, 2);
        } catch {}
      }
      
      // 构建聊天历史
      const chatHistory = messages.map((m: Record<string, string>) => 
        `${m.role === 'user' ? '用户' : 'AI'}: ${m.content}`
      ).join('\n');

      let prompt = `你是创作顾问，帮助用户梳理创意。

聊天历史：
${chatHistory}`;

      // 如果有愿景文档，添加到提示词
      if (visionContent) {
        prompt += `

=== 当前愿景文档 ===
${visionContent}

注意：用户已经生成了愿景文档，请根据文档内容回答问题。如果用户询问愿景文档内容，请基于上述文档回答。`;
      }

      prompt += `

请继续引导用户完善创意。保持友好、专业的语气，每次只问一个问题，逐步引导。`;

      let fullContent = '';
      let thinking = '';

      for await (const chunk of llm.stream(prompt, { thinking: true, thinkingBudget: 5000 })) {
        if (chunk.type === 'thinking') {
          thinking += chunk.content;
          writer.writeData({ type: 'thinking', content: chunk.content });
        } else {
          fullContent += chunk.content;
          writer.writeData({ type: 'chunk', content: chunk.content });
        }
      }

      writer.writeData({ 
        type: 'done', 
        content: fullContent,
        thinking
      });
    } catch (error) {
      writer.write('error', { message: String(error) });
    } finally {
      writer.close();
    }
  });

  // 生成愿景文档（SSE 流式）
  app.post('/api/projects/:projectId/l1/generate', async (req: Request, res: Response) => {
    const project = pm.getProject(req.params.projectId);
    if (!project) {
      return res.status(404).json({ error: 'Project not found' });
    }

    const writer = new SSEWriter(res);

    try {
      const llm = getLLM();
      
      // 把表单内容合并成一个提示字符串
      const formParts: string[] = [];
      if (req.body.idea) formParts.push(`创意/脑洞：${req.body.idea}`);
      if (req.body.target_readers) formParts.push(`目标读者：${req.body.target_readers}`);
      if (req.body.core_appeal) formParts.push(`核心爽点：${req.body.core_appeal}`);
      if (req.body.style) formParts.push(`风格基调：${req.body.style}`);
      if (req.body.rough_outline) formParts.push(`粗略大纲：${req.body.rough_outline}`);
      if (req.body.world_setting) formParts.push(`世界观设定：${req.body.world_setting}`);
      if (req.body.protagonist) formParts.push(`主角人设：${req.body.protagonist}`);
      if (req.body.golden_finger) formParts.push(`金手指/核心道具：${req.body.golden_finger}`);
      if (req.body.hot_elements) formParts.push(`热点元素：${req.body.hot_elements}`);
      if (req.body.expected_length) formParts.push(`预期字数：${req.body.expected_length}`);
      
      const userInput = formParts.length > 0 
        ? formParts.join('\n') 
        : '用户未提供具体信息，请根据创意方向生成';

      // 使用用户自定义提示词或默认提示词
      let prompt = req.body.custom_prompt || `你是一位创作顾问，帮助用户梳理创意愿景，产出清晰的故事种子文档。

用户提供的信息：
{user_input}

请根据以上信息，生成一份完整的《故事愿景文档》。要求：
1. 直接输出文档内容，不要有多余的解释
2. 使用 markdown 格式
3. 包含以下部分：核心梗、阅读契约、粗略大纲、核心设定、热点元素、预期字数
4. 内容要具体、有指导意义，不要泛泛而谈
5. 如果用户信息不足，合理补充但要符合用户意图`;

      // 替换 {user_input} 占位符
      prompt = prompt.replace('{user_input}', userInput);

      // 流式输出
      let fullContent = '';
      let thinkingContent = '';

      for await (const chunk of llm.stream(prompt, { 
        thinking: true, 
        thinkingBudget: 10000 
      })) {
        if (chunk.type === 'thinking') {
          thinkingContent += chunk.content;
          writer.writeData({ type: 'thinking', content: chunk.content });
        } else {
          fullContent += chunk.content;
          writer.writeData({ type: 'content', content: chunk.content });
        }
      }

      // 保存原始 markdown
      const visionPath = path.join(project.path, 'outputs', 'l1_vision.json');
      fs.mkdirSync(path.dirname(visionPath), { recursive: true });
      fs.writeFileSync(visionPath, JSON.stringify({
        content: fullContent,
        thinking: thinkingContent,
        createdAt: new Date().toISOString()
      }, null, 2), 'utf-8');

      writer.writeData({ type: 'done', content: fullContent, thinking: thinkingContent });
    } catch (error) {
      writer.write('error', { message: String(error) });
    } finally {
      writer.close();
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

    const data = JSON.parse(fs.readFileSync(visionPath, 'utf-8'));
    // 兼容新旧格式
    const vision = data.content ? data : { content: JSON.stringify(data, null, 2) };
    res.json({ vision });
  });

  // 创建/保存愿景文档
  app.post('/api/projects/:projectId/l1/vision', (req: Request, res: Response) => {
    const project = pm.getProject(req.params.projectId);
    if (!project) {
      return res.status(404).json({ error: 'Project not found' });
    }

    const visionPath = path.join(project.path, 'outputs', 'l1_vision.json');
    fs.mkdirSync(path.dirname(visionPath), { recursive: true });
    fs.writeFileSync(visionPath, JSON.stringify({
      content: req.body.content || req.body,
      updatedAt: new Date().toISOString()
    }, null, 2), 'utf-8');

    res.json({ status: 'saved' });
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

  // 返回下划线格式，与前端兼容
  return {
    core_idea: extractSection('核心梗') || originalInput.idea || originalInput.core_idea || '',
    target_readers: extractField(contract, '目标读者') || originalInput.targetReaders || originalInput.target_readers || '',
    core_appeal: extractField(contract, '核心爽点') || originalInput.coreAppeal || originalInput.core_appeal || '',
    style: extractField(contract, '风格基调') || originalInput.style || '',
    rough_outline: extractSection('粗略大纲') || originalInput.roughOutline || originalInput.rough_outline || originalInput.outline || '',
    world_setting: extractField(setting, '世界观') || originalInput.worldSetting || originalInput.world_setting || '',
    protagonist: extractField(setting, '主角人设') || originalInput.protagonist || '',
    golden_finger: extractField(setting, '金手指') || extractField(setting, '核心道具') || originalInput.goldenFinger || originalInput.golden_finger || '',
    hot_elements: extractSection('热点/潮流元素') || originalInput.hotElements || originalInput.hot_elements || '',
    expected_length: extractSection('预期字数') || originalInput.expectedLength || originalInput.expected_length || ''
  } as VisionDocument;
}
