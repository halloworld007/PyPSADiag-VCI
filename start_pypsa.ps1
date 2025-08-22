# =============================================================================
# PyPSADiag Startup Script (PowerShell)
# Automatically sets up environment, checks dependencies and starts application
# =============================================================================

param(
    [string]$Lang = "",
    [switch]$Simu = $false,
    [switch]$Scan = $false,
    [switch]$CheckCalc = $false,
    [switch]$Help = $false,
    [switch]$SkipVenv = $false,
    [switch]$DevMode = $false
)

# Enable colors in PowerShell
$Host.UI.RawUI.WindowTitle = "PyPSADiag Startup"

function Write-ColorText {
    param([string]$Text, [string]$Color = "White")
    
    $colors = @{
        "Red" = [ConsoleColor]::Red
        "Green" = [ConsoleColor]::Green  
        "Yellow" = [ConsoleColor]::Yellow
        "Blue" = [ConsoleColor]::Blue
        "Cyan" = [ConsoleColor]::Cyan
        "White" = [ConsoleColor]::White
        "Gray" = [ConsoleColor]::Gray
    }
    
    Write-Host $Text -ForegroundColor $colors[$Color]
}

function Write-Status {
    param([string]$Text, [string]$Status = "Info")
    
    switch ($Status) {
        "Success" { Write-Host "✓ " -ForegroundColor Green -NoNewline; Write-Host $Text }
        "Error" { Write-Host "✗ " -ForegroundColor Red -NoNewline; Write-Host $Text }  
        "Warning" { Write-Host "! " -ForegroundColor Yellow -NoNewline; Write-Host $Text }
        "Info" { Write-Host "» " -ForegroundColor Blue -NoNewline; Write-Host $Text }
        default { Write-Host $Text }
    }
}

# Show help
if ($Help) {
    Write-ColorText "`nPyPSADiag Startup Script - Help" "Cyan"
    Write-ColorText "=" * 40 "Cyan"
    Write-Host "`nUsage: .\start_pypsa.ps1 [OPTIONS]"
    Write-Host "`nOptions:"
    Write-Host "  -Lang <code>    Set language (nl, de, it, pl, uk)"
    Write-Host "  -Simu           Start in simulation mode"
    Write-Host "  -Scan           Start in scan mode" 
    Write-Host "  -CheckCalc      Run seed/key calculation test"
    Write-Host "  -SkipVenv       Skip virtual environment setup"
    Write-Host "  -DevMode        Enable development mode"
    Write-Host "  -Help           Show this help message"
    Write-Host "`nExamples:"
    Write-Host "  .\start_pypsa.ps1 -Lang de"
    Write-Host "  .\start_pypsa.ps1 -Simu -Lang nl"
    Write-Host "  .\start_pypsa.ps1 -DevMode"
    exit 0
}

# Start main execution
Write-Host ""
Write-ColorText "========================================" "Blue"
Write-ColorText "PyPSADiag - Startup Script (PowerShell)" "Blue"  
Write-ColorText "========================================" "Blue"
Write-Host ""

# Set working directory
$ProjectDir = $PSScriptRoot
Set-Location $ProjectDir
Write-Status "Project Directory: $ProjectDir" "Info"
Write-Host ""

# =============================================================================
# Check Python installations
# =============================================================================
Write-ColorText "Checking Python installations..." "Blue"

# Check main Python
$Python64 = $null
$Python32 = $null

# Try py launcher first
try {
    $pyVersion = & py --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Status "Python available via py launcher: $($pyVersion -replace 'Python ', '')" "Success"
        $Python64 = "py"
    }
} catch {
    Write-Status "py launcher not found, checking direct python..." "Warning"
}

# Check direct python if py launcher failed
if (-not $Python64) {
    try {
        $pyVersion = & python --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Status "Python available directly: $($pyVersion -replace 'Python ', '')" "Success"
            $Python64 = "python"
        }
    } catch {
        Write-Status "No main Python installation found!" "Error"
        Write-Status "Please install Python 3.8 or higher from python.org" "Warning"
        Read-Host "Press Enter to exit"
        exit 1
    }
}

