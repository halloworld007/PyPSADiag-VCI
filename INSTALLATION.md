# Installation Guide

## Prerequisites

- Windows 10/11 (64-bit recommended)
- Python 3.12 or higher
- Git (for cloning repository)

## Step-by-Step Installation

### 1. Clone Repository
```bash
git clone https://github.com/YOUR_USERNAME/PyPSADiag.git
cd PyPSADiag
```

### 2. Python Setup
```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. VCI Driver Setup (For VCI Users Only)

**Important**: VCI drivers are required for Evolution XS VCI support.

1. **Install VCI Drivers**:
   - Install Diagbox software (recommended)
   - Alternative: Install PSA XS Evolution VCI drivers separately
   - Restart computer after installation

2. **Verify Installation**:
   - Check that `C:\AWRoot\drv\VCIAccess.dll` exists
   - Verify VCI hardware is detected in Device Manager

3. **32-bit Python for VCI**:
   ```bash
   # Download and install Python 3.12 32-bit from python.org
   # Test with: py -3-32 --version
   ```

### 4. Test Installation
```bash
# Test basic functionality
python main.py --simu

# Test with language
python main.py --lang nl --simu
```

## Troubleshooting

### Common Issues

**Python not found**:
- Ensure Python is in PATH
- Use full path: `C:\Python312\python.exe`

**VCI DLL missing**:
- Install proper VCI drivers
- Check `C:\AWRoot\drv\VCIAccess.dll` exists

**Permission errors**:
- Run Command Prompt as Administrator
- Check antivirus software

**Import errors**:
- Verify virtual environment is active
- Reinstall requirements: `pip install -r requirements.txt --force-reinstall`

## Hardware Setup

### Arduino CAN Interface
1. Connect Arduino CAN shield/module
2. Upload compatible firmware
3. Connect to vehicle OBD port

### VCI Interface
1. Connect VCI to computer via USB
2. Connect VCI to vehicle diagnostic connector
3. Verify connection in Device Manager

For more help, see README.md or contact support.