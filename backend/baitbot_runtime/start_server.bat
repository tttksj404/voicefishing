@echo off
cd /d "%~dp0\..\.."
python -m uvicorn backend.baitbot_runtime.app:app --host 127.0.0.1 --port 8000
pause
