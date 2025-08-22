from .diag import diag
from .diag_bramble import diag_bramble
import serial, sys, re, serial.tools.list_ports, traceback, ctypes, time

bluetooth_available = False

try:
    import bluetooth
    bluetooth_available = True
except:
    bluetooth_available = False

class diag_adapter(diag):
    myref = "BASE"
    tla = "SER"

    adapter_types = ["arduino-psa-diag", "ELM327", "EvolutionXS"]
    default_type = adapter_types[2]
    com_port = ""
    com_ports = {}      # raw port list
    com_devices = {}    # pretty names
    connected = False

    session_active = False
    session_active_frame = {}
    session_active_timer = 0
    session_active_threshold = 4000

    adapter_log = []
    adapter_log_callback = None
    
    ka_active = False

    _port = ""
    
    rx_h = 652
    rx_m = 652
    tx_h = 752

    ka_thread = None
    ka_cmd = "7E"
    ka_interval = 2000

    adapter_busy = False

    last_cmd_millis = 0

    BYTEARR = 1
    RAW = 2

    final_cmd = None
    ser = None

    def __init__(self, bmb):
        self.bb : diag_bramble = bmb


    def get_com_ports(self):
        return self.com_ports, self.com_devices

    
    def log_com(self, data):
        '''
        Keep a log of all commands going out and coming in
        '''
        self.log("COM :: " + str(data))
        self.adapter_log.append(data)
        if self.adapter_log_callback is not None:
            self.adapter_log_callback()

    
    def set_com_port(self, com):
        pass

    def get_com_port(self):
        return self._port

    def create_inst(self, ada=None):
        self.log("Create adapter instance")
        if ada == self.adapter_types[0] or ada == None:
            self.log("Adapter type: BBL")
            return bbl_adap(self.bb)
        elif ada == self.adapter_types[1]:
            self.log("Adapter type: ELM")
            return elm327(self.bb)
        elif ada == self.adapter_types[2]:
            self.log("Adapter type: EVXS")
            return actia_xs(self.bb)
        else:
            self.log("Adapter type: None")
            return False

    # Require overrides
    def send(self, bstr):
        pass

    def read(self):
        return ""

    def connect(self):
        return False

    def init_ecu(self, frame, *largs):
        '''
        Configure the adapter
        Check and send DIAGINIT
        Start keep-alives
        '''

        # if already connected
        if self.session_active:
            if self.session_active_frame["ECUVEID"] == frame["ECUVEID"]:
                if self.millis() - self.session_active_timer < self.session_active_threshold or self.ka_active:             
                    return True
            else:
                #self.ka_end()
                self.fini_ecu()
                self.session_active = False

        # body: DIAG/RECO/DEFAULT
        # engines: SC  | SP
        if "CMDS" in frame:
            if "DIAG" in frame["CMDS"]:
                cmds = frame["CMDS"]["DIAG"]
            elif "SC" in frame["CMDS"]:
                cmds = frame["CMDS"]["SC"]
            else:
                self.log("Unknown DIAGINIT command for ECU " + str(frame["ECUVEID"]) + ". Devs can fix this manually")
                return False
        else:
            return False

        # Also need to set TP 

        if "REQUEST" in cmds:
            try:
                if not self.configure(frame["TX_H"], frame["RX_H"], frame["BUS"], frame["PROTOCOL"], target = frame["TARGET_CODE"], dialog_type = frame["DIALOG_TYPE"]):
                    return False
            except:
                self.log("Missing some or all ECU header descriptors, the frame tree is invalid or outdated.")
                self.log(frame)
                return False

            resp = self.send_wait_reply(cmds["REQUEST"])
            if not resp:
                self.log("ECU did not respond to DIAGINIT: " + str(frame["ECUVEID"]))
                return False
            if self.diagmatch(resp, cmds["ANSWEROK"]):
                self.log("DIAGINIT to ECU " + str(frame["ECUVEID"]))
                #self.ka_start()
                self.session_active_frame = frame
                self.session_active = True
                return True
            else:
                self.log("ECU " + str(frame["ECUVEID"]) + " refused init with " + str(resp))
                return False
        else:
            self.log("No diagnostic initialisation available for ECU: " + str(frame["ECUVEID"]))
            self.log(str(cmds))
            return False
    

    def fini_ecu(self, *largs):
        '''
        End an active diagnostic session
        '''
        if not self.session_active:
            return False
        
        #self.ka_end()
        
        if "fini_rq" in self.session_active_frame["CMDS"]:
            resp = self.send_wait_reply(self.session_active_frame["CMDS"]["fini_rq"])
            if not resp:
                self.log("NOTICE: ECU didn't respond to FINDIAG")
            elif resp == self.session_active_frame["CMDS"]["fini_ko"]:
                self.log("NOTICE: ECU refused to end the session")
            elif resp == self.session_active_frame["CMDS"]["fini_ok"]:
                self.log("FINDIAG with ECU " + str(self.session_active_frame["ECUVEID"]))
        
        self.session_active = False
        
        return


    def ka_start(self):
        '''
        DO NOT USE
        '''
        self.ka_active = True
        if self.ka_thread == None:
            #self.ka_thread = threading.Thread(target=self.ka_thread_fn, daemon=True)
            #self.ka_thread.start()
            self.log("Keep-alive thread intialised")
            return True

        if not self.ka_thread.is_alive():
                # we haven't finished the previous job
                self.log("Keep alive thread crashed. Restarting")
                #self.ka_thread = threading.Thread(target=self.ka_thread_fn, daemon=True)
                #self.ka_thread.start()

    def ka_end(self):
        '''
        Check if the the thread is still alive, then pause it
        '''
        #self.ka_start()
        self.ka_active = False

    
    def ka_thread_fn(self):
        '''
        Loop forever, send KA every ka_interval ms
        '''
        return
        while self.ka_active:
            if self.millis() - self.last_cmd_millis > self.ka_interval / 1000:
                while self.adapter_busy:
                    # elevator music
                    pass
                self.adapter_busy = True
                self.send_wait_reply_int(self.ka_cmd, 1000)
                self.adapter_busy = False
                self.log("KA - " + str(self.ka_cmd))
                self.last_cmd_millis = self.millis()


    def configure(self, tx_h="652", rx_h="752", bus="DIAG", protocol="DIAGONCAN", target=None, dialog_type="0"):
        '''
        Reinitialise the adapter
        '''
        self.log("Adapter incorrectly configured")
        return False


    def send_specify_reply(self, send, expect, nack=None, patience=1000):
        '''
        Send a command, and wait up to "patience" (ms) to receive
        a command described in "expect", or false
        '''

        if not self.send(send):
            return False
        else:
            self.last_cmd = send
        
        expect_len = len(expect)
        start = self.millis()
        cnt = 0

        while True:
            if (self.millis() - start) > patience:
                break
            if self.ser.in_waiting > 0:
                resp = self.read()
                if len(resp) >= 2:
                    if nack != None:
                        if resp[:2] == nack:
                            self.send(send)
                            cnt = cnt + 1
                            continue
                    elif len(resp) >= expect_len:
                        if resp[:expect_len] == expect:
                            return resp
        
        return ""

    
    def send_wait_reply_int(self, send, patience):
        '''
        INT: Use send_wait_reply instead
        '''
        return ""


    def send_wait_reply(self, send, patience=1500, fmt="raw"):
        '''
        Send a specific command, and wait up to patience
        to receive a response
        Calls adapter-specific function
        '''
        send_split = re.findall('.{1,2}', send)
        for bobj in send_split:
            try:
                clean = int(bobj, 16)
            except:
                self.log("Error parsing string " + str(bobj) + " as a hex integer, this input is not valid")
                return False
            
        self.log_com(send)
        resp = self.send_wait_reply_int(send,patience)
        self.log_com(resp)
        
        if fmt == self.BYTEARR:
            return re.findall('.{1,2}', resp)
        else:
            return resp


