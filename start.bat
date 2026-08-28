@echo off
setlocal enabledelayedexpansion

REM ============================================================
REM  IntelNexus - One-click Start (Source Distribution)
REM  Auto-detects if setup is needed, then launches the app.
REM  For non-technical users: just double-click this file.
REM ============================================================

title IntelNexus

echo.
echo  ============================================
echo    IntelNexus - AI Intelligence Platform
echo  ============================================
echo.

REM ---- Step 1: Find Python ----
set "PYTHON_EXE="
for /f "delims=" %%i in ('where python 2^>nul') do (
    if not defined PYTHON_EXE set "PYTHON_EXE=%%i"
)
if not defined PYTHON_EXE (
    for /f "delims=" %%i in ('where py 2^>nul') do (
        if not defined PYTHON_EXE set "PYTHON_EXE=%%i"
    )
)

if not defined PYTHON_EXE (
    echo  [ERROR] Python not found.
    echo.
    echo  Please install Python 3.10+ from:
    echo  https://www.python.org/downloads/
    echo.
    echo  IMPORTANT: Check "Add python.exe to PATH" during install.
    echo.
    pause
    exit /b 1
)

REM ---- Step 2: Auto-setup if needed ----
if not exist "%~dp0.venv\Scripts\python.exe" (
    echo  [1/3] Setting up for first time...
    echo        (This takes 2-5 minutes on first run^)
    echo.

    REM Create venv
    "%PYTHON_EXE%" -m venv "%~dp0.venv" >nul 2>&1
    if errorlevel 1 (
        echo  [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )

    REM Install dependencies
    echo  [2/3] Installing dependencies...
    "%~dp0.venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>&1
    "%~dp0.venv\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt"
    if errorlevel 1 (
        echo.
        echo  [ERROR] Failed to install dependencies.
        echo  If you are in mainland China, try:
        echo    .venv\Scripts\pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
        echo.
        pause
        exit /b 1
    )

    REM Install optional extras (ignore failure)
    "%~dp0.venv\Scripts\python.exe" -m pip install -r "%~dp0requirements-extras.txt" >nul 2>&1

    REM Create .env from template
    if not exist "%~dp0.env" (
        copy "%~dp0.env.example" "%~dp0.env" >nul
    )

    REM Create data directory
    if not exist "%~dp0data" mkdir "%~dp0data" >nul

    echo.
    echo  [OK] Setup complete!
    echo.
)

REM ---- Step 3: Launch ----
echo  [3/3] Starting IntelNexus...
echo        Browser will open automatically.
echo.
echo  ============================================
echo.

"%~dp0.venv\Scripts\python.exe" "%~dp0main.py" ui

echo.
echo  [IntelNexus] Exited.
pause
