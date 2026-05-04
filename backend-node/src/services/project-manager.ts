// 项目管理服务
import * as fs from 'fs';
import * as path from 'path';
import { v4 as uuidv4 } from 'uuid';
import { ProjectConfig, Project } from '../protocols';

const DATA_DIR = path.join(__dirname, '../../data/projects');

export class ProjectManager {
  private dataPath: string;

  constructor(dataPath?: string) {
    this.dataPath = dataPath || DATA_DIR;
    if (!fs.existsSync(this.dataPath)) {
      fs.mkdirSync(this.dataPath, { recursive: true });
    }
  }

  createProject(name: string, options: Partial<ProjectConfig> = {}): Project {
    const projectId = uuidv4().slice(0, 8);
    const projectPath = path.join(this.dataPath, projectId);
    
    fs.mkdirSync(projectPath, { recursive: true });
    fs.mkdirSync(path.join(projectPath, 'outputs'), { recursive: true });
    fs.mkdirSync(path.join(projectPath, 'logs'), { recursive: true });
    fs.mkdirSync(path.join(projectPath, 'library'), { recursive: true });
    fs.mkdirSync(path.join(projectPath, 'library', 'files'), { recursive: true });

    const config: ProjectConfig = {
      name,
      description: options.description || '',
      genre: options.genre || '',
      targetPlatform: options.targetPlatform || '',
      drivingMode: options.drivingMode || 'plot_driven',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };

    const configPath = path.join(projectPath, 'project.json');
    fs.writeFileSync(configPath, JSON.stringify(config, null, 2), 'utf-8');

    // 初始化世界书
    const worldbookPath = path.join(projectPath, 'worldbook.json');
    fs.writeFileSync(worldbookPath, JSON.stringify({ entries: {} }, null, 2), 'utf-8');

    // 初始化文档库
    const manifestPath = path.join(projectPath, 'library', 'manifest.json');
    const manifest = {
      projectId,
      directories: ['/'],
      documents: [],
      activeDocs: {},
      updatedAt: new Date().toISOString()
    };
    fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2), 'utf-8');

    return { id: projectId, config, path: projectPath };
  }

  getProject(projectId: string): Project | null {
    const projectPath = path.join(this.dataPath, projectId);
    const configPath = path.join(projectPath, 'project.json');
    
    if (!fs.existsSync(configPath)) {
      return null;
    }

    const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
    return { id: projectId, config, path: projectPath };
  }

  listProjects(): Project[] {
    if (!fs.existsSync(this.dataPath)) {
      return [];
    }

    const projects: Project[] = [];
    const entries = fs.readdirSync(this.dataPath);

    for (const entry of entries) {
      const projectPath = path.join(this.dataPath, entry);
      const configPath = path.join(projectPath, 'project.json');
      
      if (fs.existsSync(configPath)) {
        try {
          const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
          projects.push({ id: entry, config, path: projectPath });
        } catch {
          // 忽略损坏的项目
        }
      }
    }

    return projects.sort((a, b) => 
      (b.config.updatedAt || '').localeCompare(a.config.updatedAt || '')
    );
  }

  updateProject(projectId: string, updates: Partial<ProjectConfig>): Project | null {
    const project = this.getProject(projectId);
    if (!project) return null;

    const updatedConfig = {
      ...project.config,
      ...updates,
      updatedAt: new Date().toISOString()
    };

    const configPath = path.join(project.path, 'project.json');
    fs.writeFileSync(configPath, JSON.stringify(updatedConfig, null, 2), 'utf-8');

    return { ...project, config: updatedConfig };
  }

  deleteProject(projectId: string): boolean {
    const projectPath = path.join(this.dataPath, projectId);
    
    if (!fs.existsSync(projectPath)) {
      return false;
    }

    fs.rmSync(projectPath, { recursive: true, force: true });
    return true;
  }
}

// 单例
let _instance: ProjectManager | null = null;

export function getProjectManager(): ProjectManager {
  if (!_instance) {
    _instance = new ProjectManager();
  }
  return _instance;
}
