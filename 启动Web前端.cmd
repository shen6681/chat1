@echo off
chcp 65001 >nul
cd /d "%~dp0web"
echo ========================================================
echo   聊有据 · 现代化高精 UI 前端工作台 (React + Vite)
echo ========================================================
if not exist "node_modules" (
    echo [1/2] 首次运行，正在自动安装前端依赖...
    call npm install
)
echo [2/2] 正在启动 Vite 本地服务并打开浏览器...
start "" "http://localhost:5173"
call npm run dev
pause
