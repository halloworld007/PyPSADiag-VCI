Discovery Tree
----------------

The Discovery tree contains all important information to identify an ECU or set of ECUs from a vehicle or test rig. This allows resuming a session without requiring the vehicle to be re-scanned, or to view limited data "offline".

Items in *italic* are not guaranteed to be present in the tree. 
Other data can be assumed to be present, if STATUS is equal to IDENTOK. If STATUS has another value, some or all information may be missing.


- **PROT** int, the default protocol set for the vehicle (UDS = 1 or KWP = 0)
- **VEH** str, the internal vehicle ID number e.g. 42
- **VIN**  str, the VIN read from the vehicle, or ""
- **VER** str, the version of the diag_bramble library used to build this tree
- **LID** dict, details of the LID mapping zone read from the BSI (BSI04 only), {} otherwise
- **ECU** dict, contains all ECUs in the tree. The keys are equal to ECUNAME. For each ECU:
    - **STATUS** str, equal to IDENTOK when all information has been obtained. ECUs which did not respond or were not detected have other values (NOTFOUND, IDENTKO, RECOKO, NOTPRESENT)
    - **ECUID** int, the internal reference for the ECU type (roughly equivalent to ECUNAME in concept)
    - **ECUVEID** int, the internal reference for the ECU version (roughly equivalent to VARIANT in concept)
    - **FAMILY** str, ECU category e.g. "BMF"
    - **ECUNAME** str, ECU subtype, e.g. "BSI2010"
    - **VARIANT** str, ECU unique identifier for this software version e.g. "BSI_X7_V1"
    - **PROTOCOL** str, one of the entries in the diag_bramble::protocols dictionary
    - **TARGET_CODE** str, for CAN_FIAT the target code of the ECU, for K-LINE the ECU address
    - **DIALOG_TYPE** str, for K-LINE the OBD pin to use
    - **TX_H** str, CAN transmission ID for adapter, e.g. "652"
    - **RX_H** str, CAN reception ID for adapter, e.g. "752"
    - **BUS** str, which CAN bus to use; "DIAG" or "IS" or sometimes "" for other protocols
    - **CMDS** dict, output of diag_bramble::get_ecu_diag_cmds(ECUVEID)
    - **FRAME_TREE** dict, output of diag_bramble::get_data_frames(ECUID, ECUVEID, qtype="parameters", dont_post_process=False). Used for "live data" function
    - **FAULTS** int, -1 if they haven't been read, otherwise the number of active faults
    - **FAULT_TREE** dict, output identical to parse_dtc_response
    - *IDENTIFICATION* dict, present only if IDENTIFICATION information has been read from the ECU


FRAME_TREE (output of get_data_frames)
---------------------------------------

Example (truncated) of the fields contained in the tree

..  code-block:: python

    "ff": {"frames": []},
    "id": "TBC",
    "params": {
        "C0": {
            "request": {"1": "21", "2": "C0"},
            "params": [
                {
                    "parname": "MP_COMMUTATEUR_SYSTEME_ALERTE_FRANCH_INVOL_LIGNE",
                    "label": "Lane Departure Warning System switch",
                    "scrdat": {
                        "MESUREPARAMETREPlusE": 281392,
                        "MESUREPARAMETREmoinC": 281392,
                    },
                    "help": "Permits activation of the lane wandering alert system",
                    "unit": "",
                    "edatid": 281392,
                    "pos": 3,
                    "type": "BOOLEAN",
                    "pid": 161929,
                    "blk": "",
                    "map": "",
                    "crc": "",
                    "pencode": "",
                    "dyn": {},
                    "frid_read": 214635,
                    "zone_read": "RDBLID_LID_C0",
                    "pos_read": 3,
                    "hex_states": [
                        {
                            "name": "MP_COM_SYST_ALERTE_FRANCH_INVOL_LIGNE_0",
                            "val": "0",
                            "min": "",
                            "max": "",
                        }
                    ],
                    "edv_states": [
                        {
                            "name": "INACTIF",
                            "label": "Inactive",
                            "is_default": 0,
                            "min_val": "",
                            "max_val": "",
                            "single_val": 0.0,
                        }
                    ],
                    "lenbi": 8,
                    "lenby": 0,
                    "msk": "00010000",
                    "abs": -1,
                    "endian": 0,
                    "format": "BITS",
                }
            ]
        }
    }


- **ff** dict, information for decoding "freeze frames" which accompany fault codes. If the ECU does not support freeze frames, contains a single key "frames", with a blank list
- **params** dict, live data parameters which can be monitored
- **params/C0** dict, the key C0 indicates the zone containing these parameters (B0, B1, B2 etc)
- **params/C0/request** dict, the frame used to request data for that zone
- **params/C0/params** list, contains all parameters known for that zone
- **params/C0/params/<param>/parname** str, the internal name of the parameter. Sometimes, no translateable name is available, so the system falls back to displaying this
- **params/C0/params/<param>/label** str, the translateable name of the parameter, according to the selected language
- **params/C0/params/<param>/scrdat** dict, keys are the name of the screens, values are the screen IDs. Can be used to tie parameters together as a "category" e.g. "Air circuit information"
- **params/C0/params/<param>/help** str, the translateable "description/explanation" of the parameter, or ""
- **params/C0/params/<param>/unit** str: the unit of the parameter e.g. V, mA
- **params/C0/params/<param>/edatid** int: internal reference to parameter data, not always present
- **params/C0/params/<param>/pos** int: the byte offset of the parameter
- **params/C0/params/<param>/type** str: the type of the parameter BOOLEAN, NUMERIC
- **params/C0/params/<param>/pid** int: the internal parameter ID
- **params/C0/params/<param>/blk** str: if the parameter is part of a BLOCK, its reference
- **params/C0/params/<param>/map** str: if the parameter is mapped (BSI04), the name of the zone it is mapped to (e.g. C1)
- **params/C0/params/<param>/crc** str: if the parameter is a CRC (??)
- **params/C0/params/<param>/pencode** str: how the parameter is encoded (??)
- **params/C0/params/<param>/dyn** dict: if the parameter is part of a dynamic block, its formatting data
- **params/C0/params/<param>/frid_read** int: the ID of the frame used to read the parameter
- **params/C0/params/<param>/zone_read** str, the name of the zone used to read the parameter e.g. "RDBLID_LID_C0"
- **params/C0/params/<param>/pos_read** str, the byte position of the parameter in the read service
- **params/C0/params/<param>/hex_states** list: raw states without labels
- **params/C0/params/<param>/edv_states** list: states with labels
- **params/C0/params/<param>/lenbi** int: length in bits, of the parameter
- **params/C0/params/<param>/lenby** int: length in bytes of the parameter (only this or lenbi is >0)
- **params/C0/params/<param>/msk** str: if the parameter is a bitmask, the bitmask is here
- **params/C0/params/<param>/abs** int: absolute position, used for mapping, for other parameters = -1
- **params/C0/params/<param>/endian** int: 0 for XX endian, 1 for XX endian
- **params/C0/params/<param>/format** str: ??