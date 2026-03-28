@echo off
echo ================================
echo   !nvest Backend - FastAPI
echo   http://localhost:8000
echo   Docs: http://localhost:8000/docs
echo ================================
cd /d "%~dp0"
python -m uvicorn backend.main:app --reload --port 8000
pause