class elm327(diag_adapter):
    '''
    Support bluetooth based ELM327 adapters
    Unless a custom cable is used (see elm_with_switch) only I/S bus available
    '''
    myref = "ELM327 BT standard"
    _port = 1
    _tout = 0.5
    _encd = "utf-8"
    _conn = False
    _obus = "IS"
    _addr = ""
    _ser  = None
    on_disconnect = None    # callback
    _devicesx = {}

    # reset, and configure the ELM. Assume protocol 6 (can change it later)
    _init = ["ATZ", "ATWS", "ATD", "ATE0", "ATL0", "ATH0",
             "ATS0", "ATAL", "ATV0", "ATSP6" ] #"ATCAF1", "ATCFC1"]


    def set_com_port(self, addr):
        if addr in self._devicesx:
            self._addr = self._devicesx[addr]
        else:
            self.log("Invalid bluetooth device " + str(addr))


    def disconnect(self):
        '''
        Close the socket connection cleanly and call the UI callback
        if set
        '''
        self.ser.close()
        self._conn = False
        if self.on_disconnect != None:
            self.on_disconnect()
        return True


    def get_com_ports(self):
        '''
        Get a list of available bluetooth devices
        '''
        self.com_ports = {}
        self.com_devices = {}

        if not bluetooth_available:
            self.log("The Python bluetooth library is not available")
            return self.com_ports, self.com_devices

        try:
            self.log("Scanning for bluetooth devices")
            devices = bluetooth.discover_devices(lookup_names=True,duration=3)
            self.log("Found " + str(len(devices)) + " devices")
            for addr,name in devices:
                self.com_ports[name] = addr
                self.com_devices[addr] = name
                self.log("Adapter " + str(name) + " with address " + str(addr))
        except:
            self.log("Failed to retrieve adapters list")
            self.log(traceback.format_exc())

        return self.com_ports, self.com_devices


    def send(self, bstr):
        '''
        Send a string (after converting it to bytes)
        Use \r as required by ELM specification
        '''
        self.ser.send(str.encode(bstr) + b'\r')


    def read(self, timeout=5000):
        '''
        Wait in a read loop until we get ELM prompt character
        Give up after timeout
        '''
        start = self.millis()
        msg = ""
        x = self.ser.recv(1).decode("utf-8").replace("\r","|")
        
        while x != '>':
            msg = str(msg) + str(x)
            x = self.ser.recv(1).decode("utf-8").replace("\r","|")
            if timeout != None:
                if timeout < self.millis() - start:
                    self.log("Bluetooth read timed out")
                    break
        msg = str(msg) + str(x)

        '''
        Now parse the response down to the raw message
        02E|0:5716C402C403|1:F40AF415A4A7F4|2:BAB4BCA4C0A4C1|3:F4C3A4C5A4C7A4|4:C8A4C9A4CA9562|5:F5FFF015F019F0|6:2FC98B7173||>
        '''
        self.log("ELM DEBUG: received data: " + str(msg))
        total_payload = ""
        
        try:

            parts = msg.split("|")
            for part in parts:
                if part == "" or part == ">":
                    continue
                else:
                    index, payload = part.split(":")
                    total_payload = total_payload + payload
        except:
            traceback.format_exc()
            return ""
        
        self.log("ELM DEBUG: return " + total_payload)
        return total_payload
    
    
    def configure(self, tx_h="752", rx_h="652", bus="DIAG", alert=None):
        '''
        Initialise ELM327 per ECU
        '''
        if not self._conn:
            if not self.connect():
                self.log("Adapter has not been correctly initialised and manual attempt failed")
                return False

        if tx_h == "" or rx_h == "" or bus == "":
            self.log("Empty header fields supplied, this configuration is not valid: " + str(tx_h) + ":" + str(rx_h) + " / " + str(bus))
            return False

        if bus != "IS":
            self.log("Selected adapter can not support the protocol " + str(bus) + " yet")
            return False
        
        return self.set_headers(tx_h, rx_h)

    
    def set_headers(self, tx_h, rx_h, bus = None):
        '''
        INTERNAL ONLY - DO NOT CALL DIRECTLY!
        Use configure() instead
        '''

        '''
        FUTURE: K-line support (4 or 5)

        0	Automatic protocol detection
        1	SAE J1850 PWM (41.6 kbaud)
        2	SAE J1850 VPW (10.4 kbaud)
        3	ISO 9141-2 (5 baud init, 10.4 kbaud)
        4	ISO 14230-4 KWP (5 baud init, 10.4 kbaud)
        5	ISO 14230-4 KWP (fast init, 10.4 kbaud)
        6	ISO 15765-4 CAN (11 bit ID, 500 kbaud)
        7	ISO 15765-4 CAN (29 bit ID, 500 kbaud)
        8	ISO 15765-4 CAN (11 bit ID, 250 kbaud) - used mainly on utility vehicles and Volvo
        9	ISO 15765-4 CAN (29 bit ID, 250 kbaud) - used mainly on utility vehicles and Volvo
        '''

        resp = self.send_wait_reply("ATSH" + tx_h)
        if resp != "OK||>":
            return False
        resp = self.send_wait_reply("ATCRA" + rx_h) 
        if resp != "OK||>":
            return False
        resp = self.send_wait_reply("ATFCSH" + tx_h)
        if resp != "OK||>":
            return False
        resp = self.send_wait_reply("ATFCSD300000")
        resp = self.send_wait_reply("ATFCSM1")

        self.log("ELM adapter configured correctly")

        return True


    def send_wait_reply(self, send, patience=1500):
        '''
        Send a specific command, and wait to read the response
        character before returning
        '''
        self.log("ELM DEBUG: sending " + str(send))
        self.send(send)
        resp = self.read(patience)

        return resp


    def connect(self):
        '''
        Initialise the bluetooth connection
        '''
        if self._conn:
            self.log(str(self.myref) + " already connected on " + str(self._port))
            return True

        if self._addr == "":
            self.log("No bluetooth address was selected yet")
            return False
        
        if not bluetooth_available:
            self.log("The python bluetooth library is missing")
            return False
        
        self._conn = False
        self.ser = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
        self.ser.connect((self._addr, self._port))
        self.ser.settimeout(5.0)
        print(self.ser.getpeername())
        if not self.ser:
                self.log("ERROR")
                return False
        self.log("Connection established, sending initialisation")
        for cmd in self._init:
            resp = self.send_wait_reply(cmd)
            self.log("ELM DEBUG: " + str(cmd) + " response: " + str(resp))
            
        self.log("Serial initialised: " + str(self.myref) + " on " + str(self._port))
        self._conn = True
        return True
        #except:
        #    self.log("Failed to create bluetooth connection to " + str(self._addr))
        #    self.log(str(sys.exc_info()[0]) + " at line " + str(sys.exc_info()[2]))
        #    return False 
       

