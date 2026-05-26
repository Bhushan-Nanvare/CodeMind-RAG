@echo off
echo ===================================================
echo Starting CodeMind-RAG Services
echo ===================================================
echo.

echo [1/2] Checking Backend API setup...
if not exist "apps\api\venv" (
    echo Creating Python virtual environment...
    cd apps\api
    python -m venv venv
    cd ..\..
)

if not exist "apps\api\.env" (
    if exist "apps\api\.env.example" (
        echo Setting up default .env for API...
        copy apps\api\.env.example apps\api\.env >nul 2>&1
    )
)

echo [2/2] Checking Node.js dependencies...
call pnpm install

echo.
echo ===================================================
echo LAUNCHING SERVICES
echo ===================================================
echo.
echo - The Backend API will start in a new window.
echo - The Web Frontend will start in this window.
echo.
echo To stop everything, focus this window and press Ctrl+C, 
echo then close the Backend window.
echo.
timeout /t 3 /nobreak >nul

:: Start backend in a new command window
start "CodeMind-RAG Backend" cmd /k "TITLE CodeMind-RAG Backend && cd apps\api && call venv\Scripts\activate && pip install -r requirements.txt && echo. && echo Backend is running at: http://127.0.0.1:8000/docs && echo. && uvicorn main:app --reload --host 127.0.0.1 --port 8000"

:: Start frontend directly in the current window
echo Starting Web Frontend...
pnpm --filter @workspace/web dev
