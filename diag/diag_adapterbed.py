import serial, re
import sys, time
import ctypes

from diag import diag
from diag_adapter import diag_adapter


class actia_xs(diag_adapter):
    '''
    Support LEXIA3/XS Evolution VCI Interface
    (Windows platforms only)
    '''

    writeReadTimeout = 250  # ms
    MSG_BUFFER = 2048   # bytes, max size of buffer
    currEcuDesc = None

    # COM line numbering (see docs for full table)
    LINE_CAN_DIAG = 17
    LINE_CAN_IS = 18

    LINE_CAN_FIAT_LS6 = 47
    LINE_CAN_FIAT_LS3 = 48
    LINE_CAN_MCV_3 = 57
    LINE_CAN_MCV_6 = 58

    myref = "ACTIA PSA XS Evolution"
    vci = None

    KWP2000_PSA = 1
    PSA2 = 2
    DIAG_ON_CAN = 3
    KWP2000_FIAT = 6
    KWP2000_TOYOTA = 4

    # protocol descriptors
    # 01 = KWP, 00/1 = Fast/Slow, XXXX W5/Tidle (1000ms), XXXX P3Min, XXXX P2Max, XXXX P4Min
    pd_KWP2000PSA = "01 00 03 E8 03 E8 00 32 00 0F"
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
    pd_UDS_MCV_HIGH = "09 XXXX XXXX"
    pd_UDS_MCV_LOW = "0A XXXX XXXX"


    def __init__(self):
        self.vci = ctypes.CDLL("C:\AWRoot\drv\VCIAccess.dll")

        #self.vciGetFirmwareVersion = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_char_p, ctypes.c_int)

    def log(self,x):
        print(str(x))
        
    
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
        else:
            return "UNSPECIFIED ERROR" + str(code)

    def connect(self):
        '''
        Wraps: int openSession()
        '''
        vciOpenSession = self.vci["_openSession"]
        vciOpenSession.restype = ctypes.c_int

        result = vciOpenSession()

        if result == 0 or result == 1:
            self.log("Connected to " + str(self.myref) + " successfully")
        else:
            self.log("VCI returned error code " + str(result))

        vciGetVersion = self.vci["_getVersion"]
        vciGetVersion.restype = ctypes.c_int

        result = vciGetVersion()

        self.log("VCI API Version: " + str(result))
        
        vciGetFirmwareVersion = self.vci["_getFirmwareVersion"]
        vciGetFirmwareVersion.restype = ctypes.c_int
        vciGetFirmwareVersion.argtypes = [ctypes.c_char_p, ctypes.c_int]
        outputBuffer = ctypes.create_string_buffer(40)
        result = vciGetFirmwareVersion(outputBuffer, ctypes.c_int(len(outputBuffer)))

        self.log("VCI Firmware Version: " + str(result))

        if result >= 0:
            return True
        else:
            return False
         

    def disconnect(self):
        '''
        int closeSession()
        '''
        vciCloseSession = self.vci["_closeSession"]
        vciCloseSession.restype = ctypes.c_int
        result = vciCloseSession()
        return result


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
        ecuDescriptor = ecudescriptor

        vciPerformInit = self.vci["_performInit"]
        vciPerformInit.restype = ctypes.c_int
        outBuffer = ctypes.create_string_buffer(255)
        vciPerformInit.argtypes = [ ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int ]
        result = vciPerformInit(ecuDescriptor, len(ecuDescriptor), outBuffer, len(outBuffer))
        self.log("_performInit: " + self.statusToStr(result))

        return outBuffer
    

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
            #self.log("_writeAndRead: (" + str(result) + ")") # + str(out))
        else:
            #self.log("_writeAndRead: " + self.statusToStr(result))
            return False

        return outputBuffer.raw[:result]


    def protocolToProtocolDescriptor(self, protocol = None):
        '''
        Fetch the protocol descriptor for the protocol
        '''

        if protocol == self.DIAG_ON_CAN or protocol == None:
            return self.bytesEncode(self.pd_DIAG_ON_CAN)
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


    def ecuToEcuDescriptor(self, tx_h=None, rx_h=None, protocol=3, octet=None, kwp_id=None):
        '''
        Calculate ECU descriptor according to protocol and headers
        '''
        if protocol == self.DIAG_ON_CAN:
            if len(tx_h) == 3 and len(rx_h) == 3:
                tx_h = "0" + tx_h
                rx_h = "0" + rx_h
                return self.strby_to_char(rx_h + tx_h)
            else:
                self.log("Invalid ECU headers provided")
        
        elif protocol == self.PSA2:
            return self.strby_to_char(octet)

        elif protocol == self.KWP2000_PSA:
            return self.strby_to_char(kwp_id)

        elif protocol == self.KWP2000_TOYOTA:
            return self.strby_to_char(kwp_id)
        
        elif protocol == self.KWP2000_FIAT:
            return self.strby_to_char(kwp_id)
        

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

        self.log("_getAnalogicData: " + str(data1.value) + "V") 

        return data1.value
        
        
    ######  ==  BEGIN DIAGNOSTIQUE ADAPTER LAYER == ######    
        
    def configure(self, tx_h = "752", rx_h = "652", bus = "DIAG"):
        '''
        Initialise the VCI for a new ECU session
        '''
        if bus == "DIAG":
            if not(self._changeComLine(ac.LINE_CAN_DIAG) and self._bindProtocol(ac.DIAG_ON_CAN)):
                return False
        elif bus == "IS":
            if not(self._changeComLine(ac.LINE_CAN_IS) and self._bindProtocol(ac.DIAG_ON_CAN)):
                return False
        else:
            self.log("Invalid or unsupported bus specified")
            return False
            
        self.currEcuDesc = self.ecuToEcuDescriptor(tx_h="752",rx_h="652",protocol=ac.DIAG_ON_CAN) 
        return True
        
    
    def send_wait_reply(self, inp, timeout = 5000):
        '''
        Wrapper to send a command to an ECU and await reply
        '''
        if self.currEcuDesc is None:
            self.log("Adapter has not been configured yet")
            return False
            
        rst = self._writeAndRead(self.currEcuDesc, self.bytesEncode(inp, None))

        if not rst:
            return ""
        else:
            out = ""
            for i in rst:
                out = out + str(self.to_hex(i))
            return out

    




