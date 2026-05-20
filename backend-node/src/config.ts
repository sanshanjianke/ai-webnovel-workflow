// 配置管理
import * as fs from 'fs';
import * as path from 'path';
import * as yaml from 'js-yaml';
import { AppConfig } from './protocols';

const DEFAULT_CONFIG: AppConfig = {
  llm: {
    primary: 'openai_compat',
    model: 'GLM-5',
    apiKey: '',
    baseUrl: 'https://api.openai.com/v1'
  },
  embedding: {
    model: 'text-embedding-v3',
    apiKey: '',
    baseUrl: ''
  },
  generation: {
    temperature: 0.7,
    topP: 1.0,
    frequencyPenalty: 0,
    presencePenalty: 0,
    maxTokens: 16384,
    thinking: false,
    thinkingBudget: 10000,
    reasoningEffort: 'high'
  },
  rag: {
    history: 'hybrid_retriever',
    technique: 'simple_vector'
  },
  worldbook: {
    strategy: 'st_style',
    autoManage: true
  }
};

let _config: AppConfig | null = null;

export function getConfig(): AppConfig {
  if (!_config) {
    _config = loadConfig();
  }
  return _config;
}

export function loadConfig(configPath?: string): AppConfig {
  const filePath = configPath || path.join(__dirname, '../../data/user/config.yaml');
  
  if (fs.existsSync(filePath)) {
    const content = fs.readFileSync(filePath, 'utf-8');
    const data = yaml.load(content) as Record<string, unknown>;
    _config = mergeConfig(DEFAULT_CONFIG, data);
  } else {
    _config = { ...DEFAULT_CONFIG };
    saveConfig(_config, filePath);
  }
  
  return _config;
}

export function saveConfig(config: AppConfig, configPath?: string): void {
  const filePath = configPath || path.join(__dirname, '../../data/user/config.yaml');
  const dir = path.dirname(filePath);

  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }

  _config = config;
  const content = yaml.dump(config, { indent: 2 });
  fs.writeFileSync(filePath, content, 'utf-8');
}

function mergeConfig(defaults: AppConfig, overrides: Record<string, unknown>): AppConfig {
  const result = { ...defaults };
  
  if (overrides.llm && typeof overrides.llm === 'object') {
    const llm = overrides.llm as Record<string, unknown>;
    result.llm = {
      ...defaults.llm,
      apiKey: (llm.apiKey || llm.api_key || defaults.llm.apiKey) as string,
      baseUrl: (llm.baseUrl || llm.base_url || defaults.llm.baseUrl) as string,
      primary: (llm.primary || defaults.llm.primary) as string,
      model: (llm.model || defaults.llm.model) as string,
      headers: (llm.headers || defaults.llm.headers || undefined) as Record<string, string> | undefined
    };
  }
  if (overrides.embedding && typeof overrides.embedding === 'object') {
    const emb = overrides.embedding as Record<string, unknown>;
    result.embedding = {
      model: (emb.model || defaults.embedding.model) as string,
      apiKey: (emb.apiKey || emb.api_key || defaults.embedding.apiKey) as string,
      baseUrl: (emb.baseUrl || emb.base_url || defaults.embedding.baseUrl) as string,
    };
  }
  if (overrides.generation && typeof overrides.generation === 'object') {
    const gen = overrides.generation as Record<string, unknown>;
    result.generation = {
      temperature: (gen.temperature ?? defaults.generation.temperature) as number,
      topP: (gen.topP ?? gen.top_p ?? defaults.generation.topP) as number,
      frequencyPenalty: (gen.frequencyPenalty ?? gen.frequency_penalty ?? defaults.generation.frequencyPenalty) as number,
      presencePenalty: (gen.presencePenalty ?? gen.presence_penalty ?? defaults.generation.presencePenalty) as number,
      maxTokens: (gen.maxTokens ?? gen.max_tokens ?? defaults.generation.maxTokens) as number,
      thinking: (gen.thinking ?? defaults.generation.thinking) as boolean,
      thinkingBudget: (gen.thinkingBudget ?? gen.thinking_budget ?? defaults.generation.thinkingBudget) as number,
      reasoningEffort: (gen.reasoningEffort ?? gen.reasoning_effort ?? defaults.generation.reasoningEffort) as string
    };
  }
  if (overrides.rag && typeof overrides.rag === 'object') {
    result.rag = { ...defaults.rag, ...(overrides.rag as Record<string, unknown>) } as AppConfig['rag'];
  }
  if (overrides.worldbook && typeof overrides.worldbook === 'object') {
    result.worldbook = { ...defaults.worldbook, ...(overrides.worldbook as Record<string, unknown>) } as AppConfig['worldbook'];
  }
  if (overrides.llm_providers && typeof overrides.llm_providers === 'object') {
    result.llm_providers = { ...(overrides.llm_providers as Record<string, unknown>) } as AppConfig['llm_providers'];
  }
  if (overrides.embedding_providers && typeof overrides.embedding_providers === 'object') {
    result.embedding_providers = { ...(overrides.embedding_providers as Record<string, unknown>) } as AppConfig['embedding_providers'];
  }

  return result;
}
