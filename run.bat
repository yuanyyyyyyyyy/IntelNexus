@echo off
setlocal
REM IntelNexus 一键启动脚本（基于 conda base 环境，无需手动激活）
REM 用法:
REM   run.bat ui            -> 启动 Web 界面
REM   run.bat search -q ... -> CLI 搜索
REM   run.bat briefing / scheduler
REM 说明: 依赖与 spaCy 模型均位于 conda base；首次缺模型请双击 setup.bat。

set "CONDA_ROOT="
for %%P in (
  "D:\Tool\Develop\anaconda3"
  "%USERPROFILE%\anaconda3"
  "%USERPROFILE%\miniconda3"
  "C:\ProgramData\Anaconda3"
  "C:\ProgramData\Miniconda3"
) do (
  if exist "%%~P\Scripts\activate.bat" set "CONDA_ROOT=%%~P"
)
if not defined CONDA_ROOT (
  echo [IntelNexus] 未找到 conda，请先安装 Anaconda/Miniconda。
  pause
  exit /b 1
)

call "%CONDA_ROOT%\Scripts\activate.bat" base
python "%~dp0main.py" %*
