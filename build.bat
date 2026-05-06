@echo off
chcp 65001 >nul
echo ============================================================
echo   百佑 LawyerClaw - Windows Build Script
echo ============================================================
echo.

REM Check project root
if not exist "backend\app.py" (
    echo [ERROR] Please run this script from the project root!
    echo         Current dir: %CD%
    pause
    exit /b 1
)

REM ==================== Build venv ====================
set BUILD_VENV=backend\build_venv

echo [1/5] Preparing build virtual environment...
if exist "%BUILD_VENV%\Scripts\python.exe" (
    echo       build_venv already exists, reusing...
) else (
    echo       Creating clean build_venv...
    python -m venv "%BUILD_VENV%"
    if errorlevel 1 (
        echo [ERROR] Failed to create venv! Make sure Python 3.12 is in PATH.
        pause
        exit /b 1
    )
)

REM Activate build venv
call "%BUILD_VENV%\Scripts\activate.bat"

REM Install dependencies from requirements.txt
echo [2/5] Installing dependencies from requirements.txt...
pip install -r backend\requirements.txt --quiet
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies!
    pause
    exit /b 1
)

REM Install PyInstaller
echo [3/5] Checking PyInstaller...
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo       Installing PyInstaller...
    pip install pyinstaller
)

REM Check frontend build
echo [4/5] Checking frontend build...
if not exist "frontend\dist\index.html" (
    echo [WARN] Frontend not built! Run "npm run build" in frontend/ first.
    echo        Continuing without frontend...
) else (
    echo       Frontend dist is ready.
)

REM Clean old build artifacts
echo [5/5] Cleaning old build and running PyInstaller...
if exist "build" rmdir /s /q "build"
if exist "dist\lawyerclaw" rmdir /s /q "dist\lawyerclaw"
echo.
pyinstaller lawyerclaw.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed! Check errors above.
    pause
    exit /b 1
)

REM Create runtime directories
echo.
echo [POST] Creating runtime directories...
if not exist "dist\lawyerclaw\backend\data" mkdir "dist\lawyerclaw\backend\data"
if not exist "dist\lawyerclaw\backend\uploads" mkdir "dist\lawyerclaw\backend\uploads"
if not exist "dist\lawyerclaw\backend\output" mkdir "dist\lawyerclaw\backend\output"
if not exist "dist\lawyerclaw\backend\plugins" mkdir "dist\lawyerclaw\backend\plugins"

REM Copy .env
if exist "backend\.env" (
    echo [POST] Copying .env config...
    copy /Y "backend\.env" "dist\lawyerclaw\backend\.env" >nul
)

REM Deactivate build venv
call deactivate

echo.
echo ============================================================
echo   Build Complete!
echo ============================================================
echo.
echo   Output:  dist\lawyerclaw\
echo   EXE:     dist\lawyerclaw\lawyerclaw.exe
echo.
echo   To run:
echo     1. Go to dist\lawyerclaw\
echo     2. Edit backend\.env with your API keys
echo     3. Double-click lawyerclaw.exe
echo     4. Open http://localhost:5004
echo.
echo   To distribute: zip the entire dist\lawyerclaw\ folder.
echo.
echo   [TIP] build_venv is kept for faster rebuilds.
echo         To force a clean rebuild, delete backend\build_venv\
echo ============================================================
pause
