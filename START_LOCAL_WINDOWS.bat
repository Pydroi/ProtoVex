@echo off
setlocal
cd /d "%~dp0"
echo ========================================
echo     ProtoVex Local Release Test
echo ========================================
if not exist ".env" (
  echo.
  echo Missing .env file.
  echo Copy your PRIVATE existing V2 .env into this folder.
  echo Keep keys secret - never upload them to GitHub.
  echo.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo Creating isolated Python environment...
  py -m venv .venv
  if errorlevel 1 (
    echo Python setup failed. Install Python 3.11+ and try again.
    pause
    exit /b 1
  )
)
call .venv\Scripts\activate.bat
echo Installing package dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Dependency installation failed. Read the error above.
  pause
  exit /b 1
)
echo.
echo Open http://127.0.0.1:5000 in your web browser.
echo Press Ctrl+C to stop the server.
echo.
python app.py
pause
