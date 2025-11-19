@echo off
echo =========================================
echo GALA SEATING SYSTEM - QUICK START
echo =========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo X Python is not installed!
    echo Please install Python 3.11 or higher
    pause
    exit /b 1
)

echo Python detected
python --version
echo.

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    echo Virtual environment created
) else (
    echo Virtual environment already exists
)

echo.

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Virtual environment activated
echo.

REM Install requirements
echo Installing dependencies...
pip install -q -r requirements.txt

echo Dependencies installed
echo.

REM Run the application
echo =========================================
echo Starting Gala Seating System...
echo =========================================
echo.
echo The application will be available at:
echo http://localhost:5000
echo.
echo Press Ctrl+C to stop the server
echo.

python app.py

pause
