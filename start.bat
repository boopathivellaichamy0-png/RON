@echo off
title AcroText Precision
echo Starting AcroText Precision...
cd /d "%~dp0\backend"
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
pause
