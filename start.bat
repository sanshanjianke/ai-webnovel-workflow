@echo off
cd /d "%~dp0"

if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing dependencies...
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo Starting server on http://localhost:7860
python -m uvicorn backend.main:app --host 0.0.0.0 --port 7860 --reload