class elm327():
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

    def log(self,x):
        print(str(x))


    def millis(self):
        return int(round(time.time() * 1000))


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


    def get_com_ports(self):
        '''
        Get a list of available bluetooth devices
        '''
        output = []

        try:
            self.log("Scanning for bluetooth devices")
            devices = bluetooth.discover_devices(lookup_names=True,duration=3)
            self.log("Found " + str(len(devices)) + " devices")
            for addr,name in devices:
                self._devicesx[name] = addr
                output.append(name)
                self.log("Adapter " + str(name) + " with address " + str(addr))
        except:
            self.log("Failed to retrieve adapters list")
            self.log(str(sys.exc_info()[0]) + " at line " + str(sys.exc_info()[2]))

        return output


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

        print(msg)
        return msg
    
    
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

    
    def set_headers(self, tx_h, rx_h, bus):
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
        print(send)
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
            #print(resp)
            
        self.log("Serial initialised: " + str(self.myref) + " on " + str(self._port))
        self._conn = True
        return True
        #except:
        #    self.log("Failed to create bluetooth connection to " + str(self._addr))
        #    self.log(str(sys.exc_info()[0]) + " at line " + str(sys.exc_info()[2]))
        #    return False 


class elm_with_switch(elm327):  
    '''
    This library is mostly a wrapper for the default ELM327, but
    provides for an opportunity for the user to change from DIAG to IS
    using a crossover cable with a double pole two-way switch
    '''
    myref = "ELM327 BT with crossover"

    def configure(self, tx_h="652", rx_h="752", bus="DIAG", alert=None):
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

        if bus != "DIAG" and bus != "IS":
            self.log("Selected adapter does not support the protocol " + str(bus) + " yet")
            return False

        if self._obus != bus:
            self.wait_for_user = True
            alert("Please change the adapter switch to " + str(bus) + " and validate to continue", self.configure_step)
            while self.wait_for_user:
                # elevator music
                pass

        x = self.set_headers(tx_h, rx_h, bus)
        if x:
            self._obus = bus
        else:
            self._obus = ""
        
        return x

    def configure_step(self):
        self.wait_for_user = False


ac = actia_xs()
ac.connect()
if not ac.configure():
    exit()
ac._getAnalogicData(3)
print( ac.send_wait_reply("10C0"))
print( ac.send_wait_reply("2180"))
print( ac.send_wait_reply("17FF00"))

exit()
    

#em = elm327()

#em.get_com_ports()
#em.set_com_port("OBDII")
#em._addr = "00:1D:A5:04:04:FD"
#em.connect()
#print(em.set_headers("752","652","BUS"))
#em.send_wait_reply("22E7FF")

#time.sleep(1)
#em.disconnect()

