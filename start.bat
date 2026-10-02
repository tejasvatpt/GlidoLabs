@echo off
cd /d "%~dp0backend"
start "" http://127.0.0.1:8000
.venv\Scripts\uvicorn app.main:app --port 8000
