Project Intro
=============

- For brevity, x is sometimes used to represent hex numbers (e.g. x23) instead of 0x23
- Diagbox uses what can be kindly described as a "hybrid" model, with DLL's, script files and executables all performing different functions. As a result, there is not ''reliable'' standardisation across the various services and functions. Therefore, there are some items hardcoded in this library which are necessary because it has not been possible to figure out a way of determining them dynamically. Where this is the case, a comment should explain how it was determined that the assumption was relatively safe (and the code should detect a difference, or fail safe).
- Understanding of the protocols, data and functions has evolved as the project has developed, so some areas of code are more mature than others. There are horrendous hacks inserted along the way. Please forgive them, they will be removed and fixed where possible at some point
- In some cases, dirty hacks are necessary to work around bad behaviour in the original protocols or database and this is usually noted


Overview
~~~~~~~~

This project recreates the core tables in static SQLite databases. It consists of several components

- **diag_bramble** : the library for connecting to and extracting routines/data for each ecu

- **diag_acttest** : load and run a specific actuator test, parsing response codes
- **diag_discovery** : scan a vehicle for ECU's, and read identification and faults from them
- **diag_livedata** : read and parse data from an ECU
- **diag_translations** : convert generic language codes from the database into the relevant language
- **diag_adapter** : a generic handler class to convert library requests to whichever serial>CAN adapter is being used
- **diag** : the base class containing miscellaneous functions

- **kivy/xxx.py** : the various files making up the different screens of the Diagnostique interface (mostly just wrappers for the diag_xx libs)

- **db/dtc4.db** : the main database (~350mb with indexes) with all ECU descriptors, functions, parameters etc
- **db/act4.db** : the actuator testing database (~50mb with indexes) - only for actuator/function testing
- **db/queries.sql** : used by diag_bramble to store the SQL queries for retrieving and merging database data

- **DU9/XXX_YY.du8** : the language translation files
- **DU9/ECU_NAMES.csv** : "pretty" names for the different ECU families
- **DU9/UILANGen.csv** : the UI translation file for the kivy-based UI
- **DU9/PRJ_CONVFORM.csv** : the parameter descriptor file for parameters previously defined in DLLs


Basic explanation of processes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

There are a few main stages of identification of a given, physical, ECU:

- [ECU]Family : a group of ECU's, e.g. INJ for engine ECUs / BOITEVIT for gearboxes
- [ECU]Type   : an ECU model, e.g. SID803 for engine ECU or BVA_AL4 for gearbox
- [ECU]ID     : reference of an ECU model in a specific vehicle
- [ECU]VEID   : (version ID) reference of a specific ECU vehicle and software version. Typically 5-10 versions for each ECU per vehicle


Protocols
~~~~~~~~~

There a multiple different protocols used in the range of vehicles supported. However, the majority use one of the top two systems.

- UDS - generally vehicles post 2010 using AEE2010
- KWP-on-CAN - aka KWP2000 - generally vehicles 2004 - 2010 using AEE2004/2007 and some latter VAN-based
- K-line - for some ECU's at varying ages (usually only for ECU flashing, or specialised ones like SUSPENSION_ECOTECH)
- Fiat - unknown, seems to be similar to UDS though

For more - see the Protocols page


Process of Discovery
~~~~~~~~~~~~~~~~~~~~
From the ECUIDs you can obtain a list of possibilities for the vehicle. That gives you the headers (e.g. TX:6B0/RX:690) for the diagnostic session. Then a shortlist of ECUIDs is generated and eventually filtered based on the vehicle name being contained in the ECUVE.variant field (currently no better method has been discovered). The precise ECUVEID is then obtained using a command known as "RECO" (Reference Controle?). Often, this will be x21 xFE or similar, to read the version bytes from the ECU and compare to known values in the database.

The BSI acts as the diagnostic response and configuration node for the BSI, BSM, BSC and BSR. Each one has its own set of fault codes and ECUVEIDs, but the BSI includes all the actuator tests/config for its child ECUs, so we don't need to load them separately. They also have MAPPED parameters, and whilst get_data_frames makes a best guess at whether it needs to apply LID mapping, it doesn't always succeed. 

Note: Discovery differs from "Global Test", because it uses a more theoretical/empirical way to decide which ECU's to scan for. Global Test reads a large chunk of data from the BSI before it begins testing, which along with the LID tables (seems to) allow it to determine which ECUs are configured on the vehicle using zones B1 (CAN) and BA (LIN). Perhaps in future we could implement both and warn of a mismatch (see Database page / future notes). It would allow us to present a message like "Radio configured, but communication impossible" distinct from "No response".


Concept of diagnostic frames
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

All diagnostic frames supported natively by Diagbox are stored in the databases. This includes everything from diagnostic init, fault reading, telecoding etc. Some functions, parameters or calibration routines are contained in the DLL files specific to each ECU. Some of these have been obtained empirically, and this work is ongoing to offer full feature parity.

A full list of those used for a given ECUVEID can be obtained from the diag_bramble library. Not all ancilliary data for the parameters involved is retrievable using just the ECUVE identifier, because you have to start from the actuator test/telecode/live data descriptors in order to properly match some other data (like parameter formatting).

A diagnostic frame consists of three things

* SERVICE: (aka SID) the service identifier (e.g. RDBLID(ReadDataByLID) => 0x21)
* ZONES: (aka LID) the sub-service or sub-function, pointer to a parent service (e.g. LID_81 (memory zone 81) => 0x81)
* FRAMES: a collection of the bytes for each frame (by position). For example [ RDBLID, LID_81, XX, YY, XX, .. ]

