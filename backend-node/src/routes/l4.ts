// L4 渲染层路由
import { Express, Request, Response } from 'express';
import * as fs from 'fs';
import * as path from 'path';
import { getProjectManager } from '../services/project-manager';
import { getLLM } from '../services/llm';
import { ChapterPlan, GeneratedText } from '../protocols';
import { SSEWriter } from '../utils/sse';

const L4_PROMPT = `你是L4渲染层，负责根据L3的细纲生成正文文本。

写作约束：
{constraints}

场景要求：
{scene_requirements}

请严格按照约束生成正文。注意：
1. 视角约束：{perspective}
2. 节奏：{pace}
3. 话语模式：{discourse_mode}
4. 目标字数：{word_count}字左右

写作禁忌：
- 不要翻译腔
- 不要过度修饰
- 不要说教
- 外聚焦时禁止心理描写

直接输出正文，不要输出任何其他内容。`;

export function registerL4Routes(app: Express): void {
  const pm = getProjectManager();

  // SSE 流式渲染
  app.get('/api/projects/:projectId/l4/stream', async (req: Request, res: Response) => {
    const project = pm.getProject(req.params.projectId);
    if (!project) {
      return res.status(404).json({ error: 'Project not found' });
    }

    // 读取章纲
    const planPath = path.join(project.path, 'outputs', 'l3_chapter_plan.json');
    if (!fs.existsSync(planPath)) {
      return res.status(404).json({ error: 'Chapter plan not found, please run L3 first' });
    }

    const chapterPlan: ChapterPlan = JSON.parse(fs.readFileSync(planPath, 'utf-8'));
    const writer = new SSEWriter(res);

    try {
      const llm = getLLM();

      writer.write('start', { chapterName: chapterPlan.chapterName });

      let fullText = '';

      for (let i = 0; i < chapterPlan.scenes.length; i++) {
        const scene = chapterPlan.scenes[i];

        writer.write('scene_start', {
          sceneIndex: i,
          sceneName: scene.name || `场景${i + 1}`
        });

        const constraints = buildConstraints(scene);
        const requirements = buildSceneRequirements(scene);

        const prompt = L4_PROMPT
          .replace('{constraints}', constraints)
          .replace('{scene_requirements}', requirements)
          .replace('{perspective}', scene.perspective || '外聚焦')
          .replace('{pace}', scene.pace || '等述')
          .replace('{discourse_mode}', scene.discourseMode || '对话+动作')
          .replace('{word_count}', String(scene.wordCount || 500));

        let sceneText = '';
        for await (const chunk of llm.stream(prompt)) {
          if (chunk.type === 'content') {
            sceneText += chunk.content;
            writer.write('text', { content: chunk.content });
          }
        }

        fullText += sceneText + '\n\n';

        writer.write('scene_complete', {
          sceneIndex: i,
          wordCount: sceneText.length
        });
      }

      const wordCount = fullText.replace(/\s/g, '').length;

      writer.write('done', {
        chapterName: chapterPlan.chapterName,
        content: fullText.trim(),
        wordCount
      });

      // 保存正文
      const textPath = path.join(project.path, 'outputs', 'l4_text.json');
      fs.writeFileSync(textPath, JSON.stringify({
        chapterName: chapterPlan.chapterName,
        content: fullText.trim(),
        wordCount
      }, null, 2), 'utf-8');

    } catch (error) {
      writer.write('error', { message: String(error) });
    } finally {
      writer.close();
    }
  });

  // 获取已生成的正文
  app.get('/api/projects/:projectId/l4/text', (req: Request, res: Response) => {
    const project = pm.getProject(req.params.projectId);
    if (!project) {
      return res.status(404).json({ error: 'Project not found' });
    }

    const textPath = path.join(project.path, 'outputs', 'l4_text.json');
    if (!fs.existsSync(textPath)) {
      return res.status(404).json({ error: 'Text not found' });
    }

    const text = JSON.parse(fs.readFileSync(textPath, 'utf-8'));
    res.json({ text });
  });
}

function buildConstraints(scene: { perspective?: string; pace?: string }): string {
  const constraints: string[] = [];

  const perspective = scene.perspective || '外聚焦';
  if (perspective.includes('内聚焦')) {
    constraints.push('使用内聚焦视角，只写该人物能看到/想到的内容');
  } else if (perspective.includes('外聚焦')) {
    constraints.push('使用外聚焦视角，只写可观察的动作/对话/环境，不写任何人物心理');
  } else if (perspective.includes('自由间接')) {
    constraints.push('使用自由间接引语，无引号，混合叙述者与人物声音');
  }

  const pace = scene.pace || '等述';
  if (pace.includes('扩述')) {
    constraints.push('慢速扩述：详细描写、感官展开、对话延伸');
  } else if (pace.includes('概述')) {
    constraints.push('快速概述：省略细节，快速推进');
  } else {
    constraints.push('中速等述：动作+简短描写，不过度展开');
  }

  return constraints.join('\n');
}

function buildSceneRequirements(scene: { name?: string; wordCount?: number; contentPoints?: string[] }): string {
  const requirements: string[] = [];
  requirements.push(`场景名称：${scene.name || '未命名场景'}`);
  requirements.push(`目标字数：${scene.wordCount || 500}字`);

  if (scene.contentPoints && scene.contentPoints.length > 0) {
    requirements.push('内容要点：');
    for (const point of scene.contentPoints) {
      requirements.push(`  - ${point}`);
    }
  }

  return requirements.join('\n');
}
