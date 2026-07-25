@echo off
setlocal
cd /d "%~dp0"

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

echo [IntelNexus] 运行依赖应已随 conda base 就绪（torch / spacy / streamlit 等）。
echo [IntelNexus] 仅补充 spaCy 中英文模型（首次需要联网，约 60MB）...
python -m spacy download en_core_web_sm
python -m spacy download zh_core_web_sm

echo [IntelNexus] 初始化完成！双击 run.bat 即可启动。
pause
