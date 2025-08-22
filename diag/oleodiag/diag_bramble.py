import sqlite3, re, copy, math, json, sys, traceback, yaml, pprint
import xml.etree.ElementTree as xml
import pprint, time
from .diag import diag
from .diag_translations import diag_translations
from collections import OrderedDict


class diag_bramble(diag):
    '''
    DIAG_BRAMBLE
    (c) Copyright 2021-2024. All rights reserved.

    Application API class to get data from the new custom DB
    Supply an ECUID, and get...everything, really

    This class doesn't deal with data processing, only "fetching"
    Returns data as a dictionary based tree of information

    Functionality so far
    - Fetch telecoding frames for post 2010
    - Fetch full live data/measurement frames
    - Fetch freeze frame data
    - Fetch DTC characterisation info
    - Fetch DTC codes
    - Actuator tests
    - Fetch telecoding frames for pre-2010 (limited data currently)

    IMPORTANT WARNING: It is YOUR responsibility as an end-user/developer to ensure
    the ECUID and ECUVEID are correct/a match. Because there is no hard link between
    the two in the databases, there can be NO CHECKING of your input. Therefore, the
    software will quite happily return any parameters matching that ECUID/ECUVEID which
    may very well be wrong and even break things.

    DEV-NOTE: This is now possible using ECUVEMAP, but it is experimental and only partly implemented
    
    '''

    tla = "BMB"
    trs : diag_translations = None
    conn : sqlite3.Connection = None
    path = None
    c : sqlite3.Cursor = None
    queries: dict = {}
    cache: dict = {}
    lid_table: dict = {}
    version: str = "3.179.2403"
    logfile = None
    logback = None
    debug = False

    TLCD_PROCMAP_SPECIAL_CASES = [ "NUMERO_RELATIF", "TEL_BLOCK", "TEL_BLOCK_BA", "TEL_BLOCK_B1" ]
    CMD_SETS = ["DIAG", "RECO", "DEFAULT", "SC", "SP", "TP"]

    # currently this uses ECUFAMILY identifiers, but it may be necessary to
    # also have sub-codes (for suspension ECUs, for example)
    psa2k_target_codes = {
        "CHAUFFADD": 1,
        "INJ": 16,
        "ABRASR": 32,
        "SUSPVAR": 33,      # SUSPENSION_ECOTECH is 33 on X7/X6/X3/X4
                            # other info suggests 161 is for CSS/AMVAR
        "BOITEVIT": 164,
        "CLIM": 49,
        "AIRBAG": 179,
        "HDC": 52,
        "AFFICHEUR": 181,
        "ALARMES": 56,
        "ADDITIVATION": 61,
        "FSE": 62,
        "BMF": 208,
        "AUTORADIO": 84,
        "COMBINE": 91,
        "PORTEC": 81,
        "DIRECTN": 0xE9,
        "CORPRO": 0x3B,     # does seem to share code with CORPROD
        "CORPROD": 0x3B,
        "CORPROG": 0x9B,
        "MDS": 0x57
    }

    # these are OBD pin numbers, if you only know names:
    # klines_psa = { "K8": 2, "K2": 6, "Kiso": 7, "K7": 9, "K9": 10, "K3": 11, "K4": 12, "K6": 13, "K5": 14 }
    psa2k_pins = {
        "X250": {
            "CHAUFFADD": 12, 
            "INJ": 7,
            "ABRASR": 1,        # 1 is only available with KWP_FIAT, not implemented yet
            "DIRECTN": 12,
            "DISQROUT": 9
        },
        "X6": {
            "SUSPVAR": 12
        },
        "X7": {
            "BOITEVIT": 7,
            "CHAUFFADD": 7,
            "SUSPVAR": 12
        },
        "T6": {
            "DIRECTN": 12,
            "INJ": 7
            # "CORPROG": 0,     present but pins unknown yet
            # "CORPROD": 0,
            # "MDS": 0
        },
        "T3": { 
            "INJ": 7
        }
    }

    FTYPE_REQUEST = 0

    # ECUFAMILY.bus
    BUS_CAN_DIAG = 1
    BUS_CAN_IS = 2
    BUS_CAN_BCAN = 4
    BUS_CAN_NONE = 0
    BUS_CAN_BCAN_DIAG = 11 # not used by database currently, allows forcing adapter to use alternative BCAN lines

    # ECUFAMILY.dialog
    DIALOG_NORMAL = 2
    DIALOG_FIAT = 4
    DIALOG_FIAT_SOURCE = "F1"  # for extended addressing

    TREE_HEADERS_LEN = 6

    FRAME_REQUEST = 0
    FRAME_ANSWEROK = 1
    FRAME_ANSWERKO = 2

    # PSA2000 = K-line, DIAGONCAN = KWP2000 or UDS
    protocols = {  2: "PSA2", 4: "QUESTIONREPONSE", 6: "PSA2000", 7:"DIAGONCAN", 8:"KWPONCAN_FIAT",
                    16:	"DIAGONCAN_MMC", 17: "DIAGONCAN_FIAT", 27:	"RAW_CAN" }
    frty = [ "REQUEST", "ANSWEROK", "ANSWERKO" ]
    stattype = [ "NUMERICINTERVAL", "NUMERICFIXED", "BINARYINTERVAL", "BINARYFIXED", "BOOLEAN" ]
    parformattype = [ "BYTES", "BITS", "MAPPED" ]
    parformulatype = [ "LINEAR", "MATHFUNCTION", "MATHPARAMFUNCTION", "COMMFUNCTION" ]
    paramtype = [ "BINARY", "BOOLEAN", "NUMERIC", "IDENTICAL", "COMPUTED" ]
    frapastype = [ "SIMPLE", "PARAMETER", "MAPPED", "BLOCK", "CRC", "DYNAMICBLOCK", "HEADER", "STATICBLOCK", "ENDMARKERDYNAMICBLOCK", "ENDLENGTHDYNAMICBLOCK" ] 
    
    televaltype = [ "NUMERIC", "STATE", "TRANSCRIBED", "IMPOSED", "FILTERSTATE", "INTEGRITYCONSTRAINTDEPENDENT"]
    televalmode = [ "R", "W", "RW"]

    tlcdprocgui = ['STANDARD_GUI', 'GUI_ONLY_READ', 'GUI_NOT_READ', 'WITHOUT_GUI', 'STANDARD_GUI_AND_QUIT', 'WGUI_ONLY_WRITE', 'GUI_NOT_READ_AND_QUIT', 'GUI_WITHOUT_RESULT']
    
    acttype = ["SEQUENTIAL", "ON_OFF"]
    actscrtype = [ "START", "STEP", "NONSTARTED", "INPROGRESS", "ENDOK", "ENDKO" ]
    actserole = ["ACTUATE", "STOP", "GET_STATUS"]
    actctrltype = ["FIXED", "FORCEDBYTESTER", "MONITORBYTESTER"]
    actparamtype = ["FIXED", "INPUT"]
    actstatus = ["PROBLEM", "STOPPED", "NOTSTARTED", "INPROGRESS", "ENDED", "OTHER"]    # other added in 9.179
    actdisptype = ["COMBO", "EDIT", "SLIDER"]       # slider added in v9.135
    actrestype = ["ERROR", "NORMAL"]
    actscntype = ["ENABLE_STOP_AFTER_EACH_STEP", "DISABLE_ALL_STOP", "DISABLE_STOP_AFTER_EACH_STEP"]
    maps = []
    param_keys = [ "abs", "bits", "lenbi", "lenby", "bytes", "len", "pid", "type", "blk", "map", "crc", "dyn", "pencode", "format" ]
    read_dtc_param_names = ['RDBI_FAULTREAD', "RDDTC", "RDSDTC", "RDDTCS"]

    user_modes = { 1: "INTERN", 2: "SIMPLE", 3: "ADVANCED", 4: "EXPERIMENTAL", 5: "GOD" }

    USER_MODE_INTERN = 1
    USER_MODE_SIMPLE = 2
    USER_MODE_ADVANCED = 3
    USER_MODE_EXPERIMENTAL = 4
    USER_MODE_GOD = 5

    def __init__(self, trs=None, path="db/"):
        self.path = path
        self.trs = trs

        self.param_translations = {}

        # don't initialise act test database until asked for
        self.adb = None
        
        # we disable threadlock because we don't do any writing in this library
        self.conn = sqlite3.connect(path + "dtc4.db", check_same_thread=False)
        # get results as dict-alike
        self.conn.row_factory = sqlite3.Row
        self.c = self.conn.cursor()

        self.set_logfile()
        sys.excepthook = self.exception_override

        # load the queries.sql file
        cs = open(path + "queries.sql", 'r')
        queries = cs.read()
        qs = queries.split(";")
        for q in qs:
            spl = q.split(":")
            self.queries[spl[1]] = spl[2]

        try:
            with open(path + "param_translations.yml", "r") as param_trans:
                self.param_translations = yaml.safe_load(param_trans)
                self.log(f"Loaded parameter translation file, found {len(self.param_translations)} entries")

        except FileNotFoundError:
            self.log("No parameter translation file found")

        except Exception:
            self.log("Parameter translation file was corrupt or invalid!")
            self.log(traceback.format_exc())

        try:
            self.procdb = sqlite3.connect(path + "proc.db", check_same_thread=False)
            self.procdb.row_factory = sqlite3.Row
            self.procon = self.procdb.cursor()
        except Exception:
            self.log("Procedure database is not available")
            self.procdb = None
            self.procon = None

    
    start = time.monotonic()

    def profile(self, profile_str = ""):
        return
        self.log("[PROFILE] Time step at " + profile_str + " - " + str(round(time.monotonic() - self.start, 2)))
        self.start = time.monotonic()


    def exception_override(self, *exc_info):
        self.log("Unhandled exception in Diagnostique")
        self.log("".join(traceback.format_exception(*exc_info)))


    def log(self, x):
        '''
        Redirect to log handler
        '''
        self.logger("[BMB] " + str(x))


    def set_logfile(self, fname = "diaglib-log.txt"):
        try:
            self.logfile = open(fname, "w")
            self.log("Opened logfile: " + str(fname))
            self.log("Library version: " + str(self.version))
        except:
            self.logfile = None
            print("[BMB] Unable to create logfile")

    
    def set_log_callback(self, cb):
        if cb is not None:
            self.logback = cb
        else:
            print("NO LOGBACK")


    def logger(self, x):
        print(x)

        try:
            if self.logfile is not None:
                self.logfile.write(x + "\n")
                self.logfile.flush()
            if self.logback is not None:
                self.logback(x)
        except:
            print("ERROR WRITING")
            self.logfile = None


    def warn(self, x):
        self.log(x)


    def query(self, cmd: str, params = None, use_act_db = None, use_proc_db = None):
        '''
        INT: Wrapper for querying the database
        Uses the query database to avoid cluttering code
        - pars is a tuple, or None
        '''
        self.profile()
        
        self.logger("[BQB] Query: " + cmd )
        start = time.monotonic()

        if use_proc_db != None and self.procdb is None:
            self.logger("[BQB] Unable to use procedure database as it failed to load")
            return {}
        
        if cmd in self.queries:
            if params != None:
                parn = []
                q = self.queries[cmd]
                for arg in params:
                    if type(arg) == list:
                        next = ""
                        for x in range(0, len(arg)):
                            next = next + "?,"
                            parn.append(arg[x])
                        q = q.replace("!", next[:-1], 1)
                    else:
                        parn.append(str(arg))

                if use_act_db != None:
                    self.a.execute(q, parn)

                elif use_proc_db != None:
                    if self.procon is not None:
                        self.procon.execute(q, parn)
                    else:
                        self.log(f"PROCEDURES database is not available - skipped query {cmd}")

                else:
                    self.c.execute(q, parn)
            else:
                if use_act_db != None:
                    self.a.execute(self.queries[cmd])

                elif use_proc_db != None:
                    self.procon.execute(self.queries[cmd])

                else:
                    self.c.execute(self.queries[cmd])

            #self.log(f"Query Time: {round(time.monotonic() - start, 2)} sec")


            if use_act_db != None:
                result = self.a.fetchall()

            elif use_proc_db != None:
                if self.procon is not None:
                    result = self.procon.fetchall()
                else:
                    #self.log(f"PROCEDURES database is not available - skipped query {cmd}")
                    result = {}

            else:
                result = self.c.fetchall()

        else:
            result = {}
            self.warn("Invalid database query " + str(cmd) + " requested")

        #self.log(f"Fetch Time: {round(time.monotonic() - start)} sec")
        self.profile("DB")
        return result


    def query_iterative(self, cmd, pars = None, use_act_db=None):
        '''
        INT: Wrapper for querying the database
        Uses the query database to avoid cluttering code
        - pars is a tuple, or None

        Use this for commands where using fetchall() may produce OOM events (such as dumping large amounts of data)
        '''
        self.logger("[BQB] Query_iterative: " + cmd )
        if cmd in self.queries:
            if pars != None:
                parn = []
                q = self.queries[cmd]
                for arg in pars:
                    if type(arg) == list:
                        ne = ""
                        for x in range(0, len(arg)):
                            ne = ne + "?,"
                            parn.append(arg[x])
                        q = q.replace("!", ne[:-1], 1)
                    else:
                        parn.append(str(arg))
                if use_act_db != None:
                    self.a.execute(q, parn)
                else:
                    self.c.execute(q, parn)
            else:
                if use_act_db != None:
                    self.a.execute(q, parn)
                else:
                    self.c.execute(self.queries[cmd])

            return True
        else:
            self.warn("Invalid database query " + str(cmd) + " requested")
        return False


    def set_lid_table(self, table, overwrite = False):
        '''
        Accepts a dictionary containg LID tables to provide
        access to them from all diag_x libraries
        '''
        for zone in table:
            if zone in self.lid_table and not overwrite:
                continue
            self.lid_table[zone] = table[zone]


    def get_lid_table(self, zone):
        '''
        Obtains a memory zone from the LID table
        '''
        if self.lid_table == {}:
            return False
        if zone not in self.lid_table:
            return False
        return self.lid_table[zone]

    '''

    ========= MISCELLANEOUS FUNCTIONS ===============

    '''

    def get_supported_models_list(self):
        '''
        Get a full list of supported marques and models sorted by
        manufacturer and model alphabetically (by nature of dictionary construction only)
        '''
        r = self.c.execute("SELECT * FROM MODELS ORDER BY marque, label")
        v = self.c.fetchall()

        vehs = {}

        for row in v:
            if row["marque"] == "":
                continue
            # exclude models not at all supported yet
            if row["protocol"] == "" or row["protocol"] == "LEX":
                continue
            if row["marque"] not in vehs:
                vehs[row["marque"]] = []
            vehs[row["marque"]].append(dict(row))

        return vehs


    def get_vehicle_name(self, vehid):
        '''
        Get a vehicle name (e.g. X7) from an ID (e.g 42)
        '''
        r = self.c.execute("SELECT internal FROM VEHICLE WHERE vehid = '" + str(vehid) + "' LIMIT 1")
        v = self.c.fetchone()
        vname = v["internal"]
        return vname


    def get_vehicle_model(self, vehid):
        '''
        Get a vehicle make/model from an ID
        '''
        r = self.c.execute(f"SELECT marque,label FROM MODELS WHERE vehid = '{vehid}' LIMIT 1")
        v = self.c.fetchone()

        if v == None:
            self.log(f"Error matching vehicle with reference: {vehid}")
            return { "marque": "", "model": str(vehid) }
        
        return { "marque": v["marque"], "model": v["label"] }


    def get_vehicle_prot(self, vehid):
        r = self.c.execute(f"SELECT protocol FROM vehicle WHERE vehid = '{vehid}' LIMIT 1")
        v = self.c.fetchone()
        if v == None:
            self.log("Error finding protocol for internal ID: {vehid}")
            return 0
        vid = v["protocol"]
        return vid


    def get_vehicle_id(self, vehicle):
        '''
        API: Given an internal code like "X7", get
        the internal ID (that changes between DB releases)
        '''
        veh = vehicle
        if veh == "I3":
            veh = "I3_I4"
        elif veh == "J3":
            veh = "J3_J4"
        elif veh == "M3":
            veh = "M3_M4"
        elif veh == "S3":
            veh = "S3_S4"
        elif veh == "B9E":
            veh = "B9"      # not for crossport, not sure why B9E has different AUTORADIO
        
        vehid = -1

        self.c.execute("SELECT vehid FROM VEHICLE WHERE internal = '" + veh.upper() + "'")
        for opt in self.c.fetchall():
            vehid = opt[0]

        if vehid == -1:
            return False
        else:
            return vehid


    def get_vehicle_ecu_list(self, vehid, filt=True):
        '''
        API: Fetch a list of potential ECUIDs for the vehicle
        (for global test)
        - filt -> false if you want the TELE_x entries included

        Header format is (len 6):
            BUS : TX_H : RX_H : PROTOCOL_NAME : DIALOG_TYPE : TARGET_CODE
        '''
        tree = { "veh": vehid, "prot": self.get_vehicle_prot(vehid) }
        vname = self.get_vehicle_name(vehid)

        q = self.query("get_veh_ecu_list", [vehid])
        self.log("Fetching ECU list for " + str(vehid) + " / " + str(vname))
        if not q:
            return {}

        # Build query into the global tree format expected 
        # ECUCATEGORY.category, ECUTYPE.ecuname, ECU.ecuid, ECUFAMILY.bus, ECUFAMILY.tx_h, ECUFAMILY.rx_h, ECUVE.reco_rq, ECUVE.init_rq
        else:
            for row in q:
                if row["tx_h"] == "" or row["rx_h"] == "":
                    self.log(f"Non-CAN ECU missing headers: {row['category']}")
                    # probably K line / non CAN ECU - handle differently downstream
                    # continue

                protocol_num = int(row["ecuprot"])
                if protocol_num not in self.protocols:
                    protocol = 0
                    self.log(f"Unsupported protocol ID - {protocol_num}")
                else:
                    # interpret DoC_FIAT as DoC for now
                    if protocol_num == 17:
                        protocol_num = 7
                    protocol = self.protocols[protocol_num]

                dialog = None
                target = None

                try:
                    dialog = row["dialog"]
                    target = row["target"]
                except:
                    pass

                if dialog is None:
                    dialog = 0
                if target is None:
                    target = ""

                # if k-line, substitue "target" to the know target codes for different ECU categories
                # as this information is not in the databases
                if protocol == "PSA2000":
                    if row["category"] in self.psa2k_target_codes:
                        target = self.psa2k_target_codes[row["category"]]

                    if vname in self.psa2k_pins:
                        if row["category"] in self.psa2k_pins[vname]:
                            dialog = str(self.psa2k_pins[vname][row["category"]])

                
                hdr = f'{row["bus"]}:{row["tx_h"]}:{row["rx_h"]}:{protocol}:{dialog}:{target}'

                # ignore TELE_ ecus by default as we don't understand what's special about them yet
                if row["category"][:5] == "TELE_" and filt:
                    continue

                if row["category"] not in tree:
                    tree[row["category"]] = {}

                if hdr not in tree[row["category"]]:
                    tree[row["category"]][hdr] = { "RECO": {}, "INIT": {} }

                if row["reco_rq"] not in tree[row["category"]][hdr]["RECO"]:
                    tree[row["category"]][hdr]["RECO"][row["reco_rq"]] = []

                tree[row["category"]][hdr]["RECO"][row["reco_rq"]].append(f'{row["ecuname"]}:{row["ecuid"]}')

                if row["init_rq"] not in tree[row["category"]][hdr]["INIT"]:
                    tree[row["category"]][hdr]["INIT"][row["init_rq"]] = []

                tree[row["category"]][hdr]["INIT"][row["init_rq"]].append(row["ecuname"])

        return tree


    def get_ecuveids_for_ecuid(self, ecuid):
        '''
        Use the ECUVEMAP table to get a list of potential ECUVEIDs
        '''

        data = {}
        v = self.query("get_ecuve_from_ecu", [ecuid])

        if len(v) == 0:
            return False

        else:
            for row in v:
                if row["ecuveid"] not in data:
                    data[row["ecuveid"]] = {
                            "ecuveid": row["ecuveid"], 
                            "reference": row["idreco"], 
                            "name": row["ecuname"], 
                            "variant": row["variant"], 
                            "diaginit": row["init_rq"], 
                            "reco": row["reco_rq"], 
                            "init_ok": row["init_ok"], 
                            "reco_ok": row["reco_ok"]
                            }    
                else:
                    self.log("Duplicate variant name for ECUID " + str(ecuid))
                    continue

        return data

    
    def get_ecuid_for_ecuveid(self, ecuveid):
        '''
        Use ECUVEMAP to get the ECUID for a given ECUVEID
        '''
        v = self.query("get_ecu_from_ecuve", [ecuveid])

        if len(v) == 0:
            return False
        
        for row in v:
            if self.not_blank(dict(row), "ecuid"):
                return int(row["ecuid"])
            else:
                return False


    def identify_ecu_ver_any(self, reco, frame):
        '''
        API: For advanced diagnostics, identify an ECU RECO version
        matching against any known ID, not just for this vehicle
        - reco -> the command used to retrieve the frame
        - frame -> the ecu response frame
        '''
        v = self.query("get_reco_for_reco", [reco])
    

    def identify_ecu_ver(self, veh, ecuname, frame, poss_ecuid):
        '''
        API: Identify an ECUVEID based on a successful RECO frame
        from an ECU
        - veh: the vehicle ID
        - ecuname: the expected ECU name (e.g. ESP81)
        - frame: the data received from the ECU
        - poss_ecuid: the ecuid which matches the name we're searching for
        '''
        vname = self.get_vehicle_name(veh)
        v = self.query("get_reco_from_ecuname", [ecuname, poss_ecuid])
        
        reco = []
        ml = len(frame)
        needle = "_" + vname

        # variant, idreco, idreco_pos, idreco_len
        for rs in v:
            pos = (self.int(rs["idreco_pos"]) - 1) * 2
            end = pos + (self.int(rs["idreco_len"]) * 2)

            if pos < 0:
                continue
            if end > ml or pos > ml:
                continue
            
            if rs["idreco"] == frame[pos:end]:
                reco.append(dict(rs))

        reco2 = []
        if len(reco) == 0:
            return {}
        
        elif len(reco) > 1:
            for r in reco:
                if needle in r["variant"]:
                    reco2.append({ "ECUVEID": r["ecuveid"], 
                                    "VARIANT": r["variant"], 
                                    "RECO": r["idreco"] })
            
            if len(reco2) == 1:
                return reco2[0]
            elif len(reco2) == 0:
                return {}
            else:
                self.log("Failed to narrow down RECO identification. Possible choices are: ")
                self.log("Frame: " + str(frame))
                for r in reco2:
                    self.log(r)
                #return {}
                self.log("Assuming the first one for now...")
                return reco2[0]
        else:
            return { "ECUVEID": reco[0]["ecuveid"], "VARIANT": reco[0]["variant"], "RECO": reco[0]["idreco"] }
    

    def get_ecu_security_cmds(self, ecuveid):

        frames = self.security_request_seed + self.security_request_send
        return self.get_ecu_diag_cmds(ecuveid, command_set = frames)


    def get_ecu_diag_cmds(self, ecuveid, command_set = None):
        '''
        Get a set of ECU diag commands - for example DIAG 1003, RECO 1001, DEFAULT 1001 etc
        '''
        cmds = {}
        if command_set is None:
            command_set = self.CMD_SETS

        frame_sets = self.get_zone_frame_sets(command_set, int(ecuveid))

        z = ["REQUEST", "ANSWEROK", "ANSWERKO"]

        for mtype in frame_sets:

            cmds[mtype] = {}
            for zone in z:
                cmds[mtype][zone] = {}

                keys_max = max(list(frame_sets[mtype][zone]["params"].keys()))

                for i in range(1, keys_max+1):
                    if i not in frame_sets[mtype][zone]["params"]:
                        continue

                    if type(frame_sets[mtype][zone]["params"][i]) == list:
                        break
                    elif self.not_blank(frame_sets[mtype][zone]["params"][i]["val"]):
                        cmds[mtype][zone][i] = frame_sets[mtype][zone]["params"][i]["val"]
                    else:
                        break

                cmds[mtype][zone] = str(self.join_frame(cmds[mtype][zone]))


        return cmds


    def get_ecu_ver(self, vehid, ecuname, reco):
        '''
        API: Given a valid RECO response frame, guess the ECU variant and hence ECUVEID
        - ecuname is a list of the ECU's it might be
        - reco is a response frame from the ECU (pre-sanitised for errors, please)
        '''
        vname = self.get_vehicle_name(vehid)

        if type(ecuname) != list:
            ecuname = [ecuname]

        v = self.query("get_ecu_reco_opts", [ecuname, "%_"+vname+"_%"])
        self.log("Fetching ECU recognition for " + str(reco) + " in " + str(vehid))
        valid_ecu = -1

        for opt in v:
            offset = (opt["idreco_pos"] - 1) * 2
            end = offset + (opt["idreco_len"] * 2)

            if end < len(reco):
                if opt["idreco"] == reco[offset:end]:
                    valid_ecu = opt
                    break
            else:
                continue
        
        if valid_ecu == -1:
            return False
        else:
            return { "ECUVEID" : valid_ecu["ecuveid"], 
                     "VARIANT": valid_ecu["variant"], 
                     "NAME": valid_ecu["ecuname"], 
                     "SERIAL" : valid_ecu["idreco"] }


    def get_recos_for_ecu(self, vehicle_id):  
        '''
        Get the response frames for a given ECU to be compared against the response
        to a Discovery scan request DIAGINIT
        '''
        veh = str(vehicle_id)
        #emf_c_hacks = [ 'EMF_DGT_LVDS_BD', 'EMF_DGT_UDS_GP', 'EMF_DGT_UDS' ]

        v = self.query("get_ecuvetable_for_vehid", [ veh ])
        
        out = {}
        for row in v:
            if row["ecutyname"] not in out:
                out[row["ecutyname"]] = []
            out[row["ecutyname"]].append(dict(row))
        return out


    def get_ecu_zones(self, ecuveid):
        '''
        '''
        zones = []
        v = self.query("get_zones_for_ecuve", [ecuveid])

        if len(v) == 0:
            return False
        
        for row in v:
            zones.append(row["zonename"])
        
        return zones


    def import_proc_yml_to_db(self):
        '''
        '''
        try:
            f = open("db/procedures.yml")
            f_contents = f.readlines()
            f_contents = "".join(f_contents)
            procedures = yaml.safe_load(f_contents)
            proc_id = 0
            step_id = 0
            cmd_id = 0
            response_id = 0

            # predefined steps
            predef_steps = {
                0: "TIMED_OUT",
                1: "OPERATION_COMPLETED_OK",
                2: "OPERATION_ABANDON_NOK",
                3: "ecu_noresponse",
                4: "finish"
            }

            predef_step_ids = {
                "finish": 4,
                "ecu_noresponse": 3,
                "operation_abandon_ok": 2,
                "operation_complete_ok": 1,
                "timed_out": 0
            }

            predef_cmds = {

            }

            categories = {
                0: "normal",
                1: "entry",
                2: "repeat",
                3: "finish"
            }

            category_ids = {
                "normal": 0,
                "entry": 1,
                "repeat": 2,
                "finish": 3
            }

            step_id = len(predef_steps) + 1
            cmd_id = len(predef_cmds) + 1
            step_id = len(predef_steps) + 1

            q_pvm  = "INSERT INTO PRCVEHECUMAP(veh, ecuname, prcid) VALUES (?,?,?)"
            q_proc = "INSERT INTO PRC(prc_id, label_en, help_en) VALUES(?,?,?)"
            q_step = "INSERT INTO PRCSTEP(step_id, prcid, label_en, label_fr, next_step, category) VALUES(?,?,?,?,?,?)"
            q_cmd  = "INSERT INTO PRCCMD(command_id, step, command_svc, interval, time_out, variables) VALUES(?,?,?,?,?,?)"
            q_rsp  = "INSERT INTO PRCRESPONSE(response_id, response_svc, step_target, step_parent) VALUES(?,?,?,?)"

            for procedure in procedures:
                self.log("Importing procedure: " + procedure)

                proc = procedures[procedure]
                r = self.procon.execute(q_proc, [ proc_id, proc["label"]["en"], proc["help"]["en"] ])

                # allocate step IDs in advance to allow response entries to be created
                step_id_allocate = {}
                for step in proc["steps"]:

                    # replace with a template if specified
                    if "template" in proc["steps"][step]:
                        if proc["steps"][step]["template"] in predef_steps:
                            step_id_allocate[step] = predef_step_ids[this_step["template"]]
                            continue

                    step_id_allocate[step] = step_id
                    step_id += 1

                responses = []
                commands = []

                print(step_id_allocate)
                
                # now load the actual steps
                for step in proc["steps"]:
                    this_step = proc["steps"][step]
                    next_step = ""

                    if "template" in this_step:
                        continue

                    if "category" not in this_step:
                        this_step["category"] = "normal"
                    
                    label_en = this_step["label"]["en"]

                    # START
                    if this_step["category"] == "entry":
                        next_step = this_step["next_step"]
                        if next_step not in proc["steps"]:
                            self.log("Unknown step referenced by " + step + "; " + next_step)


                    # REQUEST
                    elif this_step["category"] == "normal":

                        command_svc = "/".join(this_step["command"]["service"])
                        repeat = int(this_step["command"]["repeat"]) if "repeat" in this_step["command"] else 1000
                        timeout = int(this_step["command"]["timeout"]) if "timeout" in this_step["command"] else 10000
                        variables = "/".join(this_step["command"]["variables"]) if "variables" in this_step["command"] else ""

                        print("Add CMD for " + step)
                        commands.append([ cmd_id, step_id_allocate[step], command_svc, repeat, timeout, variables ])
                        cmd_id += 1

                        for response_step in this_step["responses"]:
                            if response_step not in proc["steps"]:
                                self.log("Unknown step referenced by " + step + "; " + response_step)
                                continue

                            if type(this_step["responses"][response_step][0]) == list:
                                for response_child in this_step["responses"][response_step]:
                                    responses.append([ response_id, "/".join(response_child), step_id_allocate[response_step], step_id_allocate[step] ])
                                    response_id += 1
                            else:
                                responses.append([ response_id, "/".join(this_step["responses"][response_step]), step_id_allocate[response_step], step_id_allocate[step] ])
                                response_id += 1


                    # WAITRESPONSE
                    elif this_step["category"] == "repeat":
                        command_svc = "/".join(this_step["command"]["service"])
                        repeat = int(this_step["command"]["repeat"]) if "repeat" in this_step["command"] else 1000
                        timeout = int(this_step["command"]["timeout"]) if "timeout" in this_step["command"] else 10000
                        variables = ""
                        
                        print("Add CMD for " + step)
                        commands.append([ cmd_id, step_id_allocate[step], command_svc, repeat, timeout, variables ])
                        cmd_id += 1

                        for response_step in this_step["responses"]:
                            if response_step not in proc["steps"]:
                                self.log("Unknown step referenced by " + step + "; " + response_step)
                                continue

                            if type(this_step["responses"][response_step][0]) == list:
                                for response_child in this_step["responses"][response_step]:
                                    responses.append([ response_id, "/".join(response_child), step_id_allocate[response_step], step_id_allocate[step] ])
                                    response_id += 1
                            else:
                                responses.append([ response_id, "/".join(this_step["responses"][response_step]), step_id_allocate[response_step], step_id_allocate[step] ])
                                response_id += 1

                    # END
                    elif this_step["category"] == "finish":
                        next_step = 4


                    label_fr = this_step["label"]["fr"] if "fr" in this_step["label"] else this_step["label"]["en"]
                    if next_step == "":
                        next_step_id = ""
                    elif type(next_step) != int:
                        next_step_id = step_id_allocate[next_step]
                    else:
                        next_step_id = next_step

                    self.log("Adding step - " + step)
                    r = self.procon.execute(q_step, [ step_id_allocate[step], proc_id, label_en, label_fr, next_step_id, category_ids[this_step["category"]] ])


                # add all the response entries for this PROCEDURE
                #for response in responses:
                f = self.procon.executemany(q_rsp, responses)

       
                # add all the COMMAND entries
                #for command in commands:
                f = self.procon.executemany(q_cmd, commands)

                # link with all applicable vehicles
                try:
                    if type(proc["vehicle"]) != list:
                        proc["vehicle"] = [ proc["vehicle"] ]

                    # add vehicles                    
                    for vehicle in proc["vehicle"]:
                        veh_id = self.get_vehicle_id(vehicle)

                        if type(proc["ecuname"]) != list:
                            proc["ecuname"] = [ proc["ecuname"] ]

                        # add ecuname
                        for ecuname in proc["ecuname"]:
                            self.procon.execute(q_pvm, [ veh_id, ecuname, proc_id ]) 

                except:
                    print(traceback.format_exc())
                    self.log(procedure + " contains missing information")

                proc_id += 1
            
            self.log("Loaded " + str(proc_id) + " procedures from external file")
            self.procdb.commit()
        except:
            self.log(traceback.format_exc())
            self.log("Unable to load procedures file") 


    def get_procedures_for_ecu(self, veh: int, ecuname: str):
        '''
        Get all known procedures for the specified ecu

        - vehicle ID as integer
        - ecuname as string (ECUID name)

        Returns list of dictionaries (or empty list)
        prcid       = unique procedure ID
        label_en    = title
        help_en     = description
        '''
        output = []
        v = self.query("get_procs_for_ecu_veh", [ veh, ecuname ], use_proc_db=True)
        
        if len(v) == 0:
            return output
   
        for row in v:
            output.append(dict(row))

        return output


    def get_single_procedure(self, proc_id: int):
        '''
        Given a unique procedure ID, get all steps, responses etc
        '''
        steps = {}
        proc_data = self.query("get_proc_properties", [ proc_id ], use_proc_db=True)
        
        if len(proc_data) == 0:
            self.log(f"WARNING: Found no data for procedure ID {proc_id}. This shouldn't happen in normal usage")
            return steps
   
        for row in proc_data:
            step = row["step_id"]
            if step not in steps:
                steps[step] = {
                    "category": row["category"],
                    "label": row["label_en"]
                }

                if row["next_step"] != "":
                    steps[step]["next_step"] = row["next_step"]

                if row["command_svc"] != None:
                    steps[step]["command"] = row["command_svc"].split("/")
                
                if row["interval"] != None:
                    steps[step]["interval"] = row["interval"]

                if row["time_out"] != None:
                    steps[step]["timeout"] = row["time_out"]

                if row["variables"] != None and row["variables"] != "":
                    variables = row["variables"].split("/")
                    steps[step]["variables"] = {}

                    # each variable gets a name, description for the user, and a method of sending
                    # I: integer, so send 100 as 0x64
                    # R: raw, so send 100 as 0x0100
                    for variable in variables:
                        try:
                            varname, vardesc, vartype, lenby = variable.split(",")
                            steps[step]["variables"][varname] = { "label": vardesc, "lenby": int(lenby), "type": vartype }
                        except:
                            self.log(f"Invalid procedure variable in ID {proc_id}: {variable}")
                        
            # can be multiple responses per step
            if row["response_svc"] != None:
                if "responses" not in steps[step]:
                    steps[step]["responses"] = {}
                
                steps[step]["responses"][row["step_target"]] = row["response_svc"].split("/")


        return steps




    '''

    ====== GET TELECODING AND DATA FRAMES ========================

    '''

    def get_telecoding(self, ecuid, ecuveid, dofilter=True, flag_type=False, filt_level = None):
        '''
        API: Fetch any and all telecoding data available
        for the given ECU. This function redirects to get_data_frames
        if the ECU is a "newer" type

        - filter is False if you don't want parameters with default values to have their states removed (dev/expert only)

        TODO: Data loading needs rewriting to import to the new telecode format
         Problem is we don't have a tie to edataval, we only have names to go on
         to match with discval (not sure if thats reliable)
        '''
        output = {}

        result = self.query("get_tlcd_old_validate", [ecuveid, ecuid])

        if len(result) == 0:
            # no old style tlcd for this ecu
            d = self.get_data_frames(ecuid, ecuveid, qtype="telenew", dont_post_process = True, filt_level = filt_level)
            if flag_type:
                return (self.TLCD_NEW, d)
            else:
                return d
                
        tlp_to_parname = {}

        # this gives labels for the parameters and states as defined in TLCDXML
        # PID in this case is parname (database name collision)
        old = self.query("get_tlcd_old_xml", [ecuid])
        param_descriptors = {}

        for row in old:

            if row["pid"] not in param_descriptors:
                param_descriptors[row["pid"]] = { "label"   : row["tlabel"], 
                                                  "help"    : row["help"], 
                                                  "states"  : {}, 
                                                  "impval"  : ""
                                                  }

            if row["tlpid"] not in tlp_to_parname:
                tlp_to_parname[row["tlpid"]] = row["pid"]

            param_descriptors[row["pid"]]["states"][row["vname"]] = row["vlabel"]

        tlcd = {}
        # frid => pid => statid
        pids = []
        has_mapped = False
        map_me = {}

        # get imposed values
        v = self.query("get_tlcd_imp_val", [ecuid])

        for row in v:
            if row["tlpid"] in tlp_to_parname:
                pnm = tlp_to_parname[row["tlpid"]]

                param_descriptors[pnm]["impval"] = row["impval"]

            # hack - NUMERO_RELATIF doesn't seem to deserve a parameter definition
            # It has some weird internal defintion
            elif row["ptname"] in self.TLCD_PROCMAP_SPECIAL_CASES:
                if row["ptname"] not in param_descriptors:
                    param_descriptors[row["ptname"]] = { "label": "", 
                                              "help": "", 
                                              "states": {}, 
                                              "impval": ""}

                param_descriptors[row["ptname"]]["impval"] = "FF"
                    # tbc make this actually work it out based on WZONE/RZONE
                    # but currently we know it's always FF

            else:
                self.log(f"Parameter {row['tlpid']} referenced but not known")

        '''
        See issue tracker - this was intended to add in all parameters with write-services
        However that's not an accurate method, because there are params with write services that can't be written....
        (e.g. live parameters)

        # Get all zones supported by ECU
        zones = []
        ecu_zones = self.query("get_ecuve_zones", [ecuveid])
        for z in ecu_zones:
            zones.append(z["zoneid"])


        # Get all write zones
        wzone_list = []
        wzone_pids = []
        wzones = self.query("get_wdb_for_old_tele", [zones])
        for row in wzones:
            wzone_list.append(row["zoneid"])
            wzone_pids.append(row["pid"])

        # Get all read zones for all parameters that can be written also
        rzones = self.query("get_rdb_for_old_tele", [zones, wzone_pids])
        for row in rzones:
            wzone_list.append(row["zoneid"])
        '''

        # And fetch more labels & state names from EDATAVAL for this ECUID, for parameters not specified in TLCDXML
        v = self.query("get_edata_for_ecu", [ecuid])
        edata_vals = {}
        edata_val_ids = {}

        for row in v:
            edata_vals[row["parname"]] = { "parname": row["parname"], 
                                    "label"  : self.trs.decodalate(row["elabel"]), 
                                    "scrdat" : { 
                                        row["scrname"]: row["edatid"] 
                                        }, 
                                    "help"   : self.trs.decodalate(row["ehelp"]), 
                                    "unit"   : row["eunit"], 
                                    "edatid" : row["edatid"] }

            edata_val_ids[row["edatid"]] = row["parname"]

        # Next get the compatible parameters from FRAPAS    (removed wzone_list) and OR ZONES.zoneid IN (!) from SQL
        result = self.query("get_tlcd_frapas_params", [ecuveid, ecuid])
        # zonename => frametype
        for row in result:
            if row["pid"] not in pids:
                pids.append(row["pid"])
            zone = row["zonename"]

            frame_type = self.frty[row["ftype"]]

            if zone not in tlcd:
                tlcd[zone] = {}

            if frame_type not in tlcd[zone]:
                tlcd[zone][frame_type] = { "frid"  : row["frid"], 
                                           "params": {} 
                                        }

            if row["parname"] not in tlcd[zone][frame_type]["params"]:

                if row["dattype"] == None:
                    dat_type = ""
                else:
                    dat_type = self.paramtype[row["dattype"]]

                if row["pf_dattype"] is None:
                    param_format = ""
                else:
                    param_format = self.parformattype[row["pf_dattype"]]

                tlcd[zone][frame_type]["params"][row["parname"]] = { "parname": row["parname"], 
                                                              "impval": "", 
                                                              "pid": row["pid"], 
                                                              "defval": row["val"], 
                                                              "pos": row["pos"], 
                                                              "abs": row["abs_no"], 
                                                              "blk": row["blo"], 
                                                              "crc": row["crc"],
                                                              "lenby": row["len_bytes"],
                                                              "lenbi": row["len_bits"],
                                                              "type":  dat_type,
                                                              "map": row["map"],
                                                              "frid": row["frid"],
                                                              "frtype": row["ftype"],
                                                              "dyn": row["dyn"],
                                                              "format": param_format,
                                                              "msk": row["bin_mask"],
                                                              "states": {} }
                #if row["parname"] in edv:
                #    for key in edv[row["parname"]]:
                #        tlcd[zone][fty]["params"][row["parname"]][key] = edv[row["parname"]][key]

            if self.not_blank(dict(row), "map"):
                has_mapped = True
                map_me[zone] = row["map"]
                #self.log("Zone " + str(row["map"]))
        

        lid_other = []
        lid_reported = []

        # do BSI LID mapping if needed
        if has_mapped:
            for bsi_zone in tlcd:
                if bsi_zone not in map_me:
                    continue

                for cat in tlcd[bsi_zone]:
                    # check if there's any map in this
                    zone = map_me[bsi_zone]
                    
                    lid = self.get_lid_table(zone)
                    # some zones don't have maps
                    # if the user failed to read the LID properly from the ECU we can't do anything with it
                    # parse_params_hex will detect "MAPPED" and refuse to parse/skip it
                    if zone == "":
                        continue
                    if not lid:
                        if zone not in lid_reported:
                            lid_reported.append(zone)
                            self.log("LID - No data for zone " + str(zone))
                        continue

                    lid_order = []
                    new_plist = {}

                    for absmap in lid:
                        found = False
                        for pm in tlcd[bsi_zone][cat]["params"]:
                            param = tlcd[bsi_zone][cat]["params"][pm]

                            if param["abs"] == -1:
                                lid_other.append(param)
                                continue
                            
                            if param["abs"] == absmap:
                                lid_order.append(param)
                                found = True
                                break
                            

                        if not found:
                            if len(lid_order) == 0:
                                # no abs found, ignore this frame
                                break
                            else:
                                # zone B0 and B1 are not mapped
                                self.log(f"Gave up on zone {zone} because we have no parameter at abs {absmap}")
                                #print(tlcd[zy][cat]["params"][pm])
                                break
                            
                    if not found:
                        #self.debug("No data to map in " + str(zone) + " : " + str(cat))
                        continue
                    if len(lid_order) == 0:
                        #self.debug("No data to map in " + str(zone) + " : " + str(cat))
                        continue
                    #if lid_order[0]["format"] != "MAPPED":
                     #   self.debug("Told not to map data in " + str(zone) + " : " + str(cat))
                     #   continue
                    
                    # now we have a list of param names in the right order
                    exp_pos = lid_order[0]["pos"]
                    cur_pos_by = 0
                    current_bit_pos = 0

                    for param in lid_order:
                        new_plist[param["parname"]] = param

                        # update position
                        base_pos = new_plist[param["parname"]]["pos"]
                        if base_pos != exp_pos:
                            self.log("Error - parameters in the same MAP had different base positions")
                            # abandon this zone, it will be wrong
                            break

                        length_in_bits = new_plist[param["parname"]]["lenbi"]

                        # update formatting
                        if length_in_bits != 0:
                            new_plist[param["parname"]]["format"] = "BITOSET"
                            new_plist[param["parname"]]["abs"] = (cur_pos_by * 8) + current_bit_pos
                            
                            # if overflow into next byte
                            if current_bit_pos + length_in_bits > 7:
                                if current_bit_pos + length_in_bits > 14:
                                    self.log("LID BIT length overran 2 bytes - unhandled")
                                    break
                                cur_pos_by += 1
                                current_bit_pos = length_in_bits - (8 - current_bit_pos)

                            else:
                                current_bit_pos += length_in_bits
                            #print("Pos@ " + str(cur_pos_by) + " : " + str(cur_pos_bi) + " - adding " + str(new_plist[param["parname"]]["lenbi"]) + " bits")

                        elif new_plist[param["parname"]]["lenby"] != 0:
                            new_plist[param["parname"]]["format"] = "BITOSET"
                            
                            if current_bit_pos != 0:
                                current_bit_pos = 0
                                cur_pos_by += 1
                            new_plist[param["parname"]]["abs"] = (cur_pos_by * 8)

                            cur_pos_by += new_plist[param["parname"]]["lenby"]
                            #print("Pos@ " + str(cur_pos_by) + " : " + str(cur_pos_bi) + " - adding " + str(new_plist[param["parname"]]["lenby"]) + " bytes")
                        else:
                            # something broke
                            #new_plist[param["parname"]]["format"] = "MAPPED"
                            pass

                        # DEBUGGING if new_plist[param["parname"]]["label"] == "":
                        #    print(param["parname"] + ": " + str(new_plist[param["parname"]]["abs"]))
                        #else:
                        #    print(new_plist[param["parname"]]["label"] + ": " + str(new_plist[param["parname"]]["abs"]))
                    tlcd[bsi_zone][cat]["params"] = new_plist

                    # append non-abs parameters
                    for entry in lid_other:
                        tlcd[bsi_zone][cat]["params"][entry["parname"]] = entry
                    self.log(f"Added LID mapped zone {zone}")


        # STATES can have an exact value, or a min-max range
        sta = self.query("get_states_for_pids", [pids])
        states = {}
        for row in sta:
            if row["pid"] not in states:
                states[row["pid"]] = {}

            stat = { "val": row["statval"], 
                     "mini": row["mini"], 
                     "maxi": row["maxi"] }

            states[row["pid"]][row["statname"]] = stat

        # apply states to the Pids
        for zone in tlcd:
            for frame_type in tlcd[zone]:
                for param in tlcd[zone][frame_type]["params"]:

                    # HACK - SID and LID will have "set" values for all useful services, so we don't
                    #        want to load all their possible states (waste of CPU + RAM)
                    if param != "SID" and param != "LID":
                        if tlcd[zone][frame_type]["params"][param]["pid"] in states:
                            tlcd[zone][frame_type]["params"][param]["states"] = states[tlcd[zone][frame_type]["params"][param]["pid"]]

                    if param in param_descriptors:
                        tlcd[zone][frame_type]["params"][param]["label"]  = param_descriptors[param]["label"]
                        tlcd[zone][frame_type]["params"][param]["help"]   = param_descriptors[param]["help"]
                        tlcd[zone][frame_type]["params"][param]["impval"] = param_descriptors[param]["impval"]

                        for state in tlcd[zone][frame_type]["params"][param]["states"]:
                            if state in param_descriptors[param]["states"]:
                                tlcd[zone][frame_type]["params"][param]["states"][state]["label"] = param_descriptors[param]["states"][state]


        output = tlcd

        if dofilter:
            for zone in tlcd:
                for frame_type in tlcd[zone]:
                    for param in tlcd[zone][frame_type]["params"]:
                        if tlcd[zone][frame_type]["params"][param]["defval"] != "":
                            tlcd[zone][frame_type]["params"][param]["states"] = {}

        if flag_type:
            return (self.TLCD_OLD,output)
        else:
            return output


    def get_zone_frame_set(self, frid):
        '''
        API: SINGLE VERSION (str) - Given a frame ID, get all frames with that zoneID. In practice this
        should give you the REQ/ANSOK/ANSKO frames for a given query
        '''
        out = {}
        # CRITICAL!!! must use ORDER BY pos
        v = self.query("get_fridset_from_frid", [frid])

        if len(v) == 0:
            return False

        for row in v:
            frame_type = self.frty[row["ftype"]]

            if frame_type not in out:
                out[frame_type] = { "frid"   : row["frid"], 
                             "params" : {} 
                             }

            t_var = { "val"     : row["val"], 
                      "parname" : row["parname"], 
                      "crc"     : row["crc"] 
                      }
        
            if row["pos"] in out[frame_type]["params"]:
                if type(out[frame_type]["params"][row["pos"]]) != list:
                    out[frame_type]["params"][row["pos"]] = [ out[frame_type]["params"][row["pos"]] ]

                out[frame_type]["params"][row["pos"]].append(t_var)
            else:
                out[frame_type]["params"][row["pos"]] = t_var
        
        return out


    def get_zone_frame_sets(self, zones, ecuveid):
        '''
        API: LIST VERSION (setS) Given a list of ZONES and ECUVEID, get all frames with those zone IDS
        '''
        out = {}
        # CRITICAL!!! must use ORDER BY pos
        v = self.query("get_fridset_from_zone_list", [ecuveid, zones])

        if len(v) == 0:
            return False

        for row in v:
            zone = row["zonename"]
            if zone not in out:
                out[zone] = {}

            frame_type = self.frty[row["ftype"]]

            if frame_type not in out[zone]:
                out[zone][frame_type] = { "frid": row["frid"], 
                                          "params" : {} }

            t_var = { "val"     : row["val"], 
                      "parname" : row["parname"],
                      "crc"     : row["crc"] }
        
            if row["pos"] in out[zone][frame_type]["params"]:
                if type(out[zone][frame_type]["params"][row["pos"]]) != list:
                    out[zone][frame_type]["params"][row["pos"]] = [ out[zone][frame_type]["params"][row["pos"]] ]

                out[zone][frame_type]["params"][row["pos"]].append(t_var)
            else:
                out[zone][frame_type]["params"][row["pos"]] = t_var
        
        return out


    def get_params_from_telecoding(self, ecuid, ecuveid, filt_level=None):
        '''
        API: Fetch telecoding in terms of parameters with all info needed to use them
        The function flow is a bit messy here, because each of the functions in the tree
        provides a differently formatted output, with different data. All can be useful,
        so we don't merge the functions together (the performance hit is minimal)

        this fn
        - > get_telecoding
        - - > get_data_frames
        - - > or get_telecoding directly
        '''
        tlcd_type, tlcd_out = self.get_telecoding(ecuid, ecuveid, flag_type=True, filt_level = filt_level)
        tlcd = {}

        skipped_params = 0

        # filter data in terms of parameter
        if tlcd_type == self.TLCD_OLD:
            old_params = self.get_params_from_telecoding_old(ecuid, ecuveid, tlcd_out, filt_level)
        else:
            # already formatted ok
            old_params = tlcd_out

        if "params" not in old_params:
            self.log("No parameters available for this ECU")
            return False
        
        self.log(f"GPFT received {len(old_params['params'])} parameters to process")

        frids_zones = {}

        if "requests" not in old_params or "writes" not in old_params:
            self.log(f"No frames found for {ecuveid}")
            return False

        frame_info = self.query("get_frame_info", [list(old_params["requests"].keys()) + list(old_params["writes"].keys()), [2]])

        if not frame_info or len(frame_info) == 0:
            self.log(f"Could not parse telecoding params because no frame information was available from the database, {ecuveid}")
            return False
        
        for row in frame_info:
            if row["frid"] not in frids_zones:
                frids_zones[row["frid"]] = row["val"]

        for param_name in old_params["params"]:
            if param_name in ("SID", "LID"):
                continue

            par = old_params["params"][param_name]
            out_param = { "parname": param_name }

            # apply translation of parameter names to "friendly" names from a local file, if present
            if par["label"] == "":
                labels = self.param_translations.get(param_name, None)
                if labels is None:
                    out_param["label"] = param_name
                else:
                    try:
                        out_param["label"] = labels["label"].get(self.trs.lng, labels.get("en", param_name))
                        out_param["help"] = labels["help"].get(self.trs.lng, labels.get("en", param_name))
                    except KeyError:
                        #self.log(f"Error in param_translations for parameter {param_name}")
                        out_param["label"] = param_name
                        out_param["help"] = ""
            else:
                out_param["label"] = par["label"]
                out_param["help"] = par["help"]

            # The main difference is in how each type handles finding the zones
            # for each parameter. Old Tele can be a bit hit and miss, so there is
            # some logic to make a "best guess". Here, for safety, we ignore parameters that are
            # missing a read or write service.

            # OLD TELE: Copy the zread service, but delete things that aren't valid
            # (so library users can do if X in Y instead of value checking)
            if "zread" in par:
                out_param["read"] = []
                for frame in par["zread"]:
                    lng = len(out_param["read"])
                    out_param["read"].append(self.clean_parameter_descriptor(frame))
                    out_param["read"][lng]["zone"] = frids_zones[frame["frid"]]
            
            # NEW TELE:
            elif "frid_read" in par:
                # nice and clean
                # dyns should have been post processed by now, but we still use them
                # because diag_telecode will need the information

                try:
                    gs = { "blk": par["blk"], 
                        "crc": par["crc"], 
                        "dyn": par["dyn"], 
                        "format": par["format"],
                        "frid":  par["frid_read"],
                        "map": par["map"],
                        "pid": par["pid"],
                        "pos": par["pos_read"],
                        "type": par["type"],
                        "zone": frids_zones[par["frid_read"]] 
                        }
                except KeyError:
                    # this fails specifically with a C5-X IVI, but not others..??
                    self.log(f"Exception in param {param_name}, skipped it")
                    #self.log(traceback.format_exc())
                    #exit()
                    continue

                if self.not_blank(par, "lenbi"):
                    gs["lenbi"] = par["lenbi"]
                if self.not_blank(par, "lenby"):
                    gs["lenby"] = par["lenby"]
                if self.not_blank(par, "msk"):
                    gs["msk"] = par["msk"]

                out_param["read"] = [gs]
                

                # format of hex param
                if par["format"] == "BITS":
                    out_param["lenbi"] = par["lenbi"]
                    out_param["msk"] = par["msk"]

                elif par["format"] == "BYTES":
                    out_param["lenby"] = par["lenby"]

                if par["format"] == "BITOSET":
                    out_param["abs"] = par["abs"]
                    out_param["map"] = par["map"]
                
                out_param["format"] = par["format"]

                if par["blk"] != 0:
                    out_param["parser"] = "BLOCKNORM"
                    out_param["blk"] = par["blk"]

                elif par["crc"] != 0:
                    out_param["crc"] = par["crc"]
                    out_param["parser"] = "CRC"

                elif self.not_blank(par["dyn"]):
                    out_param["dyn"] = par["dyn"]
                    out_param["parser"] = "BLOCKDYN"

                else:
                    out_param["parser"] = "NORM"
           
            # OLD TELE
            if "zwrite" in par:
                out_param["write"] = []
                for frame in par["zwrite"]:
                    lng = len(out_param["write"])
                    out_param["write"].append(self.clean_parameter_descriptor(frame))
                    out_param["write"][lng]["zone"] = frids_zones[frame["frid"]]

            # NEW TELE:
            elif "frid_write" in par:
                gs = { "blk": par["blk"], 
                        "crc": par["crc"], 
                        "dyn": par["dyn"], 
                        "format": par["format"],
                        "frid":  par["frid_write"], 
                        "map": par["map"], 
                        "pid": par["pid"] ,
                        "pos": par["pos_write"], 
                        "type": par["type"], 
                        "zone": frids_zones[par["frid_write"]] 
                    }

                if self.not_blank(par, "lenbi"):
                    gs["lenbi"] = par["lenbi"]
                if self.not_blank(par, "lenby"):
                    gs["lenby"] = par["lenby"]
                if self.not_blank(par, "msk"):
                    gs["msk"] = par["msk"]

                out_param["write"] = [ gs ]
            
                # See if there are multiple available write zones/commands
                # TODO: See if this can work for OLD-style TELE too (EMF is known to use multi-zones)
                if "zone_writes" in par:
                    for zone in par["zone_writes"]:
                        if par["frid_write"] == par["zone_writes"][zone]:
                            continue
                        else:
                            gs = { "blk": par["blk"],
                                   "crc": par["crc"], 
                                   "dyn": par["dyn"], 
                                   "format": par["format"],
                                   "frid":  par["zone_writes"][zone],
                                   "map": par["map"],
                                   "pid": par["pid"] ,
                                   "pos": par["pos_write"], 
                                   "type": par["type"], 
                                   "zone": frids_zones[par["zone_writes"][zone]] 
                                }

                            out_param["write"].append(gs)

            # now states
            # old just gives "states" which are label & value
            # new gives tlcd_states, hex_states and edv_states
            if "states" in par:
                out_param["states"] = par["states"]
            
            if "hex_states" in par and "edv_states" in par:
                out_param["states"] = []
                for hexstat in par["hex_states"]:
                    for edvstat in par["edv_states"]:
                        if hexstat["name"] == edvstat["name"]:
                            lbl = edvstat["label"]  # if edvstat["label"] != "" else edvstat["name"]
                            out_param["states"].append({ "label": lbl, "name": hexstat["name"], "val": hexstat["val"] })

            elif "edv_states" in par:
                out_param["states"] = []

                for edvstat in par["edv_states"]:
                    lbl = edvstat["label"]          # if edvstat["label"] != "" else edvstat["name"]
                    val = edvstat["single_val"]
                    if "format" in out_param:
                        if out_param["format"] == "BINARY":
                            val = str(bin(self.int(val)))
                        elif out_param["format"] == "BOOLEAN":
                            val = str(bin(self.int(val)))
                            if len(val) > 1:
                                val = str(val)[:1]
                    out_param["states"].append({ "label": lbl, "name": edvstat["name"], "val": val })
            
            elif "hex_states" in par:
                out_param["states"] = []

                for hexstat in par["hex_states"]:
                    xc = { "val": hexstat["val"] } if hexstat["val"] != "" else { "min": hexstat["min"], "max": hexstat["max"] }
                    xc["label"] = hexstat["name"]
                    xc["name"] = hexstat["name"]
                    out_param["states"].append(xc)

            # apply locally available labels if needed
            if "states" in out_param:
                for state in out_param["states"]:
                    if state["label"] == "":
                        try:
                            # get the value in local language, else in english, or failing that just return the name
                            self.param_translations[param_name]["states"][state["name"]].get(self.trs.lng, 
                                                                                            self.param_translations[param_name]["states"][state["name"]].get("en", state["name"]))
                        except KeyError:
                            state["label"] = state["name"]
            
            if "read" in out_param and "write" in out_param:
                tlcd[param_name] = out_param
            #elif "read" in tpar:
            #    tlcd[param] = tpar
            else:
                skipped_params += 1

        # append the services separately as there is often commonality
        # and it keeps the parameter tree cleaner

        self.log("GPFT exported " + str(len(tlcd)) + " parameters for use")
        self.log("Skipped " + str(skipped_params) + " because of invalid R/W services")

        return tlcd

    
    def clean_parameter_descriptor(self, par):
        '''
        Reduce code duplication in get_tlcd_params above
        '''
        tpar = {}
        
        tpar["format"] = par["format"]
        tpar["type"] =  par["type"]
        
        tpar["frid"] =  par["frid"]
        tpar["pid"] =  par["pid"]
        tpar["pos"] =  par["pos"]
        
        if par["abs"] != -1:
            tpar["abs"] = par["abs"]
        if par["map"] != 0:
            tpar["map"] = par["map"]
        if par["blk"] != 0:
            tpar["blk"] = par["blk"]
        if par["crc"] != 0:
            tpar["crc"] = par["crc"]
        if par["dyn"] != None:
            tpar["dyn"] = par["dyn"]
        if par["lenbi"] != 0:
            tpar["lenbi"] = par["lenbi"]
        if par["lenby"] != 0:
            tpar["lenby"] = par["lenby"]
        if par["msk"] != 0:
            tpar["msk"] = par["msk"]
        if self.not_blank(par, "impval"):
            tpar["impval"] = par["impval"]
        if self.not_blank(par, "defval"):
            tpar["defval"] = par["defval"]

        return tpar


    def get_params_from_telecoding_old(self, ecuid, ecuveid, tlcd_out, filt_level = None):
        '''
        INT
        '''
        pars = {}
        frids = []

        if filt_level is None:
            filt_level = self.MODE_EXPERIMENTAL

        '''
        We want to take the telecoding data we just got, which is all from FRAPAS,
        and then filter and narrow it down to telecoding procedures valid for this
        car, using TELESCR

        TODO: Cross-load other procedures for other vehicles, to enable features
              not usually available on this car? 
        '''
        

        for zone in tlcd_out:
            for frame in tlcd_out[zone]:
                frid = tlcd_out[zone][frame]["frid"]
                if frid not in frids:
                    frids.append(frid)
        
        # now look up those frids and get the zone IDs from TLCDPROCMAP
        v = self.query("get_zones_for_old_tlcds", [ecuid])
        wzones = []
        rzones = []
        procs = {}
        for row in v:
            if row["wzone"] not in wzones:
                wzones.append(row["wzone"])
            if row["rzone"] not in rzones:
                rzones.append(row["rzone"])
            if row["pname"] not in procs:
                procs[row["pname"]] = { "rlabel": row["rlabel"], 
                                        "wlabel": row["wlabel"], 
                                        "wzones": [ row["wzone"]], 
                                        "rzones": [ row["rzone"] ] 
                                    }
            else:
                procs[row["pname"]]["wzones"].append(row["wzone"])
                procs[row["pname"]]["rzones"].append(row["rzone"])
       

        # Convert the output and sort by parameter
        for zone in tlcd_out:
            
            for frame in tlcd_out[zone]:
                for param in tlcd_out[zone][frame]["params"]:
                    p = tlcd_out[zone][frame]["params"][param]

                    if zone in wzones:
                        ztype = "zwrite"
                    elif zone in rzones:
                        ztype = "zread"
                    elif "RDBI_" in zone or "RDBLID_" in zone:    
                        ztype = "zread"
                    elif "WDBLID" in zone or "WDBI_" in zone:
                        ztype = "zwrite"
                    elif "ZI" in zone:
                        #TODO: Match SERVICE name instead of subparsing ZONE
                        ztype = "zid"
                    elif "REQDWN" in zone:
                        ztype = "zwrite"
                    elif "REQUPL" in zone:
                        ztype = "zread"
                    else:
                        self.log("DEVWARN: Zone " + str(zone) + " could not be identified - " + str(tlcd_out[zone][frame]["frid"]))
                        continue

                    if ztype == "zwrite" and p["frtype"] != 0:
                        continue
                    if ztype == "zread" and p["frtype"] != 1:
                        continue
                    
                    zframe = { "frid": tlcd_out[zone][frame]["frid"], 
                                "defval": p["defval"],
                                "zone": zone,
                                "pos": p["pos"],
                                "msk": p["msk"],
                                "impval": p["impval"] 
                            } 

                    for n in self.param_keys:
                        if n in p:
                            zframe[n] = p[n]

                    if param not in pars:
                        # This previously filtered parameters without a label, but I think this is a decision
                        # for the end-user of the data, not us directly. 
                        # If there's no label/help, the parameter is valid for the CAN frame, but not valid
                        # for this ECU ID (this can happen if the ECUID is for a car which)
                        # doesn't use/do anything for the given parameter, even though the e.g. radio
                        # does support it. For example, some cars display CLIM data on EMF

                        # HOWEVER - because it's valid for the CAN frame we should send it anyway, with whatever
                        #           data we read from the ECU straight back

                        if True: # "label" in p or filt_level >= self.MODE_EXPERIMENTAL:
                            if filt_level == self.MODE_SIMPLE and p["label"] == "":
                                continue                                              

                            if "help" not in p:
                                p["help"] = ""
                            if "label" not in p:
                                p["label"] = ""

                            pars[param] = {  "help": self.trs.decodalate(p["help"]), 
                                             "states": [], 
                                             "zread": [], 
                                             "zwrite": [], 
                                             "zid": [] }

                            pars[param][ztype].append(zframe)
                            pars[param]["label"] = self.trs.decodalate(p["label"])
                            

                            for stat in p["states"]:
                                if "label" in p["states"][stat]:
                                    pars[param]["states"].append({ "label": self.trs.decodalate(p["states"][stat]["label"]),
                                                                   "val": p["states"][stat]["val"] } )
                                else:
                                    pars[param]["states"].append({ "label": stat, 
                                                                   "val": p["states"][stat]["val"] } )

                    else:
                        pars[param][ztype].append(zframe)
        

        zreads = {}
        zwrites = {}
        # Check and filter zones to have minimum number of read/write choices per parameter
        # NOTE: Sometimes, there is no read service already for a parameter
        #       This is because there is a mismatch between parname in TLCD and parname in PARAMS
        # TODO: Not sure yet how to handle this, probably answer is to use pos/mask/etc from write service
        # TODO: Check more parameters to ensure the format REALLY REALLY is the same
        for par in pars:
            p = pars[par]

            if len(p["zread"]) > 0:
                #if len(p["zread"]) == 1:
                #    pars[par]["zread"] = pars[par]["zread"][0]
                #else:
                pos = p["zread"][0]["pos"]
                msk = p["zread"][0]["msk"]

                for zone in p["zread"]:
                    if zone["frid"] not in zreads:
                        zreads[zone["frid"]] = zone["zone"]

                    if zone["pos"] != pos or zone["msk"] != msk:
                        if par != "SID":
                            self.log("Different RDBLID for " + str(par))                  
                pars[par]["zread"] = pars[par]["zread"]

            else:
                # todo, use write positions if they exist
                pars[par]["zread"] = {}

            if len(p["zwrite"]) > 0:
                #if len(p["zwrite"]) == 1:
                #    pars[par]["zwrite"] = pars[par]["zwrite"][0]
                #else:
                pos = p["zwrite"][0]["pos"]
                msk = p["zwrite"][0]["msk"]

                for zone in p["zwrite"]:
                    if zone["frid"] not in zwrites:
                        zwrites[zone["frid"]] = zone["zone"]

                    if zone["pos"] != pos or zone["msk"] != msk:
                        if zone["impval"] == '' and par != "SID":
                            self.log("Different WDBLID for " + str(par))                   
                pars[par]["zwrite"] = pars[par]["zwrite"]

            else:
                pars[par]["zwrite"] = {}

        return { "params": pars, 
                 "requests": zreads, 
                 "writes": zwrites } 


    def get_old_telecoding_screens_for_ecu(self, ecuid):
        '''
        DEV: Get the telecoding services as listed in the XML files
        This is not always complete (sometimes the service is made in the DLL)
        but it can help work out which parameters to change for a given ECU
        '''

        v = self.query("get_old_tlcd_screens", [ecuid])

        out = {}
        for row in v:
            out[row["pname"]] = { "read": self.trs.decodalate(row["rlabel"]), 
                                "write": self.trs.decodalate(row["wlabel"])}
        
        return out


    def is_write_svc(self, dic):
        '''
        Determine if a given dict with zone and service name specifiers
        and FRAPAS info is a write service
        '''
        dic = dict(dic)
        write_svcs = ["WDTCI_", "WDBI_", "WDBLID_", "WDBCID_" ]

        for zone in write_svcs:
            if zone in dic["zonename"]:
                return True
        
        if "ZI" in dic["zonename"]:
            if dic["sername"] == "WDBI" or dic["sername"] == "WDBLID":
                return True
            elif dic["sername"] == "RDBI" or dic["sername"] == "RDBLID":
                return False
            else:
                self.log("Unidentified service for ZI: " + dic["sername"])
        
        return False


    def is_read_svc(self, dic):
        '''
        Determine if a given dict with zone and service name specifiers
        and FRAPAS info is a read service
        '''
        dic = dict(dic)
        read_svcs = ["RDTCI_", "RDBI_", "RDBLID_", "RDBCID_" ]

        for zone in read_svcs:
            if zone in dic["zonename"]:
                return True
        
        if "ZI" in dic["zonename"] or "ZA" in dic["zonename"]:
            if dic["sername"] == "RDBI" or dic["sername"] == "RDBLID":
                return True
            elif dic["sername"] == "WDBI" or dic["sername"] == "WDBLID":
                return False
            else:
                self.log("Unidentified service for ZI: " + dic["sername"])
        
        return False


    def get_data_frames(self, ecuid, ecuveid, qtype="parameters", dont_post_process = False, filt_level = None):
        '''
        API: Fetch a list of frames of live data
        See explanation in the documentation, this process has several sources of data
        - Request no post-processing if you're exporting the data for use elsewhere (list by parameter, not zone)
        - Qtype is parameters for live data/param measurement, and telenew for telecoding post 2010

        Sorry.
        '''
        tree = {}

        self.log("Fetching " + str(ecuid) + " / " + str(ecuveid) + " / " + qtype)

        if qtype == "parameters":
            rframe = "get_edata_for_ecu"
        elif qtype == "telenew":
            rframe = "get_teledata_for_ecu"

        v = self.query(rframe, [ecuid])
        edatids = {}
        frids = {}
        wunits = []
        runits = []
        has_mapped = False

        if len(v) == 0 and qtype == "parameters":
            return tree

        elif len(v) == 0:
            self.log("WARNING: no config screen data exists, attempting brute force method")
            v = self.query("get_params_with_write_svc", [ecuid, ecuveid])

        if len(v) == 0:
            if filt_level != self.MODE_EXPERIMENTAL:
                self.log("Still no data found, giving up")
                return tree

            else:
                self.log("EXPERIMENTAL: Using parameters with write services directly - not all of these will be accurate")
                v = self.query("get_params_from_ecuveid_only", [ecuveid])
                if len(v) == 0:
                    self.log("Tried raw, still not data found")
                    return tree
        
        # EDATA.elabel, EDATA.ehelp, EDATA.eunit,EDATA.parname
        # Its possible for a parameter to appear multiple times in a FRAPAS frame, each with a different BLOCK or BLOCKDYN marker

        for row in v:
            try:
                scrname = row["scrname"]
            except:
                scrname = "default"

            if row["edatid"] == "":
                self.log("DEVWARN: Empty edatid")
                continue
            if row["parname"] in tree:
                tree[row["parname"]]["scrdat"][scrname] = row["edatid"]
            else:
                tree[row["parname"]] = { "parname": row["parname"], 
                                        "label": self.trs.decodalate(row["elabel"]), 
                                        "scrdat": { scrname: row["edatid"] }, 
                                    "help": self.trs.decodalate(row["ehelp"]), 
                                    "unit" : row["eunit"],
                                    "edatid": row["edatid"] }

            edatids[row["edatid"]] = row["parname"]
            
            try:
                if row["runit"] not in runits:
                    runits.append(row["runit"])
            except Exception:
                pass

            try:
                if row["wunit"] not in wunits:
                    wunits.append(row["wunit"])
            except Exception:
                pass

        if len(tree) == 0:
            return tree

        params = self.query("match_edata_for_ecu", [ecuveid, list(tree.keys())])
        pids = {}

        # now calculate the request services to get these parameters
        requests = {}
        writes = {}       
        trash = {}     
        blocks_present = []
        warned_dupli_dynval = False
        
        zones_for_search = []
        multidid = 0
        zones_frame_data = {}

        # FRAMES.frid, PARAMS.pid, PARAMS.parname, ZONES.zonename, FRAPAS.pos, PARAMS.dattype
        self.log(f"Now fetching data for {len(params)} parameters")

        self.log("Generating zone list")
        for par in params:
            if par["parname"] in tree:
                if par["zonename"] not in zones_for_search:
                    zones_for_search.append(par["zonename"])

        if len(zones_for_search) == 0:
            self.log("No service zones found for the ECU")
            return tree

        collated_zones = self.query("get_frames_for_zonename_collated", [ecuveid, zones_for_search ])
        if len(collated_zones) == 0:
            self.log("DEVWARN: No services found in database for the zone list")
            return tree

        # build a cached set of zone data for later use
        for row in collated_zones:
            if row["zonename"] not in zones_frame_data:
                zones_frame_data[row["zonename"]] = []
            else:
                for frame_row in zones_frame_data[row["zonename"]]:
                    if frame_row["frid"] != row["frid"]:
                        self.log("DEVWARN: Mismatched frame ID, dumping problematic result")
                        self.log(zones_frame_data[row["zonename"]])
                        self.log(frame_row)

            zones_frame_data[row["zonename"]].append(dict(row))
            
        # now step through all parameters
        # and load as much data as we can find
        for par in params:
            if par["parname"] in tree:

                # basic information
                if "pid" in tree[par["parname"]]:
                    if tree[par["parname"]]["pid"] != par["pid"]:
                        self.log("Different PID error")
                        continue

                else:
                    pids[par["pid"]] = par["parname"]
                    tree[par["parname"]]["pos"] = par["pos"]
                    tree[par["parname"]]["type"] = self.paramtype[int(par["dattype"])]
                    tree[par["parname"]]["pid"] = par["pid"]                
                    tree[par["parname"]]["blk"] = par["blo"]
                    tree[par["parname"]]["map"] = par["map"]
                    tree[par["parname"]]["crc"] = par["crc"]
                    tree[par["parname"]]["pencode"] = par["encode"]


                # dynamic block
                if self.not_blank(dict(par),"dyn"):
                    if "dyn" not in tree[par["parname"]]:
                        tree[par["parname"]]["dyn"] = {}
                    if "dyn_pos" not in tree[par["parname"]]:
                        tree[par["parname"]]["dyn_pos"] = {}
                    if par["dynval"] in tree[par["parname"]]["dyn"] and not warned_dupli_dynval:
                        self.log("DEVWARN: Duplicate dynval in frame tree")
                        warned_dupli_dynval = True
                        continue

                    tree[par["parname"]]["dyn"][par["dynval"]] = { "pos": par["dynbytepos"], 
                                                                    "ref": par["dyn"],
                                                                    "len": par["dynbytelen"],
                                                                    "key": par["dynkey"] }
                    tree[par["parname"]]["dyn_pos"][par["dyn"]] = par["pos"]

                # static block  
                if self.not_blank(dict(par),"blo"):
                    if par["blo"] not in blocks_present:
                        blocks_present.append(par["blo"])


                # blo and dyn are checked above
                # still not convinced this does enough checking for errors....
            
                if "dyn" not in tree[par["parname"]]:
                    tree[par["parname"]]["dyn"] = {}

                # bugfix - don't load multidid services (TODO this will speed up reading/writing data
                # but it means a whole world of pain, because of crossover with normal parameters (MP as opposed to CFG
                # so you get 700 odd parameters added in validate_edata below (and write services don't get detected properly)
                # This is only a "thing" for UDS ecus, so is something we have to support in future...
                if "MULTIDID" in par["zonename"]:
                    multidid += 1
                    continue

                frame_id = par["frid"]

                if frame_id in frids:
                    
                    if frame_id in writes:
                        tree[par["parname"]]["frid_write"] = frame_id
                        tree[par["parname"]]["zone_write"] = par["zonename"]

                        if "zone_writes" not in tree[par["parname"]]:
                            tree[par["parname"]]["zone_writes"] = {}
                            
                        tree[par["parname"]]["zone_writes"][par["zonename"]] = frame_id
                        tree[par["parname"]]["pos_write"] = par["pos"]            
                        continue

                    elif frame_id in requests:                     
                        tree[par["parname"]]["frid_read"] = frame_id
                        tree[par["parname"]]["zone_read"] = par["zonename"]
                        tree[par["parname"]]["pos_read"] = par["pos"]
                        continue

                    elif frame_id in trash:
                        continue
                
                # only lookup in DB if we don't already know it
                frids[par["frid"]] = par["zonename"]

                
                # TODO: This bit is inefficient because it takes a lot of queries, but batching up is hard
                #          (if you figure it out, you get a cookie xD)

                # Get frames for zonenname will get all frames for a param measure request
                # because they typically have the same zone name with a different service
                # However, telecoding includes the service (RD/WD) in the zonename so you
                # have to get them individually
                #v = self.query("get_frames_for_zonename", [ecuveid, frids[frame_id] ])
                #print(">> " + str(frids[frame_id]))

                #if len(v) == 0:
                #    self.log("DEVWARN: No services found for zone: " + str(frids[frame_id]))
                #    continue
                #for res in v:

                # EXPERIMENTAL: use the collated zone-name data fetched above for speed boost
                for res in zones_frame_data[par["zonename"]]:

                    # SEE ALSO: Line 774 ish of get_telecoding_old which does the same
                    #           thing for old telecoding

                    # The problem here is that a given parameter might have multiple frame IDs
                    # For example it might have
                    #   RDBLID  - but only in the ANSWEROK
                    #   IOCBCID - in REQUEST
                    #   WDBLID  - in REQUEST

                    # What we want for telecoding is READ/WRITE (req/ansok/ansko)
                    # and what we want for parameters is just READ.request/ANSWEROK
                    # But whilst telecoding (new) specifies the zones, parameters don't
                    # so we have to guess them

                    # BUGFIX: If the ZONE identifier (pos2) is a BLOCK, then it will also have the position 1 in FRAPAS (because)
                    #         it's ACTUAL position is in BLOCKNORM.
                    if self.not_blank(dict(res), "blo"):
                        pos = res["blobytepos"]
                    else:
                        pos = res["pos"]

                    if self.is_read_svc(res):
                        #
                        if frame_id not in requests:
                            requests[frame_id] = {}
                        requests[frame_id][pos] = res["val"]
                        tree[par["parname"]]["frid_read"] = par["frid"]
                        tree[par["parname"]]["zone_read"] = par["zonename"]
                        tree[par["parname"]]["pos_read"] = par["pos"]
                        

                    elif self.is_write_svc(res) or frids[frame_id] in wunits:
                        #
                        if frame_id not in writes:
                            writes[frame_id] = {}

                        writes[frame_id][pos] = res["val"]
                        tree[par["parname"]]["frid_write"] = par["frid"]
                        tree[par["parname"]]["zone_write"] = par["zonename"]
                        tree[par["parname"]]["pos_write"] = par["pos"]

                    else:
                        if frame_id not in trash:
                            trash[frame_id] = {} 
                        trash[frame_id][pos] = res["val"]
                        tree[par["parname"]]["frid_trash"] = par["frid"]

            else:
                self.log("DEVWARN: Impossibility. " + str(par["parname"]) + " with ID " + str(par["pid"]) + " isn't a known parameter")
                continue

        if multidid > 0:
            self.log("Skipped " + str(multidid) + " services containing MULTIDID")

        if len(trash):
            self.log("Added " + str(len(trash)) + " services to TRASH")

        '''
        This is a tremendous hack. It fetches all the parameters from the frame IDs found above, and then
        checks they've all been added to the tree. Essentially, it means even parameters without definitions/labels/units
        in EDATA will still be included in the tree. Normally, we wouldn't care about this (in fact we don't want it), but in order 
        to make the BSI LID mapping work we HAVE to have to ALL parameters otherwise there will be a gap in the ABS and the zone mapping will fail

        NOTE this is only true for parameters, actuator tests can do it a simpler way
        '''

        self.log("Created " + str(len(tree)) + " parameters")


        if filt_level == self.MODE_EXPERIMENTAL:
            val = self.query("get_read_and_write_svc_experimental", [list(requests.keys()), ecuveid])
        else:
            val = self.query("validate_edata_for_ecu", [list(requests.keys())])
        #val = []
        ctr = 0
        for par in val:
            #if par["parname"] in skip_list:
                #continue

            if par["parname"] not in tree:
                pids[par["pid"]] = par["parname"]
                ctr += 1

                tree[par["parname"]] = { "VOID": 0 }
                tree[par["parname"]]["parname"] = par["parname"]
                tree[par["parname"]]["pid"] = par["pid"]
                tree[par["parname"]]["abs"] = par["abs_no"]
                tree[par["parname"]]["type"] = self.paramtype[int(par["dattype"])]
                tree[par["parname"]]["blk"] = par["blo"]
                tree[par["parname"]]["map"] = par["map"]
                tree[par["parname"]]["crc"] = par["crc"]
                tree[par["parname"]]["scrdat"] = { "VOID" :  0 }
                tree[par["parname"]]["label"] = ""
                tree[par["parname"]]["help"] = ""
                tree[par["parname"]]["unit"] = ""
                tree[par["parname"]]["pencode"] = par["encode"]
                tree[par["parname"]]["edatid"] = ""

                # TODO: add write services to allow r/writing undocumented parameters 

                if self.not_blank(dict(par),"dyn"):
                    if "dyn" not in tree[par["parname"]]:
                        tree[par["parname"]]["dyn"] = {}
                    if "dyn_pos" not in tree[par["parname"]]:
                            tree[par["parname"]]["dyn_pos"] = {}
                    tree[par["parname"]]["dyn"][par["dynval"]] = { "pos": par["dynbytepos"], 
                                                                   "ref": par["dyn"], 
                                                                   "len": par["dynbytelen"], 
                                                                   "key": par["dynkey"] }
                    tree[par["parname"]]["dyn_pos"][par["dyn"]] = par["pos"]
                else:
                    tree[par["parname"]]["dyn"] = ""


            if par["frid"] in frids:   
                if par["frid"] in writes:
                    tree[par["parname"]]["frid_write"] = par["frid"]
                    tree[par["parname"]]["zone_write"] = par["zonename"]
                    if "zone_writes" not in tree[par["parname"]]:
                        tree[par["parname"]]["zone_writes"] = {}
                    tree[par["parname"]]["zone_writes"][par["zonename"]] = par["frid"]
                    tree[par["parname"]]["pos_write"] = par["pos"]            
                    continue
                elif par["frid"] in requests:                     
                    tree[par["parname"]]["frid_read"] = par["frid"]
                    tree[par["parname"]]["zone_read"] = par["zonename"]
                    tree[par["parname"]]["pos_read"] = par["pos"]
                    continue
                elif par["frid"] in trash:
                    continue
                

        if ctr > 0:
            self.log("Force added " + str(ctr) + " unlabelled parameters")

        # Fetch any/all relevant formatting for the parameters
        if len(pids) > 0:
            # TODO: Might [should] be able to merge some of this with LEFT JOIN's

            states = self.query("get_states_for_pids", [list(pids.keys())])           
            pformu = self.query("get_parformulas", [list(pids.keys())])
            pforma = self.query("get_parformats", [list(pids.keys())])
            
            if len(blocks_present) > 0:
                self.log("Loading blocks...." + str(len(blocks_present)))
                pblocka = self.query("get_blocks", [list(pids.keys())])

                if len(pblocka) > 0:
                    for row in pblocka:
                        if pids[row["pid"]] in tree:
                            tree[pids[row["pid"]]]["block"] = {}

            # if there's any STATES
            if len(states) > 0:
                for st in states:
                    if pids[st["pid"]] in tree:
                        if "hex_states" not in tree[pids[st["pid"]]]:
                            tree[pids[st["pid"]]]["hex_states"] = []
                        tree[pids[st["pid"]]]["hex_states"].append({ "name" : st["statname"], 
                                                                    "val" : st["statval"], 
                                                                    "min" : st["mini"], 
                                                                    "max": st["maxi"] })

            # if there's EDATAVAL stuff to load (parameters only)
            vals = self.query("get_edataval", [list(edatids.keys())])
            if len(vals) > 0:
                for vl in vals:
                    if "edv_states" not in tree[edatids[vl["edatid"]]]:
                        tree[edatids[vl["edatid"]]]["edv_states"] = []
                    tree[edatids[vl["edatid"]]]["edv_states"].append({ "name" : vl["dvname"], 
                                                                        "label": self.trs.decodalate(vl["dvlabel"]), 
                                                                        "is_default": vl["dvdefault"], 
                                                                        "min_val": vl["dvinf"], 
                                                                        "max_val": vl["dvsup"], 
                                                                        "single_val": vl["dvcom"] })

            # get extra information from TELECODE descriptors
            if qtype == "telenew":
                vals = self.query("get_teledataval", [list(edatids.keys())])
                if len(vals) > 0:
                    for vl in vals:
                        if "tlcd_states" not in tree[edatids[vl["edatid"]]]:
                            tree[edatids[vl["edatid"]]]["tlcd_states"] = []
                        dx = dict(vl)
                        tree[edatids[vl["edatid"]]]["tlcd_states"].append(dx)
                        
            # if there's valid PARFORMULA's (factor/offset)
            if len(pformu) > 0:
                for pf in pformu:
                    if pids[pf["pid"]] in tree:
                        tree[pids[pf["pid"]]]["factor"] = pf["cfactor"]
                        tree[pids[pf["pid"]]]["offset"] = pf["coffset"]
                        tree[pids[pf["pid"]]]["formula"] = self.parformulatype[pf["ctype"]]

            # if there's valid PARFORMATS (byte mask/length etc)
            if len(pforma) > 0:
                for pa in pforma:
                    if pids[pa["pid"]] in tree:
                        tree[pids[pa["pid"]]]["lenbi"] = pa["len_bits"]
                        tree[pids[pa["pid"]]]["lenby"] = pa["len_bytes"]
                        tree[pids[pa["pid"]]]["msk"] = pa["bin_mask"]
                        tree[pids[pa["pid"]]]["abs"] = pa["abs_no"]
                        tree[pids[pa["pid"]]]["endian"] = pa["byteorder"]
                        tree[pids[pa["pid"]]]["format"] = self.parformattype[pa["dattype"]]

                        if tree[pids[pa["pid"]]]["format"] == "MAPPED":
                            has_mapped = True
              

        # at this point, tree is a list of the available parameters
        # for export for other usages, return now
        if dont_post_process:
            out = { "requests": requests, "params": tree }
            if len(writes) > 0:
                out["writes"] = writes
            return out

        trunk = { "ff": {}, "params": {}, "id": {} }
        '''
         otherwise, post-process parameters into freeze frames, params and IDENTIFICATION
            ff
            - zone
                - request frame
                - params []
                    - param
                    - param
        '''

        ff_svcs = []

        for param in tree:

            # get memory zone
            zone = -1
            if "frid_read" in tree[param]:
                tree[param]["pos"] = tree[param]["pos_read"]
                if tree[param]["frid_read"] in requests:
                    if not self.not_blank(requests[tree[param]["frid_read"]], 2):

                        # the FRAME is a dynamic one, no prescribed value for ZONE, but its stored in dyn (theoretically)
                        if self.not_blank(tree[param], "dyn"):
                            zone = -1
                            if type(tree[param]["dyn"]) == dict:
                                for dyn in tree[param]["dyn"]:
                                    # should only be 1 key but we don't know what it is
                                    # TODO: Change structure of this dict to PARAM => STATE instead of STATE => PARAM?
                                    k = tree[param]["dyn"][dyn]["key"]
                                    v = dyn
                                    # now have to get VALUE of STATE V for PARAM k
                                    if k not in tree:
                                        self.log("Invalid dynamic block key reference: " + str(k) + " in " + str(param))
                                        continue

                                    if "hex_states" not in tree[k]:
                                        self.log("Missing state values for dynamic block key reference: " + str(k) + " in " + str(param))
                                        continue

                                    for s in tree[k]["hex_states"]:
                                        if s["name"] == v:
                                            zone = s["val"]

                                            if not self.not_blank(tree[param],"zonename"):
                                                tree[param]["zonename"] = "!" + zone
                            
                            else:
                                self.log("Wrong datatype for dynamic block specified in - " + str(param) + " : " + str(requests[tree[param]["frid_read"]]))
                                continue

                            if zone == "":
                                self.log("Failed to find matching RDBI for " + str(k) + " [ " + str(v) + " ] in " + str(param))
                                continue
                        else:
                            self.log("Invalid requests dict (r) and no dynamic block specified - " + str(param) + " : " + str(requests[tree[param]["frid_read"]]))
                            continue

                    # we can just take the zone from the FRID_READ frame
                    else:
                        zone = requests[tree[param]["frid_read"]][2]

            if "frid_write" in tree[param]:           
                if tree[param]["frid_write"] in writes:
                    if 2 not in writes[tree[param]["frid_write"]]:
                        self.log("Invalid requests dict (w): " + str(requests[tree[param]["frid_write"]]))
                        continue
                    else:
                        zone = writes[tree[param]["frid_write"]][2]

            if zone == -1:
                if "pid" in tree[param]:
                    # Then we failed to identify the parameter properly
                    self.log("No available frame for " + str(param) + ": " + str(tree[param]["pid"]))
                    #pprint.pprint(tree[param])
                # If there's no PID, the parameter is most likely stored in the DLL, so we skip it
                continue

            # put them in  the FF zone, but we have to get the frame info later
            for scrname in tree[param]["scrdat"]:
                if scrname[:2] == "VA":
                    cat = "ff"
                    fr_fr = { "frid": tree[param]["frid_read"], "zone" : zone }
                    if fr_fr not in ff_svcs:
                        ff_svcs.append(fr_fr)

                elif "IDENTIFICATION" in scrname:
                    cat = "id"

                else:
                    cat = "params"

            if zone not in trunk[cat]:
                trunk[cat][zone] = {  "params": [] }

                if "frid_read" in tree[param]:
                    if tree[param]["frid_read"] in requests:
                        trunk[cat][zone]["request"] = requests[tree[param]["frid_read"]]

                if "frid_write" in tree[param]:
                    if tree[param]["frid_write"] in writes:  
                        trunk[cat][zone]["writes"] = writes[tree[param]["frid_write"]]

            trunk[cat][zone]["params"].append(tree[param])

        # give a list of FRIDs to get FF data
        trunk["ff"]["frames"] = ff_svcs
        
        #  apply LID mapping (BSI04 only)
        #  This section corrects MAPPED values using the LID database (which must be read from the ecu before this function is called)
        #  The LID table gives you a list of ABS numbers. You have to find the parameters with those abs numbers,
        #  and then use their lengths cumulatively to work out the position of each next parameter

        if has_mapped:
            for cat in list(trunk.keys()):
                for zone in list(trunk[cat].keys()):
                    lid = self.get_lid_table(zone)
                    # some zones don't have maps
                    # if the user failed to read the LID properly from the ECU we can't do anything with it
                    # parse_params_hex will detect "MAPPED" and refuse to parse/skip it
                    if not lid:
                        continue

                    lid_order = []
                    new_plist = {}

                    for absmap in lid:
                        found = False
                        for param in trunk[cat][zone]["params"]:
                            if param["abs"] == absmap:
                                lid_order.append(param)
                                found = True
                                break
                        if not found:
                            # zone B0 and B1 are not mapped
                            self.log("Gave up on zone " +  str(zone) + " because we have no parameter at abs " + str(absmap))
                            #print(trunk[cat][zone]["params"][0]["frid_read"])
                            break

                    if not found:
                        continue
                    if len(lid_order) == 0:
                        continue
                    if lid_order[0]["format"] != "MAPPED":
                        continue
                    
                    # now we have a list of param names in the right order
                    exp_pos = lid_order[0]["pos"]
                    cur_pos_by = 0
                    cur_pos_bi = 0

                    for param in lid_order:
                        new_plist[param["parname"]] = param

                        # update position
                        base_pos = new_plist[param["parname"]]["pos"]
                        if base_pos != exp_pos:
                            self.log("Error - parameters in the same MAP had different base positions")
                            # abandon this zone, it will be wrong
                            break

                        lbi = new_plist[param["parname"]]["lenbi"]

                        # update formatting
                        if lbi != 0:
                            new_plist[param["parname"]]["format"] = "BITOSET"

                            new_plist[param["parname"]]["abs"] = (cur_pos_by * 8) + cur_pos_bi
                            
                            # if overflow into next byte
                            if cur_pos_bi + lbi > 7:
                                if cur_pos_bi + lbi > 14:
                                    self.log("LID BIT length overran 2 bytes - unhandled")
                                    break
                                cur_pos_by += 1
                                cur_pos_bi = lbi - (8 - cur_pos_bi)

                            else:
                                cur_pos_bi += lbi
                            #print("Pos@ " + str(cur_pos_by) + " : " + str(cur_pos_bi) + " - adding " + str(new_plist[param["parname"]]["lenbi"]) + " bits")

                        elif new_plist[param["parname"]]["lenby"] != 0:
                            new_plist[param["parname"]]["format"] = "BITOSET"
                            
                            if cur_pos_bi != 0:
                                cur_pos_bi = 0
                                cur_pos_by += 1
                            new_plist[param["parname"]]["abs"] = (cur_pos_by * 8)

                            cur_pos_by += new_plist[param["parname"]]["lenby"]
                            #print("Pos@ " + str(cur_pos_by) + " : " + str(cur_pos_bi) + " - adding " + str(new_plist[param["parname"]]["lenby"]) + " bytes")
                        else:
                            # something broke
                            new_plist[param["parname"]]["format"] = "MAPPED"


                        # DEBUGGING if new_plist[param["parname"]]["label"] == "":
                        #    print(param["parname"] + ": " + str(new_plist[param["parname"]]["abs"]))
                        #else:
                        #    print(new_plist[param["parname"]]["label"] + ": " + str(new_plist[param["parname"]]["abs"]))

                    trunk[cat][zone]["params"] = list(new_plist.values())

        # also append READ/WRITE ACK/NACK
        return trunk

    
    def get_frame_info(self, frids, pos = 1):
        '''
        INT: Get a value for a FRAME position
        Useful for getting service number or LID for a known FRAME
        Returns a dictionary of
        frid => [ 0 => 21, 1 => C0 ]
        '''
        tree = {}
        if type(pos) != list:
            pos = [ pos ]
        v = self.query("get_frame_info", [frids, pos])

        if len(v) == 0:
            return tree

        for i in v:
            if i["frid"] not in tree:
                tree[i["frid"]] = {}
            tree[i["frid"]][i["pos"]] = i["val"]

        return tree


    def get_dtc_all(self, ecuid):
        '''
        API: Get all DTCs for an ECUID
        '''
        result = self.query("get_dtc_all", [ecuid])
        if len(result) == 0:
            return {}
        return result


    def get_dtc_printout(self, ecuid, ecuveid, dtci):
        '''
        API: Get a human readable print of DTC code/char for display
        -dtcs => string of one DTC or dict of DTCs + char codes
        '''
        dtcs = None
        char_codes = None

        if type(dtci) == dict or type(dtci) == OrderedDict:
            dtcs = list(dtci.keys())
            char_codes = list(dtci.values())
        if type(dtci) == str:
            dtcs = [dtci]
        if type(dtci) == int:
            dtcs = [str(dtci)]
        if type(dtci) == list:
            dtcs = dtci

        if dtcs == None:
            return {}

        out = {}

        noms = self.get_dtc(ecuid, dtcs)
        chas = self.get_dtc_char(ecuid, ecuveid, dtcs, char_codes)

        for code in noms:
            if code not in out:
                out[code] = { "fframe" : [] }

            for key in noms[code]:
                if type(noms[code][key]) == str:
                    if key == "internal_code":
                        out[code]["print_code"] = self.dtc_hexa_to_reality(str(noms[code][key]))
                    if noms[code][key] != "":
                        out[code][key] = self.trs.decodalate(noms[code][key])
                else:
                    out[code][key] = noms[code][key]
                    
            if code in chas:
                for stat in chas[code]:
                    if stat == "ff":
                        out[code][stat] = chas[code][stat]
                        continue
                    if "chars" not in out[code]:
                        out[code]["chars"] = []
                    out[code]["chars"].append({"title" : chas[code][stat]["label"], "value": list(chas[code][stat]["states"].values()) })
  
        return out
    

    def translate_dtc_prefix(self, dtc):
        '''
        Translate DTC name according to standard
        '''
        if type(dtc) == str:
            dtc = int(dtc, 16)

        subsystem = dtc >> 14
        fault_type = (dtc >> 12) & 0b11
        fault_type_second_digit = (dtc >> 8) & 0xF
        dtc_remainder = dtc & 0xFF

        subsystems = {
            0: "P",
            3: "U",
            1: "C",
            2: "B"
        }
        dtc_str = f"{subsystems[subsystem]}{fault_type}{fault_type_second_digit:01X}{dtc_remainder:02X}"
        return dtc_str


    def get_dtc(self, ecuid, code):
        '''
        API: Get a DTC given by code
        '''
        result = self.query("get_dtc_all", [ecuid])
        out = {}

        if type(code) != list:
            codes = [code]
        else:
            codes = code

        if result == False:
            return {}

        for dtc in result:
            if dtc["internal_code"] in codes:
                out[str(dtc["internal_code"])] = dict(dtc)

            elif "F" + str(dtc["internal_code"]) in codes:
                out["F" + str(dtc["internal_code"])] = dict(dtc)
                out["F" + str(dtc["internal_code"])]["internal_code"] = "F" + str(dtc["internal_code"])

        for dtc_hex in code:
            if dtc_hex == "NRODTC":
                continue

            # TODO - need to apply translate_dtc_prefix here, but need to know if this is UDS or KWP ECU
            # might be as simple as if it's not a F code then apply translation...need to check
            if dtc_hex not in out:
                out[dtc_hex] = { "print_code": str(dtc_hex), 
                                "internal_code": str(dtc_hex),
                                "dtclabel": "Unknown", "fframe": {}, 
                                "dtcid": 0, "chars": [], 
                                "ff": '0'}
        
        if len(out) > 0:
            return out
        else:
            self.warn("Invalid DTC(s) " + str(code) + " provided for ECU " + str(ecuid))
            return {}


    def gen_parse_param_format(self, row):
        '''
        INT: Convert a SQlite query result into a dict tree for a param
        according to what formatting it uses
        '''
        row = dict(row)

        if self.not_blank(row,"defval"):
            val = row["defval"]
        elif self.not_blank(row, "val"):
            val = row["val"]
        else:
            val = ""

        if row["bin_mask"] != "":
            f = { "pos": row["pos"], "msk": row["bin_mask"], "val": val }
            if self.not_blank(row, "len_bytes"):
                f["lenby"] = row["len_bytes"]
            elif self.not_blank(row, "len_bits"):
                f["lenbi"] = row["len_bits"]
            else:
                self.log("invalid")
            return f
        elif row["len_bytes"] != "":
            return { "pos": row["pos"], "lenby": row["len_bytes"], "val": val }
        elif row["len_bits"] != "":
            return { "pos": row["pos"], "lenbi": row["len_bits"], "val": val }
        else:
            self.log("Error, please report this: cannot figure out how to parse fault reading for " + str(row["parname"]))
            return { "pos": row["pos"] }


    def parse_dtc_response(self, ecuid, ecuveid, response = None):
        '''
        Extract DTC codes from the response string
        YOU are responsible for checking the validity, though we try to fail
        gracefully.

        This whole function is a horrendous hack, because there is little/no standardisation
        between protocols on the name of parameters/formats etc. Could possibly be improved
        just by having a different processor per-protocol?
        '''

        accepted_no_dtc = [ "NRODTC", "DTCSAM" ]
        accepted_dtc_code = [ "DTC_CODE", "JDD_DTC_CODE" ]

        tree = OrderedDict()
        pos = 0

        if response is None or response == "":
            return False
        
        r_len = len(response)

        fr = self.get_dtc_frame(ecuveid)

        if fr == False or "ANSWEROK" not in fr:
            self.log("Error - please report this - cannot find valid descriptor for " + str(ecuveid))
            return False

        # HC: database confirms NRODTC always used for KWP, not necessarily others
        # Safe to assume that its the first non-specified value though
        fr = fr["ANSWEROK"]

        faultno_id = []
        for parm in accepted_no_dtc:
            if parm in fr:
                faultno_id = fr[parm]
                break
        
        if faultno_id != []:
            #self.log("Unknown dtc no parameter in " + str(ecuveid))
            #self.log(str(fr))
            #return False
    
            # read number of faults
            if "lenby" in faultno_id:
                if faultno_id["pos"] + faultno_id["lenby"] > r_len:
                    self.log("Fault response frame too short to contain no. faults")
                    return False
            else:
                self.log("Unsupported type for NRODTC")
                return False
            
            # HC: database search confirms NRODTC always raw value
            pos = (faultno_id["pos"] - 1) * 2
            lng = faultno_id["lenby"] * 2
            nrodtc = self.int(response[pos:pos+lng], base=16)
            if nrodtc == 0:
                return {}

        block = None
        num_faults = -1

        # check for and get the block
        for param in fr:
            if "blo" in fr[param]:
                block = param

        dtc_id = ""
        
        for parm in fr[block]["params"]:
            if parm in accepted_dtc_code:
                dtc_id = parm
                break

        if dtc_id == "":
            self.log("Unknown dtc code identifier in " + str(ecuveid))
            self.log(str(fr))
            return False

        if block is None:
            self.log("Error - please report this - cannot find/invalid block for " + str(ecuveid))
            return False

        # 1-indexed to zero-indexed, then byte to character offset
        trim_to = (fr[block]["pos"] - 1) * 2
        if trim_to >= r_len:
            self.log("Fault response frame was too short to contain data")
            return False

        response = response[trim_to:]
        resp = re.findall('.{1,2}', response) 
        if "lenby" not in fr[block]:
            self.log("Length of block not specified - possibly indicates corrupt database")
            return False
        blo_len = self.int(fr[block]["lenby"])

        if num_faults != -1:
            if len(resp) != blo_len * num_faults:
                # need to get the rest of the data with 17FFFF
                self.log("Warning: not all faults contained in this frame, should be requested next")
        else:
            pass

        if len(resp) % blo_len != 0:
            self.log("Fault response frame was invalid for the expected format: " + str(ecuveid) + " for " + str(response))
            self.log(str(blo_len) + " : " + str(num_faults))
            return False

        num_faults = int(len(resp) / blo_len)
        self.log("Found " + str(num_faults) + " to be processed")
        pars = fr[block]["params"]
        
        # response[0] is now the start of the data, in byte array
        for offset in range(0, num_faults):
            
            off = offset * blo_len
            if off >= len(resp):
                break
            this_block = resp[off:off+blo_len]

            # First get DTC_CODE
            raw_val = -1
            if "lenby" in pars[dtc_id]:
                prv = pars[dtc_id]["pos"] - 1
                ple = pars[dtc_id]["lenby"]
                if ple == 3:
                    ple = 2
                raw_val = "".join(this_block[prv:prv+ple]).upper()
            elif "msk" in pars[dtc_id]:
                raw_val = self.unmask(self.bytes_to_bits(this_block), pars[dtc_id]["msk"])
                lng = int(len(raw_val) / 8)
                raw_val = self.int(raw_val, base=2)
                raw_val = "{0:0{1}x}".format(raw_val, lng).upper()

            if raw_val == -1:
                self.log("Unsupported parameter type in DTC parse: " + str(param) + " : ECUVE: " + str(ecuveid))
                continue
            else:
                # TODO: BSI faults are shown in DiBo as F5FF/F40A (which is the full code inc. chars)
                #       Do we respect that? Or do we do what's here, which is convert to a normal 4 digit fault code?
                code = raw_val

            # pad with a leading zero (FIXME: might break on earlier cars with 2 digit codes  )
            if len(code) == 2:
                code = "0" + code


            binned = []

            # Now get rest of PARAMS
            for param in pars:
                if param == dtc_id:
                    continue

                raw_val = -1
                if "lenby" in pars[param]:
                    prv = pars[param]["pos"] - 1
                    ple = pars[param]["lenby"]
                    raw_val = "".join(self.bytes_to_bits(this_block[prv:prv+ple]))
                elif "msk" in pars[param]:
                    prv = pars[param]["pos"] - 1
                    if "lenby" in pars[param]:
                        ple = pars[param]["lenby"]
                    elif "lenbi" in pars[param]:
                        ple = math.ceil(pars[param]["lenbi"] / 8)
                    else:
                        self.log("Invalid parameter definition: " + str(pars[param]))
                        continue
                    raw_val = self.unmask(self.bytes_to_bits(this_block[prv:prv+ple]), pars[param]["msk"])
                    raw_val = "".join(raw_val)
                if raw_val == -1:
                    self.log("Unsupported parameter type in DTC parse: " + str(param) + " : ECUVE: " + str(ecuveid))
                    continue

                if param == "DTC_STATUS_1":
                    #print(raw_val)
                    #print(this_block)
                    if self.int(raw_val,2) == 0:
                        tree.pop(code,None)
                        if code not in binned:
                            binned.append(code)
                        continue

                if code in binned:
                    continue

                if code not in tree:
                    tree[code] = {}
                if param not in tree[code]:
                    tree[code][param] = raw_val

        tree["NRODTC"] = len(tree)
        self.log("Wrote " + str(tree["NRODTC"]) + " to log")

        return tree


    def get_dtc_query_frame(self, ecuveid, is_query = True, is_clear = False):
        '''
        API: Try to find the DTC query command frame
        is_query : fault request
        is_clear : fault clearing
        '''
        zone_choice = ""
        zone_frame = {}
        zone_result = {}

        if is_clear:
            query_frame = self.query("get_fault_clear_cmd", [ecuveid])
        else:
            query_frame = self.query("get_fault_frame_for_ecuve", [ecuveid])

        for row in query_frame:
            zone_frame.setdefault(row["ftype"], {})

            if zone_choice == "":
                zone_choice = row["zonename"]
            elif row["zonename"] != zone_choice:
                self.log(f"Can't deduce fault frame, multiple zones returned for {ecuveid} - at least {zone_choice} and {row['zonename']}")
                return False

            if row["val"] == "":
                continue

            if row["pos"] not in zone_frame[row["ftype"]]:
                zone_frame[row["ftype"]][row["pos"]] = row["val"]
            else:
                self.log(f"Can't deduce fault frame, params share position for {ecuveid}")
                return False

        for ftype in zone_frame:
            zone_result[ftype] = ""
            indexes = list(zone_frame[ftype].keys())
            indexes.sort()
            for index in indexes:
                zone_result[ftype] += zone_frame[ftype][index]

        return zone_result


    def get_dtc_frame(self, ecuveid):
        '''
        API: Get the logic needed to parse a DTC response frame
        '''
        ecuveid = self.int(ecuveid)

        if ecuveid == 0:
            return False

        v = self.query("get_fault_frame_for_ecuve", [ecuveid])
        frames = {}
        blos = []

        # We fetch all the RDDTC frames, but we only actually accept these types
        # Anything else gets flagged for devs to review
        # Problem is that UDS has multiple fault reading methods and we only use 1 of them (190209)
        # This may not be exhaustive - feel free to add more if other ECUs require it
        accepted_zones = self.read_dtc_param_names
        ignored_zones = []

        for row in v:
            if row["zonename"] not in accepted_zones:
                if row["zonename"] not in ignored_zones:
                    ignored_zones.append(row["zonename"])
                continue

            cat = self.frty[row["ftype"]]  # REQ/ANSOK/ANSKO

            if row["blo"] not in blos:
                blos.append(row["blo"])

            if cat not in frames:
                frames[cat] = { }
            
            # order the dictionary by parameter, unless the parameter
            # is in a block, in which case do a block dict at that position

            # then modify identify_dtcs to take the DICT we output as a parameter
            # and use it to parse the hex byte string (maintaining existing command flow)
            blk = str(row["blo"])

            if blk != "0" and blk != "":
                # if there is block
                # note that if the parameter is a BLOCK, then the pos is the position IN THE BLOCK,
                # not in the frame itself
                if blk not in frames[cat]:
                    frames[cat][blk] = { "blo": int(blk), "pos": -1, "params": {} }
                frames[cat][blk]["params"][row["parname"]] = self.gen_parse_param_format(row)

            elif row["parname"] not in frames[cat]:
                frames[cat][row["parname"]] = self.gen_parse_param_format(row)
        
            else:
                self.log("Error, duplicate fault reading parameter, please report this: " + str(row["parname"]) + " for ECUVE " + str(ecuveid))

        
        if len(blos) == 0:
            self.log("Unable to find any accepted fault frames - can not accept any of these:")
            self.log(str(ignored_zones))
            return False


        u = self.query("get_blocks", [blos])
        blos = {}
        
        for row in u:
            for cat in frames:
                if str(row["bloid"]) in frames[cat]:
                    frames[cat][str(row["bloid"])]["pos"] = row["blobytepos"]
                    frames[cat][str(row["bloid"])]["lenby"] = row["blobytelen"]
            #if row["bloid"] not in blos:
            #    blos[row["bloid"]] = { "pos": row["blobytepos"], "len": row["blobytelen"], "min": row["occur_min"], "max": row["occur_max"], "exp": row["occur_exp"] }
 
        return frames


    def get_dtc_char(self, ecuid, ecuveid, dtcs, char_codes = None):
        '''
        API: Get the DTC, description and characterisations for a code.
        - dtcs can be one or a list of codes, but then char_code must be a list also
        - If char_code is specified, filter permanent/intermittent options
        - To get the freeze frame, you will need to have got ECU live data frames first
        '''
        dtc_l = dtcs
        tree_b = {}
        if type(dtc_l) != list:
            dtc_l = [dtc_l]

        if type(dtcs) == list:
            if type(char_codes) == list and len(char_codes) != len(dtcs):
                self.log("DEV WARNING: Malformed input to get_dtc_char, char code was wrong length")
            elif type(char_codes) == None:
                self.log("DEV WARNING: Malformed input to get_dtc_char, char code wasn't a list")

        # dtcid, label, paramname, statname to look for
        result = self.query("get_dtc_char", [ecuid, dtc_l])
        unique_ids = []
        tree = {}
        for dtc in result:
            if dtc["dtcid"] not in unique_ids:
                unique_ids.append(dtc["dtcid"])
                
            if dtc["internal_code"] not in tree:
                # TODO DB REBUILD: "label": dtc["dtclabel"], "help": dtc["dtchelp"],
                tree[dtc["internal_code"]] = {  "ff": dtc["ff"]}

            if dtc["parname"] not in tree[dtc["internal_code"]]:
                tree[dtc["internal_code"]][dtc["parname"]] = { "states": {}, "label": self.trs.decodalate(dtc["label"]) }

            if dtc["statname"] not in tree[dtc["internal_code"]][dtc["parname"]]["states"]:
                tree[dtc["internal_code"]][dtc["parname"]]["states"][dtc["statname"]] = self.trs.decodalate(dtc["vlabel"])

        
            
        # only do this bit if we have response codes from the ECU
        if char_codes != None:   
            if len(unique_ids) == 0:
                self.log("No matching DTC ids found for " + str(ecuid) + " : " + str(dtcs))
                return tree

            # get actual value of states by matching ecuveid
            spec_states = self.query("get_dtc_charvalues", [ ecuveid , unique_ids])

            par_states = {}

            # convert results to a dict tree
            for row in spec_states:
                if row["parname"] not in par_states:
                    par_states[row["parname"]] = {}
                if row["statname"] not in par_states[row["parname"]]:
                    par_states[row["parname"]][row["statname"]] = {"val": row["statval"], "mini": row["mini"], "maxi": row["maxi"] }

            if type(char_codes) != list:
                char_codes = [char_codes]

            skip_because_no_chars = True
            for code in char_codes:
                if len(code) > 0:
                    skip_because_no_chars = False
                    break
            if skip_because_no_chars:
                return tree

            deletes = []

            for dtc in tree:
                for parm in tree[dtc]:
                    if parm in par_states:
                        defined_val = -1
                        if parm in char_codes[dtc_l.index(dtc)]:
                            defined_val = char_codes[dtc_l.index(dtc)][parm]

                        for stat in par_states[parm]:
                
                            if par_states[parm][stat]["val"] != "":
                                # use absolute value
                                if par_states[parm][stat]["val"] == defined_val:
                                    if stat not in tree[dtc][parm]["states"]:
                                        if dtc not in deletes:
                                            deletes.append(dtc)
                                        continue
                                    tree[dtc][parm]["states"] = { stat : tree[dtc][parm]["states"][stat]  }
                                    break
                            elif par_states[parm][stat]["maxi"] != "" and par_states[parm][stat]["mini"] != "":
                                # use mini maxi
                                if int(str(par_states[parm][stat]["mini"]),16) <= int(str(defined_val),2) < int(str(par_states[parm][stat]["maxi"]),16):
                                    tree[dtc][parm]["states"] = { stat : tree[dtc][parm]["states"][stat] }
                                    break
                            else:
                                self.log("STATE" + str(stat) + " doesn't appear to have a defined value. Please report this")
                                continue
            
            tree_b = {}
            for dtc in tree:
                if dtc not in deletes:
                    tree_b[dtc] = tree[dtc]
            self.log("Filtered down to " + str(len(tree_b)) + " DTC")
            tree = tree_b
            
        return tree


    def dtc_hexa_to_reality(self, code):
        '''
        Convert e.g. D308 to U1308
        - Depends nothing
        '''

        # until we know how this works, do nothing (but we keep
        # in the control flow because we DO nEED TO DO THIS)
        return code 

        out = ""
        code = str(code)
        if code[:1] == "D":
            out = "U1" + code[1:]

        else:
            if len(code) == 3:
                code = "0" + code
            out = "P" + code

        return out


    def dump_ecu_frames(self, ecuveid, direct = False, in_fname="out", max_row_count = 85000):
        '''
        Get all possible frames supported by the given ECUID and dump them to a tree
        Useful for analysing everything diagbox supports natively for an ECU
        
        This is the closest we can get to generating a PDX/ODX file (currently our own format is output)

        You don't get as much data with this as you do with get_telecoding etc, because it's very hard to "work backwards"
        and determine that a certain frame is actually a telecode/actuator function
        '''

        ecuid = self.get_ecuid_for_ecuveid(ecuveid)
        if not ecuid:
            self.log("There is no mapping to an ECU type for that ECUVEID")
            return False

        self.log("Dumping data for ECUID/VE " + str(ecuid) + " / " + str(ecuveid))

        data = {}
        pid_map = {}  # indexed by PARNAME, tuple of zoneid, frid, pid

        if not self.query_iterative("dump_frames_all_data", [ecuveid]):
            self.log("Failed to get execute database query, giving up")
            return False

        row_count = 0

        # build data tree
        while 1:
            rows = self.c.fetchmany(500)
            row_count += 500
            if not rows:
                break

            if row_count > max_row_count:
                self.log("Hit max row limit whilst pulling data at " + str(max_row_count))
                break

            for row in rows:
                zoneid = row["zoneid"]
                frid = row["frid"]
                pid = row["pid"]
                sid = row["stid"]
                #ser = row["sername"]

                #if ser not in sers:
                #    sers[ser] = row["serlname"]

                if zoneid not in data:
                    data[zoneid] = { "!props": {"zonename": row["zonename"], "serid": row["serid"] } }

                if frid not in data[zoneid]:
                    data[zoneid][frid] = { "!props": {"ftype": self.frty[row["ftype"]] }}
                
                if pid not in data[zoneid][frid]:
                    dt = row["dattype"]
                    if dt == None:
                        dt = ""
                    else:
                        dt = self.paramtype[row["dattype"]]

                    pf = row["pf_dattype"]
                    if pf == None:
                        pf = ""
                    else:
                        pf = self.parformattype[row["pf_dattype"]]

                    data[zoneid][frid][pid] = { "!props":  { "name": row["parname"], "defval": row["val"], "pos": row["pos"], 
                                                    "map": row["map"], "crc": row["crc"], "block": row["blo"], "dynblock": row["dyn"],
                                                    "dtype": dt, "format": pf,
                                                    "msk": row["bin_mask"], "abs": row["abs_no"], "lenbi": row["len_bits"], "lenby": row["len_bytes"] }}
                                                    # todo bin_mask etc

                    if row["parname"] not in pid_map:
                        pid_map[row["parname"]] = []
                    pid_map[row["parname"]].append((zoneid, frid, pid))

                if sid not in data[zoneid][frid][pid]:
                    data[zoneid][frid][pid][sid] = { "!props": { "name": row["statname"], "val": row["statval"], "mini": row["mini"], "maxi": row["maxi"], "blockgrp": row["defgrp"]}}

        self.log("Extracted data in approximately " + str(row_count))

        # get ancilliary data
        pq = self.query("match_edata_for_ecu_dump", [ecuid, ecuid])

        # apply it
        for row in pq:
            if row["parname"] in pid_map:
                for ref in pid_map[row["parname"]]:
                    data[ref[0]][ref[1]][ref[2]]["!props"]["label"] = row["elabel"]
                    data[ref[0]][ref[1]][ref[2]]["!props"]["unit"] = row["eunit"]
                    data[ref[0]][ref[1]][ref[2]]["!props"]["help"] = row["ehelp"]

        if not direct:
            fd = open("treeview_data/" + str(ecuveid) + ".dgd", 'w')
            json.dump(data, fd)
            return True
        else:
            fd = open(str(in_fname) + ".dgd", 'w')
            json.dump(data, fd)
            return data


    def dump_ecu_to_odx(self, ecu_variant, sers, ecu_tree):
        '''
        WIP: Export a full ECU dump to ODX format
        '''

        ecu_short = ecu_variant
        ecu_long = ecu_variant

        # create the file structure
        root = xml.Element('DIAG-LAYER-CONTAINER')
        snam = xml.SubElement(root, "SHORT-NAME")
        snam.text = ecu_short
        lnam = xml.SubElement(root, "LONG-NAME")
        lnam.text = ecu_long
        ecuv = xml.SubElement(root, "ECU-VARIANTS")

        # only one variant atm
        tecuv = xml.SubElement(ecuv, "ECU-VARIANT")
        tecuv.set("ID", ecu_variant)
        snam = xml.SubElement(tecuv, "SHORT-NAME")
        snam.text = ecu_short
        lnam = xml.SubElement(tecuv, "LONG-NAME")
        lnam.text = ecu_long
        desc = xml.SubElement(tecuv, "DESC")
        desc.text = "Exported from Diagnostique"

        fcla = xml.SubElement(tecuv, "FUNCT_CLASSS")
        cnt = 0
        for svc in sers:
            felm = xml.SubElement(fcla, "FUNCT-CLASS")
            felm.set("ID", "_" + str(cnt))
            snam = xml.SubElement(felm, "SHORT-NAME")
            snam.text = svc
            lnam = xml.SubElement(felm, "LONG-NAME")
            lnam.text = sers[svc]
            cnt += 1
        


    '''#########################################

          ACTUATOR TESTS

        This uses a separate table (act.db) because
        there are a lot of tables, and many users 
        likely won't want or use actuator tests

    ########################################'''


    def get_actuator_tests(self, ecuid, ecuveid, show_all_opts = True):
        '''
        API: Fetch a list of actuator tests available
        on the selected ECU

        To run some BSI/BSx based tests, you need to have populated the LID map FIRST
        
        NOTE: Due to the way the frames are stored, the REQUEST frame
        will often contain multiple parameters for the same position. In an
        actuator test you should only parse/care about/send those parameters 
        which have a defined value. 

        The diag_acttest library deals with converting this nonsense into a usable
        data stream because sometimes you need to ask the user a value for a parameter

        - show_all_opts is not currently implemented yet
        '''

        if self.adb is None:

            self.adb = sqlite3.connect(self.path + "act4.db", check_same_thread=False)
            # get results as dict-alike
            self.adb.row_factory = sqlite3.Row
            self.a = self.adb.cursor()


        # get the STATUS parameter name and value labels
        # PARRESP is just getting error codes, we don't care about that
        #             because if we get a ANSWERKO then we report directly the code

        # Use LEFT join for pids so we get ALL zone names even if they have no PID
        z = self.query("get_zonenames_for_ecu_act", [ecuid], "a")

        # No act tests for this ECU
        if len(z) == 0:
            return {}

        parstatreq = {}
        for row in z:
            if row["azonename"] in parstatreq:
                self.log("ERROR: azonename is not a one-to-one")
                self.log(row["azonename"] + ": " + parstatreq[row["azonename"]] + " isn't " + row["reqstatusparname"])
            parstatreq[row["azonename"]] = row["reqstatusparname"]

        
        # Load parameter/frames from FRAPAS
        v = self.query("get_all_frames_for_zonenames", [ecuveid, list(parstatreq.keys())])
        pids = {}
        frames = {}

        mapped_frids = {}

        has_mapped = False

        for row in v:
            
            if row["zonename"] not in frames:
                frames[row["zonename"]] = {}

            if row["frid"] not in frames[row["zonename"]]:
                frames[row["zonename"]][row["frid"]] = { "type": self.frty[row["ftype"]], "params": {} }

            if row["parname"] == "NUMERO_RELATIF":
                self.log("FRID" + str(row["frid"]) + " contains a NUMERO_RELATIF, use with care")
                #frames[row["zonename"]][row["frid"]]["disabled"] = True

            if row["parname"] not in frames[row["zonename"]][row["frid"]]["params"]:
                pids[row["pid"]] = row["parname"]
                l = { "states": {}, "pos": row["pos"], "map": row["map"], "defval": row["val"] , "pencode": row["encode"], "pid": row["pid"] }

                # look out for LID mapped tests (BSI04 only)
                if self.not_blank(dict(row),"map"):
                    has_mapped = True
                    if row["frid"] not in mapped_frids:
                        mapped_frids[row["frid"]] = row["map"]
                
                frames[row["zonename"]][row["frid"]]["params"][row["parname"]] = l
            

            if frames[row["zonename"]][row["frid"]]["params"][row["parname"]]["defval"] == "":
                if self.not_blank(row["statname"]):
                    if self.not_blank(row["statval"]):
                        frames[row["zonename"]][row["frid"]]["params"][row["parname"]]["states"][row["statname"]] = {"exact" : row["statval"], "desc": row["statdesc"] } 
                    else:
                        frames[row["zonename"]][row["frid"]]["params"][row["parname"]]["states"][row["statname"]] = {"range" : (row["mini"], row["maxi"]), "desc": row["statdesc"] } 

            if row["parname"] == "TA_ROUTINE_FORC_DMD":
                print(str(frames[row["zonename"]][row["frid"]]["params"][row["parname"]]))



        pformu = self.query("get_parformulas", [list(pids.keys())])
        pforma = self.query("get_parformats", [list(pids.keys())])

        tree = {}

        # if there's valid PARFORMULA's (factor/offset)
        if len(pformu) > 0:
            for pf in pformu:
                if pids[pf["pid"]] not in tree:
                    tree[pids[pf["pid"]]] = {}
                tree[pids[pf["pid"]]]["factor"] = pf["cfactor"]
                tree[pids[pf["pid"]]]["offset"] = pf["coffset"]
                tree[pids[pf["pid"]]]["formula"] = self.parformulatype[pf["ctype"]]

        # if there's valid PARFORMATS (byte mask/length etc)
        if len(pforma) > 0:
            for pa in pforma:
                if pids[pa["pid"]] not in tree:
                    tree[pids[pa["pid"]]] = {}
                tree[pids[pa["pid"]]]["lenbi"] = pa["len_bits"]
                tree[pids[pa["pid"]]]["lenby"] = pa["len_bytes"]
                tree[pids[pa["pid"]]]["msk"] = pa["bin_mask"]
                tree[pids[pa["pid"]]]["abs"] = pa["abs_no"]
                tree[pids[pa["pid"]]]["format"] = self.parformattype[pa["dattype"]]

        # add formatting info to parameters
        for zone in frames:
            for frid in frames[zone]:
                for param in frames[zone][frid]["params"]:
                    if param in tree:
                        frames[zone][frid]["params"][param]["format"] = tree[param]


        ''' apply LID mapping - this is for BSI04EV ONLY!!

        # And we interrupt this algorithm for some PSA weirdness
        # An actuator test for the BSI/BSx looks a little bit like
        # SID, LID, PARAPIL, NUMERO_RELATIF, MP_DUREE, XX_Parameter
        #  30   C5       00 

        where XX_Parameter is FEUX_DE_ROUTE, FEUX_DE_CROISEMENT etc according to the item under test. 
        NUMERO_RELATIF is the post-LID-mapped POSITION of the parameter inside the LID

        So we go XX_Param[abs] --> LID translation --> gives us absolute position in the hex
        Then we take that position and we put it in NUMERO_RELATIF.
        (And then we cry)
        And then we put the value of XX_Param (usually 00 or 01) in at position 6

        For some actuator tests this doesn't seem to be valid - ones where it involves the trailer too for example
        '''        

        if has_mapped:
            self.log("Using actuator tests mapped zones (experimental)")
            for zone in frames:
                for frid in frames[zone]:            
                    if frid in mapped_frids:
                        
                        mapz = mapped_frids[frid]

                        lids = self.get_lid_table(mapz)
                        
                        if not lids:
                            self.log("No data for zone " + str(mapz))
                            continue
                        else:
                            self.log(str(lids))

                        atp_map = {}

                        # make a dict of all the parameters with relevant info
                        for parm in frames[zone][frid]["params"]:
                            if self.not_blank(frames[zone][frid]["params"][parm]["map"]):
                                #self.log(str(parm) + " @ " + str(mapz) + " @ " + str(frames[zone][frid]["params"][parm]["format"]["abs"]))
                                atp_map[frames[zone][frid]["params"][parm]["format"]["abs"]] = frames[zone][frid]["params"][parm]
                                atp_map[frames[zone][frid]["params"][parm]["format"]["abs"]]["parname"]  = parm
                                atp_map[frames[zone][frid]["params"][parm]["format"]["abs"]]["frid"] = frid
                                atp_map[frames[zone][frid]["params"][parm]["format"]["abs"]]["zone"] = zone
                        
                        relative_offset = -1

                        self.log("Transforming actuator mapping " + str(mapz) + " to LID for this vehicle")

                        for abs_offset in atp_map:
                            try:
                                relative_offset = lids.index(abs_offset)
                            except:
                                pass

                            if relative_offset > -1:
                                self.log(self.to_hex(relative_offset) + " (" + str(abs_offset) + ") : " + atp_map[abs_offset]["parname"])

                            # change "format" to NUMERO_RELATIF and set the new field "nr" to the post-mapped value. Note the reason we do this differently
                            # is so diag_acttest can cope with the VERY strange database structure of the IOCBLID commands (it needs to know the "original" abs value)  
                            # as well as the new one
                            #frames[atp_map[abs_offset]["zone"]][atp_map[abs_offset]["frid"]]["params"][atp_map[abs_offset]["parname"]]["format"]["abs_original"] = abs_offset
                            frames[atp_map[abs_offset]["zone"]][atp_map[abs_offset]["frid"]]["params"][atp_map[abs_offset]["parname"]]["format"]["nr"] = relative_offset
                            frames[atp_map[abs_offset]["zone"]][atp_map[abs_offset]["frid"]]["params"][atp_map[abs_offset]["parname"]]["format"]["format"] = "NUMERO_RELATIF"

                            relative_offset = -1
 


        # Get zones for the ECU, then get the screens, then get the steps if relevant 
        act = self.query("get_acttest_zones_for_ecu", [ecuid], "a")
        if len(act) == 0:
            self.log("No actuator tests for ECUID: " + str(ecuid))
            return {}

        # Use FRAPAS services to pad out CTRL/actuator test functions
        zones = {}
        ctrlids = []
        for row in act:

            role = self.actserole[row["azonerole"]]
            if row["ctrlid"] not in zones:
                zones[row["ctrlid"]] = {}
            
            # CTRLID = ACTUATE, GET_STATUS OR STOP
            if row["ctrlid"] not in ctrlids:
                ctrlids.append(row["ctrlid"])

            #  ZONEROLE = REQUEST/ANSWEROK/ANSWERKO
            # Copy the service frame to the new dict if its not there already
            if role not in zones[row["ctrlid"]]:
                zones[row["ctrlid"]][role] = {}

            if zones[row["ctrlid"]][role] == {}:
                new_zn = {}

                if row["azonename"] not in frames:
                    self.log(str(row["azonename"]) + " referenced by act test but has no matching frame")
                else:
                    for frid in frames[row["azonename"]]:
                        # DISABLE Numero_relatif frames
                        if "disabled" in frames[row["azonename"]][frid]:
                            new_zn["disabled"] = True

                        # BUGFIX: Use deepcopy to avoid changing defval propagating through all other users of this param zone
                        new_zn[frames[row["azonename"]][frid]["type"]] = copy.deepcopy(frames[row["azonename"]][frid]["params"])
                    zones[row["ctrlid"]][role] = copy.deepcopy(new_zn)

            for rtype in zones[row["ctrlid"]][role]:
                if rtype == "disabled":
                    continue
                if row["actparname"] in zones[row["ctrlid"]][role][rtype]:
                    if row["actparname"] == "NUMERO_RELATIF":
                        pass#print(str(row["ctrlid"]) + " " + str(row["actzvalue"]))

                    if row["actzvalue"] in zones[row["ctrlid"]][role][rtype][row["actparname"]]["states"]:
                        zones[row["ctrlid"]][role][rtype][row["actparname"]]["defval"] = zones[row["ctrlid"]][role][rtype][row["actparname"]]["states"][row["actzvalue"]]
                        #print(str(zones[row["ctrlid"]][role][rtype][row["actparname"]]["states"]))
                    elif not self.not_blank(zones[row["ctrlid"]][role][rtype][row["actparname"]]["defval"]):
                        #pass #self.log("DEFVAL was blank and " + str(row["actzvalue"]) +  " wasn't a valid state for " + str(row["actparname"]))
                        zones[row["ctrlid"]][role][rtype][row["actparname"]]["defval"] = row["actzvalue"]
       

        z = self.query("get_ctrlstatus_from_ctrl", [ctrlids], "a")
        stati = {}
        for row in z:
            if row["ctrlid"] not in stati:
                stati[row["ctrlid"]] = {}
            if row["actstatname"] not in stati[row["ctrlid"]]:
                stati[row["ctrlid"]][row["actstatname"]] = {"label": self.trs.decodalate(row["actstatlabel"]), "type": self.actstatus[row["actstatype"]]}

        act = self.query("get_ecu_act_data", [ecuid], "a")
        # Get ECU act tests screens
        acts = {}
        scnids = {}

        for row in act:
            if row["scnid"] not in scnids:
                scnids[row["scnid"]] = row["actname"]
            if row["actname"] not in acts:
                disable = False

                # should be unique to the ECU because they're ref'd by name in the S tree
                nz = {}
                for oz in zones[row["ctrlid"]]:
                    nz[oz] = zones[row["ctrlid"]][oz]
                    if "disabled" in zones[row["ctrlid"]][oz]:
                        disable = True

                if row["ctrlid"] in stati:
                    sta = stati[row["ctrlid"]]
                else:
                    sta = {}
                acts[row["actname"]] = { "title": self.trs.decodalate(row["acttitle"]), "ctrl": row["ctrlid"], "type": self.acttype[row["acttype"]],
                                         "zones":  nz, "statuses": sta, "screens": {} }
                # numero relatif disable cascade
                if disable:
                    acts[row["actname"]]["disabled"] = True

            if self.actscrtype[row["scrtype"]] not in acts[row["actname"]]["screens"]:
                acts[row["actname"]]["screens"][self.actscrtype[row["scrtype"]]] = { "label": self.trs.decodalate(row["scrlabel"]) }

        s_check = self.query("get_steps_from_scnids", [list(scnids.keys())], "a")
        stepids = {}

        if len(s_check) > 0:
            #self.log("WARNING: Steps exist for one or more actuator tests")
            for row in s_check:
                if row["stepid"] not in stepids:
                    stepids[row["stepid"]] = row["scnid"]

                #self.log(dict(row))

            s_data = self.query("get_act_step_data", [list(stepids.keys())], "a")

            if len(s_data) > 0:
                for row in s_data:
                    if row["stepid"] not in stepids:
                        self.log("Somehow found a step that I didn't look for...hmmm: " + str(row["stepid"]))
                        continue
                    scn = stepids[row["stepid"]]
                    act = scnids[scn]

                    act_dic = { "name": row["stepname"], "parname": row["actparname"], "val": row["actvalue"]}

                    if "steps" not in acts[act]:
                        acts[act]["steps"] = {}
                    if row["steporder"] in acts[act]["steps"]:
                        if type(acts[act]["steps"][row["steporder"]]) != list:
                            acts[act]["steps"][row["steporder"]] = [acts[act]["steps"][row["steporder"]]]
                            acts[act]["steps"][row["steporder"]].append(act_dic)
                    else:
                        acts[act]["steps"][row["steporder"]] = act_dic

        # post process to remove useless data 
        #if not show_all_opts:
            # hide possible options if we have a defined one, unless expert/pro
            # frames[row["azonename"]][frid]["params"][row["actparname"]]["vals"] = {}

            # remove parameters in a REQUEST frame with no defined value
        if self.debug:
            pprint.pprint(acts)
        
        return acts

