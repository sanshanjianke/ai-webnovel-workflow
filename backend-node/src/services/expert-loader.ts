import fs from 'fs';
import path from 'path';
import { ExpertDefinition } from '../protocols';

const builtinExpertsDir = path.resolve(__dirname, '../../experts');

class ExpertLoader {
  private builtinCache: Map<string, ExpertDefinition> | null = null;
  private customCache: Map<string, Map<string, ExpertDefinition>> = new Map();

  private loadDir(dir: string): Map<string, ExpertDefinition> {
    const map = new Map<string, ExpertDefinition>();
    if (!fs.existsSync(dir)) return map;

    const files = fs.readdirSync(dir).filter(f => f.endsWith('.json'));
    for (const file of files) {
      try {
        const content = fs.readFileSync(path.join(dir, file), 'utf-8');
        const def: ExpertDefinition = JSON.parse(content);
        if (def.expertId && def.expertType) {
          map.set(def.expertId, def);
        }
      } catch (e) {
        console.warn(`[ExpertLoader] Failed to load ${dir}/${file}:`, (e as Error).message);
      }
    }
    return map;
  }

  loadBuiltinExperts(): Map<string, ExpertDefinition> {
    if (this.builtinCache) return this.builtinCache;
    this.builtinCache = this.loadDir(builtinExpertsDir);
    console.log(`[ExpertLoader] Loaded ${this.builtinCache.size} built-in experts`);
    return this.builtinCache;
  }

  loadCustomExperts(projectPath: string): Map<string, ExpertDefinition> {
    if (!projectPath) return new Map();

    let cache = this.customCache.get(projectPath);
    if (cache) return cache;

    const dir = path.join(projectPath, 'user', 'custom_experts');
    cache = this.loadDir(dir);
    this.customCache.set(projectPath, cache);
    return cache;
  }

  reloadCustomExperts(projectPath: string): Map<string, ExpertDefinition> {
    this.customCache.delete(projectPath);
    return this.loadCustomExperts(projectPath);
  }

  getExpert(id: string, projectPath?: string): ExpertDefinition | null {
    const builtin = this.loadBuiltinExperts();
    if (builtin.has(id)) return builtin.get(id)!;

    if (projectPath) {
      const custom = this.loadCustomExperts(projectPath);
      if (custom.has(id)) return custom.get(id)!;
    }

    return null;
  }

  listExperts(projectPath?: string): Array<{ id: string; name: string; icon: string; description: string; builtin: boolean }> {
    const builtin = this.loadBuiltinExperts();
    const result: Array<{ id: string; name: string; icon: string; description: string; builtin: boolean }> = [];

    for (const [id, def] of builtin) {
      result.push({ id, name: def.expertType, icon: def.icon, description: def.description, builtin: true });
    }

    if (projectPath) {
      const custom = this.loadCustomExperts(projectPath);
      for (const [id, def] of custom) {
        result.push({ id, name: def.expertType, icon: def.icon, description: def.description, builtin: false });
      }
    }

    return result;
  }

  getCustomExpertsDir(projectPath: string): string {
    return path.join(projectPath, 'user', 'custom_experts');
  }

  saveCustomExpert(projectPath: string, definition: ExpertDefinition): void {
    const dir = this.getCustomExpertsDir(projectPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }

    const filePath = path.join(dir, `${definition.expertId}.json`);
    fs.writeFileSync(filePath, JSON.stringify(definition, null, 2), 'utf-8');

    this.customCache.delete(projectPath);
    console.log(`[ExpertLoader] Saved custom expert: ${definition.expertId}`);
  }

  deleteCustomExpert(projectPath: string, id: string): boolean {
    const dir = this.getCustomExpertsDir(projectPath);
    const filePath = path.join(dir, `${id}.json`);

    if (!fs.existsSync(filePath)) return false;

    fs.unlinkSync(filePath);
    this.customCache.delete(projectPath);
    console.log(`[ExpertLoader] Deleted custom expert: ${id}`);
    return true;
  }

  clearCache(): void {
    this.builtinCache = null;
    this.customCache.clear();
  }
}

export const expertLoader = new ExpertLoader();
