// SSE 工具函数
import { Response } from 'express';

export interface SSEMessage {
  type: string;
  data: Record<string, unknown>;
}

export function sseFormat(eventType: string, data: Record<string, unknown>): string {
  return `event: ${eventType}\ndata: ${JSON.stringify(data)}\n\n`;
}

export function sseData(data: Record<string, unknown>): string {
  return `data: ${JSON.stringify(data)}\n\n`;
}

export class SSEWriter {
  private res: Response;
  private closed: boolean = false;

  constructor(res: Response) {
    this.res = res;
    this.setupHeaders();
  }

  private setupHeaders(): void {
    this.res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
      'Access-Control-Allow-Origin': '*',
      'X-Accel-Buffering': 'no'
    });
  }

  write(eventType: string, data: Record<string, unknown>): void {
    if (this.closed) return;
    this.res.write(sseFormat(eventType, data));
  }

  writeData(data: Record<string, unknown>): void {
    if (this.closed) return;
    this.res.write(sseData(data));
  }

  close(): void {
    if (!this.closed) {
      this.closed = true;
      this.res.end();
    }
  }

  isClosed(): boolean {
    return this.closed;
  }
}

export async function* createSSEGenerator<T>(
  generator: AsyncGenerator<T>,
  onItem: (item: T) => void
): AsyncGenerator<T> {
  for await (const item of generator) {
    onItem(item);
    yield item;
  }
}
