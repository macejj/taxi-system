@echo off
chcp 65001 >nul
title 出租车运营管理与决策支持系统 - 初始化数据
cd /d "%~dp0backend"

if exist "..\venv\Scripts\python.exe" (
    set "PY=..\venv\Scripts\python.exe"
) else if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
) else (
    set "PY=python"
)

echo ============================================================
echo   初始化数据库并生成仿真运营数据
echo ============================================================
echo   解释器: %PY%
echo.
echo   步骤 1/2: 建表 + 初始化账号与系统参数
echo   步骤 2/2: 生成仿真数据（约需 1~3 分钟，请耐心等待）
echo ============================================================
echo.

%PY% scripts\init_db.py
if errorlevel 1 (
    echo.
    echo [错误] 建表失败。请检查 backend\.env 中的数据库配置是否正确，
    echo        并确认 MySQL 服务已启动。
    pause
    exit /b 1
)

echo.
%PY% scripts\seed_data.py --days 60 --vehicles 60 --drivers 80
if errorlevel 1 (
    echo.
    echo [错误] 数据生成失败。
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   初始化完成！现在可以运行 start-backend.bat 与 start-frontend.bat
echo   登录账号: admin / admin123
echo ============================================================
pause
