@echo off
REM =============================================================================
REM PyPSADiag Startup Script
REM Automatically sets up environment, checks dependencies and starts application
REM =============================================================================

setlocal enabledelayedexpansion

echo.
echo ========================================
echo PyPSADiag - Startup Script
echo ========================================
echo.

REM Set colors for better output
if not defined NO_COLOR (
    for /F %%a in ('echo prompt $E ^| cmd') do set "ESC=%%a"
    set "GREEN=!ESC![92m"
    set "RED=!ESC![91m"  
    set "YELLOW=!ESC![93m"
    set "BLUE=!ESC![94m"
    set "RESET=!ESC![0m"
) else (
    set "GREEN="
    set "RED="
    set "YELLOW="
    set "BLUE="
    set "RESET="
)

REM Change to script directory
cd /d "%~dp0"
set "PROJECT_DIR=%CD%"
echo %BLUE%Project Directory: %PROJECT_DIR%%RESET%
echo.

REM =============================================================================
REM Check Python installations
REM =============================================================================
echo %BLUE%Checking Python installations...%RESET%

REM Check main Python (64-bit preferred)
set "PYTHON_64="
set "PYTHON_32="

REM Try py launcher first
py --version >nul 2>&1
if !errorlevel! equ 0 (
    for /f "tokens=2" %%i in ('py --version 2^>^&1') do set "PY_VERSION=%%i"
    echo %GREEN%[OK] Python available via py launcher: !PY_VERSION!%RESET%
    set "PYTHON_64=py"
) else (
    echo %YELLOW%[WARN] py launcher not found, checking direct python...%RESET%
)

REM Check for direct python.exe
if not defined PYTHON_64 (
    python --version >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "tokens=2" %%i in ('python --version 2^>^&1') do set "PY_VERSION=%%i"
        echo %GREEN%[OK] Python available directly: !PY_VERSION!%RESET%
        set "PYTHON_64=python"
    ) else (
        echo %RED%[ERROR] No main Python installation found!%RESET%
        echo %YELLOW%Please install Python 3.8 or higher from python.org%RESET%
        pause
        exit /b 1
    )
)

REM Check 32-bit Python for VCI support
echo %BLUE%Checking 32-bit Python for VCI support...%RESET%
py -3-32 --version >nul 2>&1
if !errorlevel! equ 0 (
    for /f "tokens=2" %%i in ('py -3-32 --version 2^>^&1') do set "PY32_VERSION=%%i"
    echo %GREEN%[OK] 32-bit Python available: !PY32_VERSION!%RESET%
    set "PYTHON_32=py -3-32"
) else (
    echo %YELLOW%[WARN] 32-bit Python not found via py launcher%RESET%
    echo %YELLOW%  VCI support will be limited%RESET%
    echo %YELLOW%  Install 32-bit Python from python.org for full VCI support%RESET%
)

REM =============================================================================
REM Check VCI Requirements
REM =============================================================================
echo.
echo %BLUE%Checking VCI requirements...%RESET%

if exist "C:\AWRoot\drv\VCIAccess.dll" (
    echo %GREEN%[OK] VCI DLL found: C:\AWRoot\drv\VCIAccess.dll%RESET%
    set "VCI_AVAILABLE=1"
) else (
    echo %YELLOW%[WARN] VCI DLL not found: C:\AWRoot\drv\VCIAccess.dll%RESET%
    echo %YELLOW%  Install Diagbox or compatible VCI drivers for Evolution XS support%RESET%
    set "VCI_AVAILABLE=0"
)

REM =============================================================================
REM Setup Virtual Environment
REM =============================================================================
echo.
echo %BLUE%Setting up virtual environment...%RESET%

set "VENV_DIR=%PROJECT_DIR%\.venv"

if not exist "%VENV_DIR%" (
    echo %YELLOW%Creating new virtual environment...%RESET%
    %PYTHON_64% -m venv "%VENV_DIR%"
    if !errorlevel! neq 0 (
        echo %RED%[ERROR] Failed to create virtual environment%RESET%
        pause
        exit /b 1
    )
    echo %GREEN%[OK] Virtual environment created%RESET%
) else (
    echo %GREEN%[OK] Virtual environment exists%RESET%
)

REM Activate virtual environment
echo %BLUE%Activating virtual environment...%RESET%
call "%VENV_DIR%\Scripts\activate.bat"
if !errorlevel! neq 0 (
    echo %RED%[ERROR] Failed to activate virtual environment%RESET%
    pause
    exit /b 1
)
echo %GREEN%[OK] Virtual environment activated%RESET%

