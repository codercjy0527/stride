@echo off
echo ============================================
echo   80/20 极化训练法跑步计划
echo ============================================
echo.
echo Cleaning old processes on port 8000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    echo Killing PID %%a...
    taskkill /f /pid %%a 2>nul
)
echo.
echo Building frontend...
cd /d %~dp0frontend
call npm run build
cd /d %~dp0
echo.
echo Starting server...
cd /d %~dp0backend
start "Running App" cmd /c "python -m uvicorn main:app --host 0.0.0.0 --port 8000"
echo.
echo Opening browser...
start http://localhost:8000
echo.
echo App is running at http://localhost:8000
echo Close this window or the "Running App" terminal to stop.
pause
