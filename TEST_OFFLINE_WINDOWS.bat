@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run START_LOCAL_WINDOWS.bat first to install dependencies.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python -m unittest discover -s tests -v
pause
