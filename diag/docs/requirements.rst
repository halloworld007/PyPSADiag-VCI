System Requirements
===================

Official Support
----------------
You will need a laptop/tablet with a USB port. Direct downloads are currently maintained for

- **Windows** - XP/Vista/7/8/10
- **Linux** - tested on Mint, should work anywhere
- Support for Android/iOS is theoretically possible, but not a current target

The software is approx 350MB, due to the breadth of vehicles supported. Test functions is an optional addition, requiring an additional 50MB.

Multiplatform
-------------
The core software is written in Python with SQLite databases, and in theory will run on any platform which can provide access to the serial or bluetooth ports used by your chosen adapter.

Adapter hardware
----------------
There are several options for the physical hardware used to connect to the vehicle, and it will depend on the vehicle as to which protocols you will need. These protocols are

- **CAN Intersystems** - engines, CSS suspension, gearbox and possibly others
- **CAN Diagnostic** - majority of ECU's post 2004 except CSS suspension, full engine capability and others
- **K-Line** - mostly pre-2004 except SUSPENSION_ECOTECH and a few others

The hardware options are
- **PSA Lexia 3/Evolution XS VCI** - [recommended, Windows only] also known as the "ACTIA Evolution XS", the hardware used for Diagbox/Planet/Lexia
- **arduino-psa-diag** - Arduino-based adapter supporting a single CAN line at a time
- **ELM327** - [WIP] only CAN Intersystems & K line, and be aware some cheap clones won't work properly
- **DIY Arduino/STM based controller** - instructions for building one of these is available separately

If you have the knowledge and/or ability to write a driver for a different piece of hardware you are more than welcome to do so. The application's interface has been abstracted as much as possible away from the hardware. See "diag_adapters.py" in the root of the code tree for more detail.


ELM327
------
The limitation with these devices is the baud rate of the bluetooth module, which limits the speed the ELM can get data out of its buffer back to your laptop/computer/device. The common eBay ones are usually cheap units with a slower baud rate, and so may struggle. A USB-wired ELM327 or a unit with a higher baudrate is likely to work successfully, but the internal driver is currently only supporting Bluetooth communication.

- It will usually works OK with older vehicles (pre 2010). A large number of faults may cause reading to fail.
- On newer cars (2010-on), live data, actuator tests and telecoding will probably work but fault reading is unlikely to.

Unless you buy or build an adapter cable, you will be limited to those ECUs on the CAN Intersystems bus (engine, ABS etc)


Lexia3 and EvolutionXS devices
------------------------------
This is the most stable driver currently implemented, but there are few things to be aware of.

- Windows only - there is no way to get the driver to work on any other platform
- You will need to get the driver files separately (they're PSA/Actia copyright, we can't redistribute ourselves). You don't need the whole of Diagbox, only the drivers and interface files as listed below
    - The actual hardware drivers installer (ActiaPnPInstaller)
    - The /AWRoot/drv folder from Diagbox
    - The /AWRoot/dtrd/comm/data folder (no need for the FDB databases)
- You MUST run Diagnostique from the same disk drive (e.g. C:) as the folders above exist upon. This is a limitation of the driver DLLs. If you do not have the full Diagbox installation (only the above folders) then they and Diagnostique can exist on any drive letter (D, E, F, etc), but all must be on the same drive letter.

Install the drivers BEFORE plugging in your interface.

If you are using this hardware on the bench, be aware that both Ignition 12v and battery 12v must be connected to at least 8v, and the grounds must be good too, or you will get errors.


DIY controller
--------------
The performance of this device will depend on how well engineered it is, in particular the throughput of the Arduino/custom sketch flashed to it. Examples are available, or the protocol is available in the developer guide.
