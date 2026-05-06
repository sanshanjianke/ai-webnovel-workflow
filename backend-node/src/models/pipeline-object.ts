import { PipelineObject, PipelineObjectFile, ExpertChatLog } from '../protocols';

let objectCounter = 0;

export function createPipelineObject(
  name: string,
  inputFiles: { path: string; content: string }[]
): PipelineObject {
  objectCounter++;
  const id = `obj_${objectCounter}_${Date.now()}`;
  const files: PipelineObjectFile[] = inputFiles.map((f, i) => ({
    path: f.path || `input_${i + 1}.txt`,
    content: f.content,
    producer: 'input',
    category: 'input' as const
  }));

  return {
    id,
    name,
    files,
    status: 'pending',
    startedAt: new Date().toISOString()
  };
}

export function addExpertOutput(
  obj: PipelineObject,
  expertId: string,
  expertType: string,
  report: string,
  chatLog: ExpertChatLog,
  seq: number
): void {
  const safeName = expertType.replace(/[/\\?%*:|"<>]/g, '_');
  const prefix = `${seq}_${safeName}`;

  obj.files.push({
    path: `${prefix}_report.md`,
    content: report,
    producer: expertId,
    category: 'report'
  });

  obj.files.push({
    path: `${prefix}_chatlog.json`,
    content: JSON.stringify(chatLog, null, 2),
    producer: expertId,
    category: 'chat_log'
  });
}

export function getReportsFrom(obj: PipelineObject, producer?: string): PipelineObjectFile[] {
  return obj.files.filter(f => {
    if (f.category !== 'report') return false;
    if (producer && f.producer !== producer) return false;
    return true;
  });
}

export function getChatLogsFrom(obj: PipelineObject, producer?: string): PipelineObjectFile[] {
  return obj.files.filter(f => {
    if (f.category !== 'chat_log') return false;
    if (producer && f.producer !== producer) return false;
    return true;
  });
}

export function getInputFilesFrom(obj: PipelineObject): PipelineObjectFile[] {
  return obj.files.filter(f => f.category === 'input');
}

export function buildObjectContext(
  obj: PipelineObject,
  readCategories: ('input' | 'report' | 'chat_log')[],
  maxReportChars: number = 8000
): string {
  const parts: string[] = [];
  const relevant = obj.files.filter(f => readCategories.includes(f.category));

  if (relevant.length === 0) return '';

  for (const file of relevant) {
    const label = file.category === 'input' ? `📄 ${file.path}`
      : file.category === 'report' ? `📝 ${file.path} (${file.producer})`
      : `💬 ${file.path} (${file.producer})`;

    if (file.category === 'report' && file.content.length > maxReportChars) {
      parts.push(`${label}\n${file.content.slice(0, maxReportChars)}...\n`);
    } else {
      parts.push(`${label}\n${file.content}\n`);
    }
  }

  return `## 对象内容 (${obj.name})\n${parts.join('\n---\n')}`;
}
