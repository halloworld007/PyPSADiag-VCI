# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PyPSADiag is a Python application for sending diagnostic frames over CAN-BUS to PSA/Stellantis based cars. This is an educational tool for automotive diagnostics using various protocols (UDS, KWP).

## Development Setup

### Prerequisites
- Python 3.12 or above
- Virtual environment recommended

### Installation Commands
```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment (Windows)
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Running the Application
```bash
# Run with default language (English)
python main.py

# Run with specific language
python main.py --lang nl

# Run in simulation mode
python main.py --simu

# Run with scan mode
python main.py --scan

# Test seed/key calculations
python main.py --checkcalc
```

## Architecture

### Core Components

- **main.py**: Application entry point and main window controller
- **PyPSADiagGUI.py**: GUI layout and widget management using PySide6
- **DiagnosticCommunication.py**: Handles communication protocols (UDS, KWP_IS, KWP_HAB)
- **SerialController.py** / **SerialPort.py**: Serial communication with hardware
- **SeedKeyAlgorithm.py**: Security algorithms for ECU authentication
- **EcuZoneTreeView.py**: Tree view for displaying ECU zones and data

### ECU Configuration System

The application uses JSON configuration files in the `json/` directory to define:
- ECU communication parameters (tx_id, rx_id, protocol)
- Zone definitions and data structures
- Security keys for different ECU variants
- Protocol-specific settings

Example structure:
- `json/BMF/BSI2010.json` - BSI (Body Systems Interface) configuration
- `json/TELEMAT/NAC.json` - Navigation/Audio Computer configuration
- `data/IdentUDSECU.json` - Common UDS identification zones

### Translation System

Internationalization handled through Qt's translation system:
- Source files: `i18n/PyPSADiag_<lang>.qt.ts`
- Compiled files: `i18n/translations/PyPSADiag_<lang>.qm`

### Translation Commands
```bash
# Update translation source file
pyside6-lupdate *.py -source-language en_EN -ts ./i18n/PyPSADiag_nl.qt.ts

# Edit translations
pyside6-linguist ./i18n/PyPSADiag_nl.qt.ts

# Compile translations
pyside6-lrelease ./i18n/PyPSADiag_nl.qt.ts -qm ./i18n/translations/PyPSADiag_nl.qm
```

## Key Dependencies

- **PySide6**: GUI framework
- **PySerial**: Serial communication
- **pyinstaller**: For building executables
- **numpy**: Data processing
- **googletrans**: Translation utilities

## Data Structures

### Zone Files
- CSV format for zone data import/export
- JSON format for ECU configuration
- Simulation data in `simu/` directory

### Communication Protocols
- **UDS (Unified Diagnostic Services)**: Modern automotive diagnostic protocol
- **KWP (Keyword Protocol)**: Legacy diagnostic protocols (IS/HAB variants)
- **LIN**: Local Interconnect Network support

## Hardware Integration

The application supports multiple hardware interfaces:

### Arduino-based Adapters
Traditional serial communication via Arduino-based CAN-BUS interfaces. Serial communication parameters are configurable through the GUI.

### Evolution XS VCI
Professional diagnostic interface using the Actia PSA XS Evolution VCI adapter. This integration includes:

- **32-bit DLL Bridge**: Uses `VCIBridge.py` subprocess to handle 32-bit DLL (`VCIAccess.dll`) from 64-bit Python
- **VCI Adapter Class**: `VCIAdapter.py` manages communication with the bridge process
- **Automatic Configuration**: VCI is automatically configured when ECU JSON files are loaded
- **Protocol Support**: 
  - UDS/DIAG_ON_CAN (CAN-DIAG, CAN-IS buses)
  - KWP2000/PSA2000 (K-Line protocols)
  - KWP_ON_CAN_FIAT (FIAT specific protocols)
  - Multiple response frame support
  - Analog voltage reading
  - ECU initialization sequences

#### VCI Setup Requirements
1. Install Diagbox or compatible VCI drivers
2. Ensure `C:\AWRoot\drv\VCIAccess.dll` exists
3. 32-bit Python installation required for bridge process
4. **Important**: Uses `py -3-32` launcher (preferred) or fallback to direct 32-bit Python paths

**Python Launcher Priority:**
- Primary: `py -3-32` (Python Launcher for Windows)
- Fallback: Direct 32-bit Python executables
- This ensures compatibility with your `py` command preference

#### VCI Usage
1. Select "Evolution XS VCI" from port dropdown
2. Click Connect - VCI bridge will start automatically
3. Load ECU JSON file - VCI will be configured for the specific ECU
4. Use normal read/write operations

## Important Notes

- This is an educational tool - use with extreme caution on real vehicles
- Always verify zone data before writing to ECUs
- The application includes safety confirmations for write operations
- Supports simulation mode for testing without hardware