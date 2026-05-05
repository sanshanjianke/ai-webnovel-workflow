#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 默认使用 Node.js 后端，默认启动前后端
BACKEND="node"
START_FRONTEND=true
RESTART=false

# 解析参数
for arg in "$@"; do
    case $arg in
        python) BACKEND="python" ;;
        node) BACKEND="node" ;;
        --no-frontend) START_FRONTEND=false ;;
        restart|--restart|-r)
            RESTART=true
            ;;
    esac
done

# 重启：先杀掉占用端口的旧进程
kill_ports() {
    echo "🔪 清理旧进程..."
    lsof -ti:7860 2>/dev/null | xargs kill -9 2>/dev/null
    lsof -ti:5173 2>/dev/null | xargs kill -9 2>/dev/null
    sleep 1
    echo "✅ 端口已释放"
}

if [ "$RESTART" = true ]; then
    kill_ports
fi

if [ "$BACKEND" = "python" ]; then
    echo "🐍 启动 Python 后端..."

    if [ ! -d "venv" ]; then
        echo "创建虚拟环境..."
        python3 -m venv venv
    fi

    echo "激活虚拟环境..."
    source venv/bin/activate

    echo "安装依赖..."
    pip install -q --upgrade pip
    pip install -q -r requirements.txt

    echo "Python 服务器启动于 http://localhost:7860"
    python -m uvicorn backend.main:app --host 0.0.0.0 --port 7860 --reload &
    BACKEND_PID=$!

elif [ "$BACKEND" = "node" ]; then
    echo "🟢 启动 Node.js 后端..."

    cd backend-node

    if [ ! -d "node_modules" ]; then
        echo "安装依赖..."
        npm install
    fi

    echo "Node.js 服务器启动于 http://localhost:7860"
    npx tsx src/index.ts &
    BACKEND_PID=$!

    cd ..
fi

if [ "$START_FRONTEND" = true ]; then
    echo "🔵 启动前端..."

    cd frontend

    if [ ! -d "node_modules" ]; then
        echo "安装依赖..."
        npm install
    fi

    npm run dev &
    FRONTEND_PID=$!

    cd ..
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🌐 后端: http://localhost:7860"
if [ "$START_FRONTEND" = true ]; then
    echo "  🖥️  前端: http://localhost:5173"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 捕获退出信号，清理子进程
cleanup() {
    echo ""
    echo "🛑 停止服务..."
    [ -n "$BACKEND_PID" ] && kill $BACKEND_PID 2>/dev/null
    [ -n "$FRONTEND_PID" ] && kill $FRONTEND_PID 2>/dev/null
    echo "✅ 已停止"
}
trap cleanup EXIT INT TERM

# 等待任意子进程结束
wait
