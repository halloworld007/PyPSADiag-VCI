import threading, copy, time
from .diag import diag
from .diag_adapter import diag_adapter
from .diag_translations import diag_translations
from .diag_bramble import diag_bramble

'''
    diag_livedata
    Request and interpret Live Data from an ECU

    (c) Copyright 2021. All Rights Reserved

    It might seem a little bit "meta" to have threading in this library (which should
    always be run in a thread anyway), but we do it because the thread lives "forever",
    polling the ECU for data without user input

    - First you need to set the internal data "tree" - which is the normal ECU frame format
    - Next set the zones that will be read from
    - Then call start() to being the daemon
    - Then you can poll the zone data using get_tree/data
'''


class diag_livedata(diag):
    tla = "LVD"
    trs = None

    ecuveid = 0
    tree = {}

    request_frames = {}
    ack_frames = {}

    headers = ()
    cmds = {}
    
    live_data = {}
    ident = {}

    zones = []      # zones to filter

    active_thread = None
    access_flag = False
    run_flag = False
    dead_flag = False
    query_interval = 300    # 150ms

    callback = None

    def __init__(self, trs : diag_translations, adapter : diag_adapter, bmb : diag_bramble):
        self.adapter : diag_adapter         = adapter
        self.trs     : diag_translations    = trs
        self.bb      : diag_bramble         = bmb


    def get_data(self):
        '''
        Obtain a copy of the dictionary containing all live data (thread safe)
        '''
        #self.debug("Waiting for access flag to get live data")
        while self.access_flag:
            pass
        self.access_flag = True
        safety = self.live_data
        self.access_flag = False
        return safety

    
    def reset(self):
        '''
        Clear existing data for a new session
        '''
        self.stop()
        self.adapter.fini_ecu()
        self.request_frames = {}
        self.live_data = {}
        self.access_flag = False
        self.run_flag = False
        self.configured = False
        self.ident = {}

    
    def get_ident(self):
        '''
        Get the identification data dict (zone ZA/ZI)
        '''
        return self.ident

    
    def read_ecu_ident(self, callback=None):
        '''
        Read the ZA/ZI zones of the ECU (software version etc)
        This is a one-time thing, shouldn't change
        BLOCKING
        '''
        if "id" not in self.tree["FRAME_TREE"]:
            return False

        self.adapter.init_ecu(self.tree)
        self.ident = {}
        
        for zone in self.tree["FRAME_TREE"]["id"]:
            if "request" in self.tree["FRAME_TREE"]["id"][zone]:
                frame_request = self.join_frame(self.tree["FRAME_TREE"]["id"][zone]["request"])

                frame_refused = "7F"
                if "ako" in self.tree["FRAME_TREE"]["id"][zone]:
                    frame_refused = self.join_frame(self.tree["FRAME_TREE"]["id"]["ko"])

                for i in range(0,3):
                    resp = self.adapter.send_wait_reply(frame_request)
                    if not not resp:
                        break

                if not resp:
                    self.log("No ECU response to " + str(zone))
                    continue

                if len(resp) >= len(frame_refused):
                    if resp[:len(frame_refused)] == frame_refused:
                        self.log(f"ECU {self.ecuveid} refused to read zone {zone} with '{resp}'")
                        continue
                
                parsed = self.parse_params_hex(self.tree["FRAME_TREE"], resp, zone, "id")
                for key in parsed:
                    self.ident[key] = parsed[key]
            else:
                self.log(f"No request frame for {self.ecuveid} to read zone {zone}")
                continue
        
        self.adapter.fini_ecu(self.tree)


        #print(str(self.ident))

        if callback != None:
            callback()


    def set_tree(self, ecu_frame, callback = None):
        '''
        Set up the live data viewer with an ecu_frame (from a global test tree)

        requires/uses:
        - ECUVEID
        - TX_H, RX_H, BUS
        - FRAME_TREE
        '''
        if ecu_frame != None:
            self.tree = ecu_frame
        else:
            self.log("No live data for the ECU")
            return False

        self.reset()

        self.ecuveid = ecu_frame["ECUVEID"]

        if "TX_H" in ecu_frame and "RX_H" in ecu_frame and "BUS" in ecu_frame:
            self.headers = (ecu_frame["TX_H"], ecu_frame["RX_H"], ecu_frame["BUS"])
        else:
            self.tree = None
            self.log("Invalid ECU headers supplied for live data")
            return False
        
        if callback != None and callable(callback):
            self.callback = callback

        self.zones = []

        self.configured = True

        return True


    def set_zone(self, zones):
        '''
        Set a single zone (str) or list of zones that will be read from
        This speeds up data parsing on ECUs with lots of zones
        '''
        if type(zones) == str:
            if zones != "":
                self.zones = [ zones ]
            else:
                self.zones = []
        elif type(zones) == list:
            self.zones = zones
        else:
            self.zones = []
        

    def start(self):
        '''
        Configure the adapter and start the update daemon
        '''
        if self.tree == {}:
            self.log("No ECU data to process")
            return False

        try:
            if self.request_frames == {}:
                for frame in self.tree["FRAME_TREE"]["params"]:
                    self.request_frames[frame] = self.join_frame(self.tree["FRAME_TREE"]["params"][frame]["request"])
        except:
            self.log(f"{self.ecuveid}: Failed to build frame tree")
            return False

        self.debug("Querying live data with:")
        for x in self.request_frames:
            self.debug(f"{x}: {str(self.request_frames[x])}")

        # init the ECU session
        if not self.adapter.init_ecu(self.tree):
            self.log("No valid adapter response")
            return False

        # Initialise the daemon
        self.run_flag = True
        self.access_flag = False
        self.dead_flag = False

        # Stop the thread if its running (shouldn't be)
        if self.active_thread != None:
            if self.active_thread.is_alive():
                self.stop()
                # We don't want to wait for the thread to shut down, so chuck the reference to it
                self.active_thread = None
        self.active_thread = threading.Thread(target=self.update_thread, daemon=True)
        self.active_thread.start()
  
        return True


    def update_thread(self):
        '''
        A daemon thread to update the parameters dictionary
        '''
        ticks_since_last_good = 0

        #try:
        while self.run_flag:
            for zone in self.request_frames:

                dont = True

                if self.zones != []:
                    for zone_filter in self.zones:
                        if zone_filter == zone[:2]:
                            dont = False
                            break
                else:
                    dont = False
        
                if dont:
                    continue

                resp = self.adapter.send_wait_reply(self.request_frames[zone])

                if not resp:
                    continue

                if len(resp) < 5:
                    continue

                if resp[:2] == "62" or resp[:2] == "61":
                    ticks_since_last_good = 0
                    result = self.parse_params_hex(self.tree["FRAME_TREE"], resp, zone)
                elif resp[:2] == "7F":
                    ticks_since_last_good += 1
                    continue
                else:
                    continue

                # get access lock on the dict
                while self.access_flag:
                    pass
                self.access_flag = True

                # write to the dict
                for param in result:
                    self.live_data[param] = result[param]

                # Clear signal, call parent
                self.access_flag = False
                if self.callback != None:
                    self.callback()

                # Die if too many errors
                if ticks_since_last_good > 20:
                    raise Exception("Too many adapter errors")

                if not self.run_flag:
                    break

                time.sleep(self.query_interval/1000)


        #    self.dead_flag = True
        #    self.log("WARNING: Live data daemon crashed : " + str(sys.exc_info()[0]) + " at line " + str(sys.exc_info()[2]))
        #    if self.callback != None:
        #        self.callback()


    def get_tree(self):
        '''
        You must wait for the semaphore (access_flag) before calling this
        Will return false if communication has been lost or the thread crashed
        '''
        if not self.run_flag:
            return False

        if self.dead_flag:
            return False

        return copy.deepcopy(self.live_data)


    def stop(self):
        '''
        Kill the daemon if running
        '''
        self.run_flag = False
        self.dead_flag = False
        self.access_flag = False # must do this or we can zombie the thread
        self.log("Live data daemon terminated")
        self.adapter.fini_ecu()


        