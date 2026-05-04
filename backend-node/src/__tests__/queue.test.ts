// 队列工具单元测试
import { describe, it, expect } from 'vitest';
import { AsyncQueue } from '../utils/queue';

describe('AsyncQueue', () => {
  it('应该能够入队和出队', async () => {
    const queue = new AsyncQueue<number>();
    
    await queue.enqueue(1);
    await queue.enqueue(2);
    await queue.enqueue(3);
    
    expect(await queue.dequeue()).toBe(1);
    expect(await queue.dequeue()).toBe(2);
    expect(await queue.dequeue()).toBe(3);
  });

  it('应该支持异步等待', async () => {
    const queue = new AsyncQueue<string>();
    
    // 先启动一个等待出队的 Promise
    const dequeuePromise = queue.dequeue();
    
    // 稍后入队
    setTimeout(() => queue.enqueue('hello'), 10);
    
    const result = await dequeuePromise;
    expect(result).toBe('hello');
  });

  it('关闭后应该抛出错误', async () => {
    const queue = new AsyncQueue<number>();
    queue.close();
    
    await expect(queue.dequeue()).rejects.toThrow();
  });

  it('关闭后不能入队', async () => {
    const queue = new AsyncQueue<number>();
    queue.close();
    
    await expect(queue.enqueue(1)).rejects.toThrow();
  });

  it('应该报告正确的状态', () => {
    const queue = new AsyncQueue<number>();
    
    expect(queue.isEmpty()).toBe(true);
    expect(queue.size()).toBe(0);
    expect(queue.isClosed()).toBe(false);
    
    queue.enqueue(1);
    queue.enqueue(2);
    
    expect(queue.isEmpty()).toBe(false);
    expect(queue.size()).toBe(2);
    
    queue.close();
    expect(queue.isClosed()).toBe(true);
  });

  it('应该支持异步迭代器', async () => {
    const queue = new AsyncQueue<number>();
    
    await queue.enqueue(1);
    await queue.enqueue(2);
    await queue.enqueue(3);
    queue.close();
    
    const results: number[] = [];
    for await (const item of queue) {
      results.push(item);
    }
    
    expect(results).toEqual([1, 2, 3]);
  });
});
