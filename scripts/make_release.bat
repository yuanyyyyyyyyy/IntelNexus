@echo off
setlocal enabledelayedexpansion

REM ============================================================
REM  make_release.bat - build a CLEAN distributable source zip
REM  Excludes: .env (your keys), data/ (subscriber PII + history),
REM            .venv, .git, caches, docs, temp/ (460MB workspace),
REM            tools/ (Tor plugin binaries), backup/, paperA/,
REM            review_results*, experiments/{runs,reports-raw},
REM            以及各 AI 工具会话目录。
REM  Output: dist\IntelNexus-Source-<version>.zip
REM
REM  注意 1：本脚本位于 scripts\，仓库根是 %~dp0..
REM  注意 2：robocopy 的 /XD 按「目录名」全树匹配，不带路径前缀的条目
REM           （data、paperA、runs）会作用于任意层级——这是有意的：
REM          experiments\data、experiments\paperA、experiments\runs 都是
REM          本地跑批产物（.gitignore 已忽略），不应进分发包。
REM ============================================================

REM ---- Determine version ----
set "VERSION="
for /f "tokens=*" %%t in ('git describe --tags --always 2^>nul') do set "VERSION=%%t"
if not defined VERSION (
    set "VERSION=%date:~0,4%%date:~5,2%%date:~8,2%"
)
echo [IntelNexus] Version: %VERSION%

set "PROJ_ROOT=%~dp0.."
set "OUT_DIR=%PROJ_ROOT%\dist"
set "STAGE=%TEMP%\intelnexus-release-%RANDOM%"
set "ZIP_NAME=IntelNexus-Source-%VERSION%.zip"

echo [IntelNexus] Staging a clean copy...
mkdir "%STAGE%" >nul

robocopy "%PROJ_ROOT%" "%STAGE%" /E ^
  /XD .git .venv __pycache__ .pytest_cache dist build data docs temp tools backup paperA ^
      node_modules .codebuddy .opencode .qoder .hermes .workbuddy .workbuddy-ai ^
      review_results review_results_r2 runs ^
  /XF .env .env.local *.pyc .DS_Store >nul
if errorlevel 8 (
    echo [IntelNexus] ERROR: staging copy failed.
    pause
    exit /b 1
)

REM ---- Verify critical files are present ----
echo [IntelNexus] Verifying critical resources...
set "MISSING=0"
for %%f in (main.py ui.py config.py requirements.txt start.bat .env.example USER_GUIDE.md) do (
    if not exist "%STAGE%\%%f" (
        echo   MISSING: %%f
        set "MISSING=1"
    )
)
REM Verify font directories (robocopy /XD data can accidentally exclude nested fonts)
if not exist "%STAGE%\static\fonts\inter" (
    echo   MISSING: static/fonts/inter (fonts will render as tofu!)
    set "MISSING=1"
)
if not exist "%STAGE%\intelnexus\assets\fonts" (
    echo   MISSING: intelnexus/assets/fonts (PDF export will have no CJK fonts!)
    set "MISSING=1"
)
if "!MISSING!"=="1" (
    echo.
    echo [IntelNexus] ERROR: Critical resources missing. Aborting.
    rmdir /S /Q "%STAGE%"
    pause
    exit /b 1
)
echo   All critical resources present.

REM ---- Verify no secrets in release ----
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

REM ---- Create ZIP ----
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

REM ---- Report ----
for %%f in ("%OUT_DIR%\%ZIP_NAME%") do set "ZIP_SIZE=%%~zf"
set /a "ZIP_MB=!ZIP_SIZE! / 1048576"

echo.
echo  ============================================
echo  [IntelNexus] Release built successfully!
echo  ============================================
echo  File: %OUT_DIR%\%ZIP_NAME%
echo  Size: ~!ZIP_MB! MB
echo.
echo  This package contains NO keys, NO subscriber data, NO history.
echo  Recipients: double-click start.bat to launch.
echo  ============================================
pause
