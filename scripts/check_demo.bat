@echo off
chcp 65001 >nul
REM 本脚本位于 scripts\，先切到仓库根（.venv 与 data/ 都相对根）
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "%~dp0preflight_demo.py" %*
) else (
    python "%~dp0preflight_demo.py" %*
)
echo.
pause
