@echo off
echo ========================================
echo   AI Council Web Application
echo ========================================
echo.

REM Check if backend dependencies are installed
echo [1/3] Checking dependencies...
python -c "import fastapi; import ai_council" 2>nul
if errorlevel 1 (
    echo Installing backend dependencies...
    cd backend
    python -m pip install -r requirements.txt
    cd ..
)

REM Check for .env file
if not exist "backend\.env" (
    echo.
    echo WARNING: No .env file found!
    echo Please create backend\.env with your API keys.
    echo Example:
    echo   OPENAI_API_KEY=your_key_here
    echo   ANTHROPIC_API_KEY=your_key_here
    echo.
    pause
)

REM Start backend
echo.
echo [2/3] Starting backend server...
start "AI Council Backend" cmd /k "cd backend && python main.py"

REM Wait for backend to start
timeout /t 3 /nobreak >nul

REM Start frontend
echo [3/3] Opening frontend...
timeout /t 2 /nobreak >nul
start http://localhost:8000/api/status
start "AI Council Frontend Server" cmd /k "cd frontend && python -m http.server 8080"
timeout /t 2 /nobreak >nul
start http://localhost:8080/

echo.
echo ========================================
echo   AI Council is running!
echo ========================================
echo.
echo Backend API: http://localhost:8000
echo Frontend: http://localhost:8080
echo.
echo Press Ctrl+C in the backend window to stop
echo.
pause
