from .diag import diag
from .diag_bramble import diag_bramble
from .diag_translations import diag_translations
from .diag_adapter import diag_adapter
import time

class diag_procedures(diag):
    tla = "PRC"

    '''
        Steps

        category: "repeat"
        step (step_id, template, label_en, label_fr, next_step, category, command_id)
        command (service, repeat, timeout, variables)
        response (response_cmd, step_id)

        CREATE TABLE IF NOT EXIST PROC (
            proc_id     INTEGER PRIMARY KEY,
            veh         INTEGER,
            ecuname     VARCHAR(64)
            label_en    VARCHAR(64)
            help_en     VARCHAR(255)

            FOREIGN KEY veh REFERENCES VEHICLE(veh_id)
        );

        CREATE TABLE IF NOT EXIST PROCSTEP (
            step_id     INTEGER PRIMARY KEY,
            proc        INTEGER,
            label_en    VARCHAR(255)
            label_fr    VARCHAR(255)
            next_step   INTEGER,
            category    INTEGER,
            command     INTEGER,
            response    INTEGER,

            FOREIGN KEY proc REFERENCES PROC(proc_id),
            FOREIGN KEY next_step REFERENCES PROCSTEP(step_id),
            FOREIGN KEY command_id REFERENCES PROCCMD(command_id)
        );

        CREATE TABLE IF NOT EXIST PROCCMD (
            command_id  INTEGER PRIMARY KEY,
            step        INTEGER,
            service     VARCHAR(64),
            repeat      INTEGER,
            timeout     INTEGER,
            variables   VARCHAR(64),

            FOREIGN KEY step REFERENCES PROCSTEP(step_id)
        );

        CREATE TABLE IF NOT EXIST PROCRESPONSE (
            response_id  INTEGER PRIMARY KEY,
            response_svc VARCHAR(64),
            step_target  INTEGER,
            step_parent  INTEGER,

            FOREIGN KEY step_parent REFERENCES PROCSTEP(step_id),
            FOREIGN KEY step_target REFERENCES PROCSTEP(step_id)
        );
            

    '''
    
    IDLE = 0
    RUNNING = 1

    NEED_INPUT = 0
    STATUS_UPDATE = 1

    category_ids = {
                "normal": 0,
                "entry": 1,
                "repeat": 2,
                "finish": 3
            }
    

    def __init__(self, trs: diag_translations, adapter : diag_adapter, bb : diag_bramble ):
        '''
        '''
        self.bb : diag_bramble          = bb
        self.adapter : diag_adapter     = adapter
        self.trs : diag_translations    = trs

        self.steps = {}
        self.active_step = 0


    def set_tree(self, ecu_header: dict = None, procedure_data: dict = None):
        '''
        
        '''

        if ecu_header is None or procedure_data is None:
            self.log("diag_procedures:set tree was supplied with empty data")
            return False
        
        self.steps = procedure_data
        self.ecu_header = ecu_header
               
        # get first step ID
        for step in self.steps:
            if self.steps[step]["category"] == self.category_ids["entry"]:
                self.active_step = step
                break

        if self.active_step == 0:
            self.log("Procedure was missing first step")
            return False
        
        else:
            return self.active_step


    def start(self, end_callback = None):

        # already running
        if self.status == self.RUNNING or end_callback == None:
            self.log("Invalid input for start procedure")
            return False

        self.status = self.RUNNING
 
        # command is now populated with all necessary values
        adapter_status = self.adapter.init_ecu(self.ecu_header)
        if not adapter_status:
            end_callback(False, "the adapter failed to initialise")
            return False
        
        end_callback(True, "succeeded", next_step=self.active_step)


    def do_step(self, step_id: int, inputs:dict = None, end_callback = None):
        '''
        this library handles steps with category:

        - normal (supply variables if needed)
        - repeat
        
        any other step must be handled by client code
        '''

        if step_id not in self.steps:
            end_callback(False, "invalid step")
            return False

        # send command step
        if self.steps[step_id]["category"] == self.category_ids["normal"]:
            command = self.steps[step_id]["command"]

            # check if we need user input
            if "variables" in self.steps[step_id]:
                if inputs == None:
                    end_callback(False, "missing input")
                    return False

                # check user supplied all necessary variables
                command_byte_index = 0
                for command_byte in command:
                    if "$" in command_byte:
                        varname = command_byte.replace("$", "")
                        if varname not in inputs:
                            end_callback(False, "missing input: " + varname)
                            return False
                        
                        vartype = self.steps[step_id]["variables"][varname]["type"]
                        varlenby = self.steps[step_id]["variables"][varname]["lenby"]

                        # just convert the number to a byte form
                        if vartype == "I":
                            try:
                                int_val = int(inputs[varname])
                            except:
                                end_callback(False, "invalid value for: " + varname)
                                return False
                            
                            command[command_byte_index] = self.to_hex(int_val, varlenby)

                        # send user input of FFFF as 0xFFFF
                        elif vartype == "R":
                            # check its a valid hex value
                            try:
                                int_check = int(inputs[varname], 16)
                            except:
                                end_callback(False, "invalid value for: " + varname)
                                return False
                            
                            # do this to ensure the padding is correct (TODO: check endianness)
                            command[command_byte_index] = self.to_hex(int_check, varlenby)

                        # for string -> ascii conversion
                        #elif vartype == "S":
                        
                        else:
                            end_callback(False, "unknown variable type for : " + varname)
                            return False    
                    
                    command_byte_index += 1

        
            command_frame = "".join(command)

            adapter_response = self.adapter.send_wait_reply(command_frame)
            if not adapter_response:
                end_callback(False, "the adapter didn't respond")
                return False
            
            self.log("Procedure response: " + str(adapter_response))
            
            # obvious error code
            if adapter_response[2:] == "7F":
                end_callback(False, "the conditions are not correct")
                return False

            # check if we got a response pointing to another step
            for step_target in self.steps[step_id]["responses"]:
                if adapter_response == "".join(self.steps[step_id]["responses"][step_target]):
                    self.log("matched response; jump to step: " + str(step_target))

                    # jump straight to a "repeat" task to check status
                    if self.steps[step_target]["category"] == "repeat":
                        self.do_step(step_target, None, end_callback)
                        return True
                    else:
                        end_callback(True, "succeeded", next_step=step_target)
                        return True
                
            # if we get here, response didn't match 
            self.log("No step for procedure response, giving up")
            end_callback(False, "unknown ECU response")
            return False


        # send repeat step
        if self.steps[step_id]["category"] == self.category_ids["repeat"]:
            
            command_frame = "".join(self.steps[step_id]["command"])
            timeout = self.steps[step_id]["timeout"]
            start = self.millis()
            repeat_interval = self.steps[step_id]["interval"]

            while self.millis() - start < timeout:
                self.log("repeat query again")

                for i in range(3):
                    adapter_response = self.adapter.send_wait_reply(command_frame)
                    if not not adapter_response:
                        break

                if not adapter_response:
                    end_callback(False, "the ECU stopped responding")
                    return False
                
                if adapter_response[2:] == "7F":
                    end_callback(False, "the ECU conditions are not correct")
                    return False
                
                # check if it's a known response
                for step_target in self.steps[step_id]["responses"]:
                    if adapter_response == "".join(self.steps[step_id]["responses"][step_target]):
                        self.log("matched response; jump to step: " + str(step_target))

                        # jump straight to a "repeat" task to check status
                        if self.steps[step_target]["category"] == "repeat":
                            self.do_step(step_target, None, end_callback)
                            return True
                        else:
                            end_callback(True, "succeeded", next_step=step_target)
                            return True 
                
                self.log("ECU response did not match criteria, continuing happily")

                # wait the allotted time (don't overload the ECU)
                time.sleep(repeat_interval / 1000)

            self.log("timed out waiting for an expected response")
            end_callback(False, "reached timeout waiting for operation to complete")
            return False
        

    def reset(self):
        '''
        clear all ecu-specific data
        '''
        self.ecu_header = {}
        self.steps = {}



