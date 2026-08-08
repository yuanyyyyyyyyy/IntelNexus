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
    REM zh model is available on PyPI mirrors (e.g. aliyun)
    "%PYTHON_EXE%" -m pip install "zh-core-web-sm==3.8.0" -i http://mirrors.aliyun.com/pypi/simple --trusted-host mirrors.aliyun.com || echo [IntelNexus] WARNING: zh_core_web_sm install failed

    REM en model: prefer local proxy (e.g. NekoBox Mixed port 2080) to reach GitHub directly,
    REM then fall back to public GitHub proxies if no local proxy is available.
    set "EN_MODEL_URL=https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl"
    set "PIP_PROXY="
    powershell -Command "try { $n=New-Object System.Net.Sockets.TcpClient; $n.Connect('127.0.0.1',2080); $n.Close(); Write-Output 'PROXY_UP' } catch { Write-Output 'PROXY_DOWN' }" | findstr /C:"PROXY_UP" >nul && set "PIP_PROXY=http://127.0.0.1:2080"

    if defined PIP_PROXY (
        echo [IntelNexus] Local proxy detected at 127.0.0.1:2080, using it for en_core_web_sm
        "%PYTHON_EXE%" -m pip install "%EN_MODEL_URL%" --proxy "%PIP_PROXY%" || echo [IntelNexus] WARNING: en_core_web_sm install failed via local proxy
    ) else (
        echo [IntelNexus] No local proxy; trying public GitHub proxies for en_core_web_sm
        "%PYTHON_EXE%" -m pip install "https://ghproxy.net/https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl" --trusted-host ghproxy.net || (
            "%PYTHON_EXE%" -m pip install "https://github.bib.ink/https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl" --trusted-host github.bib.ink || echo [IntelNexus] WARNING: en_core_web_sm install failed
        )
    )
) else (
    echo [IntelNexus] Skipping model installation (--no-models)
)

echo [IntelNexus] Setup complete.
pause
