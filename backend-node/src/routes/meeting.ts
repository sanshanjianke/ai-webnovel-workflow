// 编排层路由 - 核心
import { Express, Request, Response } from 'express';
import { getProjectManager } from '../services/project-manager';
import { MeetingEngine, MeetingEvent } from '../services/meeting-engine';
import { PipelineEngine, PipelineEvent } from '../services/pipeline-engine';
import { 
  MeetingConfig, ExpertConfig, ContainerConfig, EdgeConfig,
  ExpertRole, Granularity, UserFeedback 
} from '../protocols';
import { SSEWriter } from '../utils/sse';
import { listExperts } from '../experts';

// 预设模板
const PRESET_CONFIGS: Record<string, Partial<MeetingConfig>> = {
  quick_review: {
    meetingName: '方案审核',
    experts: [
      { expertId: 'web_editor_v1', role: ExpertRole.MAIN }
    ]
  },
  volume_planning: {
    meetingName: '卷纲编排',
    experts: [
      { expertId: 'senior_author_v1', role: ExpertRole.MAIN },
      { expertId: 'reader_representative_v1', role: ExpertRole.REVIEW },
      { expertId: 'senior_author_v1', role: ExpertRole.SUPPLEMENT }
    ]
  },
  chapter_design: {
    meetingName: '章纲设计',
    experts: [
      { expertId: 'plot_architect_v1', role: ExpertRole.MAIN },
      { expertId: 'web_editor_v1', role: ExpertRole.REVIEW },
      { expertId: 'character_designer_v1', role: ExpertRole.SUPPLEMENT }
    ]
  }
};

// 存储运行中的会议
const activeMeetings = new Map<string, {
  engine: MeetingEngine | PipelineEngine;
  feedbackQueue: Array<(feedback: UserFeedback | null) => void>;
}>();

