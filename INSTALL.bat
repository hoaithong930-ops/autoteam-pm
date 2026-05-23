@echo off
echo.
echo ================================================
echo   AutoTeam PM - First Time Setup
echo   Automation Project Manager v2.0
echo ================================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found!
    echo Please download Python from: https://www.python.org/downloads/
    echo IMPORTANT: Check "Add Python to PATH" during install.
    pause
    exit /b 1
)

echo [OK] Python found.
echo.
echo [1/3] Creating virtual environment...
python -m venv venv
if %errorlevel% neq 0 (
    echo [ERROR] Failed to create venv.
    pause
    exit /b 1
)

echo [2/3] Installing packages (FastAPI + Uvicorn)...
call venv\Scripts\activate.bat
pip install fastapi "uvicorn[standard]" --quiet
if %errorlevel% neq 0 (
    echo [ERROR] pip install failed. Check internet connection.
    pause
    exit /b 1
)

echo [3/3] Creating data folder...
if not exist "data" mkdir data

echo.
echo ================================================
echo   Setup complete! Run START_SERVER.bat next.
echo ================================================
echo.
pause
