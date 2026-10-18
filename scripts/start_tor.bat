@echo off
chcp 65001 >nul
REM 本脚本位于 scripts\，先切到仓库根（.venv、data\tor_runtime、tools\tor 都相对根）
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -u "%~dp0start_tor.py"
) else (
    python -u "%~dp0start_tor.py"
)
echo.
pause