export function registerMeetingRoutes(app: Express): void {
  const pm = getProjectManager();

  // 获取预设模板
  app.get('/api/presets', (req: Request, res: Response) => {
    res.json({ presets: PRESET_CONFIGS });
  });

  // 获取专家列表
  app.get('/api/experts', (req: Request, res: Response) => {
    res.json({ experts: listExperts() });
  });

  // 启动会议（SSE 流式）
  app.post('/api/projects/:projectId/meeting/start', async (req: Request, res: Response) => {
    const project = pm.getProject(req.params.projectId);
    if (!project) {
      return res.status(404).json({ error: 'Project not found' });
    }

    const {
      meetingName = '专家会议',
      experts = [],
      containers = [],
      edges = [],
      pipeline = false,
      queueFiles = []
    } = req.body;

    // 构建会议配置
    const config: MeetingConfig = {
      meetingName,
      granularity: Granularity.CHAPTER,
      experts: (experts as Array<Record<string, unknown>>).map((e) => ({
        expertId: e.expertId as string,
        role: (e.role as ExpertRole) || ExpertRole.MAIN,
        customPrompt: e.customPrompt as string | undefined,
        containerId: e.containerId as string | undefined,
        nodeId: e.nodeId as string | undefined,
        interruptMode: (e.interruptMode as 'auto' | 'every_n_msgs' | 'every_n_tokens' | 'on_mention') || 'every_n_msgs',
        interruptThreshold: (e.interruptThreshold as number) || 1
      })),
      containers: (containers as Array<Record<string, unknown>>).map((c) => ({
        containerId: c.containerId as string,
        name: (c.name as string) || '容器',
        concurrency: (c.concurrency as 'serial' | 'parallel') || 'serial',
        speakingMode: (c.speakingMode as 'ordered' | 'mention_driven') || 'ordered',
        contextLayers: c.contextLayers as number | undefined,
        contextTokens: c.contextTokens as number | undefined,
        repeat: (c.repeat as number) || 1,
        interruptMode: c.interruptMode as string | undefined,
        interruptThreshold: (c.interruptThreshold as number) || 1,
        exitMode: (c.exitMode as 'manual' | 'consensus' | 'ratio' | 'gatekeeper') || 'manual',
        exitRatio: (c.exitRatio as number) || 0.6,
        exitGatekeeper: c.exitGatekeeper as string | undefined,
        exitMaxSpeeches: (c.exitMaxSpeeches as number) || 20,
        children: (c.children as string[]) || [],
        edges: (c.edges as EdgeConfig[]) || []
      })),
      edges: edges as EdgeConfig[],
      collaborationMode: 'semi_auto',
      maxRounds: 3,
      maxSpeeches: 0
    };

    // 设置 SSE
    const writer = new SSEWriter(res);
    const meetingId = `${req.params.projectId}_${Date.now()}`;

    // 读取世界书
    const worldbookPath = `${project.path}/worldbook.json`;
    let worldbookText = '';
    try {
      const fs = require('fs');
      if (fs.existsSync(worldbookPath)) {
        const wb = JSON.parse(fs.readFileSync(worldbookPath, 'utf-8'));
        const entries = wb.entries || {};
        worldbookText = Object.values(entries)
          .map((e) => {
            const entry = e as Record<string, unknown>;
            const keys = entry.keys as string[] | undefined;
            return `${keys?.[0] || ''}: ${entry.content || ''}`;
          })
          .join('\n');
      }
    } catch {}

    // 创建反馈队列
    const feedbackQueue: Array<(feedback: UserFeedback | null) => void> = [];
    activeMeetings.set(meetingId, {
      engine: null as any, // 稍后设置
      feedbackQueue
    });

    // 人类反馈函数
    const humanFeedback = (): Promise<UserFeedback | null> => {
      return new Promise((resolve) => {
        feedbackQueue.push(resolve);
        // 30秒超时
        setTimeout(() => resolve(null), 30000);
      });
    };

    try {
      if (pipeline && queueFiles.length > 0) {
        // 管道模式
        const pipelineEngine = new PipelineEngine(config);
        activeMeetings.get(meetingId)!.engine = pipelineEngine;

        const files = queueFiles.map((content: string, index: number) => ({
          index,
          content: { text: content }
        }));

        for await (const event of pipelineEngine.processQueue(
          files,
          {},  // 不再自动导入vision，由用户通过输入源导入
          worldbookText,
          ''
        )) {
          writer.write(event.type, event.data);
        }
      } else {
        // 会议模式
        const meetingEngine = new MeetingEngine(config);
        activeMeetings.get(meetingId)!.engine = meetingEngine;

        for await (const event of meetingEngine.run(
          {},  // 不再自动导入vision，由用户通过输入源导入
          worldbookText,
          '',
          humanFeedback
        )) {
          writer.write(event.type, event.data);
        }
      }
    } catch (error) {
      writer.write('error', { message: String(error) });
    } finally {
      activeMeetings.delete(meetingId);
      writer.close();
    }
  });

  // 通过预设启动会议
  app.get('/api/projects/:projectId/meeting/stream', async (req: Request, res: Response) => {
    const preset = req.query.preset as string;
    if (!preset || !PRESET_CONFIGS[preset]) {
      return res.status(400).json({ error: 'Invalid preset' });
    }

    // 重定向到 POST 端点
    const config = PRESET_CONFIGS[preset];
    req.body = {
      ...config,
      pipeline: false
    };

    // 调用 POST 处理逻辑
    app._router.handle(req, res, () => {});
  });

  // 发送用户反馈
  app.post('/api/projects/:projectId/meeting/feedback', (req: Request, res: Response) => {
    const { meetingId, action, message, expertId } = req.body;
    
    const meeting = activeMeetings.get(meetingId);
    if (!meeting) {
      return res.status(404).json({ error: 'Meeting not found' });
    }

    // 发送反馈到等待的会议
    const resolver = meeting.feedbackQueue.shift();
    if (resolver) {
      resolver({ action, message, expertId });
    }

    res.json({ status: 'sent' });
  });

  // 获取会议产出
  app.get('/api/projects/:projectId/meeting/output', (req: Request, res: Response) => {
    const project = pm.getProject(req.params.projectId);
    if (!project) {
      return res.status(404).json({ error: 'Project not found' });
    }

    const outputPath = `${project.path}/outputs/meeting_output.json`;
    const fs = require('fs');
    
    if (fs.existsSync(outputPath)) {
      const output = JSON.parse(fs.readFileSync(outputPath, 'utf-8'));
      res.json(output);
    } else {
      res.status(404).json({ error: 'Output not found' });
    }
  });

  // 保存会议产出
  app.put('/api/projects/:projectId/meeting/output', (req: Request, res: Response) => {
    const project = pm.getProject(req.params.projectId);
    if (!project) {
      return res.status(404).json({ error: 'Project not found' });
    }

    const fs = require('fs');
    const outputPath = `${project.path}/outputs/meeting_output.json`;
    fs.writeFileSync(outputPath, JSON.stringify(req.body, null, 2), 'utf-8');

    res.json({ status: 'saved' });
  });

  // 保存画布设计
  app.get('/api/projects/:projectId/meeting/design', (req: Request, res: Response) => {
    const project = pm.getProject(req.params.projectId);
    if (!project) {
      return res.status(404).json({ error: 'Project not found' });
    }

    const designPath = `${project.path}/outputs/canvas_design.json`;
    const fs = require('fs');
    
    if (fs.existsSync(designPath)) {
      const design = JSON.parse(fs.readFileSync(designPath, 'utf-8'));
      res.json(design);
    } else {
      res.json({ nodes: [], edges: [] });
    }
  });

  app.put('/api/projects/:projectId/meeting/design', (req: Request, res: Response) => {
    const project = pm.getProject(req.params.projectId);
    if (!project) {
      return res.status(404).json({ error: 'Project not found' });
    }

    const fs = require('fs');
    const designPath = `${project.path}/outputs/canvas_design.json`;
    fs.writeFileSync(designPath, JSON.stringify(req.body, null, 2), 'utf-8');

    res.json({ status: 'saved' });
  });
}
