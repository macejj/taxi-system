@echo off
chcp 65001 >nul
title 出租车运营管理与决策支持系统 - 前端
cd /d "%~dp0frontend"

echo ============================================================
echo   出租车运营管理与决策支持系统 - 前端开发服务
echo ============================================================
echo   访问地址: http://localhost:5173
echo   登录账号: admin / admin123
echo ------------------------------------------------------------
echo   请确保后端服务已在 8000 端口启动
echo   按 Ctrl+C 可停止服务
echo ============================================================
echo.

if not exist "node_modules" (
    echo [提示] 未检测到 node_modules，正在安装依赖...
    call npm install
    if errorlevel 1 (
        echo [错误] 依赖安装失败，请检查 Node.js 是否正确安装。
        pause
        exit /b 1
    )
)

call npm run dev

echo.
echo 前端服务已停止。
pause
