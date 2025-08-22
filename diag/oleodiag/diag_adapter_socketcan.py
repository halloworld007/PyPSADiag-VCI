from diag_adapter import diag_adapter
import can


class raw_can_socketcan(diag_adapter):
    '''
    Read RAW CAN frames from SocketCAN,
    and do the message re-assembly/interpretation here

    Designed for use with Linux SocketCAN

    Obviously you can only work with one bus at a time by default - if you have connections to both (say can0 and can1)
    you can easily modify the configure() and connect() functions to use both. Otherwise, the class will assume only DIAG
    is connected

    NOTE: This will work only with CAN protocols (KWPonCAN/UDS/Fiat etc) - NOT K line!
    NOTE: To do interrogation of the I/S bus, you will need filtering support
    '''
    usable = False
    connected = False
    _com_port = "can0"

    def __init__(self, bmb):
        try:
            self.bb = bmb
            self.usable = True
        except:
            self.log("SocketCAN adapter is not available")
            self.usable = False


    def log(self,x):
        self.bb.logger("[RCI] " + str(x))
    

    def get_com_ports(self):
        return {"can0":"can0", "can1":"can1", "can2":"can2"}, {"can0":"can0", "can1":"can1", "can2":"can2"}
    

    def set_com_port(self, com):
        _com_port = com


    def connect(self):
        if not self.usable:
            return False
        
        try:
            self.client = can.interface.Bus(channel = self._com_port, bustype = 'socketcan_ctypes')
            self.log("Interface " + str(self._com_port) + " initialised successfully")
        except:
            self.log("Unable to initialise CAN interface " + str(self._com_port))
            return False
        
        self.connected = True

    
    def set_filter(self, rxId):
        '''
        Filter in the kernel for only ID we want
        TODO: Check what's going on RE some reply messages coming from the BSI address
        '''
        msk = 0xFFF
        if type(rxId) is not int:
            rxId = int(rxId)

        filt = [{"can_id": rxId, "can_mask": msk}]
        self.client.set_filters(filt)


    def clear_filter(self):
        '''
        Clear filters
        '''
        self.client.set_filters(None)
        
    
    def configure(self, tx_h = "752", rx_h = "652", bus = "DIAG"):
        '''
        '''
        if not self.connected:
            if not self.connect():
                return False
    
        if bus != "DIAG":
            self.log("Only DIAG is supported with a single CAN connection")
            return False
    