# Check 32-bit Python for VCI support
Write-ColorText "Checking 32-bit Python for VCI support..." "Blue"
try {
    $py32Version = & py -3-32 --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Status "32-bit Python available: $($py32Version -replace 'Python ', '')" "Success"
        $Python32 = "py -3-32"
    }
} catch {
    Write-Status "32-bit Python not found via py launcher" "Warning"
    Write-Status "VCI support will be limited" "Warning" 
    Write-Status "Install 32-bit Python from python.org for full VCI support" "Warning"
}

# =============================================================================
# Check VCI Requirements  
# =============================================================================
Write-Host ""
Write-ColorText "Checking VCI requirements..." "Blue"

$VciDllPath = "C:\AWRoot\drv\VCIAccess.dll"
if (Test-Path $VciDllPath) {
    Write-Status "VCI DLL found: $VciDllPath" "Success"
    $VciAvailable = $true
} else {
    Write-Status "VCI DLL not found: $VciDllPath" "Warning"
    Write-Status "Install Diagbox or compatible VCI drivers for Evolution XS support" "Warning"
    $VciAvailable = $false
}

# =============================================================================
# Setup Virtual Environment
# =============================================================================
if (-not $SkipVenv) {
    Write-Host ""
    Write-ColorText "Setting up virtual environment..." "Blue"

    $VenvDir = Join-Path $ProjectDir ".venv"

    if (-not (Test-Path $VenvDir)) {
        Write-Status "Creating new virtual environment..." "Warning"
        try {
            & $Python64 -m venv $VenvDir
            if ($LASTEXITCODE -ne 0) { throw "venv creation failed" }
            Write-Status "Virtual environment created" "Success"
        } catch {
            Write-Status "Failed to create virtual environment: $_" "Error"
            Read-Host "Press Enter to exit"
            exit 1
        }
    } else {
        Write-Status "Virtual environment exists" "Success"
    }

    # Activate virtual environment
    Write-Status "Activating virtual environment..." "Info"
    $ActivateScript = Join-Path $VenvDir "Scripts\Activate.ps1"
    
    if (Test-Path $ActivateScript) {
        try {
            & $ActivateScript
            Write-Status "Virtual environment activated" "Success"
        } catch {
            Write-Status "Failed to activate virtual environment: $_" "Error"
            Read-Host "Press Enter to exit" 
            exit 1
        }
    } else {
        Write-Status "Activation script not found, using direct python path" "Warning"
        $env:PATH = "$VenvDir\Scripts;" + $env:PATH
    }
}

# =============================================================================
# Install/Update Dependencies
# =============================================================================
Write-Host ""
Write-ColorText "Checking and installing dependencies..." "Blue"

# Upgrade pip
Write-Status "Upgrading pip..." "Info"
try {
    & python -m pip install --upgrade pip --quiet
    Write-Status "pip upgraded" "Success"
} catch {
    Write-Status "pip upgrade failed, continuing..." "Warning"
}

# Install requirements
$RequirementsFile = Join-Path $ProjectDir "requirements.txt"
if (Test-Path $RequirementsFile) {
    Write-Status "Installing requirements from requirements.txt..." "Info"
    try {
        & python -m pip install -r $RequirementsFile
        if ($LASTEXITCODE -ne 0) { throw "requirements installation failed" }
        Write-Status "Requirements installed successfully" "Success"
    } catch {
        Write-Status "Failed to install requirements: $_" "Error"
        Read-Host "Press Enter to exit"
        exit 1
    }
} else {
    Write-Status "requirements.txt not found, installing essential packages..." "Warning"
    
    $packages = @(
        "PySide6>=6.9",
        "PySerial", 
        "numpy",
        "googletrans>=4.0.2"
    )
    
    # Check if Python 3.13+ for legacy-cgi
    try {
        $pythonVersion = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ([version]$pythonVersion -ge [version]"3.13") {
            $packages += "legacy-cgi"
            Write-Status "Adding legacy-cgi for Python 3.13+" "Info"
        }
    } catch {
        # Ignore version check errors
    }
    
    foreach ($package in $packages) {
        Write-Status "Installing $package..." "Info"
        try {
            & python -m pip install $package --quiet
            Write-Status "$package installed" "Success"
        } catch {
            Write-Status "Failed to install $package" "Error"
        }
    }
}

