// 路由注册
import { Express } from 'express';
import { registerProjectRoutes } from './projects';
import { registerMeetingRoutes } from './meeting';
import { registerL1Routes } from './l1';
import { registerL3Routes } from './l3';
import { registerL4Routes } from './l4';
import { registerWorldbookRoutes } from './worldbook';
import { registerRAGRoutes } from './rag';
import { registerLibraryRoutes } from './library';
import { registerSettingsRoutes } from './settings';

export function registerAllRoutes(app: Express): void {
  // 项目管理
  registerProjectRoutes(app);
  
  // 编排层（核心）
  registerMeetingRoutes(app);
  
  // L1 种子层
  registerL1Routes(app);
  
  // L3 叙事层
  registerL3Routes(app);
  
  // L4 渲染层
  registerL4Routes(app);
  
  // 世界书
  registerWorldbookRoutes(app);
  
  // RAG 检索
  registerRAGRoutes(app);
  
  // 文档库
  registerLibraryRoutes(app);
  
  // 系统设置
  registerSettingsRoutes(app);
}
