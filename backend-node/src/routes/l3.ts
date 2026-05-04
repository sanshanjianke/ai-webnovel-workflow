// L3 叙事层路由
import { Express, Request, Response } from 'express';
import * as fs from 'fs';
import * as path from 'path';
import { getProjectManager } from '../services/project-manager';
import { getLLM } from '../services/llm';
import { ChapterPlan, ScenePlan } from '../protocols';

const L3_PROMPT = `你是L3叙事层，负责将L2的大纲"翻译"为可直接执行的章纲/细纲。

映射规则：

### 情绪 → 视角映射
| 情绪 | 推荐视角 | 理由 |
|------|----------|------|
| 压抑（被嘲讽/轻视） | 反派/路人内聚焦 | 让读者感受傲慢，制造信息差 |
| 爆发（打脸/反转） | 外聚焦 | 客观呈现，不带感情更装逼 |
| 余韵（震惊/膜拜） | 自由间接引语 | 直接展示心理崩溃 |

### 情绪 → 节奏映射
| 情绪 | 推荐节奏 | 实现方式 |
|------|----------|----------|
| 压抑 | 慢速扩述 | 详细描写、大量对话、心理活动 |
| 爆发 | 中速等述 | 动作+环境，篇幅适中 |
| 余韵 | 快速概述 | 简短带过、留白 |

### 场景 → 话语模式映射
| 场景类型 | 推荐模式 | 说明 |
|----------|----------|------|
| 对峙/冲突 | 大量对话+动作 | 推进剧情 |
| 心理活动 | 自由间接引语 | 深入人物内心 |
| 环境烘托 | 环境描写+感官 | 渲染氛围 |
| 战斗爆发 | 短句+动词密集 | 加快节奏 |

输入大纲：
{outline}

请生成章纲/细纲，输出格式：

# 章纲/细纲

## 第X章：[章节名]

### 场景1：[场景名]
- 视角：[具体视角]
- 节奏：[扩述/等述/概述]
- 话语模式：[对话/动作/心理/环境]
- 字数：[预估]
- 内容要点：
  - [...]
  - [...]

### 场景2：[场景名]
...

## 章节情绪曲线
[描述本章的情绪走向]

## 伏笔/钩子
- [本章埋的伏笔]
- [结尾的悬念钩子]`;

export function registerL3Routes(app: Express): void {
  const pm = getProjectManager();

  // 生成章纲
  app.post('/api/projects/:projectId/l3/generate', async (req: Request, res: Response) => {
    const project = pm.getProject(req.params.projectId);
    if (!project) {
      return res.status(404).json({ error: 'Project not found' });
    }

    // 读取 L2 大纲
    const outlinePath = path.join(project.path, 'outputs', 'l2_outline.json');
    if (!fs.existsSync(outlinePath)) {
      return res.status(404).json({ error: 'Outline not found, please run L2 first' });
    }

    const outline = JSON.parse(fs.readFileSync(outlinePath, 'utf-8'));

    try {
      const llm = getLLM();
      
      // 格式化大纲
      const outlineText = formatOutline(outline);
      const prompt = L3_PROMPT.replace('{outline}', outlineText);

      const response = await llm.invoke(prompt);
      const chapterPlan = parseChapterPlan(response);

      // 保存
      const planPath = path.join(project.path, 'outputs', 'l3_chapter_plan.json');
      fs.mkdirSync(path.dirname(planPath), { recursive: true });
      fs.writeFileSync(planPath, JSON.stringify(chapterPlan, null, 2), 'utf-8');

      res.json({ status: 'generated', plan: chapterPlan });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // 获取章纲
  app.get('/api/projects/:projectId/l3/plan', (req: Request, res: Response) => {
    const project = pm.getProject(req.params.projectId);
    if (!project) {
      return res.status(404).json({ error: 'Project not found' });
    }

    const planPath = path.join(project.path, 'outputs', 'l3_chapter_plan.json');
    if (!fs.existsSync(planPath)) {
      return res.status(404).json({ error: 'Plan not found' });
    }

    const plan = JSON.parse(fs.readFileSync(planPath, 'utf-8'));
    res.json({ plan });
  });

  // 更新章纲
  app.put('/api/projects/:projectId/l3/plan', (req: Request, res: Response) => {
    const project = pm.getProject(req.params.projectId);
    if (!project) {
      return res.status(404).json({ error: 'Project not found' });
    }

    const planPath = path.join(project.path, 'outputs', 'l3_chapter_plan.json');
    fs.mkdirSync(path.dirname(planPath), { recursive: true });
    fs.writeFileSync(planPath, JSON.stringify(req.body, null, 2), 'utf-8');

    res.json({ status: 'updated' });
  });

  // 获取标签库
  app.get('/api/projects/:projectId/l3/tags', (req: Request, res: Response) => {
    // 空桩
    res.json({ tags: [] });
  });
}

function formatOutline(outline: Record<string, unknown>): string {
  const parts: string[] = [];

  if (outline.sequences && Array.isArray(outline.sequences)) {
    parts.push('序列：');
    for (const seq of outline.sequences) {
      parts.push(`- ${seq.name || '未命名序列'}`);
    }
  }

  if (outline.characters && Array.isArray(outline.characters)) {
    parts.push('\n人物：');
    for (const char of outline.characters) {
      parts.push(`- ${char.name || '未命名'}: ${char.role || ''} ${char.traits || ''}`);
    }
  }

  if (outline.world_notes && Array.isArray(outline.world_notes)) {
    parts.push('\n世界观备注：');
    for (const note of outline.world_notes) {
      parts.push(`- ${note}`);
    }
  }

  return parts.join('\n');
}

function parseChapterPlan(response: string): ChapterPlan {
  const chapterMatch = response.match(/##\s*第.+章[：:]\s*(.+)/);
  const chapterName = chapterMatch ? chapterMatch[1].trim() : '未命名章节';

  const scenes: ScenePlan[] = [];
  const scenePattern = /###\s*场景\d+[：:]\s*(.+?)(?=###|##|$)/gs;
  let sceneMatch;

  while ((sceneMatch = scenePattern.exec(response)) !== null) {
    const sceneContent = sceneMatch[1];
    const scene: ScenePlan = {
      name: sceneContent.split('\n')[0].trim()
    };

    const perspectiveMatch = sceneContent.match(/视角[：:]\s*(.+)/);
    if (perspectiveMatch) scene.perspective = perspectiveMatch[1].trim();

    const paceMatch = sceneContent.match(/节奏[：:]\s*(.+)/);
    if (paceMatch) scene.pace = paceMatch[1].trim();

    const modeMatch = sceneContent.match(/话语模式[：:]\s*(.+)/);
    if (modeMatch) scene.discourseMode = modeMatch[1].trim();

    const wordcountMatch = sceneContent.match(/字数[：:]\s*(\d+)/);
    if (wordcountMatch) scene.wordCount = parseInt(wordcountMatch[1]);

    scenes.push(scene);
  }

  const emotionMatch = response.match(/##\s*章节情绪曲线\s*(.+?)(?=##|$)/s);
  const emotionCurve = emotionMatch ? emotionMatch[1].trim() : '';

  const hooks: string[] = [];
  const hookMatch = response.match(/##\s*伏笔\/钩子\s*(.+?)(?=##|$)/s);
  if (hookMatch) {
    const hookContent = hookMatch[1];
    const lines = hookContent.split('\n');
    for (const line of lines) {
      if (line.trim().startsWith('-')) {
        hooks.push(line.trim().slice(2));
      }
    }
  }

  return {
    chapterName,
    scenes,
    emotionCurve,
    hooks
  };
}
