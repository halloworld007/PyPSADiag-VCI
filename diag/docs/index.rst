.. Diagnostique documentation master file, created by
   sphinx-quickstart on Sun Mar 14 17:48:18 2021.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Diagnostique
=======================

This project as a whole seeks to document as much of the PSA / Stellantis CAN & electronic system architecture as possible, using publicly available information and reverse-engineered data. You may wish to read the overview the systems on these vehicles. The primary software is currently "Diagnostique", a GUI application written totally in Python providing the following key functions. The eventual aim is to provide a full alternative to the manufacturer after-sales tool, plus additional discovered functions.

- **Discovery** - scan the vehicle for **all** possible ECUs (depending on the hardware used) and scan for faults
- **Manufacturer-specific fault reading** - giving the full code, message, characterisation(s) and "freeze frame" according to the OEM information
- **Live telemetry data** - full access to live parameters from the various ECUs fitted to the vehicle
- **Actuator testing** - trigger certain relays, functions and tests to ensure components are working correctly
- **Telecoding** - reading of and (*currently experimental*) modification of vehicle configuration, settings and parameters
- **Identification** - read the full parameters of an ECU (hardware/software #id) to assist with accurate replacement
- **Procedures** - *in development* running operations on the vehicle, such as key matching, calibration of suspension heights etc.

Diagnostique and its associated utilities are a project under significant development. The basic underlying vehicle communication is relatively mature, but compatibility with every ECU cannot be guaranteed. There are still instabilities, particularly in the GUI, which are being actively addressed but bug reports are important and welcome.

.. toctree::
   :maxdepth: 2
   :caption: Overview

   requirements
   faqs
   installation
   roadmap
   vehicle-support
   about

.. toctree::
   :caption: User Guide

   user-guide
   user/discovery
   user/faults
   user/live-data
   user/actuator-test
   user/telecoding
   user/procedures
   user/flashing

.. toctree::
   :caption: Developer Guide
   
   dev-guide
   dev/intro
   dev/diag_bramble
   dev/database
   dev/treeview
   dev/protocols
   dev/gui

.. toctree::
   :caption: Technical Notes

   aee-guide
   aee/



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
