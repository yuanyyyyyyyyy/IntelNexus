@echo off
REM ============================================================
REM  IntelNexus Launcher - EXE distribution entry point
REM  Double-click to start. Browser opens automatically.
REM  No Python installation required.
REM ============================================================

title IntelNexus

REM Check if the EXE exists in the same directory
if not exist "%~dp0IntelNexus.exe" (
    echo.
    echo  [ERROR] IntelNexus.exe not found.
    echo  Please make sure this file is in the same folder as IntelNexus.exe.
    echo.
    pause
    exit /b 1
)

REM Create data directory if it doesn't exist (first run)
if not exist "%~dp0data" mkdir "%~dp0data" >nul

REM Create .env from template if it doesn't exist (first run)
if not exist "%~dp0.env" (
    if exist "%~dp0.env.example" (
        copy "%~dp0.env.example" "%~dp0.env" >nul
    )
)

echo.
echo  ============================================
echo    IntelNexus - AI Intelligence Platform
echo  ============================================
echo.
echo    Starting... Browser will open automatically.
echo    Press Ctrl+C to stop the server.
echo.
echo  ============================================
echo.

REM Launch the EXE (it auto-opens the browser via main.py)
"%~dp0IntelNexus.exe" ui

echo.
echo  [IntelNexus] Exited.
pause