# =============================================================================
# Verify Installation
# =============================================================================
Write-Host ""
Write-ColorText "Verifying installation..." "Blue"

# Check PySide6
try {
    $pysideVersion = & python -c "import PySide6; print(PySide6.__version__)" 2>$null
    Write-Status "PySide6 available: $pysideVersion" "Success"
} catch {
    Write-Status "PySide6 not available" "Error"
    Read-Host "Press Enter to exit"
    exit 1
}

# Check PySerial
try {
    $serialVersion = & python -c "import serial; print(serial.__version__)" 2>$null
    Write-Status "PySerial available: $serialVersion" "Success"  
} catch {
    Write-Status "PySerial not available" "Error"
    Read-Host "Press Enter to exit"
    exit 1
}

# Check main application
$MainApp = Join-Path $ProjectDir "main.py"
if (Test-Path $MainApp) {
    Write-Status "main.py found" "Success"
} else {
    Write-Status "main.py not found in current directory" "Error"
    Read-Host "Press Enter to exit"
    exit 1
}

# =============================================================================
# System Information Summary  
# =============================================================================
Write-Host ""
Write-ColorText "========================================" "Blue"
Write-ColorText "System Information Summary" "Blue"
Write-ColorText "========================================" "Blue"
Write-Host "Project Directory: " -NoNewline; Write-ColorText $ProjectDir "Green"
Write-Host "Python (Main): " -NoNewline; Write-ColorText $Python64 "Green"
if ($Python32) {
    Write-Host "Python (32-bit): " -NoNewline; Write-ColorText $Python32 "Green"
} else {
    Write-Host "Python (32-bit): " -NoNewline; Write-ColorText "Not available" "Yellow"
}
if ($VciAvailable) {
    Write-Host "VCI Support: " -NoNewline; Write-ColorText "Available" "Green"
} else {
    Write-Host "VCI Support: " -NoNewline; Write-ColorText "Limited (DLL not found)" "Yellow"  
}
if (-not $SkipVenv) {
    Write-Host "Virtual Environment: " -NoNewline; Write-ColorText "Active" "Green"
}
Write-Host ""

# =============================================================================
# Build Launch Arguments
# =============================================================================
$LaunchArgs = @()

if ($Lang) { $LaunchArgs += "--lang", $Lang }
if ($Simu) { $LaunchArgs += "--simu" }
if ($Scan) { $LaunchArgs += "--scan" } 
if ($CheckCalc) { $LaunchArgs += "--checkcalc" }

# =============================================================================
# Launch Application
# =============================================================================
Write-ColorText "========================================" "Blue"  
Write-ColorText "Starting PyPSADiag..." "Blue"
Write-ColorText "========================================" "Blue"
Write-Host ""

if ($LaunchArgs.Count -gt 0) {
    Write-Status "Launch arguments: $($LaunchArgs -join ' ')" "Info"
}

Write-Status "Launching PyPSADiag..." "Success"
Write-Host ""

try {
    if ($DevMode) {
        # Development mode - show more verbose output
        & python main.py @LaunchArgs
    } else {
        # Normal mode
        & python main.py @LaunchArgs
    }
} catch {
    Write-Status "Application error: $_" "Error"
    Read-Host "Press Enter to exit"
    exit 1
}

# =============================================================================
# Cleanup and Exit  
# =============================================================================
Write-Host ""
Write-ColorText "========================================" "Blue"
Write-ColorText "PyPSADiag Closed" "Blue" 
Write-ColorText "========================================" "Blue"

if (-not $SkipVenv) {
    Write-Status "Deactivating virtual environment..." "Info"
    deactivate 2>$null
}

Write-Host ""
Write-Status "Press any key to exit..." "Info"
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")