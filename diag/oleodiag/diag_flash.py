from .diag import diag
from .diag_bramble import diag_bramble
import re, threading, time

class diag_flash(diag):
    '''
    (c) 2021 Diagnostique Project. See website for licence information

    Utility toolit for reading/writing different parts of ECU flash
    Parse, write and display ULP/CAL files
    '''
    bb = None

    def __init__(self, bmb):
        self.bb : diag_bramble = bmb

    
    def line_to_bytes(self, line):
        '''
        Convert a string of bytes
        '''
        return re.findall('.{1,2}', line) 
    
    def parse_ulp_to_dict(self, fname):
        '''
        Parse the important info from a ULP to internal dictionary format
        ready for flashing
        '''
        fh = open(fname, "r")

        ulp = { "HARDWARE" : {} , "IDENT": {} }

        for line in fh:
            
            bytes = self.line_to_bytes(line)

            if bytes[0] == "S0":
                ulp["HARDWARE"]["MUX_CODE"] = bytes[4]
                # 0 - CAN, 1 - LIN, 5 - ISO5, 8 - ISO8
                ulp["HARDWARE"]["CON_LINE"] = bytes[5]
                ulp["HARDWARE"]["IBYTE_TX"] = bytes[6]
                ulp["HARDWARE"]["IBYTE_RX"] = bytes[7]
                ulp["HARDWARE"]["I_TXRX"] = bytes[8]
                ulp["HARDWARE"]["I_RXTX"] = bytes[9]
                # 81 - CAL, 82 - ULP, 92 - NEW_ULP
                ulp["HARDWARE"]["CAL_TYPE"] = bytes[10]
                ulp["HARDWARE"]["LOG_MARK"] = bytes[11]
                ulp["HARDWARE"]["KL_MGMT"] = bytes[12] + bytes[13]
            
            elif bytes[0] == "S1":
                ulp["IDENT"]["FLASH_SIG"] = bytes[4] + bytes[5]
                ulp["IDENT"]["PASS_KEY"] = bytes[6] + bytes[7]
                ulp["IDENT"]["SUPPLIER"] = bytes[8]
                ulp["IDENT"]["SYSTEM"] = bytes[9]
                ulp["IDENT"]["APPLICATION"] = bytes[10]
                ulp["IDENT"]["SOFT_VER"] = bytes[11]
                ulp["IDENT"]["SOFT_EDIT"] = bytes[12] + bytes[13]
                ulp["IDENT"]["CAL_NUM"] = bytes[14] + bytes[15] + bytes[16]
                self.log("Parsed firmware file for ECU #(96) " + str(ulp["IDENT"]["CAL_NUM"]) +  " (80)")
                self.log("UDS key for this ECU is: " + str(ulp["IDENT"]["PASS_KEY"]))
            
            elif bytes[0] == "S2":
                # ecu memory / zone data
                pass

            elif bytes[0] == "S3":
                # binary flash data
                pass


        pass
