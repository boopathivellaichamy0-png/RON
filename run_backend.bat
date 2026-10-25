@echo off
title AcroText Precision Backend Server
echo ========================================================
echo   Starting AcroText Precision Backend on http://localhost:8000
echo ========================================================
cd /d "%~dp0\backend"
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
pause
