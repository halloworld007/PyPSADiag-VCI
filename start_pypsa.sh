#!/bin/bash
# =============================================================================
# PyPSADiag Startup Script (Linux/macOS)
# Automatically sets up environment, checks dependencies and starts application
# =============================================================================

# Colors for better output
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    CYAN='\033[0;36m'
    RESET='\033[0m'
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    CYAN=''
    RESET=''
fi

# Helper functions
print_status() {
    case $2 in
        "success") echo -e "${GREEN}✓${RESET} $1" ;;
        "error") echo -e "${RED}✗${RESET} $1" ;;
        "warning") echo -e "${YELLOW}!${RESET} $1" ;;
        "info") echo -e "${BLUE}»${RESET} $1" ;;
        *) echo "$1" ;;
    esac
}

print_header() {
    echo -e "${BLUE}$1${RESET}"
}

# Show help
show_help() {
    echo -e "\n${CYAN}PyPSADiag Startup Script - Help${RESET}"
    echo -e "${CYAN}========================================${RESET}"
    echo -e "\nUsage: ./start_pypsa.sh [OPTIONS]"
    echo -e "\nOptions:"
    echo "  --lang <code>     Set language (nl, de, it, pl, uk)"
    echo "  --simu            Start in simulation mode"
    echo "  --scan            Start in scan mode"
    echo "  --checkcalc       Run seed/key calculation test"
    echo "  --skip-venv       Skip virtual environment setup"
    echo "  --dev             Enable development mode"
    echo "  --help            Show this help message"
    echo -e "\nExamples:"
    echo "  ./start_pypsa.sh --lang de"
    echo "  ./start_pypsa.sh --simu --lang nl"
    echo "  ./start_pypsa.sh --dev"
    exit 0
}

# Parse command line arguments
LANG_ARG=""
LAUNCH_ARGS=()
SKIP_VENV=false
DEV_MODE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --lang)
            LANG_ARG="$2"
            LAUNCH_ARGS+=("--lang" "$2")
            shift 2
            ;;
        --simu)
            LAUNCH_ARGS+=("--simu")
            shift
            ;;
        --scan)
            LAUNCH_ARGS+=("--scan")
            shift
            ;;
        --checkcalc)
            LAUNCH_ARGS+=("--checkcalc")
            shift
            ;;
        --skip-venv)
            SKIP_VENV=true
            shift
            ;;
        --dev)
            DEV_MODE=true
            shift
            ;;
        --help|-h)
            show_help
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            ;;
    esac
done

# Start main execution
echo ""
print_header "========================================"
print_header "PyPSADiag - Startup Script (Unix/Linux)"
print_header "========================================"
echo ""

# Set working directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"
print_status "Project Directory: $PROJECT_DIR" "info"
echo ""

# =============================================================================
# Check Python installations
# =============================================================================
print_header "Checking Python installations..."

PYTHON_CMD=""

# Check for python3 first (preferred)
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1)
    print_status "Python3 available: ${PYTHON_VERSION#Python }" "success"
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_VERSION=$(python --version 2>&1)
    # Check if it's Python 3
    if [[ $PYTHON_VERSION == *"Python 3"* ]]; then
        print_status "Python available: ${PYTHON_VERSION#Python }" "success"
        PYTHON_CMD="python"
    else
        print_status "Found Python 2, but Python 3 is required" "error"
        print_status "Please install Python 3.8 or higher" "warning"
        exit 1
    fi
else
    print_status "No Python installation found!" "error"
    print_status "Please install Python 3.8 or higher" "warning"
    exit 1
fi

# Note about VCI support on Linux/macOS
echo ""
print_header "VCI Support Information..."
print_status "Evolution XS VCI is Windows-only (requires VCIAccess.dll)" "warning"
print_status "On Linux/macOS, only Arduino-based adapters are supported" "warning"

# =============================================================================
# Setup Virtual Environment
# =============================================================================
if [ "$SKIP_VENV" != true ]; then
    echo ""
    print_header "Setting up virtual environment..."

    VENV_DIR="$PROJECT_DIR/.venv"

    if [ ! -d "$VENV_DIR" ]; then
        print_status "Creating new virtual environment..." "warning"
        if $PYTHON_CMD -m venv "$VENV_DIR"; then
            print_status "Virtual environment created" "success"
        else
            print_status "Failed to create virtual environment" "error"
            exit 1
        fi
    else
        print_status "Virtual environment exists" "success"
    fi

    # Activate virtual environment
    print_status "Activating virtual environment..." "info"
    if [ -f "$VENV_DIR/bin/activate" ]; then
        source "$VENV_DIR/bin/activate"
        print_status "Virtual environment activated" "success"
    else
        print_status "Failed to find activation script" "error"
        exit 1
    fi
