@echo off
setlocal enabledelayedexpansion

echo [IntelNexus] Starting IntelNexus...

REM ---- Prefer the project venv created by setup.bat ----
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
    goto :found
)

REM ---- Fallback: any system Python (no hardcoded personal paths) ----
for /f "delims=" %%i in ('where python 2^>nul') do (
    if not defined PYTHON_EXE set "PYTHON_EXE=%%i"
)

if not defined PYTHON_EXE (
    echo [IntelNexus] ERROR: Python not found and no .venv exists.
    echo Please run setup.bat first.
    pause
    exit /b 1
)

:found
echo [IntelNexus] Using python: %PYTHON_EXE%

REM NOTE: Do NOT clear HTTP_PROXY/HTTPS_PROXY/USE_TOR here.
REM run.bat is read by cmd.exe as GBK, so Chinese comments cause mojibake errors.
REM .env values are loaded by python-dotenv inside config.py; clearing these vars
REM here would defeat .env because load_dotenv() does not override existing vars.

if not defined HF_HUB_DISABLE_PROGRESS_BARS set "HF_HUB_DISABLE_PROGRESS_BARS=0"

echo [IntelNexus] Checking dependencies...
"%PYTHON_EXE%" -c "import streamlit, click" 2>nul
if errorlevel 1 (
    echo [IntelNexus] ERROR: streamlit or click not installed. Please run setup.bat first.
    pause
    exit /b 1
)

REM Default to Web UI when launched by double-click (no arguments)
if "%~1"=="" (
    echo [IntelNexus] No command given, starting Web UI...
    "%PYTHON_EXE%" "%~dp0main.py" ui
) else (
    "%PYTHON_EXE%" "%~dp0main.py" %*
)

echo [IntelNexus] Exited.
pause
