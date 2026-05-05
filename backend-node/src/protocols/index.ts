// 核心协议定义 - 所有类型和接口

// ============ 枚举 ============

export enum ExpertRole {
  MAIN = 'main',
  REVIEW = 'review',
  SUPPLEMENT = 'supplement'
}

export enum Granularity {
  VOLUME = 'volume',
  CHAPTER = 'chapter',
  SCENE = 'scene'
}

export enum DocSource {
  GENERATE = 'generate',
  IMPORT = 'import',
  MANUAL = 'manual'
}

export enum DocStatus {
  ACTIVE = 'active',
  ARCHIVED = 'archived',
  DRAFT = 'draft'
}

// ============ LLM ============

export interface LLMProvider {
  invoke(prompt: string, options?: LLMOptions): Promise<string>;
  stream(prompt: string, options?: LLMOptions): AsyncGenerator<LLMChunk>;
}

export interface LLMOptions {
  temperature?: number;
  maxTokens?: number;
  model?: string;
  thinking?: boolean;
  thinkingBudget?: number;
}

export interface LLMChunk {
  type: 'content' | 'thinking';
  content: string;
}

// ============ 专家 ============

export interface ExpertOpinion {
  expertId: string;
  expertType: string;
  role: ExpertRole;
  content: string;
  suggestions: string[];
}

export interface ExpertConfig {
  expertId: string;
  role: ExpertRole;
  customPrompt?: string;
  containerId?: string;
  nodeId?: string;
  interruptMode?: 'auto' | 'every_n_msgs' | 'every_n_tokens' | 'on_mention';
  interruptThreshold?: number;
}

export interface Expert {
  expertId: string;
  expertType: string;
  speak(context: ExpertContext): Promise<ExpertOpinion>;
  speakStream(context: ExpertContext): AsyncGenerator<ExpertChunk>;
}

export interface ExpertContext {
  vision?: Record<string, string>;
  worldbook?: string;
  rag?: string;
  history?: ExpertOpinion[];
  containerContext?: string;
  userFeedback?: string;
  customPrompt?: string;
  round?: number;
  speechCount?: number;
}

export interface ExpertChunk {
  type: 'content' | 'thinking' | '__done__';
  content: string;
  opinion?: ExpertOpinion;
}

// ============ 会议 ============

export interface MeetingConfig {
  meetingName: string;
  granularity: Granularity;
  experts: ExpertConfig[];
  containers?: ContainerConfig[];
  edges?: EdgeConfig[];
  collaborationMode: 'semi_auto' | 'full_auto' | 'manual';
  maxRounds: number;
  maxSpeeches?: number;
}

export interface ContainerConfig {
  containerId: string;
  name?: string;
  concurrency?: 'serial' | 'parallel';
  speakingMode?: 'ordered' | 'mention_driven';
  contextLayers?: number;
  contextTokens?: number;
  repeat?: number;
  interruptMode?: string;
  interruptThreshold?: number;
  exitMode?: 'manual' | 'consensus' | 'ratio' | 'gatekeeper';
  exitRatio?: number;
  exitGatekeeper?: string;
  exitMaxSpeeches?: number;
  children?: string[];
  edges?: EdgeConfig[];
}

export interface EdgeConfig {
  source: string;
  target: string;
  type?: string;
}

export interface MeetingOutput {
  meetingName: string;
  granularity: string;
  sequences: Sequence[];
  characters: Character[];
  worldNotes: string[];
  meetingSummary: string;
  suggestions: string[];
  totalRounds: number;
  totalSpeeches: number;
}

export interface Sequence {
  name: string;
  functions?: string[];
  description?: string;
}

export interface Character {
  name: string;
  role?: string;
  traits?: string;
}

// ============ 世界书 ============

export interface WorldBookEntry {
  id: string;
  keys: string[];
  content: string;
  secondaryKeys?: string[];
  constant?: boolean;
  priority?: number;
  position?: string;
  metadata?: Record<string, unknown>;
}

export interface WorldBook {
  getActiveEntries(contextTokens: string[]): WorldBookEntry[];
  getEntry(entryId: string): WorldBookEntry | null;
  updateEntry(entryId: string, data: Partial<WorldBookEntry>): void;
  createEntry(entry: WorldBookEntry): void;
  deleteEntry(entryId: string): void;
  commit(message: string): string;
  listCommits(): CommitRecord[];
}

export interface CommitRecord {
  hash: string;
  message: string;
  timestamp: string;
  entryCount: number;
}

// ============ RAG ============

export interface RetrievedDoc {
  id: string;
  content: string;
  score: number;
  metadata?: Record<string, unknown>;
}

export interface RAGDocument {
  id: string;
  content: string;
  metadata?: Record<string, unknown>;
}

