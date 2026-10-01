@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 聊有据 · 科学沟通辅助系统 (v2.6)

echo ========================================================
echo   聊有据 · 现代化高精科学沟通与回复辅助系统 (v2.6)
echo ========================================================

:: 优先检测系统 Python 启动本地服务
where python >nul 2>&1
if %errorlevel% equ 0 (
    python main.py %*
    exit /b
)

:: 如果没有系统 Python，检测内置虚拟环境 Python
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py %*
    exit /b
)

:: 如果没有 Python，检测 Node.js 启动前端服务
where node >nul 2>&1
if %errorlevel% equ 0 (
    cd web
    if not exist "node_modules" (
        echo 正在安装前端依赖...
        call npm install
    )
    start "" "http://localhost:5173"
    call npm run dev
    exit /b
)

echo [提示] 未检测到 Python 或 Node.js 环境。
echo 请先安装 Python 或 Node.js，或查看 README.md。
pause
