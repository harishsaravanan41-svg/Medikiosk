@echo off
title MediKiosk - Qwen 2.5 Model Server
echo ======================================================
echo    Starting MediKiosk Qwen 2.5 1.5B Model Server
echo ======================================================
cd /d "%~dp0.."
python scripts\run_qwen_server.py
pause
