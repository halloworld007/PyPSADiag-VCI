# PyPSADiag - PSA/Stellantis Automotive Diagnostic Tool

![Python Version](https://img.shields.io/badge/python-3.12%2B-blue)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![License](https://img.shields.io/badge/license-GPL--2.0-green)

**⚠️ IMPORTANT DISCLAIMER**
-------
This application is provided as is, and you use it **at your own risk**.<br/>
I am not responsible for any damages or injuries resulting from the use of this application.<br/>
**VERY IMPORTANT:** This application is for **educational purposes only** and should be used with extreme caution on real vehicles!

-------

PyPSADiag is a Python application for sending diagnostic frames over CAN-BUS to PSA/Stellantis based vehicles. This educational tool supports various automotive diagnostic protocols including UDS, KWP2000, and more.

**📋 Based on Original Project**: This is a fork/enhanced version of the original [PyPSADiag by Barracuda09](https://github.com/Barracuda09/PyPSADiag) with additional VCI support and improvements.

## 🔧 Hardware Support

### Arduino-based Adapters
- Compatible with arduino-psa-diag hardware
- See [ludwig-v arduino-psa-diag](https://github.com/ludwig-v/arduino-psa-diag) for hardware info

### Evolution XS VCI Professional Interface
- **⚠️ VCI DRIVER REQUIREMENT**: You must have VCI drivers installed
- **Required**: Install Diagbox or compatible VCI drivers 
- **Critical**: `C:\AWRoot\drv\VCIAccess.dll` must be present on your system
- **32-bit Python**: Required for VCI DLL bridge communication
- Supports multiple protocols: UDS, KWP2000, KWP_ON_CAN_FIAT

Currently supporting:

- JSON Configuration for example BSI2010 to setup GUI<br/>[See more JSON Configuration Files](https://github.com/Barracuda09/PyPSADiag/tree/main/json)
- Reading Zones that are listed in JSON Configuration file
- Saving Zones to CSV file
- Saving changed Zones (as an list) to ECU

What I would like to support:
- More ECU JSON Files

Help
-------
Help in any way is appreciated, just send me an email with anything you can
contribute to the project, like:
- More ECU JSON Files
- Python coding
- GUI design
- ideas / feature requests
- test reports
- spread the word!

Build
-----
- Install Python 3.12 or above
- Get code `git clone https://github.com/halloworld007/PyPSADiag-VCI.git`<br>
  OR use this [Download ZIP](https://github.com/halloworld007/PyPSADiag-VCI/archive/refs/heads/main.zip)
- Create virtual enviroment `python -m venv /path/to/PyPSADiag-VCI/.venv`
- Goto virtual enviroment with `/path/to/PyPSADiag-VCI/.venv/Script/activate`
- Install requirements, within path of PyPSADiag-VCI with `pip install -r requirements.txt`
- Run with:
	1. `python main.py --lang nl`
	2. `Open Zone File` and select an ECU JSON file
	3. `Connect` to correct Arduino hardware
	4. `Read` Zones
	5. <b> **RISK:** You can save the Zones to the ECU by using the `Write` Button.<br/> **Always Check that these zones look correct** </b>

Make Translations
------

For example to make a translation for Dutch use this command:
- `pyside6-lupdate EcuMultiZoneTreeWidgetItem.py EcuZoneTreeView.py EcuZoneTreeWidgetItem.py PyPSADiagGUI.py DiagnosticCommunication.py main.py  -source-language en_EN -ts ./i18n/PyPSADiag_nl.qt.ts`
- `pyside6-linguist ./i18n/PyPSADiag_nl.qt.ts`
- `pyside6-lrelease ./i18n/PyPSADiag_nl.qt.ts -qm ./i18n/translations/PyPSADiag_nl.qm`
- `python main.py --lang nl`

Manual Translations
------
For manual translation, you can use the desktop application [QT Linguist](https://github.com/lelegard/qtlinguist-installers/releases).<br>
Open, for example, the `./i18n/translations/PyPSADiag_translated_nl.qt.ts` file, edit the sentences, and save the result.

Donate
------

If you like my work then please consider making a donation, to support my effort in
developing this application.<br>
Many thanks to all who donated already.<br>

| PayPal |
|-------|
|  [![PayPal](https://img.shields.io/badge/donate-PayPal-blue.svg)](https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=H9AX9N7HWSWXE&item_name=PSADiag&item_number=PSADiag&currency_code=EUR&bn=PP%2dDonationsBF%3abtn_donateCC_LG%2egif%3aNonHosted) |

Contact
-------
If you like to contact me, you can do so by sending an email to:

    mpostema09 -at- gmail.com
