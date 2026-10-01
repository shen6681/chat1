@echo off
setlocal
cd /d "%~dp0"
if exist "ChatReplyAssistant.exe" (
  start "" "%~dp0ChatReplyAssistant.exe" %*
  exit /b
)
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" main.py %*
  exit /b
)
python main.py %*
if errorlevel 1 pause
