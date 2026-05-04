// 项目管理服务单元测试
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { ProjectManager } from '../services/project-manager';

describe('ProjectManager', () => {
  let tempDir: string;
  let pm: ProjectManager;

  beforeEach(() => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'project-test-'));
    pm = new ProjectManager(tempDir);
  });

  afterEach(() => {
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it('应该创建项目', () => {
    const project = pm.createProject('测试项目', {
      genre: '玄幻',
      targetPlatform: '起点'
    });
    
    expect(project.id).toBeDefined();
    expect(project.config.name).toBe('测试项目');
    expect(project.config.genre).toBe('玄幻');
    expect(project.config.targetPlatform).toBe('起点');
    
    // 检查目录结构
    expect(fs.existsSync(project.path)).toBe(true);
    expect(fs.existsSync(path.join(project.path, 'project.json'))).toBe(true);
    expect(fs.existsSync(path.join(project.path, 'worldbook.json'))).toBe(true);
    expect(fs.existsSync(path.join(project.path, 'outputs'))).toBe(true);
    expect(fs.existsSync(path.join(project.path, 'library'))).toBe(true);
  });

  it('应该获取项目', () => {
    const created = pm.createProject('测试项目');
    const project = pm.getProject(created.id);
    
    expect(project).not.toBeNull();
    expect(project!.id).toBe(created.id);
    expect(project!.config.name).toBe('测试项目');
  });

  it('应该列出项目', () => {
    pm.createProject('项目1');
    pm.createProject('项目2');
    pm.createProject('项目3');
    
    const projects = pm.listProjects();
    expect(projects.length).toBe(3);
  });

  it('应该更新项目', () => {
    const project = pm.createProject('原名称');
    const updated = pm.updateProject(project.id, { name: '新名称' });
    
    expect(updated).not.toBeNull();
    expect(updated!.config.name).toBe('新名称');
    
    // 验证持久化
    const loaded = pm.getProject(project.id);
    expect(loaded!.config.name).toBe('新名称');
  });

  it('应该删除项目', () => {
    const project = pm.createProject('要删除的项目');
    expect(pm.getProject(project.id)).not.toBeNull();
    
    const success = pm.deleteProject(project.id);
    expect(success).toBe(true);
    expect(pm.getProject(project.id)).toBeNull();
  });

  it('不存在的项目应该返回 null', () => {
    expect(pm.getProject('nonexistent')).toBeNull();
  });

  it('删除不存在的项目应该返回 false', () => {
    expect(pm.deleteProject('nonexistent')).toBe(false);
  });
});
