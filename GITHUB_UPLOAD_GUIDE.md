# GitHub Upload Guide

## Schritt-für-Schritt Anleitung zum Upload auf GitHub

### 1. GitHub Repository erstellen

1. Gehe zu [GitHub.com](https://github.com) und logge dich ein
2. Klicke auf "New Repository" (grüner Button)
3. Repository Name: `PyPSADiag` (oder einen anderen Namen)
4. Beschreibung: `PSA/Stellantis Automotive Diagnostic Tool with VCI Support`
5. **Wichtig**: Repository als **Public** erstellen (für Open Source)
6. **NICHT** "Initialize with README" ankreuzen (wir haben schon eine README.md)
7. Klicke "Create Repository"

### 2. Git Repository initialisieren

Öffne Command Prompt/PowerShell im Projektordner:

```bash
# Git Repository initialisieren
git init

# Alle Dateien hinzufügen (außer .gitignore Einträge)
git add .

# Ersten Commit erstellen
git commit -m "Initial commit: PyPSADiag with VCI support

- Added Evolution XS VCI support
- Fixed hardcoded paths for cross-system compatibility  
- Added comprehensive documentation
- Based on original work by Barracuda09"

# GitHub Repository als Remote hinzufügen (URL von GitHub kopieren)
git remote add origin https://github.com/DEIN_USERNAME/PyPSADiag.git

# Upload zu GitHub
git push -u origin main
```

### 3. Repository konfigurieren

Nach dem Upload auf GitHub:

1. **Repository Settings**:
   - Gehe zu Settings Tab
   - Scrolle zu "Features" Sektion
   - Aktiviere "Issues" für Bug Reports
   - Aktiviere "Wiki" für Dokumentation

2. **Branch Protection** (Optional):
   - Settings → Branches
   - "Add rule" für main branch
   - "Require pull request reviews" aktivieren

3. **Topics hinzufügen**:
   - Auf der Hauptseite, Zahnrad bei "About"
   - Topics: `automotive`, `diagnostics`, `psa`, `stellantis`, `can-bus`, `uds`, `python`

### 4. README badges updaten

In README.md die GitHub-URL ersetzen:
```markdown
git clone https://github.com/DEIN_USERNAME/PyPSADiag.git
```

### 5. Releases erstellen

1. Gehe zu "Releases" Tab auf GitHub
2. "Create a new release"
3. Tag version: `v1.0.0`
4. Release title: `PyPSADiag v1.0.0 - VCI Support`
5. Beschreibung:
   ```
   First release with Evolution XS VCI support
   
   Features:
   - Arduino CAN adapter support  
   - Evolution XS VCI professional interface support
   - Multiple diagnostic protocols (UDS, KWP2000)
   - Cross-platform Python path resolution
   - Comprehensive documentation
   
   VCI Requirements:
   - VCI drivers must be installed
   - C:\AWRoot\drv\VCIAccess.dll required
   - 32-bit Python needed for VCI bridge
   ```

### 6. License und Copyright

**Wichtig**: 
- GPL-2.0 License beibehalten (wie Original)
- Credits zum Original-Projekt in README
- Copyright Notice für eigene Änderungen

### 7. Collaboration Guidelines

Erstelle `CONTRIBUTING.md`:
```bash
git add CONTRIBUTING.md
git commit -m "Add contributing guidelines"  
git push
```

### 8. Wartung

Regelmäßige Updates:
```bash
# Änderungen committen
git add .
git commit -m "Beschreibung der Änderungen"
git push

# Tags für neue Versionen
git tag v1.1.0
git push --tags
```

## Wichtige Hinweise

- **VCI DLL nicht hochladen**: Die `VCIAccess.dll` gehört nicht ins Repository
- **Sensible Daten**: Keine echten ECU Keys oder private Fahrzeugdaten
- **Testing**: Immer mit `--simu` Flag testen vor Release
- **Dokumentation**: Bei Änderungen auch Dokumentation updaten

## Support und Issues

- GitHub Issues für Bug Reports
- Wiki für erweiterte Dokumentation  
- Discussions für Fragen und Feature Requests

**Erfolgreiches Setup prüfen**:
- Repository ist öffentlich zugänglich
- README.md wird korrekt angezeigt
- Installation Guide funktioniert
- Issues sind aktiviert