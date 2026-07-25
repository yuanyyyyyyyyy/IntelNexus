@echo off
setlocal
REM IntelNexus one-click launcher (uses conda base env, no manual activation needed)
REM Usage:
REM   run.bat ui              -> start Web UI
REM   run.bat search -q ...   -> CLI search
REM   run.bat briefing / scheduler
REM Note: deps and spaCy model live in conda base; first-time missing model -> run setup.bat

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
  echo [IntelNexus] conda not found, please install Anaconda/Miniconda.
  pause
  exit /b 1
)

call "%CONDA_ROOT%\Scripts\activate.bat" base

REM Clear ghost proxy vars inherited from the Shell. load_dotenv() will not
REM overwrite existing env vars, so clearing them lets .env proxy settings apply.
set "HTTP_PROXY="
set "HTTPS_PROXY="
set "USE_TOR="

python "%~dp0main.py" %*