It is not always possible to work out exactly what a frame is for from it's core descriptors, and the name of each SERVICE or ZONE aren't necessarily consistent. However, there is a small enough number of exceptions for most commands that it can be checked manually. Diag_bramble is fairly smart with different methods to work out what a zone or service belongs to.


Parameters
~~~~~~~~~~
There are actually two different kinds of "parameter". EDATA, which is tied to ECUID, and PARAMS which is tied to ECUVEID. The link between them is by their name (not by ID), such that a particular EDATA parameter may have multiple PARAMS with the same name (just as there are many ECUVEID for a given ECUID). This is because a particular EDATA parameter (with a name, description, etc) may have different positions/values/types in different software versions (ECUVEIDs). Parameters show up everywhere, because the FRAMES are all built of parameters. This means even SERVICES and ZONES are PARAMS (e.g SID, LID) with a prescribed value or list of STATES. Each time they show up the usage/checking of data is slightly different, so currently it's not possible to have a unified function or class to process them (hence some code duplication in various functions).

The information about a EDATA is:

 - EDATA - label, and sometimes description and help
 - EDATAVAL - labels for "STATES" information 

There are several potential source of information about a PARAM:

* PARFORMULA - (optional, some datatypes only) Provides an offset, factor and unit for a parameter to convert into a real value from hex/binary values
* PARFORMAT - provides the type of data value the parameter represents (how many bits or bytes it is long, the bitmask of the value if applicable, etc)
* FRAPAS - provides the position of the parameter in the FRAME, and a prescribed value for that particular frame (as a parameter may be shared across multiple different FRAME's)
* STATES - (generally only ENUM type) A particular set of values a parameter may have (e.g. the currently selected gear)

Parsing the values of a parameter is quite complex, and is best explained with examples. A parameter can have one of several different types, including NUMERIC, ENUM, HEXA. This and the states that can be extracted as above are combined, and from this you can work out how to establish the parameter value. For "Live Data" measurements, you might have states AND a formula. This works as follows

* For a value in range 0 - 245, use formula { fac: 0.1, offset: 10 }
* For a value > 255, state is INVALID

Obtaining the "raw value" is done separately. The main extraction options (convert hex bytes to the parameter "value") are

One or other of:

- BITS (lenbi) - the number of bits
- BYTES (lenby) - the number of bytes


Fault finding (DTCs)
~~~~~~~~~~~~~~~~~~~~
There are two different types of DTC storage. One uses the FAULT prefixed tables (up to approx 2005) whilst the other uses the DTC prefixed tables (2005 on).

The latter DTC-based tables have three components.

* Displayed DTC (PXXXX, UXXXX and other prefixes) and description of the fault
* Characterisations/Properties - variables associated with the fault like location/permanent/intermittent etc.
* Freeze frame - stored data values at the time the fault occurred (RPM, speed etc)

Sometimes characterisations can be set by the ECU (for example, it might be possible for a DTC to be either intermittent or permanent). However, the format for doing so varies according to ECU (and must be determined dynamically by "guessing" the READ_DTC FRAME for the ECU. Therefore, the hex code response could be:

* 57 02 F308 F108       (characterisation is determined by bitmasks of the F)
* 57 02 F308 02 F108 01 (characterisation is determined by 02)
* etc

The freeze frame data comes in the same format as a "live data" frame. Therefore, the formatting, memory zone to be read and other information about it must be obtained using bramble::get_data_frames(). See the documentation in the fault reading code for explanation on how it works out what "type" of freeze frame to use (it's not trivial!)


Live data frames
~~~~~~~~~~~~~~~~
Loading data from get_data_frames gets you 3 root dictionary keys

id - From zone ZI, providing identification information about the ECU
params - 
ff - Freeze frame descriptors (for decoding fault code data)

Telecoding/Programming
~~~~~~~~~~~~~~~~~~~~~~
There are currently two main storage mechanisms for the telecoding of data, with that changing around 2010-12. The older data is stored in tables with the prefix TLCD, the newer data with the prefix TELE, because there is different information for each type and therefore cannot be stored together.

Traditionally, telecoding would be achieved with pre-defined screens or routines. That is possible to do in this software, but by default what we do is simply offer the user a big list of supported parameters and their values. In default/SIMPLE mode, this is filtered to show only those parameters with full text descriptors. For later ECUs (the ones that generally require online telecoding with DB) it is more likely that parameters will not have friendly names.

All of these should be valid, but it is ultimately up to the user to check whether a particular combination of configurations are valid. An ECU will reject certain invalid configurations, but not all. YOU MODIFY AT YOUR OWN RISK.

Currently we restrict to supporting writing telecoding data using 0x3B (KWP) and 0x2E (UDS). Some ECUs (notably INJ) use 0x34 to write telecoding data directly to flash. Since these options are not usually meant to be user configurable (or aren't available in diagbox UI) we block them currently. Sometimes the order of parameters is totally different between the read service and write service, and that will require better understanding of how these methods work before we can do the necessary checks and support them. This means that toggling things like cruise control will not work with all vehicles.

Some ECU's require security authentication to write some or all data. These authentication keys appear to be on a vehicle + ECU name basis (not tied to an ECUID or ECUVEID). Some are already known but others can be obtained by sniffing traffic with pre-existing systems. There is currently no known way of establishing if security is required beforehand, so instead the software tries to write a memory zone and waits to receive a rejection (7F) with a "access required" error. It will then try to establish access and if no key is available telecoding will fail.



