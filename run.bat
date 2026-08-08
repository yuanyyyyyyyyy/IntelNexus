@echo off
setlocal enabledelayedexpansion

echo [IntelNexus] Starting IntelNexus...

set "PYTHON_EXE="
set "CONDA_ROOT="

for %%p in (
    "D:\Tool\Develop\anaconda3"
    "%USERPROFILE%\anaconda3"
    "%USERPROFILE%\miniconda3"
    "C:\anaconda3"
    "C:\miniconda3"
    "D:\anaconda3"
    "D:\miniconda3"
) do (
    set "p=%%~p"
    if not defined PYTHON_EXE (
        if exist "!p!\python.exe" (
            set "PYTHON_EXE=!p!\python.exe"
            set "CONDA_ROOT=!p!"
        )
    )
)

if not defined PYTHON_EXE (
    for /f "delims=" %%i in ('where python 2^>nul') do (
        if not defined PYTHON_EXE set "PYTHON_EXE=%%i"
    )
)

if not defined PYTHON_EXE (
    echo [IntelNexus] ERROR: python not found. Install Python or Anaconda.
    pause
    exit /b 1
)

echo [IntelNexus] Using python: %PYTHON_EXE%

set HTTP_PROXY=
set HTTPS_PROXY=
set USE_TOR=

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
