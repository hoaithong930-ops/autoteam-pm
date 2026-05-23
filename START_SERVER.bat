@echo off
echo.
echo ================================================
echo   AutoTeam PM - Starting Server
echo   Automation Project Manager v2.0
echo ================================================
echo.

if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Not installed yet! Please run INSTALL.bat first.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

echo [*] Server starting at: http://localhost:8000
echo [*] API Documentation:  http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop the server.
echo.

start "" /b cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8000"

cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

pause
