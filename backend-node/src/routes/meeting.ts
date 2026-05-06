// 编排层路由 - 核心
import { Express, Request, Response } from 'express';
import { getProjectManager } from '../services/project-manager';
import { MeetingEngine, MeetingEvent } from '../services/meeting-engine';
import { PipelineEngine, PipelineEvent } from '../services/pipeline-engine';
import { ObjectPipelineEngine, PipelineEventV2 } from '../services/object-pipeline-engine';
import { createPipelineObject } from '../models/pipeline-object';
import { exportPipelineToZip } from '../services/zip-exporter';
import { loadCheckpoint, deleteCheckpoint, cleanIncompleteRound, restoreObjects } from '../services/recovery-manager';
import {
  MeetingConfig, ExpertConfig, ContainerConfig, EdgeConfig,
  ExpertRole, Granularity, UserFeedback, ExpertDefinition, AgentStopConfig
} from '../protocols';
import { SSEWriter } from '../utils/sse';
import { listExperts } from '../experts';
import { expertLoader } from '../services/expert-loader';

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
  engine: MeetingEngine | PipelineEngine | ObjectPipelineEngine;
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
    const projectId = req.query.projectId as string || '';
    const project = projectId ? pm.getProject(projectId) : null;
    const projectPath = project?.path || '';

    const builtinExperts: Record<string, { label: string; icon: string; desc: string }> = {};
    const customExpertsData: Record<string, { id: string; label: string; icon: string; desc: string; prompt: string }> = {};

    const allExperts = expertLoader.listExperts(projectPath);
    for (const expert of allExperts) {
      const def = expertLoader.getExpert(expert.id, projectPath);
      if (expert.builtin) {
        builtinExperts[expert.id] = { label: expert.name, icon: expert.icon, desc: expert.description };
      } else {
        customExpertsData[expert.id] = {
          id: expert.id, label: expert.name, icon: expert.icon,
          desc: expert.description,
          prompt: def?.prompt_template || ''
        };
      }
    }

    res.json({
      experts: allExperts.filter(e => e.builtin).map(e => e.id),
      builtin_experts: builtinExperts,
      custom_experts: customExpertsData
    });
  });

  // 自定义专家 CRUD
  app.post('/api/experts/custom', (req: Request, res: Response) => {
    try {
      const { id, name, icon, description, prompt_template } = req.body;
      if (!id || !name) {
        return res.status(400).json({ error: 'id and name are required' });
      }

      const projectId = req.query.projectId as string || '';
      const project = projectId ? pm.getProject(projectId) : null;
      const projectPath = project?.path || '';

      const definition: ExpertDefinition = {
        expertId: id,
        expertType: name,
        icon: icon || '📄',
        description: description || '',
        temperature: 0.7,
        prompt_template: prompt_template || '',
        role_instructions: {},
        granularity_contexts: {},
        self_review_prompt: '请审视并修正你的意见。定稿时请包裹在<报告>...</报告>中。',
        suggestion_patterns: [],
        agent_defaults: {
          enableTagStop: true,
          blockEveryNRounds: 0,
          maxRounds: 3,
          onMaxRounds: 'accept_last'
        },
        builtin: false
      };

      expertLoader.saveCustomExpert(projectPath, definition);
      res.json({ status: 'created', id });
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  app.delete('/api/experts/custom/:id', (req: Request, res: Response) => {
    try {
      const projectId = req.query.projectId as string || '';
      const project = projectId ? pm.getProject(projectId) : null;
      const projectPath = project?.path || '';

      const success = expertLoader.deleteCustomExpert(projectPath, req.params.id);
      if (success) {
        res.json({ status: 'deleted' });
      } else {
        res.status(404).json({ error: 'Expert not found' });
      }
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  app.get('/api/experts/:id/prompt', (req: Request, res: Response) => {
    const projectId = req.query.projectId as string || '';
    const project = projectId ? pm.getProject(projectId) : null;
    const projectPath = project?.path || '';

    const def = expertLoader.getExpert(req.params.id, projectPath);
    if (!def) {
      return res.status(404).json({ error: 'Expert not found' });
    }
    res.json({ prompt_template: def.prompt_template });
  });

  // 启动会议（SSE 流式）
  app.post('/api/projects/:projectId/meeting/start', async (req: Request, res: Response) => {
    const project = pm.getProject(req.params.projectId);
    if (!project) {
      return res.status(404).json({ error: 'Project not found' });
    }

    const {
      meetingName = '专家会议',
      meeting_name: meetingNameAlt,
      experts = [],
      containers = [],
      edges = [],
      pipeline = false,
      pipeline_version: pipelineVersion = 1,
      queueFiles = [],
      queue_files: queueFilesAlt = [],
      agent_configs: agentConfigs = {}
    } = req.body;

    // 支持两种字段名
    const finalMeetingName = meetingName || meetingNameAlt || '专家会议';
    const finalQueueFiles = queueFiles.length > 0 ? queueFiles : queueFilesAlt;

    // 构建会议配置
    const config: MeetingConfig = {
      meetingName: finalMeetingName,
      granularity: Granularity.CHAPTER,
      experts: (experts as Array<Record<string, unknown>>).map((e) => ({
        expertId: (e.expertId || e.expert_id) as string,
        role: (e.role as ExpertRole) || ExpertRole.MAIN,
        customPrompt: (e.customPrompt || e.custom_prompt) as string | undefined,
        containerId: (e.containerId || e.container_id) as string | undefined,
        nodeId: (e.nodeId || e.node_id) as string | undefined,
        interruptMode: (e.interruptMode || e.interrupt_mode || 'every_n_msgs') as 'auto' | 'every_n_msgs' | 'every_n_tokens' | 'on_mention',
        interruptThreshold: (e.interruptThreshold || e.interrupt_threshold || 1) as number
      })),
      containers: (containers as Array<Record<string, unknown>>).map((c) => ({
        containerId: (c.containerId || c.container_id) as string,
        name: (c.name as string) || '容器',
        concurrency: (c.concurrency as 'serial' | 'parallel') || 'serial',
        speakingMode: (c.speakingMode || c.speaking_mode || 'ordered') as 'ordered' | 'mention_driven',
        contextLayers: (c.contextLayers || c.context_layers) as number | undefined,
        contextTokens: (c.contextTokens || c.context_tokens) as number | undefined,
        repeat: (c.repeat as number) || 1,
        interruptMode: (c.interruptMode || c.interrupt_mode) as string | undefined,
        interruptThreshold: (c.interruptThreshold || c.interrupt_threshold || 1) as number,
        exitMode: (c.exitMode || c.exit_mode || 'manual') as 'manual' | 'consensus' | 'ratio' | 'gatekeeper',
        exitRatio: (c.exitRatio || c.exit_ratio || 0.6) as number,
        exitGatekeeper: (c.exitGatekeeper || c.exit_gatekeeper) as string | undefined,
        exitMaxSpeeches: (c.exitMaxSpeeches || c.exit_max_speeches || 20) as number,
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

    // 清除专家缓存，确保模板修改后无需重启服务器
    expertLoader.clearCache();

    try {
      if (pipeline && finalQueueFiles.length === 0) {
        writer.write('error', { message: '管道模式需要输入源文件，请先添加输入源' });
        writer.close();
        activeMeetings.delete(meetingId);
        return;
      }

      if (pipeline && pipelineVersion === 2 && finalQueueFiles.length > 0) {
        // 管道模式 v2 — ObjectPipelineEngine
        const engine = new ObjectPipelineEngine(config);
        engine.meetingId = meetingId;
        engine.checkpointDir = `${project.path}/outputs`;
        activeMeetings.get(meetingId)!.engine = engine;

        // Apply per-node agent configs and read configs
        const ac = agentConfigs as Record<string, Record<string, unknown>>;
        for (const [nodeId, cfg] of Object.entries(ac)) {
          if (cfg.stopConfig) {
            engine.setAgentConfig(nodeId, cfg.stopConfig as AgentStopConfig);
          }
          if (cfg.readCategories) {
            engine.setReadConfig(nodeId, cfg.readCategories as ('input' | 'report' | 'chat_log')[]);
          }
        }

        // Create pipeline objects from queue files
        const objects = finalQueueFiles.map((content: string, index: number) =>
          createPipelineObject(`对象${index + 1}`, [{ path: `input_${index + 1}.txt`, content }])
        );

        for await (const event of engine.processQueue(
          objects,
          {},
          worldbookText,
          ''
        )) {
          writer.write(event.type, event.data);
        }

        // 持久化管道产出供后续导出
        try {
          const fs = require('fs');
          const outputDir = `${project.path}/outputs`;
          if (!fs.existsSync(outputDir)) {
            fs.mkdirSync(outputDir, { recursive: true });
          }
          const outPath = `${outputDir}/pipeline_${meetingId}.json`;
          fs.writeFileSync(outPath, JSON.stringify(objects.map((o: any) => ({
            id: o.id, name: o.name, status: o.status,
            files: o.files.map((f: any) => ({ path: f.path, content: f.content, category: f.category, producer: f.producer }))
          })), null, 2), 'utf-8');
        } catch {}
      } else if (pipeline && finalQueueFiles.length > 0) {
        // 管道模式 v1 — PipelineEngine
        const pipelineEngine = new PipelineEngine(config);
        activeMeetings.get(meetingId)!.engine = pipelineEngine;

        const files = finalQueueFiles.map((content: string, index: number) => ({
          index,
          content: { text: content }
        }));

        for await (const event of pipelineEngine.processQueue(
          files,
          {},
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
          {},
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
    const projectId = req.params.projectId;
    
    // 尝试通过meetingId查找，如果没有则通过projectId查找
    let meeting = meetingId ? activeMeetings.get(meetingId) : null;
    if (!meeting) {
      // 通过projectId查找活跃的会议
      for (const [id, m] of activeMeetings.entries()) {
        if (id.startsWith(projectId + '_')) {
          meeting = m;
          break;
        }
      }
    }
    
    if (!meeting) {
      return res.status(404).json({ error: 'Meeting not found' });
    }

    // 对于 ObjectPipelineEngine (v2)，直接注入反馈
    if (meeting.engine instanceof ObjectPipelineEngine) {
      if (action === 'stop') {
        meeting.engine.stop();
      } else if (action === 'accept') {
        meeting.engine.stop();
      } else if (message && expertId) {
        meeting.engine.injectFeedback(expertId, message);
      }
      return res.json({ status: 'sent' });
    }

    // 发送反馈到等待的会议 (v1)
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

  // 导出管道产出为 ZIP
  app.get('/api/projects/:projectId/meeting/export/:sessionId', async (req: Request, res: Response) => {
    const project = pm.getProject(req.params.projectId);
    if (!project) {
      return res.status(404).json({ error: 'Project not found' });
    }

    try {
      const fs = require('fs');
      const outputPath = `${project.path}/outputs/pipeline_${req.params.sessionId}.json`;

      if (!fs.existsSync(outputPath)) {
        // 尝试模糊匹配
        const outputDir = `${project.path}/outputs`;
        const files = fs.existsSync(outputDir) ? fs.readdirSync(outputDir) : [];
        const match = files.find((f: string) =>
          f.startsWith(`pipeline_${req.params.projectId}_`) || f.endsWith(`_${req.params.sessionId}.json`)
        );
        if (match) {
          const objects = JSON.parse(fs.readFileSync(`${outputDir}/${match}`, 'utf-8'));
          const { buffer, filename } = await exportPipelineToZip(objects);
          res.setHeader('Content-Type', 'application/zip');
          res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
          return res.send(buffer);
        }
        return res.status(404).json({ error: 'Export data not found' });
      }

      const objects = JSON.parse(fs.readFileSync(outputPath, 'utf-8'));
      const { buffer, filename } = await exportPipelineToZip(objects);
      res.setHeader('Content-Type', 'application/zip');
      res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
      res.send(buffer);
    } catch (error) {
      res.status(500).json({ error: String(error) });
    }
  });

  // 恢复中断的管道
  app.post('/api/projects/:projectId/meeting/resume', async (req: Request, res: Response) => {
    const project = pm.getProject(req.params.projectId);
    if (!project) {
      return res.status(404).json({ error: 'Project not found' });
    }

    const { sessionId, agent_configs: agentConfigs = {} } = req.body;
    if (!sessionId) {
      return res.status(400).json({ error: 'sessionId is required' });
    }

    const checkpointDir = `${project.path}/outputs`;
    const checkpoint = loadCheckpoint(checkpointDir, sessionId);
    if (!checkpoint) {
      return res.status(404).json({ error: 'Checkpoint not found' });
    }

    // Clean incomplete rounds from all objects' chat logs
    for (const sobj of checkpoint.objects) {
      for (const f of sobj.files) {
        if (f.category === 'chat_log' && f.content) {
          try {
            const chatLog = JSON.parse(f.content);
            if (cleanIncompleteRound(chatLog)) {
              f.content = JSON.stringify(chatLog);
            }
          } catch {}
        }
      }
    }

    // Restore objects
    const objects = restoreObjects(checkpoint.objects);

    // Create engine from saved config
    const engine = new ObjectPipelineEngine(checkpoint.config);
    engine.meetingId = checkpoint.state.meetingId;
    engine.checkpointDir = checkpointDir;

    // Apply per-node agent configs
    const ac = agentConfigs as Record<string, Record<string, unknown>>;
    for (const [nodeId, cfg] of Object.entries(ac)) {
      if (cfg.stopConfig) {
        engine.setAgentConfig(nodeId, cfg.stopConfig as AgentStopConfig);
      }
      if (cfg.readCategories) {
        engine.setReadConfig(nodeId, cfg.readCategories as ('input' | 'report' | 'chat_log')[]);
      }
    }

    // Register for feedback
    const newMeetingId = checkpoint.state.meetingId;
    const feedbackQueue: Array<(feedback: UserFeedback | null) => void> = [];
    activeMeetings.set(newMeetingId, {
      engine: engine,
      feedbackQueue
    });

    // Set SSE
    const writer = new SSEWriter(res);

    // Read worldbook
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

    try {
      for await (const event of engine.processQueue(
        objects,
        {},
        worldbookText,
        '',
        checkpoint.state
      )) {
        writer.write(event.type, event.data);
      }
    } catch (error) {
      writer.write('error', { message: String(error) });
    } finally {
      activeMeetings.delete(newMeetingId);
      writer.close();
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
