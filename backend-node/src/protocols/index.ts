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
  reasoningEffort?: string;
  topP?: number;
  frequencyPenalty?: number;
  presencePenalty?: number;
}

// simple: GLM — thinking: { type: "enabled" }
// effort: DeepSeek — thinking: { type: "enabled" } + reasoning_effort at top level
export type ThinkingMode = 'none' | 'simple' | 'effort';

export interface GenerationParams {
  temperature: number;
  topP: number;
  frequencyPenalty: number;
  presencePenalty: number;
  maxTokens: number;
  thinking: boolean;
  thinkingBudget: number;
  reasoningEffort: string;
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
  nodeType?: string;
  interruptMode?: 'auto' | 'every_n_msgs' | 'every_n_tokens' | 'on_mention';
  interruptThreshold?: number;
  preprocessConfig?: PreprocessConfig;
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
  worldbook_bindings?: Record<string, string>;  // nodeId → bookId
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
  sourcePort?: string;
  targetPort?: string;
}

export interface OutputPort {
  name: string;
  label: string;
  color?: string;
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

// 选择性逻辑（参照 SillyTavern world_info_logic）
export enum SelectiveLogic {
  AND_ANY = 'AND_ANY',     // Primary OR secondary 任一命中
  NOT_ALL = 'NOT_ALL',     // Primary AND NOT ALL secondary
  NOT_ANY = 'NOT_ANY',     // Primary AND NOT ANY secondary
  AND_ALL = 'AND_ALL'      // Primary AND ALL secondary
}

// 注入位置（参照 SillyTavern world_info_position）
export enum WorldBookPosition {
  BEFORE_CHAR = 'before_char',
  AFTER_CHAR = 'after_char',
  AN_TOP = 'an_top',
  AN_BOTTOM = 'an_bottom',
  AT_DEPTH = 'at_depth',
  EM_TOP = 'em_top',
  EM_BOTTOM = 'em_bottom',
  OUTLET = 'outlet'
}

export interface WorldBookEntry {
  id: string;
  keys: string[];
  content: string;
  secondaryKeys?: string[];
  constant?: boolean;
  selective?: boolean;             // 启用选择性逻辑
  selectiveLogic?: SelectiveLogic; // 选择逻辑模式
  priority?: number;               // 排序权重
  position?: string;               // 注入位置（向前兼容，也可是 WorldBookPosition 枚举值）
  disable?: boolean;               // 禁用条目
  comment?: string;                // 标题/备注
  probability?: number;            // 触发概率 0-100
  depth?: number;                  // 搜索深度
  group?: string;                  // 同组名（互斥激活）
  groupWeight?: number;            // 组内权重
  sticky?: number;                 // 激活后保持 N 条消息
  cooldown?: number;               // 停用后冷却 N 条消息
  delay?: number;                  // 延迟 N 条消息后激活
  role?: string;                   // 注入角色 system/user/assistant
  scanDepth?: number;              // 逐条目搜索深度覆盖
  caseSensitive?: boolean;         // 大小写敏感
  matchWholeWords?: boolean;       // 全词匹配
  excludeRecursion?: boolean;      // 不可被递归激活
  preventRecursion?: boolean;      // 阻止递归从此条目开始
  delayUntilRecursion?: number;    // 延迟到第 N 层递归
  ignoreBudget?: boolean;          // 无视 token 预算
  metadata?: Record<string, unknown>;
}

export interface WorldBookInfo {
  bookId: string;       // 唯一标识
  name: string;         // 书名
  entryCount: number;   // 条目数
  createdAt: string;    // 创建时间
  updatedAt: string;    // 最后更新时间
}

export interface WorldBook {
  getActiveEntries(contextTokens: string[]): WorldBookEntry[];
  getEntry(entryId: string): WorldBookEntry | null;
  listAllEntries(): WorldBookEntry[];
  updateEntry(entryId: string, data: Partial<WorldBookEntry>): void;
  createEntry(entry: WorldBookEntry): void;
  deleteEntry(entryId: string): void;
  commit(message: string): string;
  listCommits(): CommitRecord[];
  getInfo(): WorldBookInfo;
}

export interface WorldBookCollection {
  listBooks(): WorldBookInfo[];
  createBook(name: string): WorldBookInfo;
  deleteBook(bookId: string): boolean;
  getBook(bookId: string): WorldBook | null;
  getDefaultBook(): WorldBook;
}

export interface CommitRecord {
  hash: string;
  message: string;
  timestamp: string;
  entryCount: number;
}

// ============ 世界书管理员 ============

export interface WorldBookSummaryConfig {
  enableWorldBookSummary: boolean;
  targetBookId: string;
  triggerGranularity: 'per_round' | 'per_node';
  summaryDepth: number;
  operationMode: 'auto' | 'semi_auto' | 'manual';
}

export interface WorldBookSummaryTask {
  taskId: string;
  nodeId: string;
  nodeType: 'expert' | 'group_chat';
  objectId: string;
  objectName: string;
  targetBookId: string;
  summaryConfig: WorldBookSummaryConfig;
  chatContent: string;
  existingEntries: WorldBookEntry[];
  triggeredBy: string;
  timestamp: string;
}

export interface WorldBookAction {
  actionId: string;
  action: 'create' | 'update' | 'merge' | 'skip';
  keys: string[];
  content: string;
  reason: string;
  targetEntryId?: string;
  mergeFromIds?: string[];
  priority?: number;
  group?: string;
  status: 'pending' | 'applied' | 'rejected' | 'modified';
  modifiedContent?: string;
  modifiedKeys?: string;
}

export interface WorldBookAnalysisResult {
  actions: WorldBookAction[];
  summary: string;
  confidence: number;
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

// ============ RAG 实例管理 ============

export type RAGRetrieverType = 'keyword' | 'hybrid' | 'vector';
export type RAGInstanceType = 'history' | 'technique' | 'custom';

export interface RAGInstanceConfig {
  instanceId: string;
  name: string;
  type: RAGInstanceType;
  retrieverType: RAGRetrieverType;
  description?: string;
  embeddingModel?: string;
  slicingDimensions?: string[];
  enhancementEnabled?: boolean;
  autoIndex?: boolean;
  maxResults?: number;
  maxInjectionTokens?: number;
  vectorWeight?: number;
  keywordWeight?: number;
  threshold?: number;
  createdAt: string;
  updatedAt: string;
}

export interface RAGInstanceInfo {
  instanceId: string;
  name: string;
  type: RAGInstanceType;
  retrieverType: RAGRetrieverType;
  documentCount: number;
  description?: string;
  createdAt: string;
  updatedAt: string;
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
    apiKey: string;
    baseUrl: string;
    headers?: Record<string, string>;
  };
  embedding: {
    model: string;
    apiKey: string;
    baseUrl: string;
  };
  generation: GenerationParams;
  rag: {
    history: string;
    technique: string;
  };
  worldbook: {
    strategy: string;
    autoManage: boolean;
  };
  llm_providers?: {
    custom: LLMProviderPreset[];
  };
  embedding_providers?: {
    custom: EmbeddingProviderPreset[];
  };
}

/** 解析实际使用的 embedding 配置，空值 fallback 到 LLM 配置 */
export function resolveEmbeddingConfig(config: AppConfig): { model: string; apiKey: string; baseUrl: string } {
  return {
    model: config.embedding.model || 'text-embedding-v3',
    apiKey: config.embedding.apiKey || config.llm.apiKey,
    baseUrl: config.embedding.baseUrl || config.llm.baseUrl,
  };
}

export interface LLMProviderPreset {
  id: string;
  name: string;
  baseUrl: string;
  models: string[];
  thinkingMode?: ThinkingMode;
  supports?: {
    frequencyPenalty?: boolean;
    presencePenalty?: boolean;
  };
  headers?: Record<string, string>;
}

export interface EmbeddingProviderPreset {
  id: string;
  name: string;
  baseUrl: string;
  models: string[];
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

// ============ 专家定义 (JSON-based) ============

export interface ExpertDefinition {
  expertId: string;
  expertType: string;
  icon: string;
  description: string;
  temperature: number;
  prompt_template: string;
  role_instructions: Record<string, string>;
  granularity_contexts: Record<string, string>;
  self_review_prompt: string;
  suggestion_patterns: string[];
  agent_defaults: AgentStopConfig;
  builtin: boolean;
}

// ============ Agent 中止条件 ============

export interface AgentStopConfig {
  enableStopSignal: boolean;
  blockEveryNRounds: number;    // 0 = disabled
  maxRounds: number;
  onMaxRounds: 'accept_last' | 'pick_best';
}

// ============ 管道对象 ============

export interface PipelineObject {
  id: string;
  name: string;
  files: PipelineObjectFile[];
  status: 'pending' | 'running' | 'completed' | 'failed';
  currentNodeId?: string;
  startedAt?: string;
  completedAt?: string;
  meta?: PipelineObjectMeta;
}

export interface PipelineObjectMeta {
  rejectCount: number;
  maxRejects: number;
  routePort?: string;
  [key: string]: any;  // allow extra fields like chunkIndex, totalChunks, outputMode
}

export interface PipelineObjectFile {
  path: string;
  content: string;
  producer: 'input' | string;
  category: 'input' | 'report' | 'chat_log';
}

// ============ 聊天记录 ============

export interface ExpertChatLog {
  expertId: string;
  expertType: string;
  objectId: string;
  reportFile: string;
  startedAt: string;
  completedAt: string | null;
  rounds: ExpertRound[];
}

export interface ExpertRound {
  round: number;
  messages: ExpertMessage[];
  selfScore?: number;
  completedAt?: string;
}

export interface ExpertMessage {
  role: 'system' | 'assistant' | 'user';
  content?: string;
  thinking?: string;
  timestamp: string;
}

// ============ Agent 上下文 ============

export interface AgentContext {
  vision?: Record<string, string>;
  worldbook?: string;
  rag?: string;
  customPrompt?: string;
  round: number;
  userFeedback?: string;
  chatLog?: ExpertChatLog;
  object?: PipelineObject;
  stopConfig: AgentStopConfig;
  readCategories: ('input' | 'report' | 'chat_log')[];
}

// ============ Agent 事件 ============

export interface AgentEvent {
  type: 'agent_round_start' | 'agent_chunk' | 'agent_round_complete' | 'agent_complete' | 'agent_waiting_user';
  data: Record<string, unknown>;
}

// ============ 用户反馈 ============

export interface UserFeedback {
  action: 'approve' | 'modify' | 'stop' | 'call_expert' | 'restart';
  message?: string;
  expertId?: string;
}

// ============ 预处理节点 ============

export interface TextSegment {
  content: string;
  meta: {
    index: number;
    title?: string;
    chapterNumber?: number;
    charCount: number;
    [key: string]: any;
  };
}

export type PreprocessStageType = 'replace' | 'split_regex' | 'split_token'
  | 'split_lines' | 'window_group' | 'custom';

export type PreprocessLanguage = 'javascript' | 'python' | 'perl';

export interface StageConfig {
  id: string;
  type: PreprocessStageType;
  enabled: boolean;
  label: string;
  language?: PreprocessLanguage;
  config: Record<string, any>;
  customCode?: string;
}

export interface PreprocessConfig {
  stages: StageConfig[];
  outputMode: 'expand' | 'pack';
}
