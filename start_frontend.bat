@echo off
title AutoSync Video - Frontend Studio UI
echo ===================================================
echo   Menjalankan Frontend Web Studio UI (Port 3000)
echo ===================================================
cd /d "%~dp0frontend"
npm run dev
pause
