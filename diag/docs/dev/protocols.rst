Protocols and Connection Overview
=================================

The following protocols and communications links are used across the system. The specific type to use can be found from the PROTOCOL specifier and ECUFAMILY table, between the "bus", "dialog" and "target" fields

The meaning of the "bus" field
- 0 = no CAN bus specified so probably K line
- 1 = CAN_DIAG
- 2 = CAN_IS
- 4 = FIAT B_CAN

The meaning of the "dialog" field (mitsubishi somewhere here). This might help to set Evolution XS "line" choices
- 0 = not specified - unknown
- 2 = normal UDS/KWP-on-CAN all ECUs have own headers
- 4 = FIAT - include "target" as first byte on request
- 5 = TOYOTA - unknown yet
- 6 = NEW FIAT - unknown yet
- 7 = NEW FIAT - unknown yet


- KWP-on-CAN - the KWP command set, but using CAN as a transport layer. CAN message IDs usually unique for that ECU (e.g. 752/652 for BSI04). The first byte indicates message length, or if a multipacket part then the packet number
- UDS-on-CAN - the UDS command set using CAN as a transport layer. Similar to KWP-on-CAN but with more commands
- KWP-on-CAN FIAT - the KWP command set, but CAN EMIT ID is the same for all ECUs and the first byte of the message indicates the target ECU with a code
- PSA2000 - K-line communication using the KWP command set

Most vehicles use the OBD pins as follows
- 3 CAN DIAG HIGH (500kbs)
- 8 CAN DIAG LOW  (500kbs)
- 6 CAN I/S HIGH (500kbs, also the OBD2 protocol bus)
- 14 CAN I/S LOW (500kbs, also the OBD2 protocol bus)

Early X250 fiat based systems use
- 6 CAN BCAN HIGH (50kbs)
- 14 CAN BCAN LOW (50kbs)

Later X250/FL/X290 Fiat based systems require the S1279 box to work with the EvolutionXS adapter, but their raw OBD pinout is
- 1 CAN DIAG HIGH
- 9 CAN DIAG LOW
- 6  CAN ISO
- 14 CAN ISO

Other Fiat based vehicles (Bipper and equivalent)
- TBC


Actia XS Evolution
------------------
Connecting to Fiat-based vehicles may require some manual adjustment. It may also require the S1279 box and that may require a wiring fix to work properly (see image). 

In software, there are several possible connection options. LS6 is assumed by default for all vehicles using KWP_ON_CAN_FIAT protocol. If this is not correct for your vehicle, please contact the developers so support can be added correctly.

- LS6 - use FIAT LOW SPEED BCAN on pins 6/14
- LS3 - use FIAT LOW SPEED BCAN on pins 3/8
- UDS_MCV - use FIAT UDS_MCV CAN


