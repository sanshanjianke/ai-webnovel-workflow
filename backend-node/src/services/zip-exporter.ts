import JSZip from 'jszip';
import { PipelineObject } from '../protocols';

export interface ExportStats {
  totalObjects: number;
  totalFiles: number;
  totalChatLogs: number;
  totalReports: number;
  exportedAt: string;
  projectId?: string;
  pipelineVersion: number;
}

/**
 * 将管道产出打包为 ZIP。结构：
 *   config.cfg
 *   对象1/
 *     01_初始文件名.md
 *     02_专家名_report.md
 *     02_专家名_chatlog.json
 *     ...
 *   对象2/
 *     ...
 */
export async function exportPipelineToZip(
  objects: PipelineObject[],
  pipelineConfig?: Record<string, unknown>,
  stats?: ExportStats
): Promise<{ buffer: Buffer; filename: string }> {
  const zip = new JSZip();

  // config.cfg
  const configData = {
    software: 'AI网文创作系统',
    exportTime: new Date().toISOString(),
    pipeline: pipelineConfig || {},
    objects: objects.map(o => ({ id: o.id, name: o.name, status: o.status })),
    statistics: stats || {
      totalObjects: objects.length,
      totalFiles: objects.reduce((s, o) => s + o.files.length, 0),
      totalReports: objects.reduce((s, o) => s + o.files.filter(f => f.category === 'report').length, 0),
      totalChatLogs: objects.reduce((s, o) => s + o.files.filter(f => f.category === 'chat_log').length, 0),
      exportedAt: new Date().toISOString(),
      pipelineVersion: 2
    }
  };
  zip.file('config.cfg', JSON.stringify(configData, null, 2));

  // 每个对象一个文件夹
  for (const obj of objects) {
    const safeDirName = sanitizeName(obj.name);
    const folder = zip.folder(safeDirName);
    if (!folder) continue;

    // 按 producer + seq 排序文件
    const sorted = [...obj.files].sort((a, b) => {
      const aNum = extractSeq(a.path);
      const bNum = extractSeq(b.path);
      if (aNum !== bNum) return aNum - bNum;
      return a.path.localeCompare(b.path);
    });

    for (const file of sorted) {
      // 保留原始文件名或使用 path
      const fileName = file.path.includes('/')
        ? file.path.split('/').pop()!
        : file.path;
      folder.file(fileName, file.content);
    }
  }

  const buffer = await zip.generateAsync({ type: 'nodebuffer' });
  const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
  const filename = `pipeline_export_${ts}.zip`;

  return { buffer, filename };
}

/**
 * 从导出的 ZIP 解析回 PipelineObject[]（供前端回放页使用的前置逻辑在后端）
 */
export async function parseExportZip(buffer: Buffer): Promise<{
  config: Record<string, unknown>;
  objects: PipelineObject[];
}> {
  const zip = await JSZip.loadAsync(buffer);
  const configFile = zip.file('config.cfg');
  let config: Record<string, unknown> = {};
  if (configFile) {
    config = JSON.parse(await configFile.async('text'));
  }

  const objects: PipelineObject[] = [];
  const objDirs = new Map<string, { name: string; files: PipelineObject['files'] }>();

  for (const [path, entry] of Object.entries(zip.files)) {
    if (entry.dir || path === 'config.cfg') continue;

    const parts = path.split('/');
    if (parts.length < 2) continue; // skip root-level files

    const dirName = parts[0];
    const fileName = parts.slice(1).join('/');

    if (!objDirs.has(dirName)) {
      objDirs.set(dirName, { name: dirName, files: [] });
    }

    const content = await entry.async('text');
    const category = fileName.endsWith('_chatlog.json') ? 'chat_log' as const
      : fileName.endsWith('_report.md') || (fileName.endsWith('.md') && fileName.includes('_')) ? 'report' as const
      : 'input' as const;

    const producer = extractProducer(fileName, category);

    objDirs.get(dirName)!.files.push({
      path: fileName,
      content,
      producer,
      category
    });
  }

  for (const [_, obj] of objDirs) {
    objects.push({
      id: obj.name,
      name: obj.name,
      files: obj.files,
      status: 'completed'
    });
  }

  return { config, objects };
}

function sanitizeName(name: string): string {
  return name.replace(/[/\\?%*:|"<>]/g, '_').slice(0, 80);
}

function extractSeq(path: string): number {
  const match = path.match(/^(\d+)_/);
  return match ? parseInt(match[1]) : 999;
}

function extractProducer(fileName: string, category: string): string {
  if (category === 'input') return 'input';
  // Remove sequence prefix and suffix
  return fileName
    .replace(/^\d+_/, '')
    .replace(/_report\.md$/, '')
    .replace(/_chatlog\.json$/, '')
    .replace(/\.md$/, '');
}