REM =============================================================================
REM Install/Update Dependencies
REM =============================================================================
echo.
echo %BLUE%Checking and installing dependencies...%RESET%

REM Upgrade pip first
echo %BLUE%Upgrading pip...%RESET%
python -m pip install --upgrade pip >nul 2>&1

REM Check if requirements.txt exists
if exist "requirements.txt" (
    echo %BLUE%Installing requirements from requirements.txt...%RESET%
    python -m pip install -r requirements.txt
    if !errorlevel! neq 0 (
        echo %RED%[ERROR] Failed to install requirements%RESET%
        pause
        exit /b 1
    )
    echo %GREEN%[OK] Requirements installed successfully%RESET%
) else (
    echo %YELLOW%! requirements.txt not found, installing essential packages...%RESET%
    
    REM Install essential packages
    echo %BLUE%Installing PySide6...%RESET%
    python -m pip install PySide6>=6.9
    
    echo %BLUE%Installing PySerial...%RESET%
    python -m pip install PySerial
    
    echo %BLUE%Installing numpy...%RESET%
    python -m pip install numpy
    
    echo %BLUE%Installing additional packages...%RESET%
    python -m pip install googletrans>=4.0.2
    
    REM For Python 3.13+ compatibility
    python -c "import sys; exit(0 if sys.version_info >= (3, 13) else 1)" >nul 2>&1
    if !errorlevel! equ 0 (
        echo %BLUE%Installing legacy-cgi for Python 3.13+...%RESET%
        python -m pip install legacy-cgi
    )
    
    echo %GREEN%[OK] Essential packages installed%RESET%
)

REM =============================================================================
REM Verify Installation
REM =============================================================================
echo.
echo %BLUE%Verifying installation...%RESET%

REM Check PySide6
python -c "import PySide6; print('PySide6:', PySide6.__version__)" >nul 2>&1
if !errorlevel! equ 0 (
    echo %GREEN%[OK] PySide6 available%RESET%
) else (
    echo %RED%[ERROR] PySide6 not available%RESET%
    pause
    exit /b 1
)

REM Check PySerial
python -c "import serial; print('PySerial:', serial.__version__)" >nul 2>&1
if !errorlevel! equ 0 (
    echo %GREEN%[OK] PySerial available%RESET%
) else (
    echo %RED%[ERROR] PySerial not available%RESET%
    pause
    exit /b 1
)

REM Check main application file
if exist "main.py" (
    echo %GREEN%[OK] main.py found%RESET%
) else (
    echo %RED%[ERROR] main.py not found in current directory%RESET%
    pause
    exit /b 1
)

REM =============================================================================
REM System Information Summary
REM =============================================================================
echo.
echo %BLUE%========================================%RESET%
echo %BLUE%System Information Summary%RESET%  
echo %BLUE%========================================%RESET%
echo %GREEN%Project Directory%RESET%: %PROJECT_DIR%
echo %GREEN%Python ^(Main^)%RESET%: %PYTHON_64%
if defined PYTHON_32 (
    echo %GREEN%Python ^(32-bit^)%RESET%: %PYTHON_32%
) else (
    echo %YELLOW%Python ^(32-bit^)%RESET%: Not available
)
if "%VCI_AVAILABLE%"=="1" (
    echo %GREEN%VCI Support%RESET%: Available
) else (
    echo %YELLOW%VCI Support%RESET%: Limited ^(DLL not found^)
)
echo %GREEN%Virtual Environment%RESET%: Active
echo.

REM =============================================================================
REM Launch Application
REM =============================================================================
echo %BLUE%========================================%RESET%
echo %BLUE%Starting PyPSADiag...%RESET%
echo %BLUE%========================================%RESET%
echo.

REM Check for command line arguments
set "LAUNCH_ARGS="
if not "%1"=="" (
    set "LAUNCH_ARGS=%*"
    echo %BLUE%Launch arguments: %LAUNCH_ARGS%%RESET%
)

REM Launch the application
echo %GREEN%Launching PyPSADiag...%RESET%
echo.
python main.py %LAUNCH_ARGS%

REM =============================================================================
REM Cleanup and Exit
REM =============================================================================
echo.
echo %BLUE%========================================%RESET%
echo %BLUE%PyPSADiag Closed%RESET%
echo %BLUE%========================================%RESET%

REM Deactivate virtual environment
deactivate >nul 2>&1

echo.
echo %YELLOW%Press any key to exit...%RESET%
pause >nul

endlocal