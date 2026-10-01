@echo off
cd /d "%~dp0"
if exist "%~dp0dist\ChatReplyAssistant.exe" (
    start "" "%~dp0dist\ChatReplyAssistant.exe"
    exit /b
)
if exist "%~dp0.venv\Scripts\pythonw.exe" (
    start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0main.py"
    exit /b
)
echo Please run setup.ps1 first, or use the packaged executable.
pause