class bbl_adap(diag_adapter):
    myref = "arduino-psa-diag"
    _vers = "1.0"
    _mode = "M"
    _port = '/dev/ttyACM3'
    _baud = 115200
    _tout = 0.3
    _encd = "utf-8"
    _conn = False

    connected = False

    last_cmd = ""

    ser = None

    def get_com_ports(self):
        lis = serial.tools.list_ports.comports()
        self.com_ports = {}
        self.com_devices = {}
        for item in lis:
            self.com_ports[item[0]] = str(item[1])
            self.com_devices[item[1]] = str(item[0])
        return self.com_ports, self.com_devices


    def set_com_port(self, addr):
        if addr in self.com_ports:
            self._port = addr
        else:
            self.log("Tried to set invalid COM port: " + str(addr))


    def connect(self):
        try:
            if self._conn:
                self.log(str(self.myref) + " already connected on " + str(self._port))
                return True

            if self._port == "":
                self.log("No adapter port has been selected yet")
                return False

            self._conn = False
            self.ser = serial.Serial(self._port, self._baud, timeout=self._tout)
            self.ser.flushInput()
            if not self.ser:
                return False
            self.log("Serial initialised: " + str(self.myref) + " on " + str(self._port))
            self._conn = True
            return True
        except:
            self.log(str(sys.exc_info()[0]))
            return False 


    def send(self, bstr):
        '''
        Implement sending a byte string to the adapter
        '''
        try:
            if not self._conn:
                return False

            # attemptfix: clear any waiting input
            if self.ser.in_waiting > 0:
                c = self.ser.readline()
                self.log("Cleared junk from adapter:" + str(c))

            self.ser.write(bytes(bstr, encoding=self._encd))
            self.ser.write(b"\n")
            self.debug("Adapter write: " + str(bstr))

            self.last_cmd_millis = self.millis()

            return True
        except:
            self.log("Unexpected write error: " + str(bstr))
            self.log(str(sys.exc_info()[0]))
            return False


    def read(self):
        '''
        Implement reading a byte(s) from the adapter
        '''
        try:
            output = ""
            line = self.ser.readline()
            start = self.millis()

            self.log("Reading...")
            
            while not line.endswith(b'\n'):
                line = line + self.ser.readline()
                self.log(line)
                #if line == b'':
                #    return ""
                if self.millis() - start > 5000:
                    # fix hanging on broken read
                    return ""
            
            output = line.strip().decode(self._encd).strip("\x02").strip("\x03")
            self.debug("Adapter read: " + str(output))

            if len(output) >= 2:
                if output[:2] == "S_":
                    output = output[2:]
            
            if output == "7F0000":
                self.log("This is the wrong software version for this adapter.")
                self.log("Adapter reported malformed input. Last input was: " + str(self.last_cmd))
                return ""

            if len(output) >= 4:
                if output[3] == ":":
                    header = output[:3]
                    if header == self.rx_h or header == self.rx_m:
                        return output[4:]
                    # if its not our header, return full byte string
                    # in case something expects it

            return output 

        except:
            self.log("Unexpected read error: " + str(output))
            self.log(str(sys.exc_info()[0]))
            return ""


    def configure(self, tx_h="652", rx_h="752", bus="DIAG", protocol="DIAGONCAN", target=None, dialog_type="0"):
        '''
        Set up the adapter for the required bus/headers
        '''

        if not self._conn:
            if not self.connect():
                self.log("Adapter has not been correctly initialised and manual attempt failed")
                return False

        if tx_h == "" or rx_h == "" or bus == "":
            self.log("Empty header fields supplied, this configuration is not valid: " + str(tx_h) + ":" + str(rx_h) + " / " + str(bus))
            return False

        if protocol != "DIAGONCAN":
            self.log("Error, this adapter does not support protocol other than DIAGONCAN")
            return False

        self.debug("Adapter configuring on " + str(tx_h) + ":" + str(rx_h) + " / " + str(bus))
        self.log("This adapter doesn't know or care which bus it is connected to")
        
        # Now set headers
        r_q = ">" + str(tx_h) + ":" + str(rx_h)
        self.send(r_q)
        resp = self.read()
        if resp == "":
            self.log("Adapter did not respond to a request to set headers")
            return False
        else:
            if resp == "OK":
                self.rx_h = rx_h
                self.tx_h = tx_h
                self.debug("Adapter headers configured correctly")
                return True
            else:
                self.log("Adapter refused request to set headers")
                return False


    def send_wait_reply_int(self, send, patience):
        '''
        Adapter specific implementation
        '''
        resp = ""
        start = self.millis()
        attempt = 1

        if not self.send(send):
            return resp
        else:
            self.last_cmd = send
        while self.ser.in_waiting <= 0:
            if self.millis() - start > patience:
                return resp
            elif self.millis() - start > start + ((patience / 3) * attempt):
                if attempt < 3:
                    if not self.send(send):
                        return resp
                attempt = attempt + 1
        resp = self.read()
        return resp


