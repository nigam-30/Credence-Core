@echo off
setlocal
echo ===================================================
echo   Credence Core - Local Development Runner
echo ===================================================

echo [1/3] Verifying Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    pause
    exit /b 1
)

echo [2/3] Checking dependencies...
python -m pip install -r requirements.txt >nul 2>&1

echo [3/3] Starting Credence Core Backend...
echo Application URL: http://127.0.0.1:5000/
python -m gunicorn --config gunicorn_config.py "backend.app:create_app()"
pause
