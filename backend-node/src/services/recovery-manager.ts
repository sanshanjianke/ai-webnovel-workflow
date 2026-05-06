import { MeetingConfig, PipelineObject } from '../protocols';

export interface CheckpointState {
  sessionId: string;
  meetingId: string;
  savedAt: string;
  currentObjectIndex: number;  // 0-based index in objects array
  completedNodeIds: string[];  // nodes already done for current object
  outputSeq: number;
}

export interface PipelineCheckpoint {
  state: CheckpointState;
  objects: SerializedObject[];
  config: MeetingConfig;
}

interface SerializedObject {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  files: Array<{
    path: string;
    content: string;
    producer: string;
    category: 'input' | 'report' | 'chat_log';
  }>;
  startedAt?: string;
  completedAt?: string;
}

export function saveCheckpoint(
  dir: string,
  sessionId: string,
  meetingId: string,
  config: MeetingConfig,
  objects: PipelineObject[],
  currentObjectIndex: number,
  completedNodeIds: string[],
  outputSeq: number
): void {
  const fs = require('fs');

  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }

  const checkpoint: PipelineCheckpoint = {
    state: {
      sessionId,
      meetingId,
      savedAt: new Date().toISOString(),
      currentObjectIndex,
      completedNodeIds,
      outputSeq
    },
    config,
    objects: objects.map(o => ({
      id: o.id,
      name: o.name,
      status: o.status,
      files: o.files.map(f => ({
        path: f.path,
        content: f.content,
        producer: f.producer,
        category: f.category
      })),
      startedAt: o.startedAt,
      completedAt: o.completedAt
    }))
  };

  const path = `${dir}/checkpoint_${sessionId}.json`;
  fs.writeFileSync(path, JSON.stringify(checkpoint, null, 2), 'utf-8');
}

export function loadCheckpoint(dir: string, sessionId: string): PipelineCheckpoint | null {
  const fs = require('fs');
  const path = `${dir}/checkpoint_${sessionId}.json`;

  if (!fs.existsSync(path)) return null;

  try {
    return JSON.parse(fs.readFileSync(path, 'utf-8'));
  } catch {
    return null;
  }
}

export function deleteCheckpoint(dir: string, sessionId: string): void {
  const fs = require('fs');
  const path = `${dir}/checkpoint_${sessionId}.json`;
  if (fs.existsSync(path)) {
    fs.unlinkSync(path);
  }
}

/**
 * 检测最后一个轮次是否不完整。
 * 规则：最后一条 assistant 消息 content 为空或未完成标记。
 */
export function cleanIncompleteRound(
  chatLog: { rounds?: Array<{ messages?: Array<{ role: string; content?: string }>; completedAt?: string }> }
): boolean {
  const rounds = chatLog.rounds || [];
  if (rounds.length === 0) return false;

  const lastRound = rounds[rounds.length - 1];
  const messages = lastRound.messages || [];
  if (messages.length === 0) {
    rounds.pop();
    return true;
  }

  const lastMsg = messages[messages.length - 1];
  if (lastMsg.role === 'assistant' && (!lastMsg.content || lastMsg.content.trim() === '')) {
    rounds.pop();
    return true;
  }

  if (!lastRound.completedAt) {
    // Round never completed — but only discard if assistant message is empty
    const lastAssistant = [...messages].reverse().find(m => m.role === 'assistant');
    if (lastAssistant && (!lastAssistant.content || lastAssistant.content.trim() === '')) {
      rounds.pop();
      return true;
    }
  }

  return false;
}

/**
 * 将序列化对象还原为 PipelineObject
 */
export function restoreObjects(serialized: SerializedObject[]): PipelineObject[] {
  return serialized.map(s => ({
    id: s.id,
    name: s.name,
    status: s.status as PipelineObject['status'],
    files: s.files.map(f => ({
      path: f.path,
      content: f.content,
      producer: f.producer,
      category: f.category
    })),
    startedAt: s.startedAt,
    completedAt: s.completedAt,
    currentNodeId: undefined
  }));
}