class raw_can_serial(diag_adapter):
    '''
    '''
    pass
    

class actia_xs(diag_adapter):
    '''
    Support LEXIA3/XS Evolution VCI Interface
    (Windows platforms only)

    Supports all protocols supported by Lexia in theory, but may not be implemented
    or activated yet
    '''

    writeReadTimeout = 1000  # ms
    MSG_BUFFER = 2048   # bytes, max size of buffer
    currEcuDesc = None

    # COM line numbering (see docs for full table)
    LINE_CAN_DIAG = 17
    LINE_CAN_IS = 18
    LINE_CAN_PSA2000 = 0

    LINE_CAN_FIAT_LS6 = 47
    LINE_CAN_FIAT_LS3 = 48
    LINE_CAN_MCV_3 = 57
    LINE_CAN_MCV_6 = 58

    myref = "ACTIA PSA XS Evolution"
    vci = None
    _conn = False

    KWP2000_PSA = 1
    PSA2 = 2        # 9600 bps
    DIAG_ON_CAN = 3
    KWP2000_FIAT = 6
    KWP_ON_CAN_FIAT = 7
    KWP2000_TOYOTA = 4
    UDS_PSA = 11
    UDS_MCV_HI = 9
    UDS_MCV_LO = 10

    # protocol descriptors
    # 01 = KWP, 00/1 = Fast/Slow, XXXX W5/Tidle (1000ms), XXXX P3Min, XXXX P2Max, XXXX P4Min
    pd_KWP2000PSA = "01 00" # 03 E8 03 E8 00 32 00 0F"
    pd_PSA2 = "02"
    # 03 followed by maximum wait time (minimum working tested is 10E8)
    pd_DIAG_ON_CAN = "03 10 E8"
    pd_UDS_PSA = ""
    # b2 => 00 = fast, 01 = Slow
    # 0x04 = Toyota, 0x05 ISO9141-2
    pd_KWP_2000_FIAT = "06 00"
    pd_KWP_ON_CAN_FIAT = "07"
    # b2/3 = max time, b4/5 min time before new tool request XX XX
    pd_KWP_ON_CAN_MITSUBISHI = "08 XXXX XXXX"
    pd_UDS_MCV_HIGH = "09 10 E8 10 E8"      # untested estimates
    pd_UDS_MCV_LOW = "0A 10 E8 10 E8"
    pd_UDS_PSA = "0B"
    pd_UDS_PSA_FULL = "11"
    pd_LIN_21 = "0C"


    klines_psa = { "K8": 2, "K2": 6, "Kiso": 7, "K7": 9, "K9": 10, "K3": 11, "K4": 12, "K6": 13, "K5": 14 }
    klines_fiat = { 1 : 31, 3 : 33, 7 : 37, 8 : 38, 9 : 39, 11 : 41, 12 : 42, 13 : 43 }


    def __init__(self, bmb):
        try:
            self.bb = bmb
            self.vci = ctypes.CDLL("C:\AWRoot\drv\VCIAccess.dll")
        except:
            self.log("The DLL could not be loaded. Check it is correctly located in C:/AWRoot/drv/VCIAccess.dll or check platform requirements")


    def log(self,x):
        self.bb.logger("[VCI] " + str(x))
        
    
    def statusToStr(self, code):
        
        if code == 0:
            return "OPERATION SUCCEEDED"
        elif code == -1:
            return "HARDWARE ERROR"
        elif code == -2:
            return "SOFTWARE ERROR"
        elif code == -3:
            return "MISSING DRIVER RESOURCE"
        elif code == -4:
            return "CABLE IS UNPLUGGED"
        elif code == -5:
            return "NO RESPONSE FROM ECU"
        elif code == -6:
            return "INVALID COMMUNICATION LINE"
        elif code == -7:
            return "INVALID PROTOCOL DESCRIPTOR"
        elif code == -8:
            return "INVALID ECU DESCRIPTOR"
        elif code == -9:
            return "INVALID FUNCTION ORDER"
        elif code == -10:
            return "RESPONSE BUFFER OVERFLOW"
        elif code == -12:
            return "VCI BUSY"
        elif code < 0:
            return "UNSPECIFIED ERROR" + str(code)
        else:
            return str(code)


    def connect(self):
        '''
        Wraps: int openSession()
        '''

        if self.vci is None:
            return False

        vciOpenSession = self.vci["_openSession"]
        vciOpenSession.restype = ctypes.c_int

        result = vciOpenSession()

        if result == 0 or result == 1:
            self.log("Connected to " + str(self.myref) + " successfully")
        else:
            self.log("VCI returned error code " + self.statusToStr(result))

        vciGetVersion = self.vci["_getVersion"]
        vciGetVersion.restype = ctypes.c_int

        result = vciGetVersion()

        self.log("VCI API Version: " + self.statusToStr(result))
        
        vciGetFirmwareVersion = self.vci["_getFirmwareVersion"]
        vciGetFirmwareVersion.restype = ctypes.c_int
        vciGetFirmwareVersion.argtypes = [ctypes.c_char_p, ctypes.c_int]
        outputBuffer = ctypes.create_string_buffer(40)
        result = vciGetFirmwareVersion(outputBuffer, ctypes.c_int(len(outputBuffer)))
       
        if result > 0:
            out = ""
            for i in range(0, result):
                out = out + chr(outputBuffer.raw[i])
            self.log("VCI Firmware Version: " + str(out))
        else:
            self.log("VCI Firmware Version not available")

        if result >= 0:
            self._conn = True
            return True
        else:
            self._conn = False
            return False
         

    def disconnect(self):
        '''
        int closeSession()
        '''
        if self._conn:
            vciCloseSession = self.vci["_closeSession"]
            vciCloseSession.restype = ctypes.c_int
            result = vciCloseSession()
            self._conn = False

            if result >= 0:
                self.log("VCI Disconnected")
                return True
            else:
                self.log("Error during VCI disconnection")
                return False
        else:
            return True


    def _changeComLine(self, num_line):
        '''
        Wraps: int changeComLine(int numline)

        Change which pins are used by the VCI to connect to the ECU
        '''
        vciChangeComLine = self.vci["_changeComLine"]
        vciChangeComLine.restype = ctypes.c_int
        vciChangeComLine.argtypes = [ ctypes.c_int ]
        result = vciChangeComLine(num_line)

        self.log("_changeComLine: (" + str(num_line) + ") " + self.statusToStr(result)) 
        
        if result >= 0:
            return True
        else:
            return False


    def _bindProtocol(self, protocol):
        '''
        Wraps: int bindProtocol(unsigned char* protocolDescriptor, int descriptorLength)

        Set the VCI to a specific protocol
        '''
        protocolDescriptor, pDlen = self.protocolToProtocolDescriptor(protocol)
        vciBindProtocol = self.vci["_bindProtocol"]
        vciBindProtocol.restype = ctypes.c_int
        vciBindProtocol.argtypes = [ ctypes.c_char_p, ctypes.c_int ]
        result = vciBindProtocol(protocolDescriptor, pDlen)
        self.log("_bindProtocol: " + self.statusToStr(result))

        if result >= 0:
            return True
        else:
            return False


    def _performInit(self, ecudescriptor):
        '''
        Wraps: int performInit(unsigned char* ecuDescriptor, int ecuDescriptorLength
                               unsigned char* outBuffer, int outBufferLen)
        
        Initialise a given ECU (PSA2, KWP2000 or ISO9141-2 only). Not used for KWP/D oC
        '''
        ecuDescriptor, ecuDescriptorLen = ecudescriptor

        vciPerformInit = self.vci["_performInit"]
        vciPerformInit.restype = ctypes.c_int
        outBuffer = ctypes.create_string_buffer(255)
        vciPerformInit.argtypes = [ ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int ]
        result = vciPerformInit(ecuDescriptor, ecuDescriptorLen, outBuffer, self.MSG_BUFFER)

        if result > 0:
            out = ""
            for i in range(0, result):
                out = out + hex(outBuffer.raw[i]) + " "

            try:
                out = out.replace("0x", "").upper()
            except:
                pass

            self.log("_performInit: " + str(out))

        else:
            self.log("_performInit did not get a response")

        if result >= 0:
            time.sleep(0.5)
            return True
        else:
            return False
    

    def _writeAndRead(self, ecudescriptor, inBuffer, timeOut = None):
        '''
        Wraps: int writeAndRead(unsigned char* ecuDescriptor, int ecuDescriptorLength
                                unsigned char* inBuffer, int inBufferLen,
                                unsgined char* outBuffer, int outBufferLen,
                                int timeOut)

        Timeout is -1 for "forever", otherwise in ms

        Send a message to a given ECU and return the response
        '''
        if timeOut is None:
            timeOut = self.writeReadTimeout

        #time.sleep(0.5)

        ecuDesc, ecuDescLen = ecudescriptor
        inBuffer, inl = inBuffer

        vciWriteAndRead = self.vci["_writeAndRead"]
        vciWriteAndRead.restype = ctypes.c_int
        vciWriteAndRead.argtypes = [ ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_int ]
        outputBuffer = ctypes.create_string_buffer(self.MSG_BUFFER)
        result = vciWriteAndRead(ecuDesc, ecuDescLen, inBuffer, inl, outputBuffer, self.MSG_BUFFER, timeOut)
             
        if result > 0:
            out = ""
            for i in range(0, result):
                out = out + hex(outputBuffer.raw[i]) + " "

            try:
                out = out.replace("0x", "").upper()
            except:
                pass

            self.log("_writeAndRead: (" + str(result) + ")") #  + str(out))
        else:
            self.log("_writeAndRead: " + self.statusToStr(result))
            return False

        return outputBuffer.raw[:result]


    def protocolToProtocolDescriptor(self, protocol = None):
        '''
        Fetch the protocol descriptor for the protocol
        '''

        if protocol == self.DIAG_ON_CAN or protocol == None:
            return self.bytesEncode(self.pd_DIAG_ON_CAN)

        elif protocol == self.KWP_ON_CAN_FIAT:
            return self.bytesEncode(self.pd_KWP_ON_CAN_FIAT)

        elif protocol == self.KWP2000_PSA:
            return self.bytesEncode(self.pd_KWP2000PSA)

        else:
            self.log("Protocol " + str(protocol) + " is not implemented yet")

    
    def bytesEncode(self, pd, divisor=" "):
        '''
        Convert string format to descriptor
        '''
        if divisor == None:
            byt = re.findall('.{1,2}', pd)
        else:
            byt = pd.split(" ")
        out = []
        for by in byt:
            out.append(int(by, 16))
        #'char_array = ctypes.c_char * len(sst)
        return ctypes.create_string_buffer(bytes(out),len(out)), len(out)


    def ecuToEcuDescriptor(self, tx_h=None, rx_h=None, protocol=3, octet=None, kwp_id=None, dialog_type="0"):
        '''
        Calculate ECU descriptor according to protocol and headers
        tx_h - CAN EMIT ID
        rx_h - CAN RECV ID
        protocol - according to Evolution data above
        octet - for K line
        kwp_id - FIAT_CAN: ecu target code, KWP: id
        dialog_type - FIAT: dialog type
        '''

        if protocol == self.DIAG_ON_CAN:
            if len(tx_h) == 3 and len(rx_h) == 3:
                tx_h = "0" + tx_h
                rx_h = "0" + rx_h
                return self.strby_to_char(rx_h + tx_h)
            else:
                self.log("Invalid ECU headers provided: DIAG_ON_CAN")
        
        elif protocol == self.PSA2:
            return self.strby_to_char(kwp_id)

        elif protocol == self.KWP2000_PSA:
            return self.strby_to_char(kwp_id)

        elif protocol == self.KWP2000_TOYOTA:
            return self.strby_to_char(kwp_id)
        
        elif protocol == self.KWP2000_FIAT:
            return self.strby_to_char(kwp_id)

        elif protocol == self.KWP_ON_CAN_FIAT:
            if len(kwp_id) == 1:
                kwp_id = "0" + kwp_id
				
            if len(tx_h) == 3 and len(rx_h) == 3 and len(kwp_id) == 2:
                tx_h = "0" + tx_h
                rx_h = "0" + rx_h
                self.log("Generate Fiat ECU headers with " + str(rx_h + tx_h + kwp_id + "00"))
                return self.strby_to_char(rx_h + tx_h + kwp_id + "00")
            else:
                self.log("Invalid ECU headers provided: FIAT")  
        

    def _writeAndReadMultipleFrames(self, ecudescriptor, inBuffer, responses=1, timeOut=None):
        '''
        For KWP2000 and TOYOTA protcols ONLY
        '''
        if timeOut is None:
            timeOut = self.writeReadTimeout

        ecuDesc, ecuDescLen = ecudescriptor
        inBuffer, inl = inBuffer
        vciWriteAndReadMF = self.vci["_writeAndReadMultipleFrames"]
        vciWriteAndReadMF.restype = ctypes.c_int
        vciWriteAndReadMF.argtypes = [ ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_int ]
        outputBuffer = ctypes.create_string_buffer(self.MSG_BUFFER)
        result = vciWriteAndReadMF(ecuDesc, ecuDescLen, inBuffer, inl, responses, outputBuffer, self.MSG_BUFFER, timeOut)
        
        if result > 0:
            out = ""
            for i in range(0, result):
                out = out + hex(outputBuffer.raw[i]) + " "
            self.log("_writeAndReadMultipleFrames: (" + str(result) + ") " + str(out))
        else:
            self.log("_writeAndReadMultipleFrames: " + self.statusToStr(result))

        return True


    def strby_to_char(self, inp):
        '''
        Convert string representation of bytes to chars
        '''
        bys = re.findall('.{1,2}', inp)
        
        return self.bytesEncode(" ".join(bys))


    def _getAnalogicData(self, idx):
        '''
        Return analog readings from the VCI
        '''
        c_float_p = ctypes.POINTER(ctypes.c_float)
        vciGetAnalogicData = self.vci["_getAnalogicData"]
        vciGetAnalogicData.restype = ctypes.c_int
        vciGetAnalogicData.argtypes = [ ctypes.c_int, c_float_p ]
        data1 = ctypes.c_float()
        result = vciGetAnalogicData(idx, ctypes.byref(data1))

        if result >= 0:
            self.log("_getAnalogicData: " + str(data1.value) + "V") 
            return data1.value
        else:
            return False
        
        
    ######  ==  BEGIN DIAGNOSTIQUE ADAPTER LAYER == ######    
        
    def configure(self, tx_h = "752", rx_h = "652", bus = "DIAG", protocol="DIAGONCAN", target=None, dialog_type="0"):
        '''
        Initialise the VCI for a new ECU session
        '''

        if not self._conn:
            if not self.connect():
                self.log("Adapter has not been correctly initialised and manual attempt failed")
                return False
        
        #if tx_h == "" or rx_h == "" or bus == "":
        #    self.log("Invalid headers supplied")
        #    return False
            
        if bus == "0":
            bus = "IS"
            protocol = "DIAGONCAN"

        elif bus == "1":
            bus = "DIAG"
            protocol = "DIAGONCAN"

        elif bus == "2":
            bus = "DIAG"
            protocol = "KWPONCAN_FIAT"

        elif bus == "3":
            bus = "IS"
            protocol = "KWPONCAN_FIAT"

        elif bus == "4":
            bus = "IS"
            protocol = "PSA2000"

        self.log(f"Try configuring with {tx_h}:{rx_h} {bus}, {protocol}, {target}, {dialog_type}")

        if protocol == "DIAGONCAN":
            if bus == "DIAG":
                self.log("Using CAN DIAG connection on 3/8")
                self.currEcuDesc = self.ecuToEcuDescriptor(tx_h, rx_h, protocol=self.DIAG_ON_CAN) 
                if not(self._changeComLine(self.LINE_CAN_DIAG) and self._bindProtocol(self.DIAG_ON_CAN)):
                    return False

            elif bus == "IS":
                self.log("Using CAN I/S connection on 6/14")
                self.currEcuDesc = self.ecuToEcuDescriptor(tx_h, rx_h, protocol=self.DIAG_ON_CAN) 
                if not(self._changeComLine(self.LINE_CAN_IS) and self._bindProtocol(self.DIAG_ON_CAN)):
                    return False
            
            else:
                self.log(f"ERROR cannot initialise adapter - unknown bus {bus} please report this")

        elif protocol == "KWPONCAN_FIAT":
            if bus == "DIAG":
                self.log("Using FIAT BCAN connection on LS6/14. It's possible you should be using LS3/8. If you have issues, please report them.")
                self.currEcuDesc = self.ecuToEcuDescriptor(tx_h, rx_h, protocol=self.KWP_ON_CAN_FIAT, kwp_id = str(target), dialog_type=dialog_type) 
                if not(self._changeComLine(self.LINE_CAN_FIAT_LS6) and self._bindProtocol(self.KWP_ON_CAN_FIAT)):
                    return False
            
            elif bus == "IS":
                self.log("Using FIAT BCAN connection on LS3/8")
                self.currEcuDesc = self.ecuToEcuDescriptor(tx_h, rx_h, protocol=self.KWP_ON_CAN_FIAT, kwp_id = str(target), dialog_type=dialog_type) 
                if not(self._changeComLine(self.LINE_CAN_FIAT_LS3) and self._bindProtocol(self.KWP_ON_CAN_FIAT)):
                    return False
            
            else:
                self.log(f"ERROR cannot initialise adapter - unknown bus {bus} please report this")

        elif protocol == "DIAGONCAN_FIAT":
            self.log("Using DIAGONCAN_FIAT is not supported yet. Please contact the developers to help add support for this type.")
            return False

        elif protocol == "DIAGONCAN_MMC":
            self.log("Using DIAGONCAN_MMC is not supported yet. Please contact the developers to help add support for this type.")
            return False

        elif protocol == "PSA2000":
            self.log("Using PSA2000 K-Line protocol")
            if target is None:
                target = 0x0D
            try:
                target = int(target)
                dialog_type = int(dialog_type)
            except:
                self.log("Couldn't interpret KWP target code or dialog_type as integer: " + str(target) + " / " + str(dialog_type))
                return False

            self.currEcuDesc = self.ecuToEcuDescriptor(protocol=self.KWP2000_PSA, kwp_id = self.to_hex(target))
            if not(self._changeComLine(int(dialog_type)) and self._bindProtocol(self.KWP2000_PSA)):
                return False  
            else:
                # TODO: do this here, or do it whenever a client application sends just 0x81 to send_wait_reply?
                if not self._performInit(self.currEcuDesc):
                    return False
                
        else:
            self.log("Invalid or unsupported bus specified")
            return False

        self.active_protocol = protocol            
        return True
        
    
    def send_wait_reply_int(self, inp, timeout = 5000):
        '''
        Wrapper to send a command to an ECU and await reply
        '''
        self.log_com(inp)

        if self.currEcuDesc is None:
            self.log("Adapter has not been configured yet")
            return False
            
        # this is a bit of a hack, because for KWP2k PSA you have to do 
        # _performInit() in order to wake the ECU (you can't just send 81 with writeAndRead)
        # performInit() sends the 81 as part of the init sequence, and if you send it subsequently you'll get an error code
        # Since a client application shouldn't be trying to call this function if performInit (and consequently configure()) failed
        # we just return the success code and don't mess with the ECU
        if self.active_protocol == "PSA2000" and inp == "81":
            rst = [ 0xC1, 0xD0, 0x8F ]
        else:
            rst = self._writeAndRead(self.currEcuDesc, self.bytesEncode(inp, None))

        if not rst:
            return ""
        else:
            out = ""
            for i in rst:
                out = out + str(self.to_hex(i))
            self.log_com(out)
            return out
