// 入口文件
import express from 'express';
import cors from 'cors';
import { registerAllRoutes } from './routes';

const app = express();
const PORT = process.env.PORT || 7860;

// 中间件
app.use(cors({
  origin: '*',
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['*']
}));

app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true }));

// 根路由
app.get('/', (req, res) => {
  res.json({
    status: 'ok',
    message: 'AI Web Novel Creator API (Node.js)',
    version: '1.0.0'
  });
});

// 健康检查
app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

// 注册所有路由
registerAllRoutes(app);

// 错误处理
app.use((err: Error, req: express.Request, res: express.Response, next: express.NextFunction) => {
  console.error('Unhandled error:', err);
  res.status(500).json({ error: 'Internal server error' });
});

// 启动服务器
app.listen(PORT, () => {
  console.log(`Server is running on http://localhost:${PORT}`);
  console.log(`Environment: ${process.env.NODE_ENV || 'development'}`);
});

export default app;
