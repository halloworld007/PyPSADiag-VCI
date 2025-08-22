# PyPSADiag Startskripte

Diese Sammlung von Startskripten automatisiert das Setup und den Start von PyPSADiag auf verschiedenen Plattformen.

## 🚀 Verfügbare Startskripte

### Windows

#### `start_pypsa.bat` - Batch-Skript
- **Verwendung**: Doppelklick oder `start_pypsa.bat [SPRACHE]`
- **Features**:
  - Automatische Python-Erkennung (64-bit + 32-bit)
  - VCI DLL Überprüfung
  - Virtual Environment Setup
  - Dependency Installation
  - Farbige Ausgabe
  - System-Informations-Zusammenfassung

#### `start_pypsa.ps1` - PowerShell-Skript (Empfohlen)
- **Verwendung**: `.\start_pypsa.ps1 [OPTIONEN]`
- **Features**:
  - Erweiterte Kommandozeilen-Optionen
  - Bessere Fehlerbehandlung
  - Entwicklungsmodus
  - Ausführliche Statusmeldungen

##### PowerShell Optionen:
```powershell
.\start_pypsa.ps1 -Lang de              # Deutsch
.\start_pypsa.ps1 -Simu                 # Simulationsmodus
.\start_pypsa.ps1 -Scan                 # Scan-Modus
.\start_pypsa.ps1 -CheckCalc            # Seed/Key Test
.\start_pypsa.ps1 -SkipVenv             # Ohne Virtual Environment
.\start_pypsa.ps1 -DevMode              # Entwicklungsmodus
.\start_pypsa.ps1 -Help                 # Hilfe anzeigen
```

### Linux/macOS

#### `start_pypsa.sh` - Shell-Skript
- **Verwendung**: `./start_pypsa.sh [OPTIONEN]`
- **Features**:
  - Python3 Erkennung
  - Virtual Environment Setup
  - Dependency Installation
  - Unix-spezifische Anpassungen

##### Shell Optionen:
```bash
./start_pypsa.sh --lang de             # Deutsch
./start_pypsa.sh --simu                # Simulationsmodus  
./start_pypsa.sh --scan                # Scan-Modus
./start_pypsa.sh --checkcalc           # Seed/Key Test
./start_pypsa.sh --skip-venv           # Ohne Virtual Environment
./start_pypsa.sh --dev                 # Entwicklungsmodus
./start_pypsa.sh --help                # Hilfe anzeigen
```

## 🔧 Was die Skripte tun

### 1. Python-Überprüfung
- Erkennt verfügbare Python-Installationen mit `py` Launcher (bevorzugt)
- Fallback zu direkten `python` Befehlen wenn nötig
- Überprüft Python-Version (3.8+ erforderlich)
- **Windows**: Sucht nach 32-bit Python via `py -3-32` für VCI-Unterstützung

### 2. VCI-Unterstützung (Windows)
- Überprüft `C:\AWRoot\drv\VCIAccess.dll`
- Validiert 32-bit Python für VCI Bridge
- Zeigt VCI-Status an

### 3. Virtual Environment
- Erstellt `.venv` Ordner wenn nicht vorhanden
- Aktiviert Virtual Environment automatisch
- Isoliert Projekt-Dependencies

### 4. Dependency Management
- Aktualisiert pip automatisch
- Installiert aus `requirements.txt` (wenn vorhanden)
- Fallback: Installiert essentielle Pakete manuell:
  - PySide6 >= 6.9
  - PySerial
  - numpy
  - googletrans >= 4.0.2
  - legacy-cgi (Python 3.13+)

### 5. Verifikation
- Überprüft PySide6 Installation
- Überprüft PySerial Installation  
- Validiert `main.py` Verfügbarkeit

### 6. Anwendungsstart
- Übergibt Kommandozeilen-Parameter
- Startet PyPSADiag mit korrekter Konfiguration
- Zeigt System-Informationen an

## 🎯 Schnellstart

### Windows (Einfach)
```cmd
# Doppelklick auf start_pypsa.bat
# ODER
start_pypsa.bat de
```

### Windows (Erweitert)
```powershell
# PowerShell als Administrator öffnen (falls erforderlich)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\start_pypsa.ps1 -Lang de -Simu
```

### Linux/macOS
```bash
# Ausführbar machen (einmalig)
chmod +x start_pypsa.sh

# Starten
./start_pypsa.sh --lang de --simu
```

## ⚙️ Systemanforderungen

### Allgemein
- Python 3.8 oder höher
- Internetverbindung (für Dependency Installation)

### Windows (VCI-Unterstützung)
- 64-bit Python (Hauptanwendung)
- 32-bit Python (VCI Bridge)
- Diagbox Installation oder VCIAccess.dll

### Linux/macOS
- python3-venv Paket
- build-essential (für einige Dependencies)

## 🛠️ Fehlerbehebung

### "Python nicht gefunden"
- Installieren Sie Python von [python.org](https://python.org)
- Stellen Sie sicher, dass Python im PATH ist
- Windows: Verwenden Sie den Python Launcher (`py`)

### "VCI DLL nicht gefunden"
- Installieren Sie Diagbox oder kompatible VCI-Treiber
- Überprüfen Sie `C:\AWRoot\drv\VCIAccess.dll`
- 32-bit Python für VCI erforderlich

### "PySide6 Installation fehlgeschlagen"
- Aktualisieren Sie pip: `python -m pip install --upgrade pip`
- Verwenden Sie Virtual Environment
- Windows: Installieren Sie Visual C++ Redistributable

### PowerShell Execution Policy
```powershell
# Für aktuellen Benutzer erlauben
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## 📝 Anpassung

### Eigene Abhängigkeiten hinzufügen
1. Bearbeiten Sie `requirements.txt`
2. Oder erweitern Sie die Skripte um zusätzliche Pakete

### Andere Python-Versionen
- Ändern Sie die Python-Befehle in den Skripten
- Passen Sie Versionsprüfungen an

### Zusätzliche Startoptionen
- Erweitern Sie die Argument-Parser
- Fügen Sie neue Kommandozeilen-Parameter hinzu

## 🔍 Debug-Modus

Alle Skripte bieten erweiterte Ausgabe für Debugging:

```bash
# Windows PowerShell
.\start_pypsa.ps1 -DevMode

# Linux/macOS
./start_pypsa.sh --dev

# Windows Batch (immer verbose)
start_pypsa.bat
```

## 📋 Unterstützte Sprachen

- `de` - Deutsch
- `nl` - Niederländisch  
- `it` - Italienisch
- `pl` - Polnisch
- `uk` - Ukrainisch
- (Standard: Englisch)