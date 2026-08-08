@echo off
setlocal enabledelayedexpansion

echo [IntelNexus] Starting setup...

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

"%PYTHON_EXE%" -c "import pip" 2>nul
if errorlevel 1 (
    echo [IntelNexus] ERROR: pip not available for %PYTHON_EXE%. Please use a Python with pip.
    pause
    exit /b 1
)

echo [IntelNexus] Upgrading pip...
"%PYTHON_EXE%" -m pip install --upgrade pip
if errorlevel 1 (
    echo [IntelNexus] WARNING: pip upgrade failed, continuing...
)

echo [IntelNexus] Installing requirements...
"%PYTHON_EXE%" -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo [IntelNexus] ERROR: failed to install requirements
    pause
    exit /b 1
)

set "INSTALL_MODELS=1"
for %%a in (%*) do (
    if /I "%%~a"=="--no-models" set "INSTALL_MODELS=0"
)

if %INSTALL_MODELS%==1 (
    echo [IntelNexus] Installing spaCy models...
    "%PYTHON_EXE%" -m pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl || echo [IntelNexus] WARNING: en_core_web_sm install failed
    "%PYTHON_EXE%" -m pip install https://github.com/explosion/spacy-models/releases/download/zh_core_web_sm-3.8.0/zh_core_web_sm-3.8.0-py3-none-any.whl || echo [IntelNexus] WARNING: zh_core_web_sm install failed
) else (
    echo [IntelNexus] Skipping model installation (--no-models)
)

echo [IntelNexus] Setup complete.
pause
