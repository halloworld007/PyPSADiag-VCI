@echo off
REM =============================================================================
REM Create Desktop Shortcuts for PyPSADiag
REM =============================================================================

setlocal enabledelayedexpansion

echo.
echo Creating Desktop Shortcuts for PyPSADiag...
echo.

set "PROJECT_DIR=%~dp0"
set "DESKTOP=%USERPROFILE%\Desktop"

REM Create main shortcut
set "SHORTCUT_NAME=PyPSADiag"
set "TARGET=%PROJECT_DIR%start_pypsa.bat"
set "WORKING_DIR=%PROJECT_DIR%"
set "ICON_PATH=%PROJECT_DIR%main.py"

echo Creating "%SHORTCUT_NAME%" shortcut...

powershell -Command "$WshShell = New-Object -comObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%DESKTOP%\%SHORTCUT_NAME%.lnk'); $Shortcut.TargetPath = '%TARGET%'; $Shortcut.WorkingDirectory = '%WORKING_DIR%'; $Shortcut.Save()"

if exist "%DESKTOP%\%SHORTCUT_NAME%.lnk" (
    echo ✓ Main shortcut created successfully
) else (
    echo ✗ Failed to create main shortcut
)

REM Create language-specific shortcuts
set languages[0]=de:Deutsch
set languages[1]=nl:Nederlands  
set languages[2]=it:Italiano
set languages[3]=pl:Polski
set languages[4]=uk:Українська

for /L %%i in (0,1,4) do (
    for /f "tokens=1,2 delims=:" %%a in ("!languages[%%i]!") do (
        set "LANG_CODE=%%a"
        set "LANG_NAME=%%b"
        set "LANG_SHORTCUT=PyPSADiag - !LANG_NAME!"
        
        echo Creating "!LANG_SHORTCUT!" shortcut...
        
        powershell -Command "$WshShell = New-Object -comObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%DESKTOP%\!LANG_SHORTCUT!.lnk'); $Shortcut.TargetPath = '%TARGET%'; $Shortcut.Arguments = '!LANG_CODE!'; $Shortcut.WorkingDirectory = '%WORKING_DIR%'; $Shortcut.Save()"
        
        if exist "%DESKTOP%\!LANG_SHORTCUT!.lnk" (
            echo ✓ !LANG_NAME! shortcut created
        ) else (
            echo ✗ Failed to create !LANG_NAME! shortcut
        )
    )
)

REM Create simulation mode shortcut
set "SIM_SHORTCUT=PyPSADiag - Simulation"
echo Creating "%SIM_SHORTCUT%" shortcut...

powershell -Command "$WshShell = New-Object -comObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%DESKTOP%\%SIM_SHORTCUT%.lnk'); $Shortcut.TargetPath = '%PROJECT_DIR%start_pypsa.ps1'; $Shortcut.Arguments = '-Simu'; $Shortcut.WorkingDirectory = '%WORKING_DIR%'; $Shortcut.Save()"

if exist "%DESKTOP%\%SIM_SHORTCUT%.lnk" (
    echo ✓ Simulation shortcut created
) else (
    echo ✗ Failed to create simulation shortcut  
)

echo.
echo Desktop shortcuts created in: %DESKTOP%
echo.
echo Available shortcuts:
echo - PyPSADiag (Main application)
echo - PyPSADiag - Deutsch
echo - PyPSADiag - Nederlands
echo - PyPSADiag - Italiano  
echo - PyPSADiag - Polski
echo - PyPSADiag - Українська
echo - PyPSADiag - Simulation
echo.

pause