@echo off
chcp 65001 >nul
REM 重启 Tor：长时间运行后 .onion 建链明显变慢（2026-10-20 实测：早 8.8s 晚超时）。
REM 演示前 / .onion 连续超时时执行本脚本。
echo [IntelNexus] Stopping tor.exe ...
taskkill /IM tor.exe /F >nul 2>&1
timeout /t 2 /nobreak >nul
echo [IntelNexus] Starting Tor ...
call "%~dp0start_tor.bat"
