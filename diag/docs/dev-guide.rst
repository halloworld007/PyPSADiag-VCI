Developer Guide
===============

Most of the documentation for the project focuses on the library and the Kivy-based GUI Diagnostique. However, there are a few other utilities :-

- **OleoMux** - used for visualising CAN messages and documenting definitions and signals, now available separately on GitHub
- **Treeview** - used to visualise the full set of commands for an ECU as well as extract key information. Also provides a raw UDS terminal with automatic Keep-Alive 
- **Proc_Editor** - [WIP] a simple tool used to import extracted or discovered UDS commands into the main software database
- **Parser_S** - see below [WIP], a script to extract and visualise the main commands in an S file, and simulate stepping through them

The development manuals for this project assume a basic knowledge and understanding of the KWP-on-CAN/UDS diagnostic protocol.

This software and database consists of a reconstruction of PSA's diagnostic protocols as faithfully as possible, based on current understanding of the system. There may be functionality missing, misunderstood or mis-parsed.

There are four basic functions fulfilled by Diagbox and replicated by the software

- Fault finding (DTC)
    - Reading fault codes (diagnostic trouble codes)
    - Read accompanying characterisation data (manufacturer specific)
    - Retrieve and parse freeze-frames

- Live parameter measurement (reading data in real-time)
    - ECU identification (software/hardware version)
    - Telemetry (air pressure/temp/fuel flow/other ecu statuses)

- Testing of functions (actuator tests)
    - Execute functions on ECU's to test valves, flaps or other functions

- Telecoding (configuration)
    - Read, backup and display configuration
    - Unlock ECUs that require authentication '[WIP]'
    - Write configuration to ECUs

In addition to this there are various supporting functions which are necessary:

- Discovery (aka global test)
    - Scan the vehicle for ECUs and retrieve a list of those fitted, and their version information
    - Optionally, scan for fault codes as the scan progresses
  
- Execute ECU routines
    - Some ECUs have functions for calibrating etc which in Diagbox are executed with external DLL's. **Extracting and implementing these must be done manually, and so is limited at present**
    - These processes, once extracted, can be reimplemented and appear under the "Procedures" tables

- Parser/Visualiser for ACTIA Script files
    - ACTIA's XML-based S script format contains *some* data needed to run various telecoding routines successfully (or at least, in the formats pre-ordained by the manufacturer)
    - This function is being developed gradually as and when needed, and as such is not feature-complete yet
    - Newer versions of Diagbox use a different format for the S files (the tags are in french). Support for this is partially implemented

Need-to-knows
-------------
Any changes which alter the output of get_data_frames or functions which depend on it (telecoding) require the version number of the diag_bramble library to be incremented. This will invalidate old Discovery files and force a refresh of ECU data.


Development Environment
-----------------------

**Use 32 bit Python only for compatibility with EvolutionXS hardware**

- Python 3.8.8 with Tcl/Tkinter installed (for auxiliary utilities) 
- Kivy 2.0.0
- Kivy Garden with garden-navigationdrawer flower
- pyserial
