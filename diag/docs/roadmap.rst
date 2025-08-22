Roadmap
=======

This project is under active development, with the following goals in the short, medium and long term. You can help just by testing the software on your own hardware/vehicles, or getting involved with development. Improving overall stability of the GUI and underlying library is a permanent goal, but here are some specifics.

If you find bugs, PLEASE report them with the tracker and attach a log and explanation of what you were trying to do.

Program
~~~~~~~
- TELECODING: list view sometimes requiring a switch toggled twice before it will register the change?
- SETTINGS: "browse" for log folder doesn't work, modes don't work, and need another checkbox for actuator tests 
- DISCOVERY: Allow "adding" to an existing Discovery (say we read INJ and BMF last time, lets allow the user to add COMBINE etc, for example to rescan a failed unit)
- LIDATA: Add logging of live data
- LIDATA: Rewrite from end to end to improve performance and CPU usage
  
Kivy/UI
~~~~~~~
- Add graphing of a live data parameter (needs **significant** speed up in reading from ECU)
- Implement better dropdown/combobox support to avoid the ugly hacks that currently exist
- "Quicksearch" function to filter/jump to a specific setting or settings
- Implement improvements to Kivy to improve performance of telecoding & live data views

Library
~~~~~~~
- Proper detection of protocol/com-line for each ECU (in database, partially complete)
- Support for badge-engineered vehicles using Mitsubishi, Fiat (WIP) and Toyota protocols
- Figure out how LID mapping applies to the BSI04 Actuators table (partially complete)
- "C02" and others need to be imported properly into ECU FAMILY table (partially complete)
- Load fault prefixes (U/F/P etc) correctly - it can be determined using a flag in the code parameter definition
- Develop support for flashing firmware files to/from ECUs
- Some vehicle codes are not yet known / do not have friendly names in the database (so some models are missing from the list). If yours is among them, let us know!

Adapters
~~~~~~~~
- Figure out K-line support - currently unknown how to work out which line to connect to. This is particularly for SUSPENSION_ECOTECH, SEVEL vans and older vehicles
- Toyota and Mitsubishi protocols

Tools
~~~~~
- Implement Proc_Editor to allow importing DLL functions (e.g. key pairing) into the main tables
