@echo off
REM Run voice-fast-service locally (no Docker)

cd /d "%~dp0"

REM Create storage dirs
if not exist storage\voices mkdir storage\voices
if not exist storage\history mkdir storage\history

REM Activate venv
call .venv\Scripts\activate.bat

REM Start server
cd src
uvicorn app.main:app --host %HOST% --port %PORT% --workers 1 --reload
