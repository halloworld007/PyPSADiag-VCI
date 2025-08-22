from .diag import diag
from .diag_adapter import *
from .diag_bramble import diag_bramble
from .diag_translations import diag_translations
import re
from collections import OrderedDict

class diag_discovery(diag):

    tla = "DIS"
    globalResults = {}
    globalTree = {}
    active_prot = None
    progressCallback = None             # temp storage for callback for discovery/etc
    stop_discovery = False

    scan_faults = True                  # whether to scan faults during discovery
    tree_ignore = ["prot", "veh"]      # anything in global tree that isnt an ECU to be scanned

    vin_search = { "BSI": "21B0", "BSI2010": "22F190"}

    def __init__(self, trs: diag_translations, adapter : diag_adapter, bb : diag_bramble ):
        '''
        '''
        self.bb : diag_bramble          = bb
        self.adapter : diag_adapter     = adapter
        self.trs : diag_translations    = trs


    def diag_vin(self, response):
        '''
        Parse the response from an attempt to read the vehicle VIN no
        '''
        vin = ""
        # TODO: Parse this properly instead of 4: :O
        if len(response) > 6:
            if response[:4] == "61B0":
                vin = self.parse_ascii(response[4:]) 
            elif response[:6] == "62F190":
                vin = self.parse_ascii(response[6:]) 
        if vin == "":
            self.log("Failed to parse VIN: " + response)
            return ""
        else:
            return vin
       

    def emptyCallback(self, *largs):
        '''
        INT: Used by default by functions that can use callbacks
        '''
        # do nothing
        return

    
    def stopDiscovery(self, *largs):
        '''
        API: Interrupt a running discovery session
        '''
        self.stop_discovery = True

    
    def resumeDiscovery(self, *largs):
        '''
        API: Resume a running discovery session (not implemented yet)
        '''
        pass


    def set_global_tree(self, tree):
        '''
        Assign a globalTree for a discovery scan
        '''
        if "veh" in tree and "prot" in tree:
            self.veh = tree["veh"]
            self.prot = tree["prot"]
            self.globalTree = tree
            return True
        else:
            self.log("Invalid tree supplied to SGT, missing veh or protocol information")
            return False


    def record_ecu(self, ecuname=None, ecufam=None, ecuid=None, ecuveid=None, status="NOTFOUND"):
        '''
        INT: Record data from discovery in the table
        '''
        self.globalResults["ECU"][ecufam] = { "FAMILY": ecufam, "STATUS": status }

        if ecuname != None:
            self.globalResults["ECU"][ecufam]["ECUNAME"] = ecuname

        self.progressCallback(self.globalResults)
        return
  

    def run_discovery(self, progressCallback=None, sortByBus=False):
        '''
        API: Start the discovery scan
        - progressCallback -> call this each time an ECU is processed
        - sortByBus -> sort the tree by bus before starting (to make using multi-bus adapters easier)
        - BLOCKING
        - Global tree format for each ECU:
            STATUS  -> IDENTOK, 
            ECUID   -> ECUID number
            ECUVEID -> ECUVEID number
            FAMILY  -> e.g. "BMF"
            ECUNAME -> e.g. "BSI"
            VARIANT -> e.g. "BSI_X7_V1"
            TX_H    -> 752
            RX_H    -> 652
            BUS     -> DIAG/IS
            CMDS    -> result of get_ecu_diag_cmds(ecuveid)
            FAULTS  -> number of faults
            FAULT_TREE -> 
            FRAME_TREE -> result from get_data_frames(ecuid, ecuveid)
        '''
        if progressCallback == None:
            self.progressCallback = self.emptyCallback
        else:
            self.progressCallback = progressCallback

        if self.globalTree == {} or self.veh == None:
            return {}

        self.globalResults = { "VEH": str(self.veh), 
                               "VIN": "", 
                               "VER": self.bb.version, 
                               "PROT": self.globalTree["prot"], 
                               "LID": {} , 
                               "ECU": {} 
                            }
        self.active_prot = self.globalTree["prot"]

        scan_faults = self.scan_faults

        # pre load the list of recognition IDs
        recos = self.bb.get_recos_for_ecu(self.veh)

        # check the adapter is present and responding to us
        if not self.adapter.configure():
            self.log("The adapter failed the initial configuration request")
            return {}

        # sort dict to scan DIAG, then IS rather than switching between at random
        if sortByBus:
            tree_diag      = {}
            tree_is        = {}
            tree_other     = {}
            tree_dialog    = {}
            tree_protocols = {}
            
            for ecu in self.globalTree:
                if type(self.globalTree[ecu]) != dict:
                    tree_other[ecu] = self.globalTree[ecu]
                    continue

                for hdrs in self.globalTree:
                    headers = hdrs.split(":")
                    if len(headers) != self.bb.TREE_HEADERS_LEN:
                        self.log(f"Invalid headers for ECU {ecu}")
                        continue

                    bus     = headers[0]
                    dialog  = headers[4]
                    prot    = headers[3]

                    tree_dialog[ecu]    = dialog
                    tree_protocols[ecu] = prot

                    if not (dialog == 2 or dialog == 4):
                        self.log(f"Dialog communication type {dialog} is not supported for ecu {ecu}")
                        continue

                    if bus == self.bb.BUS_CAN_DIAG:
                        self.log(f"Using DIAG for ECU: {ecu}")
                        tree_diag[ecu] = self.globalTree[ecu]

                    elif bus == self.bb.BUS_CAN_IS:
                        self.log(f"Using IS for ECU:   {ecu}")
                        tree_is[ecu] = self.globalTree[ecu]

                    elif bus == self.bb.BUS_CAN_BCAN:
                        self.log(f"Using BCAN for ECU: {ecu}")
                        tree_is[ecu] = self.globalTree[ecu]

                    else:
                        self.log(f"Using other protocol for ECU: {ecu}")
                        tree_other[ecu] = self.globalTree[ecu]
            
            for item in tree_is:
                tree_diag[item] = tree_is[item]
            
            for item in tree_other:
                tree_diag[item] = tree_other[item]
            
            self.globalTree = tree_diag


        for ecu in self.globalTree:
            if self.globalTree[ecu] == {}:
                continue

            if self.stop_discovery:
                self.stop_discovery = False
                return 

            if ecu == "prot" or ecu == "veh":
                continue

            self.debug("Discovery for: " + str(ecu))

            found_nothing_for_category = False

            for headers in self.globalTree[ecu]:
                conn_params = headers.split(":")
                if len(conn_params) != self.bb.TREE_HEADERS_LEN:
                    self.log(f"Bad header assembly for ecu {ecu}::{headers}")
                    continue

                bus         = conn_params[0]
                tx_h        = conn_params[1]
                rx_h        = conn_params[2]
                protocol    = conn_params[3]
                target_code = conn_params[5]
                dialog_type = conn_params[4]

                if not self.adapter.configure(tx_h, rx_h, bus, protocol, target_code, dialog_type):
                    self.log("Configure failed, skipping entry")
                    continue

                for init in self.globalTree[ecu][headers]["INIT"]:
                    init_success = False    # did the ECU respond correctly
                    init_alive = False      # did the ECU respond

                    # FIX bug where sending 1001 followed by 81 too quickly
                    #     causes no response from ECU
                    if not self.adapter.configure(tx_h, rx_h, bus, protocol, target_code, dialog_type):
                        continue

                    # send_wait_reply returns any input it gets, or False on timeout
                    response = self.adapter.send_wait_reply(init)
                    if not response:
                        # ecu didn't respond, ignore this
                        self.debug("No response from ECU: " + init)
                        found_nothing_for_category = True
                        continue

                    found_nothing_for_category = False

                    # Check response against possibilities
                    for possible_ecu in self.globalTree[ecu][headers]["INIT"][init]:
                        if possible_ecu not in recos:
                            self.log(f"No RECO entry for {possible_ecu}")
                            continue

                        try_recos = recos[possible_ecu]
                        for rec in try_recos:
                            if self.diagmatch(response, rec["init_ok"]):
                                self.debug(init + ": init ok")
                                init_alive = True
                                init_success = True
                                break
                            if self.diagmatch(response, rec["init_ko"]):
                                self.debug(init + ": init rejected")
                                init_success = False
                                init_alive = True
                                break
                        if init_alive:
                            break

                    if not init_alive:
                        # probably not a valid INIT, or not an existing ECU
                        self.log(f"Invalid init_alive:{ response }")
                        #self.record_ecu(ecufam=ecu, status="INITKO")
                        continue
                    
                    if not init_success:
                        # ecu responded, but with an error, so log that
                        self.log(f"{ecu} rejected init but recorded")
                        #self.record_ecu(ecufam=ecu, status="INITKO")
                        continue

                    self.log(f"Found valid {ecu}")

                    # Valid INIT, so try recognition of ECU version
                    for reco in self.globalTree[ecu][headers]["RECO"]:
                        reco_status = True

                        for i in range(0,3):
                            response = self.adapter.send_wait_reply(reco)
                            if not not response:
                                break

                        if not response:
                            # RECO for ecu failed (no response)
                            reco_status = False
                            continue

                        valid_ecu = ""
                        valid_ecuid = 0
                        reco_alive = False
                        reco_success = False

                        # check response against possibilities for RECO_OK
                        for check_ecu in self.globalTree[ecu][headers]["RECO"][reco]:
                            possible_ecu = check_ecu.split(":")[0]
                            if possible_ecu not in recos:
                                self.log(f"Potential ECU not in RECO - {possible_ecu}")
                                continue

                            try_recos = recos[possible_ecu]
                            for rec in try_recos:
                                if rec["init_rq"] != init:
                                    continue

                                if self.diagmatch(response, rec["reco_ok"]):
                                    self.debug(f"{init}: id ok")
                                    reco_alive = True
                                    reco_success = True
                                    #valid_ecu = poss_ecu
                                    #valid_ecuid = chk_ecu.split(":")[1]
                                    break

                                if self.diagmatch(response, rec["reco_ko"]):
                                    reco_alive = True
                                    reco_success = False
                                    self.debug(f"{init}: id rejected")
                                    break
                            
                            if reco_alive:
                                break

                        if not reco_success:
                            # ecu responded, but indicated RECO failed. Handle this later
                            self.log("No RECO")
                            reco_status = False
                            continue

                        # Valid recognition of ECUVEID done
                        # We must loop again here, because we have onlu established that a valid
                        # RECO response was received, we didn't necessarily match the right one
                        # e.g. if EDC17CP11 and EDC15C2 both respond to RECO 21FE, we have to check both
                        #       to match the returned ID
                        for check_ecu in self.globalTree[ecu][headers]["RECO"][reco]:
                            try:
                                ecu_name, ecu_id, *e = check_ecu.split(":")
                            except:
                                continue
                            ecu_details = self.bb.identify_ecu_ver(self.veh, ecu_name, response, ecu_id)

                            if ecu_details == {}:
                                continue
                            else:
                                valid_ecu = ecu_name
                                valid_ecuid = ecu_id
                                break

                        if ecu_details == {}:
                            # Failed to identify ECU
                            self.record_ecu(ecufam=ecu, status="IDENTKO")
                            self.debug(f"ECU identification failed for any kind of {ecu} : {response}")
                            break    
                        else:    
                            self.debug(f"Identified ECU: { ecu_details['VARIANT'] } with reference #{ ecu_details['RECO'] }") 

                        # If ECU is a BSI, prompt for VIN and read LID maps
                        # Fail silently. TODO: Add BSI2010 etc?
                        if valid_ecu in self.vin_search:
                            self.globalResults["VIN"] = ""
                            queryvin = self.vin_search[valid_ecu]

                            for i in range(0,3):
                                response = self.adapter.send_wait_reply(queryvin)
                                if not not response: 
                                    result = self.diag_vin(response)
                                    if result != "":
                                        self.globalResults["VIN"] = result
                                        break
                                else:
                                    self.debug("Warning, VIN not obtained, computer did not respond")

                            self.globalResults["LID"] = {}

                            # Read LID maps also (BSI2004 only)
                            if valid_ecu == "BSI":
                                
                                self.add_lid("B0")
                                self.add_lid("C0")
                                self.add_lid("D0")
                            

                        cmds = {}
                        rec = {}
                        cmds = self.bb.get_ecu_diag_cmds(ecu_details["ECUVEID"])

                        if valid_ecu not in recos:
                            self.log(f"ERROR: Could not find {valid_ecu} in reco table, database mismatch has occurred")
                            self.record_ecu(ecuname=possible_ecu, ecufam=ecu, status="RECOKO")
                        else:
                            for rec in recos[valid_ecu]:
                                if rec["variant"] == ecu_details["VARIANT"]:
                                    rec = rec
                                    break
                        
                        # Store every relevant piece of data for later
                        self.globalResults["ECU"][valid_ecu] = {}
                        self.globalResults["ECU"][valid_ecu]["STATUS"] = "IDENTOK"
                        self.globalResults["ECU"][valid_ecu]["FAMILY"] = ecu                            # BMF
                        self.globalResults["ECU"][valid_ecu]["ECUID"] = int(valid_ecuid)
                        self.globalResults["ECU"][valid_ecu]["ECUVEID"] = int(ecu_details["ECUVEID"])
                        self.globalResults["ECU"][valid_ecu]["VARIANT"] = ecu_details["VARIANT"]        # BSI_X7_V1
                        #self.globalResults[valid_ecu]["RECOID"] = int(ecu_details["RECO"])
                        self.globalResults["ECU"][valid_ecu]["PROTOCOL"] = protocol                     # KWPONCAN
                        self.globalResults["ECU"][valid_ecu]["TARGET_CODE"] = target_code               # only fiat, ECU target code
                        self.globalResults["ECU"][valid_ecu]["DIALOG_TYPE"] = dialog_type               # ??
                        self.globalResults["ECU"][valid_ecu]["ECUNAME"] = valid_ecu                     # BSI
                        self.globalResults["ECU"][valid_ecu]["TX_H"] = tx_h
                        self.globalResults["ECU"][valid_ecu]["RX_H"] = rx_h
                        self.globalResults["ECU"][valid_ecu]["BUS"] = bus
                        self.globalResults["ECU"][valid_ecu]["CMDS"] = cmds
                        self.globalResults["ECU"][valid_ecu]["FAULTS"] = -1
                        self.globalResults["ECU"][valid_ecu]["FAULT_TREE"] = {}
                        self.globalResults["ECU"][valid_ecu]["FRAME_TREE"] = self.bb.get_data_frames(int(valid_ecuid), int(ecu_details["ECUVEID"]))
                        

                        # Now scan for faults
                        if scan_faults:
                            try:
                                for i in range(0,3):
                                    fresult = self.scan_ecu_faults(self.globalResults["ECU"][valid_ecu], configured=True)
                                    if fresult != {}:
                                        self.globalResults["ECU"][valid_ecu]["FAULTS"] = fresult["FAULTS"]
                                        self.globalResults["ECU"][valid_ecu]["FAULT_TREE"] = fresult["FAULT_TREE"]
                                        self.globalResults["ECU"][valid_ecu]["FRAME_TREE"] = fresult["FRAME_TREE"]
                                        break
                            except:
                                self.log("Fatal error whilst reading faults from ECU, giving up on that")
                                
                                if self.globalResults["ECU"][valid_ecu]["FRAME_TREE"] == {}:
                                    self.globalResults["ECU"][valid_ecu]["FRAME_TREE"] = self.bb.get_data_frames(self.globalResults["ECU"][valid_ecu]["ECUID"], self.globalResults["ECU"][valid_ecu]["ECUVEID"])
                            

                        # Clean up nicely
                        self.adapter.send_wait_reply(rec["fini_rq"])

                        # Update anyone who's listening
                        progressCallback(self.globalResults)

                        
                    if not reco_status:
                        self.record_ecu(ecuname=possible_ecu, ecufam=ecu, status="RECOKO")
                        continue     

            if found_nothing_for_category:
                self.record_ecu(ecufam=ecu, status="NOTPRESENT")

        return self.globalResults

    def add_lid(self, root):
        '''
        Add a LID zone
        '''
        result = self.read_table_lid(root)

        if not not result:
            for zone in result:
                self.globalResults["LID"][zone] = result[zone]

                    
    def scan_ecu_faults(self, ecu_frame=None, configured=False):
        '''
        API: Scan an ECU for faults, either one that's already connected (configured=True)
        or one described by ecuFrame (a globalTest Result definition of an ECU)

        - ecu_frame must have ecuid, ecuveid, reco_id, tx_h, rx_h, bus, prot
        - Set is_conn to true if calling with an existing ECU connection (post DIAGINIT)
        '''

        if ecu_frame == None and configured == False:
            return {}

        # try to find the command from the database
        query_frames = self.bb.get_dtc_query_frame(ecu_frame["ECUVEID"])
        
        # otherwise try the most likely command set
        if not query_frames:
            cmds = self.get_lang("READFAULT")
        else:
            cmds = { "REQUEST": query_frames[0], "ANSWEROK": query_frames[1], "ANSWERKO": query_frames[2] }

        cmdext = self.get_lang("READFAULTEXT")

        self.log(f"Querying faults with {cmds['REQUEST']}")

        tree = { "FAULTS" : "",
                 "FAULT_TREE" : {},
                 "FRAME_TREE": {} 
                 }
        # FAULTS : x
        # FAULT_TREE :
        #    result of dtc::get_fault_information
        if not configured:
            if not self.adapter.init_ecu(ecu_frame):
                return tree

        
        if "FRAME_TREE" in ecu_frame:
            tree["FRAME_TREE"] = ecu_frame["FRAME_TREE"]

    
        # Now scan for faults
        response = self.adapter.send_wait_reply(cmds["REQUEST"])
        
        if not response:
            self.debug(f"ECU fault reading failed for: {ecu_frame['VARIANT']}")
            self.debug(response)
            return tree

        # ignore any junk
        if len(response) < 4:
            self.debug(f"Invalid fault query response received: {response}")
            return tree
        
        if len(response) == 4:
            tree["FAULTS"] = 0;
            return tree

        fault_tree = OrderedDict()
        
        # Decode the fault response
        if response[:len(cmds["ANSWEROK"])] == cmds["ANSWEROK"]:
            fault_tree = self.bb.parse_dtc_response(ecu_frame["ECUID"], ecu_frame["ECUVEID"], response)
            if not fault_tree:
                self.log(f"Error parsing fault response: {response}")
                return tree

            try:
                # Check if there's more faults to be read (use 17FFFF on A2004)
                if len(fault_tree) - 1 != fault_tree["NRODTC"]:
                    response_ext = self.adapter.send_wait_reply(cmdext["REQUEST"])
                    if not response_ext or len(response_ext) <= 4:
                        self.log("WARNING: Fault reading response was incomplete")
                    else:
                        if response_ext[:len(cmds["ANSWEROK"])] == cmds["ANSWEROK"]:
                            more_faults = self.bb.parse_dtc_response(ecu_frame["ECUID"], ecu_frame["ECUVEID"], response_ext)
                            if not more_faults:
                                self.log(f"Error parsing additional fault response: {response_ext}")
                            else:
                                for fault in more_faults:
                                    if fault == "NRODTC":
                                        continue
                                    fault_tree[fault] = more_faults[fault]
            except:
                self.log("Unhandled exception reading additional fault data. Continuing happily.")
                pass

            tree["FAULTS"] = fault_tree["NRODTC"]
            tree["FAULT_TREE"] = {}

            # Read here, but will also be loaded by Discovery if this function fails to return it
            if tree["FRAME_TREE"] == {}:
                tree["FRAME_TREE"] = self.bb.get_data_frames(ecu_frame["ECUID"], ecu_frame["ECUVEID"])

            self.log("Registered " + str(tree["FAULTS"]) + " faults")

            if tree["FAULTS"] > 0:                   
                if fault_tree != "":
                    fault_details_tree = self.bb.get_dtc_printout(ecu_frame["ECUID"], ecu_frame["ECUVEID"], fault_tree)

                    if fault_details_tree == {}:
                        self.debug("Error obtaining fault details tree for " + str(ecu_frame["VARIANT"]))
                        return tree

                    ctr = -1

                    for code in fault_tree:
                        if code not in fault_details_tree:
                            continue

                        ctr += 1        # which no of fault this is (needed for some FF retrieval)
                        tree["FAULT_TREE"][code] = fault_details_tree[code]
                        tree["FAULT_TREE"][code]["fframe"] = {}
                        #print(str(tree["FAULT_TREE"][code]))
                        ff = ""
                        if "ff" in fault_details_tree[code]:
                            ff = fault_details_tree[code]["ff"]

                        if ff != "":
                            self.log("Fetching freeze frame ID: " + str(ff) + " for code " + str(code))
                            if tree["FRAME_TREE"]["ff"] != {}:
                                if len(tree["FRAME_TREE"]["ff"]["frames"]) != 1:
                                    if len(tree["FRAME_TREE"]["ff"]["frames"]) != 0:
                                        self.log("Currently can't support reading FF from multiple frames. Report this to dev and it will be fixed - " + str(tree["FRAME_TREE"]["ff"]["frames"]))
                                    continue
                                else:   
                                    # no guarantee that the freeze frame we get will match the code because dictionaries
                                    # get out of order during all the processing and the ECU indexing is silly anyway 
                                    freeze = self.get_dtc_ff(code, ctr, tree["FRAME_TREE"]["ff"]["frames"][0]["frid"])

                                    if freeze == False:
                                        self.log("Freeze frame response obtained was invalid")
                                        tree["FAULT_TREE"][code]["fframe"] = {}
                                        continue
                                    
                                    fparse = self.parse_params_hex(tree["FRAME_TREE"], freeze, tree["FRAME_TREE"]["ff"]["frames"][0]["zone"], "ff", va_id=ff)
                                    tree["FAULT_TREE"][code]["fframe"] = fparse
                            else:
                                self.log("No freeze frames for this ECU")
                        else:
                            self.log("FF is blank")
                else:
                    self.debug(f"Error identifying DTCs for {ecu_frame['VARIANT']}")
                    self.debug(str(fault_tree))
                   
        elif response[:len(cmds["ANSWERKO"])] == cmds["ANSWERKO"]:
            self.debug("KO Error obtaining fault codes for ECU")

        # clean up nicely
        if not configured:
            self.adapter.fini_ecu()

        return tree

    
    def get_dtc_ff(self, dtc, code_offset: int, frame_id: int):
        '''
        Send a request string to the ECU to ask for freeze frame data on a DTC code
        - dtc is the code bytes that came from the ECU
        - code_offset is the offset of the code (1 indexed)
        - frid is the frame ID of the freeze frame request frame
        - Returns False if no response, otherwise the full bytes response
        '''
        send_par = ""
        param_name = ""

        frames = self.bb.get_zone_frame_set(frame_id)
        if not frames:
            return False

        par_len = max(list(frames["REQUEST"]["params"].keys()))

        if par_len != 3:
            self.log("Unexpected length of freeze frame parameter - " + str(par_len) + " for " + str(frame_id))
            return False

        if 3 in frames["REQUEST"]["params"]:
            param_name = frames["REQUEST"]["params"][3]["parname"]
            
            if param_name == "DTC_CODE":
                # send the DTC to get the freeze frame
                send_par = dtc

            elif param_name == "DTC_RANG":
                # send the DTC offset
                code_offset = str(code_offset)
                if len(code_offset) == 1:
                    code_offset = "0" + str(code_offset)
                send_par = code_offset

            else:
                self.log(f"Please report this - unimplemented DTC FF request parameter: {param_name} in {frame_id}")
                return False
        else:
            self.log("No third parameter for freeze frame")
            return False

        sendstr = ""

        for pos in range(1, par_len + 1):
            if frames["REQUEST"]["params"][pos]["val"] != "":
                sendstr = sendstr + str(frames["REQUEST"]["params"][pos]["val"])

            elif frames["REQUEST"]["params"][3]["parname"] == param_name:
                sendstr = sendstr + str(send_par)

        response = self.adapter.send_wait_reply(sendstr)
        if not response:
            self.log("No response for freeze frame request " + sendstr)
            return False
        else:
            # disassemble response according to frs["ANSWEROK"]
            if response[:2] != "7F":

                return response


                ########## TODO STUFF ###############
                frm = []
                pars = frames["ANSWEROK"]["params"]

                kes = max(list(pars.keys()))

                print(pars)

                # skip LID and SID
                for pos in range(0, kes+1):
                    if pos not in pars:
                        continue
                    
                    if "DTC_CODE" == pars["parname"]:
                        # ( pos + 2 ) - 1, we hardcode for 2 bytes of code FOR NOW
                        if pos + 1 < len(response):
                            return
            #return code, response


    def clear_and_refresh(self, ecu_frame):
        '''
        Clear faults and then re-read them

        - Returns false if the clear operation failed (no change)
        - Else returns a dict of new fault data
        '''
        if not self.adapter.init_ecu(ecu_frame):
            return False
        
        ret = self.clear_all_faults(ecu_frame, True)

        if not ret:
            return False

        self.log("DTC cleared, re-scanning now...")

        ret = self.scan_ecu_faults(ecu_frame, True)

        return ret


    def clear_all_faults(self, ecu_frame, configured=False):
        '''
        Clear all faults (that will clear) from a given ECU frame
        '''
        
        if not configured:
            if not self.adapter.init_ecu(ecu_frame):
                return False

        # try to find the command from the database
        query_frames = self.bb.get_dtc_query_frame(ecu_frame["ECUVEID"], is_clear = True)
        
        # otherwise try the most likely command set
        if not query_frames:
            cmds = self.get_lang("CLEARFAULT")
        else:
            cmds = { "REQUEST": query_frames[0], "ANSWEROK": query_frames[1], "ANSWERKO": query_frames[2] }

        response = self.adapter.send_wait_reply(cmds["REQUEST"])

        if not configured:
            self.adapter.fini_ecu()

        if not response:
            self.log("No response to fault clearing request")
            return False
        
        if self.diagmatch(response, cmds["ANSWEROK"]):
            return True

        elif self.diagmatch(response, cmds["ANSWERKO"]):
            self.log(f"ECU rejected fault clear attempt: '{response}'")
            return False

        else:
            self.log(f"ECU returned unexpected data '{response}'")
            return False
        

    def zeroes(self, lng, data, filler="0", data_pos="right"):
        '''
        Generate a fixed "lng" string, with data aligned right or left
        '''
        p = ""
        lng = lng - len(str(data))
        for i in range(0,lng):
            p = p + filler
        if data_pos == "left":
            return str(data) + p
        elif data_pos == "right":
            return p + str(data)
        else:
            self.log("Invalid data_pos to zeroes")
            return p + str(data)

    
    def load(self):
        rb = open("bsi_flash.dmp", "r")
        self.lines = rb.read().splitlines()
        self.linepos = 0


    def simulate(self, request, fmt):
        if self.lines[self.linepos][:3] == "35B":
            self.linepos += 1
            return self.simulate(request, fmt)
        
        self.log(f"QUERY: " + request)
        px = self.lines[self.linepos]
        self.linepos += 1
        self.log("RESPO: " + px)
        return re.findall('.{1,2}', px)


    def read_table_lid(self, root = "C0"):
        '''
        Read from the BSI flash the LID table for parameters & telecoding
        - For Bx, Cx, Dx zones only
        - For A0 ONLY (Ax above that is development only)

        The returned strings give the MAP ABS numbers, in the order they appear in the returned byte string?

        OFFICIALLY VALID FOR AEE2004 ONLY, not used in AEE2010
        '''
        #self.load()
        self.log("Reading LID tables for root..." + str(root))

        rqst = "35" + root
        more_data = True
        offset = 1

        lid_zones = {}
        lid_tables = []
        this_lid = []

        while more_data:

            exp_zone = self.zeroes(6, self.to_hex(offset))
            next_rqst = rqst + exp_zone + "11"
            for i in range(0,5):
                resp = self.adapter.send_wait_reply(next_rqst, fmt=self.adapter.BYTEARR)
                #resp = self.simulate(next_rqst, "")
                if not not resp:
                    break
            if not resp:
                # lost the flow, give up with this zone
                this_lid = []
                more_data = False
                offset += 1
                continue

            bytes_read = len(resp)
            
            # if we're done reading
            if resp[2] == "FF":
                self.log(f"Finished reading at {root} : {offset}")
                more_data = False
                break

            if resp[2] != "80":
                self.log("Response to this root got corrupted")
                more_data = False
                return

            if "".join(resp[3:6]) != exp_zone:
                self.log(f"Received wrong zone information: {resp[3:6]}")
                more_data = False
                return

            len_data = self.int(resp[6],base=16)   # 0x11 => 17

            if 7 + len_data <= bytes_read:
                for i in range(7, 7+len_data):
                    if resp[i] == "FF":
                        if this_lid != []:
                            lid_tables.append(this_lid)
                        this_lid = []
                    else:
                        this_lid.append(resp[i])
                

            # we should then have a CRC @ J+1
            # TODO: Work out the real CRC algorithm
            crc = resp[7 + len_data ]
            crcb = resp[7 + len_data + 1]
            self.log("LID CRC: " + str(crc) + ", " + str(crcb))

            offset += 1

        # write any remaining data (no closing FF on the actual data)
        if this_lid != []:
            lid_tables.append(this_lid)

        # Now A0 is a special case
        if root == "A0":
            # first entry gives the order of parameters
            parameters = lid_tables[0]
            lid_zones["A0"] = parameters[1:]
            
            # each following one gives the data format of the data
            # 0xFE = Log, 0xFD = Octets (uint_8), 0xFC = Word (uint_16), 0xFB = Dword (uint_32)
            # TODO: Work out to implement this: is only used to format identification data properly, low priority
            for i in range(1, len(lid_tables)):
                pass

        else:
            # Bx, Cx, Dx
            for offset in lid_tables:
                fb = self.int(offset[0],base=16)
                # first byte should be 0-16 (B0 - BF)
                if 0 <= fb < 16:
                    zone = root[0] + self.to_hex(fb,lng=1)
                    lid_zones[zone] = []
                    for bt in range(1, len(offset)):
                        lid_zones[zone].append(self.int(offset[bt],base=16))

                else:
                    self.log(f"Invalid LID zone identifier: {fb}")
                    continue

        # share with other diag_x libraries directly
        self.bb.set_lid_table(lid_zones)

        return lid_zones
                



