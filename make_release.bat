@echo off
setlocal enabledelayedexpansion

REM ============================================================
REM  make_release.bat - build a CLEAN distributable zip
REM  Excludes: .env (your keys), data/ (subscriber PII + history),
REM            .venv, .git, caches, docs.
REM  Output: dist\IntelNexus-<date>.zip  (safe to share)
REM ============================================================

set "STAMP=%date:~0,4%%date:~5,2%%date:~8,2%"
set "OUT_DIR=%~dp0dist"
set "STAGE=%TEMP%\intelnexus-release-%RANDOM%"
set "ZIP_NAME=IntelNexus-%STAMP%.zip"

echo [IntelNexus] Staging a clean copy...
mkdir "%STAGE%" >nul

robocopy "%~dp0." "%STAGE%" /E ^
  /XD .git .venv __pycache__ .pytest_cache dist data docs node_modules ^
  /XF .env .env.local *.pyc .DS_Store >nul
if errorlevel 8 (
    echo [IntelNexus] ERROR: staging copy failed.
    pause
    exit /b 1
)

REM Keep the example template so recipients know what .env supports
if not exist "%STAGE%\.env.example" (
    echo [IntelNexus] WARNING: .env.example missing from stage.
)

echo [IntelNexus] Verifying no secrets in release...
findstr /S /M /C:"sk-" "%STAGE%\*.json" >nul 2>&1
if not errorlevel 1 (
    echo [IntelNexus] ERROR: possible API key found in staged files. Aborting.
    rmdir /S /Q "%STAGE%"
    pause
    exit /b 1
)
findstr /S /M /C:"BEGIN PRIVATE KEY" "%STAGE%\*" >nul 2>&1
if not errorlevel 1 (
    echo [IntelNexus] ERROR: private key material found. Aborting.
    rmdir /S /Q "%STAGE%"
    pause
    exit /b 1
)

echo [IntelNexus] Creating %OUT_DIR%\%ZIP_NAME% ...
mkdir "%OUT_DIR%" >nul 2>&1
powershell -NoProfile -Command "Compress-Archive -Path '%STAGE%\*' -DestinationPath '%OUT_DIR%\%ZIP_NAME%' -Force"
if errorlevel 1 (
    echo [IntelNexus] ERROR: zip creation failed.
    rmdir /S /Q "%STAGE%"
    pause
    exit /b 1
)

rmdir /S /Q "%STAGE%"
echo.
echo [IntelNexus] DONE: %OUT_DIR%\%ZIP_NAME%
echo [IntelNexus] This package contains NO keys, NO subscriber data, NO history.
pause
