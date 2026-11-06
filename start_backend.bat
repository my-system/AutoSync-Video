@echo off
title AutoSync Video - Backend API Server
echo ===================================================
echo   Menjalankan Backend API AutoSync Video (Port 8000)
echo ===================================================
cd /d "%~dp0"
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
pause
