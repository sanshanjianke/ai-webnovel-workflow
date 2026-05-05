// 配置管理
import * as fs from 'fs';
import * as path from 'path';
import * as yaml from 'js-yaml';
import { AppConfig } from './protocols';

const DEFAULT_CONFIG: AppConfig = {
  llm: {
    primary: 'openai_compat',
    model: 'GLM-5',
    embedding: 'text-embedding-v3',
    apiKey: '',
    baseUrl: 'https://api.openai.com/v1'
  },
  rag: {
    history: 'hybrid_retriever',
    technique: 'simple_vector'
  },
  worldbook: {
    strategy: 'st_style',
    autoManage: true
  },
  pipeline: {
    l15: {
      meetingProtocol: 'editor_reader',
      collaborationMode: 'semi_auto',
      maxRounds: 3,
      experts: {
        author: 'senior_author_v1',
        reader: 'reader_representative_v1'
      }
    },
    l2: {
      meetingProtocol: 'plot_driven',
      collaborationMode: 'semi_auto',
      maxRounds: 3,
      experts: {
        architect: 'plot_architect_v1',
        editor: 'web_editor_v1',
        character: 'character_designer_v1'
      }
    },
    l3: { strategy: 'mapping_compiler' },
    l4: { strategy: 'constrained_renderer' }
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
      embedding: (llm.embedding || defaults.llm.embedding) as string
    };
  }
  if (overrides.rag && typeof overrides.rag === 'object') {
    result.rag = { ...defaults.rag, ...(overrides.rag as Record<string, unknown>) } as AppConfig['rag'];
  }
  if (overrides.worldbook && typeof overrides.worldbook === 'object') {
    result.worldbook = { ...defaults.worldbook, ...(overrides.worldbook as Record<string, unknown>) } as AppConfig['worldbook'];
  }
  if (overrides.pipeline && typeof overrides.pipeline === 'object') {
    result.pipeline = { ...defaults.pipeline, ...(overrides.pipeline as Record<string, unknown>) } as AppConfig['pipeline'];
  }
  
  return result;
}
