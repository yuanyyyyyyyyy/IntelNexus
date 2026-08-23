@echo off
setlocal enabledelayedexpansion

echo [IntelNexus] Setting up IntelNexus...

REM ---- 1. Locate a Python (no hardcoded personal paths) ----
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
    echo [IntelNexus] ERROR: Python not found.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo IMPORTANT: check "Add python.exe to PATH" during install.
    pause
    exit /b 1
)

echo [IntelNexus] Using base python: %PYTHON_EXE%

REM ---- 2. Create an isolated venv (does NOT touch your global Python) ----
if not exist "%~dp0.venv\Scripts\python.exe" (
    echo [IntelNexus] Creating virtual environment .venv ...
    "%PYTHON_EXE%" -m venv "%~dp0.venv"
    if errorlevel 1 (
        echo [IntelNexus] ERROR: failed to create virtual environment.
        pause
        exit /b 1
    )
)

set "VENV_PYTHON=%~dp0.venv\Scripts\python.exe"

"%VENV_PYTHON%" -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)"
if errorlevel 1 (
    echo [IntelNexus] ERROR: Python 3.10+ is required.
    "%VENV_PYTHON%" --version
    pause
    exit /b 1
)

REM ---- 3. Install core dependencies into the venv ----
echo [IntelNexus] Installing dependencies (this may take a few minutes)...
"%VENV_PYTHON%" -m pip install --upgrade pip
"%VENV_PYTHON%" -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo [IntelNexus] ERROR: failed to install requirements.
    echo If you are in mainland China, retry with a mirror:
    echo   %VENV_PYTHON% -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    pause
    exit /b 1
)

REM ---- 4. Optional extras (Anthropic/Gemini SDK, NLP). Skip on failure ----
"%VENV_PYTHON%" -m pip install -r "%~dp0requirements-extras.txt" >nul 2>&1
echo [IntelNexus] Optional extras installed where possible (missing ones degrade gracefully).

REM ---- 5. Prepare a clean .env from template (never overwrite existing) ----
if not exist "%~dp0.env" (
    copy "%~dp0.env.example" "%~dp0.env" >nul
    echo [IntelNexus] Created .env from template. All settings optional;
    echo              you can configure the AI model inside the app later.
)

echo.
echo [IntelNexus] Setup complete! Double-click run.bat to start.
pause
