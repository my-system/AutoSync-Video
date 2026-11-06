@echo off
title AutoSync Video Launcher
echo ================================================================
echo           AutoSync Video - Local Desktop Studio
echo   Automated Video & Voiceover Synchronization Engine
echo ================================================================
echo.
cd /d "%~dp0"

echo [1/3] Menyalakan Backend API (FastAPI di http://localhost:8000)...
start "AutoSync Video - Backend API" cmd /k "call start_backend.bat"

echo [2/3] Menyalakan Frontend Studio UI (Next.js di http://localhost:3000)...
start "AutoSync Video - Frontend UI" cmd /k "call start_frontend.bat"

echo [3/3] Menunggu server siap dan membuka browser...
timeout /t 3 /nobreak >nul
start http://localhost:3000

echo.
echo ================================================================
echo   AutoSync Video aktif mandiri di laptop Anda!
echo   Jendela ini boleh Anda minimize/tutup.
echo ================================================================
timeout /t 5 >nul
exit