fi

# =============================================================================
# Install/Update Dependencies
# =============================================================================
echo ""
print_header "Checking and installing dependencies..."

# Upgrade pip
print_status "Upgrading pip..." "info"
python -m pip install --upgrade pip --quiet

# Install requirements
if [ -f "requirements.txt" ]; then
    print_status "Installing requirements from requirements.txt..." "info"
    if python -m pip install -r requirements.txt; then
        print_status "Requirements installed successfully" "success"
    else
        print_status "Failed to install requirements" "error"
        exit 1
    fi
else
    print_status "requirements.txt not found, installing essential packages..." "warning"
    
    packages=("PySide6>=6.9" "PySerial" "numpy" "googletrans>=4.0.2")
    
    # Check if Python 3.13+ for legacy-cgi
    python_version=$(python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
    if [[ $(echo "$python_version >= 3.13" | bc -l 2>/dev/null) -eq 1 ]]; then
        packages+=("legacy-cgi")
        print_status "Adding legacy-cgi for Python 3.13+" "info"
    fi
    
    for package in "${packages[@]}"; do
        print_status "Installing $package..." "info"
        if python -m pip install "$package" --quiet; then
            print_status "$package installed" "success"
        else
            print_status "Failed to install $package" "error"
        fi
    done
fi

# =============================================================================
# Verify Installation
# =============================================================================
echo ""
print_header "Verifying installation..."

# Check PySide6
if python -c "import PySide6; print('PySide6:', PySide6.__version__)" &> /dev/null; then
    pyside_version=$(python -c "import PySide6; print(PySide6.__version__)" 2>/dev/null)
    print_status "PySide6 available: $pyside_version" "success"
else
    print_status "PySide6 not available" "error"
    exit 1
fi

# Check PySerial
if python -c "import serial; print('PySerial:', serial.__version__)" &> /dev/null; then
    serial_version=$(python -c "import serial; print(serial.__version__)" 2>/dev/null)
    print_status "PySerial available: $serial_version" "success"
else
    print_status "PySerial not available" "error"
    exit 1
fi

# Check main application
if [ -f "main.py" ]; then
    print_status "main.py found" "success"
else
    print_status "main.py not found in current directory" "error"
    exit 1
fi

# =============================================================================
# System Information Summary
# =============================================================================
echo ""
print_header "========================================"
print_header "System Information Summary"
print_header "========================================"
echo -e "${GREEN}Project Directory:${RESET} $PROJECT_DIR"
echo -e "${GREEN}Python:${RESET} $PYTHON_CMD"
echo -e "${YELLOW}VCI Support:${RESET} Not available (Windows only)"
if [ "$SKIP_VENV" != true ]; then
    echo -e "${GREEN}Virtual Environment:${RESET} Active"
fi
echo ""

# =============================================================================
# Launch Application
# =============================================================================
print_header "========================================"
print_header "Starting PyPSADiag..."
print_header "========================================"
echo ""

if [ ${#LAUNCH_ARGS[@]} -gt 0 ]; then
    print_status "Launch arguments: ${LAUNCH_ARGS[*]}" "info"
fi

print_status "Launching PyPSADiag..." "success"
echo ""

# Launch the application
if [ "$DEV_MODE" = true ]; then
    # Development mode - show more verbose output
    python main.py "${LAUNCH_ARGS[@]}"
else
    # Normal mode
    python main.py "${LAUNCH_ARGS[@]}"
fi

# =============================================================================
# Cleanup and Exit
# =============================================================================
echo ""
print_header "========================================"
print_header "PyPSADiag Closed"
print_header "========================================"

if [ "$SKIP_VENV" != true ] && [ -n "$VIRTUAL_ENV" ]; then
    print_status "Deactivating virtual environment..." "info"
    deactivate 2>/dev/null
fi

echo ""
print_status "Press any key to exit..." "info"
read -n 1 -s