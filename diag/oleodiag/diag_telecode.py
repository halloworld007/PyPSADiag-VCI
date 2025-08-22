from .diag import diag
from enum import IntEnum
import os.path, re, math, yaml, traceback, datetime

'''
    diag_telecode
    Interpret telecoding frames from the database, and use them to communicate with the ECU

    (c) Copyright 2021. All Rights Reserved

    IMPORTANT: This particular library is the one with the potential to do ECU damage. Develop,
               and use, with extreme caution.

'''

class TelecodeResult(IntEnum):
    OK = 0              # succeeded
    OK_AUTH = 1         # succeeded but auth was required
    AUTH_FAILED = 2     # unlocked, but it still says locked
    REJECTED = 3        # ECU rejected the telecoding request
    NO_AUTH = 4         # ECU rejected the security access
    NO_RESPONSE = 5     # ECU did not respond or was invalid
    UNSAFE = 6          # unable to identify services properly
    INVALID_INPUT = 7   # invalid parameter or error unformatting


class diag_telecode(diag):
    tla = "TLC"
    callback = None 
    trs = None      # translations instance
    adapter = None  
    tree = None     # TREE from discovery
    tlcd = None
    local_mirror = {}     # dict of ecu memory zones (content of each zone stored as a list)
    params = {}     # params to values
    bb = None       # bramble instance

    display_mode = 2 # MODE_SIMPLE

    tlcd_display = []

    ecuname = ""
    ecuid = 0
    ecuveid = 0
    vin = 0

    cache_file = None
    callback_opt = None
    choice_waiting = False
    choice_made = None


    fr_ws = {}
    fr_rs = {}
    fr_rs_p = {}
    read_services = {}

    UDS_LOCKED = "33"
    UDS_TEL_BLOCK_ALL = "FF"    # 255 -> write all parameters
    TLCD_SID_SUPPORTED = [ "3B", "2E" ]     # allow write using known/understood services only


    def __init__(self, trs, adapter, bb):
        self.adapter = adapter
        self.trs = trs
        self.bb = bb

        try:
            # support importing keys from external file
            f = open("db/ecu_keys.yml")
            f_contents = f.readlines()
            f_contents = "".join(f_contents)
            keys = yaml.safe_load(f_contents)

            for key in keys:
                if type(keys[key]) == list:
                    for key_possibility in keys[key]:
                        if type(key_possibility) != str:
                            keys[key] = str(keys[key])

                            while len(keys[key]) < 4:
                                keys[key] = "0" + keys[key]

                elif type(keys[key]) != str:
                    keys[key] = str(keys[key])

                    while len(keys[key]) < 4:
                        keys[key] = "0" + keys[key]
                    
                    keys[key] = [ keys[key] ]

                else:
                    keys[key] = [ keys[key] ]

            self.uds_keys = keys
            self.log("Loaded " + str(len(keys)) + " keys from external file")
        except:
            self.log("Unable to load external keys, falling back to internal ones")


    def set_up(self, ecu_frame, tlcd_tree, vin=None, prot=None):
        '''
        API: Initial configuration with Discovery tree

        ecu_frame - the ECU key in the global tree [BSI2010] -> {}
        tlcd_tree - the output from diag_bramble:get_params_from_telecoding
        vin - the VIN key from the global tree - if available (only to label the backup)
        '''

        # Reset stuff
        self.fr_ws = {}
        self.fr_rs = {}
        self.fr_rs_p = {}
        self.read_services = {}
        self.local_mirror = {}
        self.params = {}

        if ecu_frame != None:
            self.tree = ecu_frame
        else:
            return False    

         # TODO - read ECU specific protocol once implemented
        if prot is None:
            prot = self.PROTOCOL_KWP

        # bus headers
        if "TX_H" in ecu_frame and "RX_H" in ecu_frame and "BUS" in ecu_frame:
            self.headers = (ecu_frame["TX_H"], 
                            ecu_frame["RX_H"], 
                            ecu_frame["BUS"], 
                            ecu_frame["PROTOCOL"], 
                            ecu_frame["TARGET_CODE"], 
                            ecu_frame["DIALOG_TYPE"])
        else:
            self.tree = None
            return False

        # ecu parameters
        self.ecuid = self.tree["ECUID"]
        self.ecuveid = self.tree["ECUVEID"]
        self.ecuname = self.tree["ECUNAME"]
        self.command_set = prot

        # vin or fall back to variant name
        if vin == None:
            self.vin = self.tree["VARIANT"]
        else:
            self.vin = vin

        # response to get_params_tlcd
        if tlcd_tree != None:
            self.tlcd = tlcd_tree
        else:
            return False

        return True


    def reset(self):
        pass


    def read_all_configuration(self, callback = None, zone_restrict = None):
        '''
        API: BLOCKING: Read all configuration from an ECU
        This copies the relevant ECU memory zones into local storage, to be accessed
        by each parameter

        This also builds the relevant lookup tables for forming and using zone read/write frames
        This is a complex process as we try to guesstimate/calculate which frame(s) can or should be used
        Sometimes the user will have to decide for themselves, because there is simply not enough information
        in the database to distinguish between different frames (its a hotchpotch mess of XML and S scripts)

        Hopefully 2010-on should be simpler because there's no XML...?

        callback will be called after each zone is read, if supplied
        zone_restrict to read only from specific zones
        '''
        if self.tree == None or self.tlcd == None:
            return False

        # clear local cache
        self.local_mirror = {}
        self.tlcd_display = []

        # work out a list of parameters we actually want to DISPLAY
        ctr = 0
        if self.display_mode == self.MODE_SIMPLE:
            for parm in self.tlcd:

                if self.tlcd[parm]["label"] != "":
                    self.tlcd_display.append(parm)
                    self.log("Displaying parameter: " + str(parm))
                    ctr += 1
                else:
                    self.log("Refuse to show parameter: " + str(parm))

            self.log("Displayed " + str(ctr) + " of " + str(len(self.tlcd)) + " available parameters")
        else:
            self.log("This display mode is not valid")
            return False

        # do initial processing into class dicts when we change ECU
        if self.fr_ws == {} or self.fr_rs == {} or self.fr_rs_p == {} or self.read_services == {}:
            self.fr_ws = {}
            self.fr_rs = {}
            self.fr_rs_p = {}

            self.read_services = {}
            self.read_services_by_param = {}
            self.write_services_by_param = {}

            # get the FRAPAS dump for the FRID
            for parm in self.tlcd:

                self.read_services_by_param[parm] = {}
                self.write_services_by_param[parm] = {}
                # there are some cases where there will be multiple FRAMES/ZONES which
                # actually all read from the same frame zone (e.g. B3). Whilst we care about
                # the distinction  when WRITING the parameter back, for reading we
                # can optimise away this duplication because 21B3 is always 21B3

                # but we have to process it like this make sure we respect different SID read cmds
                # TODO: If read cmd is REQUPL, do we have to init with 0x35 first?

                for read_svc in self.tlcd[parm]["read"]:

                    if type(read_svc) != dict:
                        self.log(str(parm) +  " - read service was generated incorrectly")
                        continue

                    # only read parameters we want to display (this means we will only read frames containing
                    # data we want (and avoid reading frames that don't contain any relevant data)
                    if parm in self.tlcd_display:
                        # this means we get zone_frame_set for ALL read frids
                        if read_svc["frid"] not in self.fr_rs:
                            self.fr_rs[read_svc["frid"]] = self.bb.get_zone_frame_set(read_svc["frid"])

                        # point zones to all possible frids that read them
                        if read_svc["zone"] not in self.read_services:
                            if read_svc["zone"] not in self.read_services:
                                self.read_services[read_svc["zone"]] = []
                            self.read_services[read_svc["zone"]].append(read_svc["frid"])

                    # read this stuff regardless, cuz we need to have all parameters zone/frid data
                    if read_svc["zone"] not in self.read_services_by_param[parm]:
                        self.read_services_by_param[parm][read_svc["zone"]] = []
                    if read_svc["frid"] not in self.read_services_by_param[parm][read_svc["zone"]]:
                        self.read_services_by_param[parm][read_svc["zone"]].append(read_svc["frid"])
                
                # also generate param : frid_writes map
                for write_svc in self.tlcd[parm]["write"]:

                    if type(write_svc) != dict:
                        self.log(str(parm) +  " - write service was generated incorrectly")
                        continue

                    if write_svc["zone"] not in self.write_services_by_param[parm]:
                        self.write_services_by_param[parm][write_svc["zone"]] = []

                    if write_svc["frid"] not in self.write_services_by_param[parm][write_svc["zone"]]:
                        self.write_services_by_param[parm][write_svc["zone"]].append(write_svc["frid"])


        # Read data from the adapter
        if not self.adapter.configure(*self.headers):
            self.debug("Telecoding abandoned due to ECU config response failure")
            return False
            
        if not self.adapter.init_ecu(self.tree):
            self.debug("Telecoding abandoned because ECU did not initialise")
            return False

        for rzon in self.read_services:
            if zone_restrict is None or rzon in zone_restrict:
                if len(self.read_services[rzon]) > 0:
                    self.read_memory_zone(self.read_services[rzon][0], rzon)
                    if callback is not None:
                        callback(rzon)
                else:
                    self.log("Skipped zone " + str(rzon) + " because it has no valid read commands")
            else:
                self.log("Skipped zone " + str(rzon) + " because we were asked to")
        self.adapter.fini_ecu()

        # Now extract the actual parameters from the memory zones
        if len(self.local_mirror) > 0:

            # note we have to extract everything in tlcd, not just display
            for parm in self.tlcd:
                #z = self.read_services_by_param[parm]
                v = self.format_tlcd_param(parm)
                if not v:
                    continue
                else:
                    #self.log("Added " + str(parm))
                    self.params[parm] = v
            self.log("Parsed " + str(len(self.tlcd)) + " parameters")
            return True
    

        return False

    
    def read_memory_zones(self, zone_list):
        '''
        Read only the zones given in zone_list

        '''
        return self.read_all_configuration(zone_restrict = zone_list)


    def read_memory_zone(self, zone, rzon):
        '''
        Read from a specified memory zone (give by zone)

        zone = frid
        rzon = zone Bx
        '''
        self.log("Reading from zone: " + str(rzon))
        self.fr_rs[rzon] = self.fr_rs[zone]

        # use pre-calculated chain if possible
        if zone in self.fr_rs_p:
            sq = self.fr_rs_p[zone]["REQUEST"]
        else:
            rq = self.fr_rs[zone]["REQUEST"]
            sq = {}
            for pos in rq["params"]:
                if type(rq["params"][pos]) == list:
                    self.log("WARNING: Unsupported request frame parameter list : " + str(rq))
                    break
                else:
                    if not self.not_blank(rq["params"][pos]["val"]):
                        self.log("WARNING: Unexpected blank request parameter : " + str(rq))
                        break
                    sq[pos] = rq["params"][pos]["val"]
            
            sq = self.join_frame(sq)
            self.fr_rs_p[zone] = {}
            self.fr_rs_p[zone]["REQUEST"] = sq

        # request the frame
        resp = self.adapter.send_wait_reply(sq)
        if not resp or len(resp) < 4:
            self.log("ECU " + str(self.ecuveid) + " failed to respond to read request for " + str(sq))
            return False

        # ANSWERKO should always be 7F something, but we parse to be safe
        if "ANSWERKO" in self.fr_rs_p[zone]:
            ako = self.fr_rs_p[zone]["ANSWERKO"]
        else:
            ako = self.fr_rs[zone]["ANSWERKO"]
            aks = {}
            for pos in ako["params"]:
                if type(ako["params"][pos]) == list:
                    self.log("WARNING: Unsupported ansko frame parameter list : " + str(ako))
                    return False
                if ako["params"][pos]["val"] == 0:
                    break
                aks[pos] = ako["params"][pos]["val"]
            ako = self.join_frame(aks)
            self.fr_rs_p[zone]["ANSWERKO"] = ako
        
        if len(resp) >= len(ako):
            if ako == resp[:len(ako)]:
                if resp == "7F2231":
                    self.log("Reading from " + str(zone) + " not supported by this firmware version")
                    return False
                else:
                    self.log("ECU refused reading: " + str(resp))
                    return False
        
        # ANSWEROK
        if "ANSWEROK" in self.fr_rs_p[zone]:
            aok = self.fr_rs_p[zone]["ANSWEROK"]
            # compile this too
        else:
            aok = self.fr_rs[zone]["ANSWEROK"]
            aks = {}
            for pos in aok["params"]:
                if type(aok["params"][pos]) == list:
                    # param list
                    break
                    #self.log("WARNING: Unsupported ansok frame parameter list : " + str(aok))
                    #return False
                # only read values up to the point where it becomes variable
                # (ie. read SID, LID but not further PARAMS)
                if aok["params"][pos]["val"] == 0 or aok["params"][pos]["val"] == "":
                    break
                aks[pos] = aok["params"][pos]["val"]
            aok = self.join_frame(aks)
            self.fr_rs_p[zone]["ANSWEROK"] = aok
        
        if len(resp) >= len(aok):
            if aok == resp[:len(aok)]:
                # read went OK
                self.cache_ecu_backup(resp)

                self.local_mirror[rzon] = re.findall('.{1,2}', resp)

                self.debug("Read from zone " + str(rzon))
                return True

        self.log(aok)

        self.log("ECU " + str(self.ecuveid) + " response to reading configuration was invalid : " + str(resp))


    def format_tlcd_param(self, parm):
        '''
        Format (from hex to display) a parameter

        - Assume that self.mirror contains all the ECU memory we could desire
        - Decide which read frame to use
        '''
        #self.log(str(zone) + " : " + str(parm))

        if len(self.tlcd[parm]["read"]) == 0:
            return False
        else:
            base_svc = self.tlcd[parm]["read"][0]

        # now have to work out which FRID/response to use
        for read_svc in self.tlcd[parm]["read"]:
            for key in read_svc:
                if read_svc[key] != base_svc[key]:
                    # if everything is the same except FRID
                    if key != "frid":
                        self.log("Mismatch in ECU read frame services for " + str(parm) + " - " + str(read_svc["frid"]) + " and " + str(base_svc["frid"]))
                        return False

        zone = self.tlcd[parm]["read"][0]["zone"]
        pardes = self.tlcd[parm]["read"][0]         # get the parameter description (pos/lby etc)
        
        if zone in self.local_mirror and parm in self.tlcd:
            resp = self.local_mirror[zone]
            mlen = len(resp)
            pos = pardes["pos"] - 1

            if self.not_blank(pardes, "crc") or self.not_blank(pardes,"blk") or self.not_blank(pardes, "dyn"):        
                self.log("CRC, block and dynamic block type parameters are currently not supported, frame skipped")
                return False

            raw_val = self.param_format(pardes, pos, mlen, resp)

            # fix because format = BINARY is lies - it might be BINARY but the STATES are bytes 01, 02 etc
            if "lenby" in pardes:
                raw_val = self.int(raw_val, base=2)
                if len(str(raw_val)) == 1:
                    raw_val = "0" + str(raw_val)

            if raw_val is None:
                self.log("Failed to parse " + str(parm))
                return False

            if "states" not in self.tlcd[parm] or len(self.tlcd[parm]["states"]) == 0:
                # TODO: When this is supported, enable in advanced mode only
                self.log("Parameter " + str(parm) + " without predefined states is currently not supported")
                return False

            for state in self.tlcd[parm]["states"]:
                if str(state["val"]) == str(raw_val):
                    #self.debug("Parameter " + str(parm) + " : " + str(state["label"]))
                    return state["label"]
            
            self.log(str(parm) + " did not match any known state with: " + str(raw_val))
            return False
        else:
            return False

    
    def unformat_tlcd_param(self, zone_content: list, parameter, value, frid: dict):
        '''
        Take a param value from its fully parsed state back to a hex value

         - zone_content is the full byte ECU response
         - parm is the dict describing the parameter
         - val should be the new state value
         - frid service to use for unformatting
        '''

        self.log(f"Unformatting {parameter} : {value}")

        value = str(value)
        hex_val = -1


        if parameter in self.tlcd:
            mlen = len(zone_content)
            pos = frid["pos"] - 1

            # are we sure about the conversion regards numeric/enum/binary etc?

            if frid["type"] == "BOOLEAN":
                if len(value) > 0:
                    value = value[:1]
                if value != "0" and value != "1":
                    self.log("Invalid boolean value supplied for " + str(parameter))
                    return False


            if frid["format"] == "BITS":
                # get new bit value
                lng = frid["lenbi"]
                msk = frid["msk"]
                bitarr = list(value)

                # get old bit array
                rlen = math.ceil(lng / 8)
                if pos + rlen <= mlen:
                    old_arr = self.bytes_to_bits(zone_content[pos:pos+rlen])
                else:
                    self.log(str(pos) + " and " + str(rlen) + " beyond scope " + str(mlen) + " in param " + str(parameter))
                    return False

                new_arr = self.remask(bitarr, old_arr, msk)
                if not new_arr:
                    return False

                # merge new value into old response
                hex_val = self.to_hex(int(str(new_arr),2))
                lng = rlen
                

            elif frid["format"] == "BYTES":
                # read old value
                lng = frid["lenby"]
                if pos + lng <= mlen:
                    old_val = zone_content[pos:pos+lng]
                else:
                    self.log("Couldn't read existing value for "+ str(parameter))
                    return False
                hex_val = self.to_hex(value)
                self.log("Telecoding parameter from " + str(old_val) + " to " + str(hex_val))


            elif frid["format"] == "BITOSET":
                # post-parse LID tables
                lenbi = 0
                typ = ""

                if "lenby" in frid:
                    if frid["lenby"] != 0:
                        lenbi = self.int(frid["lenby"]) * 8
                        typ = "by"
                if "lenbi" in frid:
                    if frid["lenbi"] != 0:
                        lenbi = self.int(frid["lenbi"])
                        typ = "bi"
                
                if lenbi == 0:
                    self.log("Invalid length for BITOSET " + str(frid["pid"]))
                else:
                    lng = lenbi
                    base_pos = pos
                    abs_len = frid["abs"]
                    start = base_pos + math.floor(abs_len / 8)
                    end = base_pos + math.ceil((abs_len + lenbi) / 8)

                    if end <= len(zone_content):                
                        sty = "msb"

                        # bit values need to be processed with LSB as index 0 per byte
                        #if "endian" in tree:
                        #   if tree["endian"] == 1:
                        if typ == "bi":
                            sty = "lsb"

                        if "endian" in frid:
                            if frid["endian"] == self.LITTLE_ENDIAN:
                                sty = "msb"

                        rval = self.bytes_to_bits(zone_content[start:end], sty)
                            
                        bit_start = abs_len % 8
                        bit_end = bit_start + lenbi
                        raw_val = rval[bit_start:bit_end]

                        # don't reverse endinanness?
                        new_val = self.bytes_to_bits(value)

                        if lenbi < len(new_val):
                            new_val = new_val[-lenbi:]
                        else:
                            self.log("Length mismatch at 0")

                        self.log("From " + str(raw_val) + " to " + str(new_val))

                        if len(new_val) == len(raw_val):
                            self.log("From: "  + (str(rval)))
                            hex_val = rval[:bit_start] + new_val + rval[bit_end:]
                            self.log("To: " + str(hex_val))
                            if sty == "lsb":
                                hex_val = hex_val[::-1]

                            hex_val = "".join(hex_val)
                            hex_val = self.int(hex_val, base=2)
                            hex_val = self.to_hex(hex_val)
                            pos = start
                            lng = end-start
                        else:
                            self.log("Length mismatch at 1")

                    elif frid["pid"] not in self.warned_params:
                        self.log("Invalid length for BITOSET " + str(frid["pid"]))
                        self.warned_params.append(frid["pid"])


            elif frid["format"] == "MAPPED":
                self.log("Un-LID parsed BSI parameters are not codable")
                return False
        
            else:
                self.log("Format" + str(frid["format"]) + " is not yet supported for param " + str(parameter))
                return False

            if hex_val == -1:
                return False

            # join the new value into the hex string
            out_val = "".join(zone_content[:pos]) + hex_val + "".join(zone_content[pos+lng:])
            out_val = re.findall('.{1,2}', out_val)
            if len(out_val) != mlen:
                self.log(str(out_val) + " is not the same length as original " + str(zone_content))
                return False
            else:
                return out_val

        else:
            return False


    '''         ===========  WRITING OF VALUES ==================== '''

    def write_change_list(self, change_set: dict, callback_opt = None):
        '''
        API: Write a list of changes, may not necessarily be in the same zone

        # MUST BE RUN in a background thread

        Expects the label of the state (blocks)

        [parm] =>
            [ "old" ] = old value
            [ "new" ] = new value
            [ "zone"] = zone Bx

        Returns:
         a list of tuples with (zone_frid, zone)
        '''
        if callable(callback_opt):
            self.callback_opt = callback_opt

        if len(change_set) == 0:
            self.log("No changes to be made")
            return False

        frames_to_choose = {}
        frames_to_try = {}

        # par_frames_try is used to find all the FRIDs which have the parameter in the same position
        # but may contain other parameters - then it tries to match each of them against the read
        # service to guess which one is the "correct" write service

        for param in change_set:
            if len(self.tlcd[param]["write"]) == 0:
                self.log("Skipped because no valid write service for " + str(param))
                continue
            elif len(self.tlcd[param]["write"]) == 1:
                frames_to_choose[param] = [ self.tlcd[param]["write"][0]["frid"] ] 
                frames_to_try[param] = [ self.tlcd[param]["write"][0]["frid"] ] 
            else:
                
                base_svc = self.tlcd[param]["write"][0]
                frames_to_choose[param] = [ base_svc["frid"] ]
                frames_to_try[param] = [ base_svc["frid"] ]

                # now have to work out which FRID/response to use
                # compare the parameter properties for each zone
                # if they match, we can use either zone to write this parameter
                # and we add that to the list to try (see comment below)
                # if they don't match {NOT SURE IF ACTUALLY IMPLENTED IN GPFT at this point}, 
                # ask the user to choose which one they want
                for write_svc in self.tlcd[param]["write"]:
                    for key in write_svc:
                        if write_svc[key] != base_svc[key]:
                            # if some things besides FRID is different
                            if key != "frid" and key != "zone":
                                frames_to_choose[param].append(write_svc["frid"])
                            else:
                                frames_to_try[param].append(write_svc["frid"])


        #  par_frames_choose:
        #  currently, for some ECUs, we can't work out which
        # frame to use for writing, so we have no option but to
        # ask the user to do so (for now, user guide will have to recommend on a per-ecu basis)
        # The primary guilty ECU so far is the EMF with its colour/not colour options and also some engine ECUs
        # -- NOTE: This is currently not enabled, because it's untested and unimplemented in the UI
        """         
        for parm in par_frames_choose:
            if len(par_frames_choose[parm]) > 1:
                if self.callback_opt != None:
                    self.choice_waiting = True
                    self.callback_opt(par_frames_choose[parm], parm, self.write_change_update)
                    self.log("Asking user to choose frame ID....")
                    while self.choice_waiting:
                        # elevator music
                        pass
                    if self.choice_made in par_frames_choose[parm]:
                        final_frames[parm] = self.choice_made
                    else:
                        self.log("User cancelled operation or chose invalid option: " + str(self.choice_made))
                        return False
                else:
                    self.log("UI didn't provide a callback to let user choose an option. Abandoning")
                    return False

            else:
                final_frames[parm] = par_frames[parm][0] """

        if len(frames_to_try) != len(change_set):
            self.log("Warning - some parameters are missing frames to attempt: " + str(change_set.keys()) + " / " + str(frames_to_try.keys()))

        # now we have decided which frames to use for each parameter

        results = {}

        for param in frames_to_try:
            zone = change_set[param]["zone"]
            res = self.write_memory_zone(param, change_set[param], self.read_services[zone][0], frames_to_try[param])
            results[zone] = (res, self.read_services[zone][0])
        
        return results


    def write_change_update(self, choice, *largs):
        '''
        Respond to a callback made from an end user interface
        '''
        if self.choice_waiting:
            self.choice_made = choice
            self.choice_waiting = False
            self.log("User selected " + str(choice))


    def write_memory_zone(self, parameter: str, old_new_vals: dict, read_svc: int, write_svcs: list):
        '''
        API: WRITE changes to a memory zone. Use with caution

        - parm is the parname
        - vals is a dict, with { "old": old_val, "new": value }
        - read_svc is a single integer for the read service for the parameter
        - write_svc is a list of possible services used to write the parameter
        '''

        rsvc = {}
        wsvc = {}

        if type(write_svcs) != list:
            write_svcs = [ write_svcs ]

        self.log("Preparing " + str(parameter) + " using rsvc " + str(read_svc) + " and wsvc(s) " + str(write_svcs))

        # integrity of process check
        if parameter not in self.tlcd:
            self.log("Serious internal flow error - parameter does not exist: " + str(parameter))
            return TelecodeResult.UNSAFE

        # get zone for frid - READ
        for svc in self.tlcd[parameter]["read"]:
            if read_svc == svc["frid"]:
                rsvc = svc
                break
            
        # make a list of the parameter properties for each service (as write_svc contains only numbers)
        for svc in self.tlcd[parameter]["write"]:
            for possible_svc in write_svcs:
                if possible_svc == svc["frid"]:
                    wsvc[possible_svc] = svc
                    break
        
        if wsvc == {} or rsvc == {}:
            self.log("Invalid frame id(s) for " + str(parameter))
            return False

        for possible_svc in wsvc:
            if wsvc[possible_svc]["zone"] != rsvc["zone"]:
                # TODO - try to throw out the svc that threw the error and try the next one
                self.log(f"It's not supported to write to a different location {wsvc[possible_svc]['zone']} than I read from {rsvc['zone']}")
                return TelecodeResult.UNSAFE

        if rsvc["zone"] not in self.local_mirror:
            self.log(f"Tried to modify zone {rsvc['zone']} which hasn't been read yet")
            return TelecodeResult.UNSAFE

        # get full frame descriptors for read and write
        read_frames = self.bb.get_zone_frame_set(read_svc)
        write_frames = {}
        for frid in write_svcs:
            write_frames[frid] = self.bb.get_zone_frame_set(frid)

        if not read_frames or not write_frames:
            self.log("Invalid frame ID's specified or could not be obtained: " + str(read_svc)  + " / " + str(write_svcs))
            return False

        zone = rsvc["zone"]

        # check the "old" value matches whats in our cache
        fmt = self.format_tlcd_param(parameter)
        if fmt != old_new_vals["old"]:
            self.log("Integrity of cache failed - " + str(old_new_vals["old"]) + " doesn't match " +  str(fmt))
            return TelecodeResult.UNSAFE

         # check the state is a valid state, and get its value
        new_value = None
        for state in self.tlcd[parameter]["states"]:
            if old_new_vals["new"] == state["label"]:
                #self.debug(str(parm) + " : " + str(stat["val"]))
                new_value = state["val"]
                break
        if new_value == None:
            self.log("Supplied value was not a valid parameter state, or user attempted to change a numeric/text value - supplied " + str(old_new_vals["new"]))
            return TelecodeResult.INVALID_INPUT


        # verify we can format + unformat the parameter according to the given specs
        # this verifies the integrity of the parameter properties / parsing code
        self.debug("Current value of zone in memory: " + str(self.local_mirror[zone]))

        hex_val = self.unformat_tlcd_param(self.local_mirror[zone], parameter, new_value, rsvc)
        if not hex_val:
            self.log("Failed in unformatting " + str(parameter))
            return TelecodeResult.INVALID_INPUT
        self.debug("New value of zone in memory: " + str(hex_val))

        if hex_val == self.local_mirror[zone]:
            self.log("Unable to format parameters successfully. Giving up.")
            return TelecodeResult.INVALID_INPUT


        # now try parsing the parameter for all the possible write frames until one passes the safety checks
        checks_passed = False
        using_write_svc = None

        for possible_svc in write_frames:
            '''
            Process is
            1. Get the writing frame for the parameter
            2. X Change the byte string we hold
            3. Verify the list of parameters in the read and write frames match
            - if there are additional parameters without defined values, give up
            - if they have defined values, use them
            4. 
            '''
            using_write_svc = possible_svc

            self.log("Trying write service " + str(possible_svc))
        
            # rule out anything with an unsupported service identifier
            if 1 in write_frames[possible_svc]["REQUEST"]["params"]:
                if write_frames[possible_svc]["REQUEST"]["params"][1]["val"] not in self.TLCD_SID_SUPPORTED:
                    self.log("Writing to memory requiring the service " + str(write_frames[possible_svc]["REQUEST"]["params"][1]["val"]) + " is not currently supported, frid of " + str(possible_svc))
                    continue
            else:
                self.log("Unable to verify service is supported - check frid " + str(possible_svc))
                continue

            # TODO: move read_frame calculation outside of loop
            read_request_frame = read_frames["ANSWEROK"]
            write_request_frame = write_frames[possible_svc]["REQUEST"]
            request_header = ""
            write_header = {}
            broke_data = ""
            first_data = ""

            # Here we do another sanity check - working out what bytes of
            # the write frame are UDS commands and what are our parameters
            # For the BSI there is extra parameter between LID and start of data
            # This is set to FF because we write the whole zone at once

            # read all prescribed elements of request header
            number_of_params = max(list(read_request_frame["params"].keys()))

            for pos in range(1, number_of_params+1):
                if pos in read_request_frame["params"]:

                    if type(read_request_frame["params"][pos]) == list:
                        if first_data == "":
                            first_data = read_request_frame["params"][pos][0]["parname"]
                        # TODO: do we need to check for imposed/prescribed values inside the list (e.g. mapped parameters with absolute stuff)?
                        
                    elif not self.not_blank(read_request_frame["params"][pos]["val"]):
                        if first_data == "":
                            first_data = read_request_frame["params"][pos]["parname"]
                    
                    elif first_data != "":
                        self.log("Prescribed values in read service continued after non-prescribed values. Unable to continue for " + str(read_svc))
                        return TelecodeResult.UNSAFE
                    else:
                        request_header = request_header + str(read_request_frame["params"][pos]["val"])

            if first_data == "":
                self.log("Failed to find any non-prescribed values")
                return TelecodeResult.UNSAFE

            self.log("rsvc is OK, must match to " + str(first_data))

            # read elements of writing frame until we reach first_data
            number_of_params = max(list(write_request_frame["params"].keys()))

            # this needs to take account of the bitmask, where used
            # for parameters where there are multiple ones in a single byte
            # and might be listed in a different order
            reached = 0
            for pos in range(1, number_of_params+1):
                reached += 1
                if pos in write_request_frame["params"]:
                    if type(write_request_frame["params"][pos]) == list:
                        if write_request_frame["params"][pos][0]["parname"] == first_data:
                            break 
                        else:
                            broke_data = write_request_frame["params"][pos][0]["parname"]
                            break

                    if write_request_frame["params"][pos]["parname"] == first_data:
                        break

                    write_header[write_request_frame["params"][pos]["parname"]] = str(write_request_frame["params"][pos]["val"])
            
            if broke_data != "":
                self.log("Failed to match write frame parameter order, stuck on " + str(broke_data))
                self.log(str(write_request_frame["params"]))
                continue
            else:
                for pos in range(reached+1, number_of_params):
                    if type(write_request_frame["params"][pos]) == list:
                        for j in write_request_frame["params"][pos]:
                            if str(j["val"]) != "":
                                self.log("Found prescribed value " + str(j["parname"]) + " after expected data at position " + str(pos) + " - unable to continue for " + str(possible_svc))
                                continue
                    else:
                        if str(write_request_frame["params"][pos]["val"]) != "":
                            self.log("Found prescribed value " + str(write_request_frame["params"][pos]["parname"]) + " after expected data at position " + str(pos) + " - unable to continue for " + str(possible_svc))
                            continue
            
            checks_passed = True

        if not checks_passed or using_write_svc == None:
            self.log("No write service could be found which produced a satisfactory result, giving up")
            return TelecodeResult.UNSAFE
        else:
            self.log("Using write svc: " + str(using_write_svc))

        writ_hdr_str = ""
        self.log("Writing header: " + str(write_header))

        # Look for values that have non-hexadecimal characters in them, and then look for states with that name
        # Otherwise, there may be more values in read and write headers with prescribed/imposed values

        for par in write_header:
            if write_header[par] == "":
                # some blank parameters may have "imposed values" or defined values in the tlcd tree         
                if par in self.tlcd:
                    # TODO: implement this check in wri_hdr discovery, because some "blank" parameters may still have imposed values
                    found = False
                    for svc in self.tlcd[par]["write"]:
                        if svc["frid"] == using_write_svc:
                            found = True
                            print(svc)
                            if self.not_blank(svc, "defval"):
                                writ_hdr_str += svc["defval"]
                            elif self.not_blank(svc, "impval"):
                                writ_hdr_str += svc["impval"]
                            else:
                                self.log("Found " + str(par) + " but it has no prescribed values")
                                return TelecodeResult.UNSAFE
                            break
                    
                    if not found:
                        #else:
                        self.log("Found " + str(par) + " but it has no prescibed write services")
                        return TelecodeResult.UNSAFE
                else:         
                    self.log("Error - invalid blank parameter(s) in write header: " + str(write_header))
                    return TelecodeResult.UNSAFE
            else:
                writ_hdr_str += write_header[par]

        if len(request_header) < 4 or len(writ_hdr_str) < 4:
            self.log("Invalid header strings calculated - " + str(request_header) + " / " + str(writ_hdr_str))
            return TelecodeResult.UNSAFE

        # limit to 1 because there might be more occurrences in the byte string
        hex_val = "".join(hex_val)
        hex_val = hex_val.replace(request_header, writ_hdr_str, 1)

        # sanity check the replacement
        if hex_val[0] != writ_hdr_str[0]:
            self.log("Mismatch in intended writing string with memory zone log: " + str(hex_val) + " / " + str(writ_hdr_str))
            return TelecodeResult.UNSAFE
        
        self.log("Plan to write: " + str(hex_val))
        write_str = hex_val

        '''
        Note -: maybe useful in future
        Writing frame for BSI ONLY
        3B LID Nx Bx ..
        Nx = either abs or post-processed abs, or 255 for full memory zone
        '''

        exp_ok = write_frames[using_write_svc]["ANSWEROK"]["params"][1]['val']


        if not self.adapter.init_ecu(self.tree):
            self.log("ECU failed to respond to initialise")
            return TelecodeResult.NO_RESPONSE

        ret = self.ecu_do_write(write_str, exp_ok)

        return ret


    def ecu_do_write(self, write_str, exp_ok, auth = False):
        '''
        write_str : the full command to send to the ECU
        '''

        # try to write the parameter
        self.cache_ecu_backup(write_str)

        if write_str[:2] == "2E":
            self.command_set = self.PROTOCOL_UDS

        if auth:
            self.log("Trying telecoding with authentication")
            if not self.security_access(self.ecuname, commands = self.bb.get_ecu_security_cmds(self.ecuveid)):
                self.log("Security access rejected, telecoding abandoned")
                return TelecodeResult.AUTH_FAILED

        resp = self.adapter.send_wait_reply(write_str)
        if not resp:
            self.log("No response from ECU to write request")
            return TelecodeResult.NO_RESPONSE
        
        if len(resp) < 4:
            self.log("Invalid ECU response: " + str(resp))
            return TelecodeResult.NO_RESPONSE
        
        if resp[:2] == exp_ok:
            self.log("ECU accepted the telecoding request")
            if auth:
                return TelecodeResult.OK_AUTH
            else:
                return TelecodeResult.OK
        
        if resp[:2] == "7F":
            # read detail codes to know if we need SA
            if resp[2:4] == write_str[:2]:
                # it was meant for us
                if resp[4:6] == self.UDS_LOCKED:
                    if auth:
                        self.log("ECU rejected request, claimed it was locked, despite unlocking it")
                        return TelecodeResult.NO_AUTH
                    else:
                        self.log("ECU rejected telecoding request, requires authentication.")
                        return self.ecu_do_write(write_str, exp_ok, auth=True)
                else:
                    self.log("ECU rejected the telecoding request with code: " + str(resp[4:]))
                    return TelecodeResult.REJECTED
            else:
                self.log("Unexpected rejection from the ECU -> wasn't a reply to our command")
                return TelecodeResult.REJECTED
        
        else:
            self.log("ECU responded in an unexpected manner with " + str(resp) + " but expected " + str(exp_ok))


    def do_write_secure_telecoding(self, is_uds: bool = False):
        '''
        Write to the traceability zone to avoid DTC stored for "secured telecoding"
        is_uds = True - use UDS
        otherwise uds KWP
        '''

        type_of_repairer = 0xFB         # FB = independent, FD = Aftersales
        diagnostic_tool = 0xC7B7E3      # C7B7E3 = diagbox, 000000 = Factory
        current_date = datetime.date.today().strftime("%d%m%y")

        if not is_uds:
            if self.command_set == self.PROTOCOL_UDS:
                is_uds = True

        self.log(f"Writing traceability zone with UDS: {is_uds}")
        if is_uds:
            traceability: str = f"2E2901{type_of_repairer:x}{diagnostic_tool:x}{current_date}"  # FD000000010101
            response = "6E"
        else:
            traceability: str = f"3BA0FF{type_of_repairer:x}{diagnostic_tool:x}{current_date}"  # FD0000000101010000
            response = "62"

        return self.ecu_do_write(traceability, response)


    def cache_ecu_backup(self, frame):
        '''
        Any time an ECU zone is read, write it to a backup file. This helps to restore configuration
        in case of program or user error
        '''
        try:
            tlc_name = str(self.vin)
            if tlc_name == "" or tlc_name == "0":
                tlc_name = str(self.ecuid) + "-" + str(self.ecuveid) + "-" + str(self.ecuname)

            fname = str(tlc_name) + ".tll"
            
            if not os.path.isdir(self.logdir):
                os.mkdir(self.logdir)
            self.cache_file = open(self.logdir + fname, "a")

            log_str = str(self.millis()) + "," + str(self.ecuid) + "," + str(self.ecuveid) + ","
            log_str = log_str + str(frame) + "\n"

  

            self.cache_file.write(log_str)
            self.cache_file.close()
            return True
            
        except:
            self.log("WARNING: Unable to save telecoding backup data. Check the location " + self.logdir + " is writable. Proceed with caution")
            self.log(traceback.format_exc())
            return False
        

