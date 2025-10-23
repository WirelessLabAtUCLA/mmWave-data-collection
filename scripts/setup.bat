@echo off
REM Setup script for Windows (for development only)
REM Note: This project is designed for Ubuntu/macOS deployment

echo ===================================
echo mmWave Data Collection Setup
echo ===================================
echo.
echo WARNING: This project requires Ubuntu or macOS for deployment.
echo This setup is for development/testing on Windows only.
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found!
    exit /b 1
)

echo Python: 
python --version

REM Install Python dependencies
echo.
echo Installing Python dependencies...
pip install -r requirements.txt

REM Create directories
echo.
echo Creating data directories...
if not exist "data" mkdir data
if not exist "logs" mkdir logs

echo.
echo ===================================
echo Setup complete!
echo ===================================
echo.
echo Note: ROS2 build must be done on Ubuntu/macOS
echo For deployment, use Ubuntu or macOS
echo.

pause

