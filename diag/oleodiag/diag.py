'''

diag - base class for each one in the library containing functions used by them all

Copyright (c) 2020 BrambleDiag


'''

import re, math, csv, time
import pprint

class diag:
    '''
    Root class to provide global constants and logging functions
    '''

    tla = "DIA"
    PROTOCOL_UDS = 1
    PROTOCOL_KWP = 0
    
    PARAM_INVALID = "INVALID"
    PARAM_EMPTY = "EMPTY"
    STATUS_VALID = "Valid"
    ECUIDENTOK = "IDENTOK"

    MODE_STARTER = 1
    MODE_SIMPLE = 2
    MODE_ADVANCED = 3
    MODE_EXPERIMENTAL = 4

    LITTLE_ENDIAN = 1

    TLCD_OLD = 1
    TLCD_NEW = 2

    LID_MISSING = -1    # should be an impossible raw_val

    NACKS = { "11": "Service not supported", "12": "Subfunction not supported", "21": "System busy, try again", "22": "Conditions not correct"}

    # Keep track of what gave errors so we don't flood warnings 
    # every time a parameter is read (once per subsystem)
    warned_params = []
    hexa_warns = []

    prot = PROTOCOL_KWP
    trs = None
    bb = None
    hexa_trs = {}
    uds_keys = { "BSI2010": "B2B2", "MATT_C_2010": "ECEC" }
    adapter = None
    logdir = "logs/"
    zone_map = False

    # 19 01 XX YY ZZ ZZ (ZZZZ = data count, XX = dtc status mask, YY = DTC FID)
    # 19 02 XX YYYY ZZ (XX = status mask, YYYY = DTC, ZZ = status)
    # 19 0F = mirror memory (journal?)
    # 19 11 = NRO mirror memory
    # UDS fault reading has 19 and then 01 = NRODTC, 02 =, 11 = , 0F = 

    # zones to try and find how to request SA
    security_request_seed = [ "GETSEED" ]
    security_request_send = [ "SENDKEY" ]

    uds = { "READZONE": { "REQUEST": "22", "ANSWEROK": "62", "ANSWERKO": "7F22" },
            "READFAULT": { "REQUEST": "22E7FF", "ANSWEROK": "62E7", "ANSWERKO": "7F22"},
            "READFAULTEXT": { "REQUEST": "190209", "ANSWEROK": "5902", "ANSWERKO": "197F" },
            "CLEARFAULT": { "REQUEST": "14FF00", "ANSWEROK": "54", "ANSWERKO": "147F" },
            "SA_DL_GETSEED": { "REQUEST": "2701" , "ANSWEROK": "6701", "ANSWERKO": "7F27"},
            "SA_DL_SENDKEY": { "REQUEST": "2702" , "ANSWEROK": "6702", "ANSWERKO": "7F27"},
            "SA_CF_GETSEED": { "REQUEST": "2703" , "ANSWEROK": "6703", "ANSWERKO": "7F27"},
            "SA_CF_SENDKEY": { "REQUEST": "2704" , "ANSWEROK": "6704", "ANSWERKO": "7F27"}
            }
    kwp = { "READZONE": { "REQUEST": "21", "ANSWEROK": "61", "ANSWERKO": "7F21" },
            "READFAULT": { "REQUEST": "17FF00", "ANSWEROK": "57", "ANSWERKO": "177F"},
            "READFAULTEXT": { "REQUEST": "17FFFF", "ANSWEROK": "57", "ANSWERKO": "177F" },
            "CLEARFAULT": { "REQUEST": "14FF00", "ANSWEROK": "54", "ANSWERKO": "147F" },
            "SA_DL_GETSEED": { "REQUEST": "2781" , "ANSWEROK": "6781", "ANSWERKO": "7F27"},
            "SA_DL_SENDKEY": { "REQUEST": "2782" , "ANSWEROK": "6782", "ANSWERKO": "7F27"},
            "SA_CF_GETSEED": { "REQUEST": "2783" , "ANSWEROK": "6783", "ANSWERKO": "7F27"},
            "SA_CF_SENDKEY": { "REQUEST": "2784" , "ANSWEROK": "6784", "ANSWERKO": "7F27"} 
            }

    def get_lang(self, x):
        if self.prot == self.PROTOCOL_UDS:
            return self.uds[x]
        else:
            return self.kwp[x]
    
    def millis(self):
        return int(round(time.time() * 1000))

    def not_blank(self, inp, key = None):
        '''
        Warning: known bug where "in" can fail if called with sqlite3.row object
        '''
        if key != None:
            if key in inp:
                inp = inp[key]
            else:

                return False
        if inp is None:

            return False
        if inp == "":

            return False
        if inp == 0:
      
            return False
   
        return True

    def bytes_to_bits(self, data, endian="msb"):
        '''
        Convert a byte string to a binary list [0,0,0,0,0,0,0]
        Default to big-endian but sometimes PSA used little
        '''
        out = []
        for x in data:
            x = int(x, 16)
            c = "{0:08b}".format(x)
            if endian == "lsb":
                c = c[::-1]
            out.append(c)
        binstr = "".join(out)
        
        return list(binstr)

    def unmask(self, data, mask):
        '''
        Extract only the relevant bits
        '''
        if len(mask) < len(data):
            data = data[:len(mask)]
        out = []
        offset = 0
        in_mask = False
        mask_zeroes = 0
        for sign in mask:
            
            if sign == 1 or sign == '1':
                if not in_mask:
                    in_mask = True
                    out.append(data[offset])
                else:
                    for i in range(0, mask_zeroes):
                        out.append("0")
                    out.append(data[offset])

            else:
                if in_mask:
                    mask_zeroes +=1

            
            offset = offset + 1

        
        return "".join(out)


    def remask(self, needle, haystack, mask):
        '''
        Insert data into a bitarr using mask
        '''
        if len(mask) > len(haystack):
            # something is invalid
            return False
        out = []
        needle_offset = 0
        haystack_offset = 0
        for sign in mask:
            if sign == 1 or sign == "1":
                out.append(needle[needle_offset])
                needle_offset += 1
            else:
                out.append(haystack[haystack_offset])
            haystack_offset += 1
        
        # append any remaining bits (if the parameters was 1.5 bytes, we need
        # to still write the other 0.5 bytes back because the parser only works
        # with whole bytes
        if haystack_offset < len(haystack):
            for i in range(haystack_offset,len(haystack)):
                out.append(haystack[i])
        
        return "".join(out)


    def uds_transform(self, data, sec):
        '''
        UDS authentication transformation function from seed
        '''
        if data > 32767:
            data = -65536 | data
        if data > 0:
            q = int(data % int(sec[0]))
        else:
            q = int(data % int(sec[0])) - sec[0]
        a = (q * int(sec[2])) & 0xFFFFFFFF
        b = ((int(round(data / int(sec[0]), 12)) & 0xFFFFFFFF) * sec[1]) & 0xFFFFFFFF
        subresult = (a - b) & 0xFFFFFFFF
        if subresult > 0x7FFFFFFF:
            subresult = subresult + (sec[0] * sec[2]) + sec[1]
        subresult = subresult & 0xFFFF
        return subresult


    def uds_bruteforce(self, seeds):
        '''
        Bruteforce a UDS key from a list of challenge responses

        -seeds : tuples of (chall, resp) as string of bytes (0AF676A1,96B2F3C1)
        '''
        keys = []
        for a in range(0, 16):
            for b in range(0,16):
                for c in range(0,16):
                    for d in range(0,16):
                        key = "{0:x}".format(a) + "{0:x}".format(b) + "{0:x}".format(c) + "{0:x}".format(d)
                        valid = True
                        for pair in seeds:
                            if self.uds_compute_response(pair[0], key) != pair[1]:
                                valid = False
                                break         
                        if valid:
                            keys.append(key)
        return keys
                        

    def uds_compute_response(self, seed_txt, app_key_txt):
        '''
        Compute a UDS response for a given key and seed
        '''
        self.log("Compute SA response for seed: " + str(seed_txt))
        seed = [seed_txt[0:2], seed_txt[2:4], seed_txt[4:6], seed_txt[6:8]]
        app_key = [app_key_txt[0:2], app_key_txt[2:4]]

        sec_1 = [0xB2, 0x3F, 0xAA]
        sec_2 = [0xB1, 0x02, 0xAB]

        res_msb_1 = self.uds_transform(int(app_key[0] + app_key[1], 16), sec_1)
        res_msb_2 = self.uds_transform(int(seed[0] + seed[3], 16), sec_2)
        res_msb = res_msb_1 | res_msb_2

        res_lsb = self.uds_transform(int(seed[1] + seed[2], 16), sec_1) | self.uds_transform(res_msb, sec_2)

        subresult = (res_msb << 16) | res_lsb
        subresult = hex(subresult)
        subresult = subresult.rjust(8, '0')

        self.log("Giving SA seed response of " + str("{0:x}".format(int(subresult, 16))))

        return "{0:x}".format(int(subresult, 16))

    
    def security_access(self, ecuname, dl_or_cfg = "cfg", commands = None):
        '''
        Request security access to an ECU

        NOTE this is hardcoded because there are no known exceptions to the standard
        
        - dl_or_cfg - whether to ask for DOWNLOAD or CONFIGURE permissions
        - expect ECU session already configured
        - commands is the output of diag_bramble::get_ecu_security_cmds()
        '''

        if ecuname == None:
            return False
        
        if commands is None:
            self.log("Unable to perform security access without commands")
            return False

        #if dl_or_cfg != "dl" and dl_or_cfg != "cfg":
        #    return False

        if ecuname in self.uds_keys:
            key_possibles = self.uds_keys[ecuname]

            for key in key_possibles:

                self.log("Found UDS key for " + str(ecuname))

                # Get the seed
                #if dl_or_cfg == "dl":
                #    cmds = self.get_lang("SA_DL_GETSEED")
                #else:
                #    cmds = self.get_lang("SA_CF_GETSEED")
                try:
                    cmds = commands["GETSEED"]
                except:
                    self.log("No command to unlock ECU")
                    return False
                    
                resp = self.adapter.send_wait_reply(cmds["REQUEST"])
                
                if not resp:
                    # no response
                    self.log("No response from ECU to SA request")
                    return False
                
                if len(resp) > 4:
                    if resp[:4] == cmds["ANSWEROK"]:
                        seed = resp[4:]
                        self.log("ECU sent seed: " + str(seed))
                    elif resp[:4] == cmds["ANSWERKO"]:
                        # rejected request
                        self.log("ECU rejected SA request")
                        return False
                
                if len(seed) != 8:
                    return False

                # Compute key
                auth = self.uds_compute_response(seed, key)

                if len(auth) != 8:
                    self.log("Authentication response was too short")
                    return False

                # Send it
                #if dl_or_cfg == "dl":
                #    cmds = self.get_lang("SA_DL_SENDKEY")
                #else:
                #    cmds = self.get_lang("SA_CF_SENDKEY")
                try:
                    cmds = commands["SENDKEY"]
                except:
                    self.log("No command to send key to ECU")
                    return False
                
                resp = self.adapter.send_wait_reply(cmds["REQUEST"] + auth)

                if not resp:
                    self.log("ECU did not respond to SA request")
                    return False

                if len(resp) >= 4:
                    if resp[:4] == cmds["ANSWEROK"]:
                        self.log("ECU SA response was OK")
                        return True
                    else:
                        self.log("ECU SA response was not valid")
                        continue
                else:
                    self.log("ECU SA response was too short")
                    return False
                
            
        else:
            self.debug("There is no known or valid key for this ECU: " + str(ecuname))
            return False


    def parse_param_format(self, tree, frame, ff = None):
        '''
        Parse a parameter subtree, by working out what the data type is
        and presenting it in the correct, decoded, final, format (with units etc)

        - frame is the clean data string, stripped of headers and pre-error checked

        TODO: General note, can we be sure a parameter will not intentionally be ""?
        TODO: Output a state with is_default: 1 in case of parse error
        '''
        data = { "PARAM" : "", "LABEL": "", "VALUE": "", "HELP": "", "PID": "", "STATUS": "NULL" }

        mlen = len(frame)

        pos = None      # what byte to start read
        rlen = None     # how many bytes to read

        raw_val = None
        parsed_val = None

        if "parname" in tree:
            data["PARAM"] = tree["parname"]
        else:
            self.log("Invalid parameter entry supplied, will not be parsed")
            self.log(print(tree))
            return {}

        if "label" in tree:
            if tree["label"] != "":
                data["LABEL"] = tree["label"]
            else:
                data["LABEL"] = tree["parname"]
        else:
            data["LABEL"] = tree["parname"]

        if "help" in tree:
            data["HELP"] = tree["help"]

        if "pid" in tree:
            data["PID"] = tree["pid"]

        if "pos" in tree:
            if tree["pos"] != 0:
                # get position. Check it's not beyond len (frame)
                # in case calling function didn't do its job properly
                if self.int(tree["pos"]) - 1 < mlen:
                    pos = tree["pos"] - 1

        # use the pos that matches the dynamic block ID
        if "dyn_pos" in tree and ff is not None:
            if ff in tree["dyn"]:
                dynid = tree["dyn"][ff]["ref"]
                pos = (tree["dyn_pos"][dynid] - 1) + (tree["dyn"][ff]["pos"] - 1)
                self.log("Use " + str(tree["dyn_pos"][dynid]) + " and " + str(tree["dyn"][ff]["pos"]) + " instead of " + str(tree["pos"]))
            else:
                self.log("Bad FF in dynamic position - " + str(ff))

        if "formula" in tree:
            if tree["formula"] != "LINEAR":
                self.log("Parameter formula is not supported")
                return data

        
        if pos == None:
            self.debug("Invalid or improper parameter position for " + str(tree["parname"]) + " : " + str(tree["pos"]))
            return data

        if "format" in tree:
            raw_val = self.param_format(tree, pos, mlen, frame)

        if raw_val == None:
            #self.log("Invalid or improper parameter format for " + str(data["PARAM"]) + " with PID " + str(data["PID"]))
            return data

        # Now parse the data into the correct format
        if "type" in tree and raw_val != self.LID_MISSING:
            #[ "BINARY", "BOOLEAN", "NUMERIC", "IDENTICAL", "COMPUTED" ]

            if tree["type"] == "BINARY":
                parsed_val = str(raw_val)

            elif tree["type"] == "BOOLEAN":
                if len(raw_val) > 1:
                    self.debug("WARNING: BOOLEAN value was more than LENGTH 1. Clamping to [0] from " + str(raw_val))
                parsed_val = self.int(raw_val)

            elif tree["type"] == "NUMERIC":
                if "offset" in tree and "factor" in tree:
                    fac = self.float(tree["factor"], 1)
                    off = self.float(tree["offset"], 0)
                    floated = self.float(self.int(raw_val, base = 2), 0)
                    parsed_val = (floated * fac) + off
                    parsed_val = round(parsed_val, 2)
                else:
                    self.log("Missing numeric formula in " + str(tree["parname"]))
                
        if parsed_val == None:
            #self.log("WARNING: Cannot parse parameter " + str(tree["parname"]) + " with type " + str(tree["type"]))
            data["STATUS"] = "UNSUPPORTED"
            return data

        data["STATUS"] = "PARSED"

        if raw_val == self.LID_MISSING:
            # Because there's no way of knowing until this point whether or not
            # a parameter is actually available from the BSI we're connected to
            # It is up to end-user/GUI software to filter out parameters which
            # have the STATUS of NOTEXIST
            data["VALUE"] = "Not available"
            data["STATUS"] = "NOTEXIST"

        # states gives better labelling/formatting
        # but if we don't have that fall back to hex_states
        elif 'edv_states' in tree:
            if len(tree['edv_states']) > 0:
                default = None
                for state in tree['edv_states']:
                    if state["single_val"] != '':

                        if type(state["single_val"]) == float:
                            cmp_val = float(self.int(str(parsed_val), base=2))
                        else:
                            cmp_val = parsed_val

                        if state['single_val'] == cmp_val:
                            if state["label"] != "":
                                data["VALUE"] = state["label"]
                            elif state["name"] != "":
                                data["VALUE"] = state["name"]
                            else:
                                data["VALUE"] = str(parsed_val)

                    elif state["min_val"] != '' and state["max_val"] != '':
                        if self.float(state["min_val"]) <= self.float(parsed_val) < self.float(state["max_val"]):
                            if tree["type"] == "NUMERIC":
                                if tree["unit"] != "":
                                    temp = self.trs.decodalate(tree["unit"], str(parsed_val))
                                    if temp != "":
                                        data["VALUE"] = temp
                                    else:
                                        data["VALUE"] = str(parsed_val)
                                else:
                                    data["VALUE"] = str(parsed_val)
                    else:
                        if state["label"] != "":
                            default = state["label"]
                        elif state["name"] != "":
                            default = state["name"]
                
                if data["VALUE"] == "":
                    # can only be empty if no value set, due to other logic here
                    if default != None:
                        data["VALUE"] = default
                    else:
                        # no default provided
                        data["VALUE"] = self.PARAM_INVALID

        elif 'hex_states' in tree:
            # fall back on hex_states if needed
            if len(tree["hex_states"]) > 0:
                for state in tree["hex_states"]:
                    # compare min/max/exact value
                    if state["val"] != "":
                        if state["val"] == parsed_val:
                            if state["name"] != "":
                                data["VALUE"] = state["name"]
                            else:
                                data["VALUE"] = str(parsed_val)
                    elif state["max"] != "" and state["min"] != "":
                        if float(state["min"]) <= parsed_val < float(state["max"]):
                            if state["name"] != "":
                                data["VALUE"] = state["name"]
                            else:
                                data["VALUE"] = str(parsed_val)

        if data["VALUE"] == "":
            if parsed_val != None:
                parsed_val = str(parsed_val)
                if tree["type"] == "BINARY":
                    parsed_val = self.to_hex(self.int(parsed_val, base=2))
                if tree["pencode"] == "HEXA":
                    data["STATUS"] = "HEXFIX"
                    if "edatid" in tree:
                        parsed_val = str(self.hexa_fix(tree["edatid"], parsed_val))
                elif tree["pencode"] == "ASCII":
                    parsed_val = self.parse_ascii(parsed_val)

                data["VALUE"] = str(self.trs.decodalate(tree["unit"], parsed_val))
            else:
                data["STATUS"] = "EMPTY"
                data["VALUE"] = self.PARAM_EMPTY

        #self.log(str(data["LABEL"]) + " : " + str(data["VALUE"]) + " from " + str(raw_val))

        return data


    def param_format(self, tree, pos, mlen, frame):
        '''
        Handle the parsing of the formatting type of the parameter

        Use PID to refer to parameter because tree is only guaranteed to contain format info + PID
        '''
        raw_val = None

        
        if tree["format"] == "BITS":

            if "lenbi" in tree:
                if "msk" in tree:
                    rlen = math.ceil(tree["lenbi"] / 8)
                    if pos + rlen <= mlen:
                                           
                        bitarr = self.bytes_to_bits(frame[pos:pos+rlen])
                        raw_val = self.unmask(bitarr, tree["msk"])

                        raw_val = "".join(raw_val)
                    else:
                        self.log(str(pos) + " and " + str(rlen) + " beyond scope " + str(mlen))

            if self.not_blank(tree, "abs") and not self.not_blank(tree, "map"):
                if tree["abs"] != -1 and tree["pid"] not in self.warned_params:
                    self.log("Check existence of ABS in parameter " + str(tree["pid"]))                    
                    self.warned_params.append(tree["pid"])


        if tree["format"] == "BYTES":
                      
            if "lenby" in tree:
                rlen = tree["lenby"]
                if pos + rlen <= mlen:

                    raw_val = self.bytes_to_bits(frame[pos:pos+rlen])

                    raw_val = "".join(raw_val)
                else:
                    self.debug(str(tree["pid"]) + ": pos + rlen exceeds byte string")

            if self.not_blank(tree, "abs"):
                if tree["abs"] != -1 and not self.not_blank(tree, "map"):
                    self.log("Check existence of ABS in parameter " + str(tree["pid"]))


        elif tree["format"] == "MAPPED":
            # means the data is stored using the LID_TABLE format and Bramble didn't decode it properly
            if tree["pid"] not in self.warned_params:
                #self.log("Could not parse " + str(tree["parname"]) + " as LID should have been filtered out")
                self.warned_params.append(tree["pid"])

        elif tree["format"] == "BITOSET":
            # post-parse LID tables
            lenbi = 0
            typ = ""

            if "lenby" in tree:
                if tree["lenby"] != 0:
                    lenbi = self.int(tree["lenby"]) * 8
                    typ = "by"
            if "lenbi" in tree:
                if tree["lenbi"] != 0:
                    lenbi = self.int(tree["lenbi"])
                    typ = "bi"
            
            if lenbi == 0:
                if tree["pid"] not in self.warned_params:
                    self.log("Invalid length for BITOSET " + str(tree["pid"]))
                    self.warned_params.append(tree["pid"])
            else:
                base_pos = pos
                abs_len = tree["abs"]
                start = base_pos + math.floor(abs_len / 8)
                end = base_pos + math.ceil((abs_len + lenbi) / 8)

                if end <= len(frame):                
                    sty = "msb"

                    # bit values need to be processed with LSB as index 0 per byte
                    #if "endian" in tree:
                    #   if tree["endian"] == 1:
                    if typ == "bi":
                        sty = "lsb"

                    if "endian" in tree:
                        if tree["endian"] == self.LITTLE_ENDIAN:
                            sty = "msb"

                    rval = self.bytes_to_bits(frame[start:end], sty)
                        
                    bit_start = abs_len % 8
                    bit_end = bit_start + lenbi
                    raw_val = rval[bit_start:bit_end]
                    raw_val = "".join(raw_val)

                elif tree["pid"] not in self.warned_params:
                    self.log("Invalid length for BITOSET " + str(tree["pid"]))
                    self.warned_params.append(tree["pid"])

                            
        elif tree["format"] == "PARAMBITS":
            self.debug("PARAMBITS is currently unimplemented")

        elif tree["format"] == "MINMAXBITS":
            # TODO_ON_REBUILD: Currently assumes TERM is zero, 
            self.debug("MINMAXBITS is currently unimplemented")

        elif tree["format"] == "NUMERO_RELATIF":
           # somehow we got passed an actuator test tree, give up
            self.debug("param_format passed NUMERO_RELATIF - check your code, fool")

        return raw_val


    def parse_ascii(self, response):
        '''
        Parse ASCII data stored using algorithm below

        response is a raw string of bytes ONLY the ASCII value

        Each byte XY is a type (X) and a data value (Y)
        The type field divides the alphabet into chunks of 16
        '''
        out = ""
        try:
            for x in range(0, len(response) - 1, 2):
                typ = int(response[x])
                cha = int(response[x+1],16)
                if typ == 3:
                    out = out + str(cha)
                elif typ == 4:
                    out = out + chr(ord('A')-1 + cha)
                elif typ == 5:
                    out = out + chr(ord('A')-1 + 16 + cha)
                else:
                    self.log("Unknown ASCII type permutation: " + str(typ))
                    out = out + hex(cha)
        except:
            pass
        return out


    def parse_params_hex(self, root_tree, resp, zone, frame="params", va_id = ""):
        '''
        Parse a parameter response into a dictionary of values

        Response frame should be the full one, we work out here if it needs shortened
        - tree = FRAME_TREE => id or FRAME_TREE => ff etc
        - frame = "params", "ff" or "id"
        - zone  = the memory zone resp is for
        '''
        data = {}
        resp = str(resp)
        self.zone_map = self.bb.get_lid_table(zone)     # will be junk unless we need it

        if frame in root_tree:
            if zone not in root_tree[frame]:
                # all ok
                self.debug("Invalid request to parse parameter frame: " + str(zone) + " in " + str(frame) + " does not exist")
                return {}
            else:
                tree = root_tree[frame][zone]
        else:
            self.debug("Invalid request to parse parameter frame: " + str(frame) + " does not exist")
            return {}


        if len(resp) < 6:
            self.log("Invalid diag response supplied to param parser: " + str(resp))
            return data
              
        if frame == "ff":
            if resp[2:4] != zone:
                self.log("WARNING: Incorrect zone information supplied to freeze frame parser. Told " + str(zone) + " but got " + str(resp[2:4]))     
                return data

        # Fix because VA frames expect only raw data (trim 61 87 D308)
        # AMENDED: dyn block position should be 6 (or whatever), to get pos for parsing
        #          we do dyn_pos + parameter_pos
        #if frame == "ff":
        #    resp = resp[10:]

        if len(frame) % 2 != 0:
            self.debug("Frame response data was not a multiple of 2, therefore corrupted. Unsafe to continue")
            return data

        spl = re.findall('.{1,2}', resp)        # split into two char chunks

        #pprint.pprint(tree["params"])

        for param in tree["params"]:
            ff_to_use = None

            if frame == "ff":
                if "dyn" not in param:
                    self.log("Freeze frame missing dynamic block allocator - this might be OK. Please report this ECU combination for analysis")
                    continue
                else:
                    can_parse_this = False
                    va_search_txt = va_id.replace("VA","")
                    for entry in param["dyn"]:
                        # TODO needs to be a REGEX so VA5 doesn't trigger on VA50
                        if va_search_txt in entry and "VA" in entry:
                            self.log("Matched to " + str(entry))
                            can_parse_this = True
                            ff_to_use = entry
                            break
                    
                    if not can_parse_this:
                        continue
            

            # gets the formatted value (as str, with units)
            out = self.parse_param_format(param, spl, ff_to_use)
            out["ZONE"] = zone
            data[param["parname"]] = out                 

        return data

    
    def hexa_fix(self, parid, val):
        '''
        This function plugs the gap of parameter conversion factors that aren't in CONVFORM,
        but for some nonsensical reason PSA chose to keep in the ECU specific DLL's 
        This is random, and some parameters for an ECU might be in the database, yet other
        obvious ones like battery voltage will be hidden in the DLL.

        !A warning that this factor/offset is non-original will be displayed to the user
        Might return string, integer, or who knows what else
        '''
        try:
            # First run, load data
            if self.hexa_trs == {}:
                csvfile = open(self.trs.path + "PARFORMULA.csv", newline='')
                cs = csv.reader(csvfile, delimiter=',', quotechar='"')  
                for f in cs:
                    if f[0] == "PARID":
                        continue
                    pid = self.int(f[0])
                    # 1 -> ecu name, used when updating databases to preserve PIDs
                    name = f[2]
                    fmt = f[4]
                    fac = self.float(f[5], 1)
                    add = self.int(f[6])
                    self.hexa_trs[pid] = { "name" : name, "fmt": fmt, "fac" : fac, "offset": add }
                
                self.log("Loaded " + str(len(self.hexa_trs)) + " hex fixes")

            parid = self.int(parid)
            if parid in self.hexa_trs:
                #  TODO - different parformats besides fac/offset
                mul = self.hexa_trs[parid]

                if mul["fmt"] == "HEXI":
                    y = ""
                    for x in range(0, len(str(val)), 2):
                        y = y + val[x:x+1] + ""
                    return y

                elif mul["fmt"] == "HEXA":
                    return self.to_hex(val)

                elif mul["fmt"] == "NUMERIC":
                    return (val * self.float(mul["fac"],1)) + self.float(mul["offset"])
            else:
                if parid not in self.hexa_warns:
                    self.log("Missing HEXA correction for EDATID: " + str(parid))
                    self.hexa_warns.append(parid)
                return str("0r" + val)
        except:
            pass
        return val


    def join_frame_zfs(self, tree, pars=None, error_on_blank=False):
        '''
        Join a zone_frame_set result into a sendable string
        '''
        self.log("JOIN_FRAME_ZFS NOT IMPLEMENTED - please report this")
        return

    
    def join_frame_bb(self, tree, error_on_blank=False):
        '''
        Join a frame from a diag_bramble dict
        up to the first non-specified parameter
         - Supply a dictionary of parameters in the frame
         - Returns a string
         - If error_on_blank is set, return False if there are empty parameters
        '''
        fr_pos = {}

        for param in tree:
            if "pos" in tree[param]:
                if tree[param]["pos"] in fr_pos:
                    if error_on_blank:
                        return False
                    break

                val = ""

                if "defval" in tree[param]:
                    if type(tree[param]["defval"]) is dict:
                        if "exact" in tree[param]["defval"]:
                            val = tree[param]["defval"]["exact"]
                    else:
                        val = tree[param]["defval"]     # acttest/new types
                elif "val" in tree[param]:
                    val = tree[param]["defval"]     # legacy

                if val != "":
                    fr_pos[tree[param]["pos"]] = val
                else:
                    if error_on_blank:
                        return False
                    break
        
        return self.join_frame(fr_pos) 


    def join_frame(self, rq):
        '''
        Join a dictionary of parameter values into a string
        and pad with zeroes when needed
        { 0 : 10, 1: 10C0, 2: 0F }
        '''

        pos_so_far = 1
        fr = []

        for pos in rq:
            v = rq[pos]
            ml = len(v)

            pos_so_far = int(pos_so_far)
            pos = int(pos)

            if str(pos) != str(pos_so_far):
                for x in range(pos_so_far,pos):
                    fr.append("00")
                pos_so_far = pos

            if ml == 2:
                fr.append(str(v))
                pos_so_far = pos_so_far + 1
            
            elif ml == 1:
                fr.append("0" + str(v))
                pos_so_far = pos_so_far + 1
            
            elif ml % 2 == 0:
                fr.append(str(v))
                pos_so_far = pos_so_far + (ml / 2)

            else:
                fr.append("0" + str(v))
                pos_so_far = pos_so_far + ((ml+1)/2)

        return "".join(fr)


    def diagmatch(self, resp, cmd):
        '''
        Checks to see if the first characters of resp are equal to cmd, safely
        This makes code that uses it much cleaner
        '''

        if type(cmd) == str and type(resp) == str:
            if resp != "" and cmd != "":
                r = len(resp)
                c = len(cmd)
                if c <= r:
                    if resp[:c] == cmd:
                        return True

        return False


    def diagnack(self, resp):
        '''
        Given a response resp that has been determined as an error code,
        try to extract the error
        This won't work for all ECU types yet, but most of them
        '''

        if len(resp) < 6:
            return "unknown"
        
        if resp[:2] == "7F":
            code = resp[4:6]

            if code in self.NACKS:
                return self.NACKS[code]
            else:
                return str(code)

        return "unknown"


    def log(self, x):
        logg = "[" + str(self.tla) + "] " + str(x)
        self.bb.logger(logg)
        #print(logg)

    def debug(self, x):
        self.log("WARN: " + str(x))

    '''
    INT and FLOAT functions which can handle empty input safely
    '''
    def int(self, inp, auto=0, base=10):
        try:
            if str(inp) == "":
                return auto
            else:
                return int(str(inp), base)
        except:
            return auto


    def float(self, inp, auto=0):
        try:
            if str(inp) == "":
                return auto
            else:
                return float(str(inp))
        except:
            return auto


    def to_hex(self, raw_val, lng=2):
        return "{0:0{1}x}".format(raw_val, lng).upper()
