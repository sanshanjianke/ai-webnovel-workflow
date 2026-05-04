#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 默认使用 Node.js 后端
BACKEND=${1:-node}

if [ "$BACKEND" = "python" ]; then
    echo "Starting Python backend..."
    
    if [ ! -d "venv" ]; then
        echo "Creating virtual environment..."
        python3 -m venv venv
    fi
    
    echo "Activating virtual environment..."
    source venv/bin/activate
    
    echo "Installing dependencies..."
    pip install -q --upgrade pip
    pip install -q -r requirements.txt
    
    echo "Starting Python server on http://localhost:7860"
    python -m uvicorn backend.main:app --host 0.0.0.0 --port 7860 --reload
    
elif [ "$BACKEND" = "node" ]; then
    echo "Starting Node.js backend..."
    
    cd backend-node
    
    if [ ! -d "node_modules" ]; then
        echo "Installing dependencies..."
        npm install
    fi
    
    echo "Starting Node.js server on http://localhost:7860"
    npx tsx src/index.ts
    
else
    echo "Usage: ./start.sh [python|node]"
    echo "  python - Start Python backend"
    echo "  node   - Start Node.js backend (default)"
    exit 1
fi
