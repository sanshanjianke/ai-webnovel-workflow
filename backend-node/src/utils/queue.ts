// 异步队列 - 实现生产者-消费者模式的核心

export class AsyncQueue<T> {
  private items: T[] = [];
  private waiters: Array<(value: IteratorResult<T>) => void> = [];
  private closed: boolean = false;
  private error: Error | null = null;

  async enqueue(item: T): Promise<void> {
    if (this.closed) {
      throw new Error('Queue is closed');
    }

    // 如果有等待的消费者，直接传递
    if (this.waiters.length > 0) {
      const waiter = this.waiters.shift()!;
      waiter({ value: item, done: false });
      return;
    }

    // 否则放入队列
    this.items.push(item);
  }

  async dequeue(): Promise<T> {
    // 如果队列中有元素，直接取出
    if (this.items.length > 0) {
      return this.items.shift()!;
    }

    // 如果队列已关闭且没有元素
    if (this.closed) {
      if (this.error) {
        throw this.error;
      }
      throw new Error('Queue is closed and empty');
    }

    // 等待新元素
    return new Promise<T>((resolve, reject) => {
      this.waiters.push((result) => {
        if (result.done) {
          if (this.error) {
            reject(this.error);
          } else {
            reject(new Error('Queue closed'));
          }
        } else {
          resolve(result.value);
        }
      });
    });
  }

  close(): void {
    this.closed = true;
    // 唤醒所有等待的消费者
    while (this.waiters.length > 0) {
      const waiter = this.waiters.shift()!;
      waiter({ value: undefined as unknown as T, done: true });
    }
  }

  errorClose(error: Error): void {
    this.error = error;
    this.close();
  }

  isEmpty(): boolean {
    return this.items.length === 0;
  }

  size(): number {
    return this.items.length;
  }

  isClosed(): boolean {
    return this.closed;
  }

  // 实现异步迭代器接口
  [Symbol.asyncIterator](): AsyncIterator<T> {
    return {
      next: async (): Promise<IteratorResult<T>> => {
        try {
          const value = await this.dequeue();
          return { value, done: false };
        } catch {
          return { value: undefined as unknown as T, done: true };
        }
      }
    };
  }
}

// 并发控制
export class ConcurrencyLimiter {
  private running: number = 0;
  private queue: Array<() => void> = [];
  private maxConcurrent: number;

  constructor(maxConcurrent: number) {
    this.maxConcurrent = maxConcurrent;
  }

  async run<T>(fn: () => Promise<T>): Promise<T> {
    await this.acquire();
    try {
      return await fn();
    } finally {
      this.release();
    }
  }

  private acquire(): Promise<void> {
    if (this.running < this.maxConcurrent) {
      this.running++;
      return Promise.resolve();
    }

    return new Promise<void>((resolve) => {
      this.queue.push(() => {
        this.running++;
        resolve();
      });
    });
  }

  private release(): void {
    this.running--;
    if (this.queue.length > 0) {
      const next = this.queue.shift()!;
      next();
    }
  }
}

// 批处理队列
export class BatchQueue<T> {
  private queue: AsyncQueue<T>;
  private batchSize: number;
  private timeout: number;

  constructor(batchSize: number, timeout: number = 1000) {
    this.queue = new AsyncQueue<T>();
    this.batchSize = batchSize;
    this.timeout = timeout;
  }

  async enqueue(item: T): Promise<void> {
    await this.queue.enqueue(item);
  }

  async *batches(): AsyncGenerator<T[]> {
    while (!this.queue.isClosed()) {
      const batch: T[] = [];
      const deadline = Date.now() + this.timeout;

      while (batch.length < this.batchSize) {
        const remaining = deadline - Date.now();
        if (remaining <= 0) break;

        try {
          const item = await Promise.race([
            this.queue.dequeue(),
            new Promise<never>((_, reject) => 
              setTimeout(() => reject(new Error('timeout')), remaining)
            )
          ]);
          batch.push(item);
        } catch {
          break;
        }
      }

      if (batch.length > 0) {
        yield batch;
      }
    }
  }

  close(): void {
    this.queue.close();
  }
}
