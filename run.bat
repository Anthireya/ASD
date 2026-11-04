@echo off
REM One command to start the website on Windows: double-click run.bat
cd /d "%~dp0"
if not exist venv (
  echo First time setup: creating a private Python environment...
  python -m venv venv || (echo Python 3 is required: https://www.python.org/downloads/ & pause & exit /b 1)
  venv\Scripts\python -m pip install --upgrade pip
  venv\Scripts\pip install -r requirements.txt
)
echo Starting DEEPFACE-ASD at http://127.0.0.1:5000  (close this window or press Ctrl+C to stop)
start "" http://127.0.0.1:5000
venv\Scripts\python app.py
pause