export interface RAGRetriever {
  retrieve(query: string, k?: number): Promise<RetrievedDoc[]>;
  index(documents: RAGDocument[]): Promise<void>;
  count(): Promise<number>;
}

// ============ 文档库 ============

export interface DocEntry {
  uid: string;
  name: string;
  layer: string;
  format?: string;
  source?: DocSource;
  parentUid?: string;
  directory?: string;
  tags?: string[];
  createdAt?: string;
  updatedAt?: string;
  wordCount?: number;
  status?: DocStatus;
  checkpoint?: Record<string, unknown>;
}

export interface LibraryManifest {
  projectId: string;
  directories: string[];
  documents: DocEntry[];
  activeDocs: Record<string, string>;
  updatedAt: string;
}

// ============ 项目 ============

export interface ProjectConfig {
  name: string;
  description?: string;
  genre?: string;
  targetPlatform?: string;
  drivingMode?: string;
  createdAt?: string;
  updatedAt?: string;
}

export interface Project {
  id: string;
  config: ProjectConfig;
  path: string;
}

// ============ 配置 ============

export interface AppConfig {
  llm: {
    primary: string;
    model?: string;
    embedding?: string;
    apiKey: string;
    baseUrl: string;
  };
  rag: {
    history: string;
    technique: string;
  };
  worldbook: {
    strategy: string;
    autoManage: boolean;
  };
  pipeline: {
    l15: PipelineStageConfig;
    l2: PipelineStageConfig;
    l3: { strategy: string };
    l4: { strategy: string };
  };
}

export interface PipelineStageConfig {
  meetingProtocol: string;
  collaborationMode: string;
  maxRounds: number;
  experts?: Record<string, string>;
}

// ============ L1 愿景文档 ============

export interface VisionDocument {
  core_idea: string;
  target_readers?: string;
  core_appeal?: string;
  style?: string;
  rough_outline?: string;
  world_setting?: string;
  protagonist?: string;
  golden_finger?: string;
  hot_elements?: string;
  expected_length?: string;
}

// ============ L3 章纲 ============

export interface ChapterPlan {
  chapterName: string;
  scenes: ScenePlan[];
  emotionCurve?: string;
  hooks?: string[];
}

export interface ScenePlan {
  name: string;
  perspective?: string;
  pace?: string;
  discourseMode?: string;
  wordCount?: number;
  contentPoints?: string[];
}

// ============ L4 正文 ============

export interface GeneratedText {
  chapterName: string;
  content: string;
  wordCount: number;
}

// ============ SSE 事件 ============

export interface SSEEvent {
  type: string;
  data: Record<string, unknown>;
}

// 会议模式事件
export interface RoundStartEvent {
  type: 'round_start';
  round: number;
  speechCount: number;
  maxSpeeches: number;
  meetingName: string;
}

export interface ExpertStartEvent {
  type: 'expert_start';
  expertId: string;
  expertType: string;
  role: string;
  round: number;
  speechCount: number;
  containerId?: string;
}

export interface ExpertSpeakEvent {
  type: 'expert_speak';
  expertId: string;
  expertType: string;
  role: string;
  content: string;
  suggestions: string[];
  speechCount: number;
  mention?: string;
  containerId?: string;
}

export interface ExpertChunkEvent {
  type: 'expert_chunk';
  chunkType: string;
  content: string;
  expertId: string;
  containerId?: string;
}

export interface WaitingUserEvent {
  type: 'waiting_user';
  speechCount: number;
}

export interface OutputReadyEvent {
  type: 'output_ready';
  output: MeetingOutput;
  speechCount: number;
  rounds: number;
  reason?: string;
}

// 管道模式事件
export interface PipelineStartEvent {
  type: 'pipeline_start';
  levels: number;
  nodes: string[];
}

export interface QueueStartEvent {
  type: 'queue_start';
  total: number;
}

export interface QueueItemStartEvent {
  type: 'queue_item_start';
  index: number;
  total: number;
}

export interface QueueItemCompleteEvent {
  type: 'queue_item_complete';
  index: number;
  total: number;
}

export interface QueueCompleteEvent {
  type: 'queue_complete';
  total: number;
}

export interface LevelStartEvent {
  type: 'level_start';
  level: number;
  totalLevels: number;
  nodes: string[];
  fileIndex: number;
}

export interface LevelCompleteEvent {
  type: 'level_complete';
  level: number;
  fileIndex: number;
}

export interface PipelineCompleteEvent {
  type: 'pipeline_complete';
  output: PipelineOutput;
}

export interface PipelineOutput {
  nodeOutputs: Record<string, string>;
  totalSpeeches: number;
  meetingSummary: string;
}

// ============ 用户反馈 ============

export interface UserFeedback {
  action: 'approve' | 'modify' | 'stop' | 'call_expert' | 'restart';
  message?: string;
  expertId?: string;
}
