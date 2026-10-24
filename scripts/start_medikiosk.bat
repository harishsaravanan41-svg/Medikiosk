@echo off
title MediKiosk Unified Launcher
echo ======================================================
echo    Launching MediKiosk AI Suite with Qwen 2.5
echo ======================================================
cd /d "%~dp0.."

echo 1. Starting Qwen 2.5 Model API Server (Port 8000)...
start "Qwen 2.5 API Server" cmd /k "python scripts\run_qwen_server.py"

echo 2. Waiting 5 seconds for initialization...
timeout /t 5 /nobreak >nul

echo 3. Starting MediKiosk Flask Web App (Port 5000)...
python run.py
pause