'''

trs = diag_translations()
bb = diag_bramble(trs)

pprint.pprint(bb.get_data_frames(5596, 31989, "telenew"))

#
#pprint.pprint(bb.get_actuator_tests(2985, 2101))
#bb.get_actuator_tests(2993,25118)

# 207
# EMF_A: 4166 / 23251
# EMF_C: 4167 / 15566

#bb.dump_ecu_frames(23251)

#PHP: 26 B7 7F 7A
#PYT: 37 b6 67 f8
#COR: 36 f7 7b 7a
#pprint.pprint(bb.get_vehicle_ecu_list(7))

#print(bb.uds_bruteforce([ ("01998393", "36f77b7a"), ("F7F02C62","3fdf2d8d") ]))

#pprint.pprint(bb.dump_ecu_frames(10641))

#pprint.pprint(bb.get_data_frames(2985, 2101))
#f = bb.get_data_frames(4451,26837)
#pprint.pprint(bb.get_dtc_char(4451,26837,[2565,1693],[23,28]))
#pprint.pprint(bb.get_dtc_char(1102, 10641, "D121"))
#pprint.pprint(bb.get_data_frames(201, 31604, qtype="telenew", dont_post_process=False))
#pprint.pprint(bb.get_data_frames(3081, 15330))

#combine
#pprint.pprint(bb.get_telecoding(2990, 1050))
#pprint.pprint(bb.get_telecoding(2974, 13746))

k = bb.get_params_from_telecoding(bb.get_telecoding(4167, 15566))
pp = pprint.PrettyPrinter(width=120)
pp.pprint(k)




#pprint.pprint(bb.get_dtc(670, "521"))
#pprint.pprint(bb.trs.decodalate(bb.get_dtc(670, "521")["label"]) + ": " + bb.trs.decodalate(bb.get_dtc(670, "521")["descrip"]))
#pprint.pprint(bb.get_dtc_char(670, 11963, "521"))

#pprint.pprint(bb.get_dtc_printout(670, 1196, "521"))



#pprint.pprint(bb.dump_ecu_frames(15566))

#pprint.pprint(bb.get_recos_for_ecu(54, "EMF_C", init=None))

# AM6 
#v = bb.get_data_frames(2975, 2535)
#pprint.pprint(bb.parse_params_hex(v, "61FF45786800000044", "C2"))

#for p in c:
#    if "NOTE" in c[p]:
#        print(c[p]["LABEL"] + ":" + c[p]["VALUE"] + str("(!)"))
#    else:
#        print(c[p]["LABEL"] + ":" + c[p]["VALUE"])
# SUSPENSION_ECOTECH:2993, 25118
# CSS:3081, 15330
'''
