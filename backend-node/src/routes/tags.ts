import { Express, Request, Response } from 'express';
import * as fs from 'fs';
import * as path from 'path';

const TAGS_DIR = path.join(__dirname, '../../tags');

interface TagDefinition {
  tagId: string;
  category: string;
  genre: string[];
  效果标签: string;
  叙事指令: {
    视角: string;
    节奏: string;
    话语模式: string;
  };
  理由: string;
  关联网文概念: string[];
  适用专家: string[];
}

function loadAllTags(): TagDefinition[] {
  const tags: TagDefinition[] = [];
  if (!fs.existsSync(TAGS_DIR)) return tags;

  const categories = fs.readdirSync(TAGS_DIR, { withFileTypes: true })
    .filter(d => d.isDirectory())
    .map(d => d.name);

  for (const cat of categories) {
    const catDir = path.join(TAGS_DIR, cat);
    const files = fs.readdirSync(catDir).filter(f => f.endsWith('.json'));
    for (const file of files) {
      try {
        const raw = fs.readFileSync(path.join(catDir, file), 'utf-8');
        const items: TagDefinition[] = JSON.parse(raw);
        tags.push(...items);
      } catch (err) {
        console.error(`Failed to load tags from ${cat}/${file}:`, err);
      }
    }
  }
  return tags;
}

export function registerTagRoutes(app: Express): void {
  app.get('/api/tags', (_req: Request, res: Response) => {
    try {
      const tags = loadAllTags();
      const categories = [...new Set(tags.map(t => t.category))];
      const genres = [...new Set(tags.flatMap(t => t.genre || []))].sort();
      res.json({ tags, categories, genres });
    } catch (err) {
      console.error('GET /api/tags error:', err);
      res.status(500).json({ error: 'Failed to load tags' });
    }
  });
}
