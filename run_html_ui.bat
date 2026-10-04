@echo off
setlocal

echo ===================================================
echo   Credence Core - Digital Banking Platform
echo ===================================================

echo [1/4] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not added to your system PATH.
    echo Please install Python 3.8+ from https://www.python.org/downloads/
    pause
    exit /b
)
echo Python is installed.

echo.
echo [2/4] Checking g++ Compiler installation...
g++ --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] C++ compiler g++ is not installed or not in PATH.
    echo Please install MinGW-w64 via MSYS2 from https://www.msys2.org/
    echo Or ensure your compiler's bin folder is in the system PATH.
    pause
    exit /b
)
echo C++ Compiler g++ is installed.

echo.
echo [3/4] Checking and installing Python dependencies...
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install Python dependencies.
    echo Please check your internet connection and try again.
    pause
    exit /b
)
echo Dependencies are up to date.

echo.
echo [4/4] Starting Credence Core Banking Platform with C++ Engine...
echo The application will be available at http://127.0.0.1:5000/
echo Press Ctrl+C in this window to stop the server.
echo.
python flask_app.py

pause
