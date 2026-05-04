@echo off

set BACKEND=%1
if "%BACKEND%"=="" set BACKEND=node

if "%BACKEND%"=="python" (
    echo Starting Python backend...
    
    if not exist "venv" (
        echo Creating virtual environment...
        python -m venv venv
    )
    
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
    
    echo Installing dependencies...
    pip install -q --upgrade pip
    pip install -q -r requirements.txt
    
    echo Starting Python server on http://localhost:7860
    python -m uvicorn backend.main:app --host 0.0.0.0 --port 7860 --reload
    
) else if "%BACKEND%"=="node" (
    echo Starting Node.js backend...
    
    cd backend-node
    
    if not exist "node_modules" (
        echo Installing dependencies...
        npm install
    )
    
    echo Starting Node.js server on http://localhost:7860
    npx tsx src/index.ts
    
) else (
    echo Usage: start.bat [python^|node]
    echo   python - Start Python backend
    echo   node   - Start Node.js backend ^(default^)
    exit /b 1
)
