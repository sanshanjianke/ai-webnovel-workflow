// 配置管理单元测试
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { loadConfig, saveConfig } from '../config';

describe('配置管理', () => {
  let tempDir: string;
  let configPath: string;

  beforeEach(() => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'config-test-'));
    configPath = path.join(tempDir, 'config.yaml');
  });

  afterEach(() => {
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it('应该加载默认配置', () => {
    const config = loadConfig(configPath);
    
    expect(config.llm.primary).toBe('openai_compat');
    expect(config.llm.baseUrl).toBe('https://api.openai.com/v1');
    expect(config.worldbook.strategy).toBe('st_style');
  });

  it('应该保存和加载配置', () => {
    const config = loadConfig(configPath);
    config.llm.apiKey = 'test-key';
    config.llm.model = 'test-model';
    
    saveConfig(config, configPath);
    
    const loaded = loadConfig(configPath);
    expect(loaded.llm.apiKey).toBe('test-key');
    expect(loaded.llm.model).toBe('test-model');
  });

  it('应该合并覆盖配置', () => {
    // 先创建一个部分配置
    fs.writeFileSync(configPath, `
llm:
  apiKey: "my-key"
  model: "custom-model"
`);
    
    const config = loadConfig(configPath);
    
    expect(config.llm.apiKey).toBe('my-key');
    expect(config.llm.model).toBe('custom-model');
    expect(config.llm.primary).toBe('openai_compat'); // 默认值
  });
});
