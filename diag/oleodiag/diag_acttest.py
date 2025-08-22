from .diag import diag
import traceback, pprint

'''

DIAG_ACTTEST
(c) Copyright 2021

This class conducts an actuator test
Most functions are blocking, and designed to be run in a thread

'''

class diag_acttest(diag):
    tree = {}
    nctr = None
    bb = None

    screens = {}

    rq_cmd = { "REQUEST", "ANSWEROK", "ANSWERKO" }

    act_data = {}
    active_test = None
    ecu_frame = None
    is_step = False
    active_step = 0

    def __init__(self, trs, adapter, bmb):
        self.trs = trs
        self.adapter = adapter
        self.bb = bmb


    def set_up(self, active_test, tree, ecu_frame):
        '''
        Assign an actuator test tree (one test)
        '''
        self.tree = tree
        self.active_test = active_test
        self.type = tree['type']
        self.ecu_frame = ecu_frame



    def init_advanced(self, tree):
        '''
        Same as init_test below, but present user with all parameters to change
        as wished
        '''
        self.log("INIT_ADVANCED is not implemented yet - please report this")
        pass


    def init_test(self):
        '''
        User clicked "ACTUATE", so parse to find if any parameters
        need user specification

        '''

        self.rq_cmd = { "REQUEST" : {}}
        ask_user = {}

        self.is_step = False
        self.active_step = 0

        if "disabled" in self.tree:
            return { "STATUS": "NUMERO_RELATIF DISABLED" }

        # relatifs
        relatifs = {}

        self.log("Initialise actuator test: " + str(self.active_test))

        #pprint.pprint(self.tree)

        if "ACTUATE" in self.tree["zones"]:
            if "REQUEST" in self.tree["zones"]["ACTUATE"]:
                rq = self.tree["zones"]["ACTUATE"]["REQUEST"]

                # BSI04EV only: populate the numero_relatifs map
                # this is (for each parameter) abs => nr
                for param in rq:
                    if rq[param]["format"]["format"] == "NUMERO_RELATIF":
                        try:
                            relatifs[int(rq[param]["format"]["abs"])] = rq[param]["format"]["nr"]
                            #self.log("NR: Remapped ABS from " + str(rq[param]["format"]["abs"]) + " to " + str(rq[param]["format"]["nr"]))
                        except:
                            self.log("Internal error: please report this")
                            self.log(traceback.format_exc())
                            #pprint.pprint(rq[param]["format"])
                            return {"STATUS": "INVALID DATA FOUND"}

                for param in rq:

                    if rq[param]["defval"] != '':

                        # BSI04EV only: if the parameter is NUMERO_RELATIF, we need to replace its value with 
                        # the post-LID-mapped value. The defval of NUMERO_RELATIF is the abs value
                        # for the LID table we created above
                        if param == "NUMERO_RELATIF":
                            if int(rq[param]["defval"], 16) in relatifs:
                                if relatifs[int(rq[param]["defval"],16)] == -1:
                                    return {"STATUS": "Test is not supported by the ECU firmware version"}
                                else:                           
                                    self.rq_cmd["REQUEST"][rq[param]["pos"]] = self.to_hex(relatifs[int(rq[param]["defval"],16)])
                                    continue
                            else:
                                self.log("Unknown NUMERO_RELATIF " + str(rq[param]["defval"]))
                                return {"STATUS": "Test has invalid mapping and cannot be used"}

                        # otherwise we just populate with the defval, or if there isn't one
                        # ask the user what value they want to send
                        if type(rq[param]["defval"]) != dict:
                            self.debug("Using defval for param "  + str(param) + " : " + str(rq[param]["defval"]))
                            self.rq_cmd["REQUEST"][rq[param]["pos"]] = rq[param]["defval"]
                        else:
                            if "exact" in rq[param]["defval"]:
                                self.rq_cmd["REQUEST"][rq[param]["pos"]] = rq[param]["defval"]["exact"]
                                self.debug("Using exact value for " + str(param) + " : " + str(rq[param]["defval"]["exact"]))
                            else:
                                # is it invalid, or does it require user interaction?
                                ask_user[param] = rq[param]
                                self.debug("DEVWARN: Min/Max provided for actuator parameter, is not valid")

                    elif "steps" in self.tree:
                        self.log("Parameter " + str(param) + " will have value set according to the step")
                        self.rq_cmd["REQUEST"][rq[param]["pos"]] = param

                    else:
                        ask_user[param] = rq[param]
                        self.log("Added unknown parameter: " + str(param))
            
        else:
            return { "STATUS": "INVALID" }

        
        # Delete any unknown parameters if they have been usurped by a known one
        # Sometimes one FRAME can have 15 parameters at pos 7, but only one is valid
        # for a given test
        # TODO: What if it's not a whole byte?
        # TODO: Here is where we can let the user override MP_DUREE, for example (duration of test)
        def_ask_user = {}
        if len(ask_user) > 0:
            for param in ask_user:
                if ask_user[param]["pos"] not in self.rq_cmd["REQUEST"]:
                    def_ask_user[param] = ask_user[param]
                else:
                    self.log("Found value for unknown parameter: " + str(param))
        
        self.log("Ready to actuate " + str(self.active_test) + " (" + str( self.tree["title"]) + ") with : " + str(self.rq_cmd["REQUEST"]))

        if len(def_ask_user) > 0:
            return { "STATUS": "ASK", "PARAMS": def_ask_user }

        elif "steps" in self.tree:
            self.is_step = True
            self.active_step = 1

            self.log("Found " + str(len(self.tree["steps"])) + " for this test")

            if self.active_step not in self.tree["steps"]:
                self.log("Steps were promised but none were specified")
                return { "STATUS": "INVALID" }
                
            return { "STATUS": "OKSTEP" }

        else:
            return { "STATUS": "OK" }
        

    def begin_test(self, *pargs):
        '''
        Actually send the ACTUATE command

        Returns { STATUS : str
                  (o) ECU: { label, type }  
                  }
        '''

        if len(pargs) != 0:
            pass

        do_cmd = self.rq_cmd["REQUEST"]

        if self.is_step:

            if type(self.tree["steps"][self.active_step]) == list:
                self.log("DEVWARN: Don't support lists of (multiple) step parameters yet but " + str(self.active_test) + " has them")
                return { "STATUS": "Unsupported step types" }

            parname = self.tree["steps"][self.active_step]["parname"]
            found = False

            for pos in self.rq_cmd["REQUEST"]:
                if parname == self.rq_cmd["REQUEST"][pos]:
                    found = True
                    do_cmd[pos] = self.tree["steps"][self.active_step]["val"]
                    self.log("Set value of " + str(parname) + " to step value " + str(do_cmd[pos]))
                    break

            if not found:
                self.log("begin_test: Invalid step specified " +  self.active_step + "  param : " + str(parname))
                return { "STATUS": "Invalid step specified"}

        self.log("Final command is: " + str(do_cmd))

        if not self.adapter.init_ecu(self.ecu_frame):
            self.log("ECU did not respond to initialisation")
            return { "STATUS": "No response from ECU" }

        self.log("Building " + str(do_cmd))
        req = self.join_frame(do_cmd)
        nack = self.tree["zones"]["ACTUATE"]["ANSWERKO"]
        ack = self.tree["zones"]["ACTUATE"]["ANSWEROK"]


        self.log("Actuator begin sending " + str(req))

        resp = self.adapter.send_wait_reply(req)
        if not resp:
            return { "STATUS": "No response" }

        if self.diagmatch(resp, self.join_frame_bb(nack)):
            self.log("begin_test: ECU rejected command with code " + str(self.diagnack(resp)))
            return { "STATUS": "ECU rejected command with code: " + str(self.diagnack(resp)) }
        
        elif self.diagmatch(resp, self.join_frame_bb(ack)):
            self.log("begin_test: ECU replied " + str(self.parse_status(resp, ack)))
            return { "STATUS": "OK", "PAYLOAD": self.parse_status(resp, ack) }

        else:
            self.log("Unexpected response from ECU: " + resp)
            return { "STATUS": "unexpected response from ECU" }      


    def get_status(self):
        '''
        Execute the "GET_STATUS" command
        You can execute this as fast as you like, so it is up to the calling software
        to choose when. Approximately once a second is sensible.
        > We don't init the ECU, because if it's not been keep-alived then it stopped the test
        '''

        if "GET_STATUS" in self.tree["zones"]:
            if "REQUEST" in self.tree["zones"]["GET_STATUS"]:
                cmd = self.join_frame_bb(self.tree["zones"]["GET_STATUS"]["REQUEST"], error_on_blank=True)
                ack = self.tree["zones"]["GET_STATUS"]["ANSWEROK"]
                nack = self.tree["zones"]["GET_STATUS"]["ANSWERKO"]

                if not cmd:
                    # unsupported type with a blank parameter
                    self.log("get_status: Blank parameter in command request field")
                    return {"STATUS": "IMPOSSIBLE"}
                
                resp = self.adapter.send_wait_reply(cmd)

                if not resp:
                    self.log("get_status: no response from ECU")
                    return {"STATUS": "NOCOMMS"}
                
                elif self.diagmatch(resp,  self.join_frame_bb(nack)):
                    self.log("get_status: ECU rejected command with code " + str(self.diagnack(resp)))
                    return { "STATUS": "ECU rejected command with code: " + str(self.diagnack(resp)) }

                elif self.diagmatch(resp,  self.join_frame_bb(ack)):
                    self.log("get_status: ECU replied " + str(self.parse_status(resp, ack)))
                    return { "STATUS": "OK", "PAYLOAD": self.parse_status(resp, ack) } 

        else:
            self.log("Test " + str(self.active_test) + " missing a GET_STATUS command")
            return { "STATUS": "IMPOSSIBLE"}

    
    def parse_status(self, resp, ack, ident="GET_STATUS"):
        '''
        INT: Parse the response frame that looks like "SID LID STATPIL"
        Return a string
        '''

        status = { "label": "undefined", "type": "UNDEFINED" }

        for param in ack:
            if ack[param]["defval"] != "":
                continue
            else:
                # if param in resp
                if ack[param]["pos"] - 1 <= len(resp) / 2:
                    start = (ack[param]["pos"] - 1) * 2
                    end = start + 2
                    val = resp[start:end]

                    for stat in ack[param]["states"]:
                        if "exact" in ack[param]["states"][stat]:
                            if ack[param]["states"][stat]["exact"] == str(val):
                                # the serial value matces a STATPIL state
                                if stat in self.tree["statuses"]:
                                    self.log("ECU responded with actuator test state: " + self.tree["statuses"][stat]["type"])
                                    return self.tree["statuses"][stat]
                        else:
                            self.debug("DEVWARN: Unexpected MinMax in " + str(param) + "/" + str(ack[param]["pid"]) + ", state: " + str(stat))

        return status


    def stop_test(self):
        '''
        User interrupted, execute "STOP" command
        '''
        if "STOP" in self.tree["zones"]:
            if "REQUEST" in self.tree["zones"]["STOP"]:
                cmd = self.join_frame_bb(self.tree["zones"]["STOP"]["REQUEST"], error_on_blank=True)
                ack = self.tree["zones"]["STOP"]["ANSWEROK"]
                nack = self.tree["zones"]["STOP"]["ANSWERKO"]

                if not cmd:
                    # unsupported type with a blank parameter
                    self.log("stop_test: Blank parameter in command request field")
                    return {"STATUS": "IMPOSSIBLE"}
                
                resp = self.adapter.send_wait_reply(cmd)

                if not resp:
                    self.log("stop_test: no response from ECU")
                    return {"STATUS": "NOCOMMS"}
                
                elif self.diagmatch(resp,  self.join_frame_bb(nack)):
                    self.log("stop_test: ECU rejected command with code " + str(self.diagnack(resp)))
                    return { "STATUS": "ECU rejected command with code: " + str(self.diagnack(resp)) }

                elif self.diagmatch(resp,  self.join_frame_bb(ack)):
                    self.log("stop_test: ECU replied " + str(self.parse_status(resp, ack)))
                    return { "STATUS": "OK", "PAYLOAD": self.parse_status(resp, ack) } 

            else:
                self.log("Failed to stop the actuator test because there was no command")
                return { "STATUS": "Cannot stop the actuator test. Disconnect the cable to do so manually" }
        else:
            self.log("Test " + str(self.active_test) + " missing a STOP command")
            return { "STATUS": "IMPOSSIBLE"}

        
