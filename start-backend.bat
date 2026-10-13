@echo off
chcp 65001 >nul
title 出租车运营管理与决策支持系统 - 后端服务
cd /d "%~dp0backend"

REM 优先使用项目同级的 venv 虚拟环境，否则使用系统 PATH 中的 python
if exist "..\venv\Scripts\python.exe" (
    set "PY=..\venv\Scripts\python.exe"
) else if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
) else (
    set "PY=python"
)

echo ============================================================
echo   出租车运营管理与决策支持系统 - 后端服务
echo ============================================================
echo   解释器 : %PY%
echo   接口文档: http://localhost:8000/docs
echo   健康检查: http://localhost:8000/api/health
echo ------------------------------------------------------------
echo   按 Ctrl+C 可停止服务
echo ============================================================
echo.

%PY% -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

echo.
echo 服务已停止。若为异常退出，请检查上方错误信息。
pause
