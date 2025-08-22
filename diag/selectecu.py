from kivy.app import App
from kivy.properties import ObjectProperty, StringProperty, DictProperty
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.factory import Factory
from kivy.clock import Clock

class SelectECU(Screen):

    mi : App = None
    models = {}
    famids = {}
    ecuids = {}
    ecuveids = {}
    hdrs = {}
    protocols = {}

    active_ecuid = 0
    active_ecuveid = 0
    
    def initiate(self):
        '''
        load the screen
        '''
        self.mi = App.get_running_app()

        self.dialog = Factory.WaitPopup()
        self.dialog.open()
        self.dialog.ids.stat.text = "Loading initial data, this may take a few seconds..."

        Clock.schedule_once(self.load_initial_data, 1)


    def load_initial_data(self, *largs):

        self.manager.current = "selectecu"

        if self.models == {}:
            self.ids.models.values = []
            #self.mi.log("Starting look for models")
            models = self.mi.bmb.get_supported_models_list()
            #self.mi.log("Got models")

            models_temp = []

            for marque in models:
                for model in models[marque]:
                    model_name = marque + " " + model["label"]
                    self.models[model_name] = model
                    models_temp.append(model_name)
            
            self.ids.models.values = models_temp
            
            if len(models) > 0:
                self.ids.models.text = self.ids.models.values[0]
                self.ids.models.disabled = False

        self.dialog.dismiss()


    def user_search(self):
        pass

    
    def make_ecu_spec(self):
        '''
        Make discovery ECU frame format
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
        spec = {}

        spec["ECUID"] = int(self.active_ecuid)
        spec["ECUVEID"] = int(self.active_ecuveid)
        spec["FAMILY"] = self.ids.famids.text
        spec["ECUNAME"] = self.ids.ecuids.text
        spec["VARIANT"] = str(self.ecuveids[self.ids.ecuveids.text]["variant"])
        spec["TX_H"] = str(self.hdrs[self.ids.ecuids.text][1])
        spec["RX_H"] = str(self.hdrs[self.ids.ecuids.text][2])
        spec["BUS"] = str(self.hdrs[self.ids.ecuids.text][0])
        spec["PROTOCOL"] = str(self.hdrs[self.ids.ecuids.text][3])
        spec["TARGET_CODE"] = str(self.hdrs[self.ids.ecuids.text][5])
        spec["DIALOG_TYPE"] = str(self.hdrs[self.ids.ecuids.text][4])
        spec["CMDS"] = self.mi.bmb.get_ecu_diag_cmds(spec["ECUVEID"])
        spec["FAULTS"] = -1
        spec["FAULT_TREE"] = {}
        spec["FRAME_TREE"] = self.mi.bmb.get_data_frames(spec["ECUID"], spec["ECUVEID"])

        return spec


    def render_readout(self):

        out = "\nModel Code: " +  str(self.models[self.ids.models.text]["internal"])
        out = out + "\nVehicle ID: " +  str(self.models[self.ids.models.text]["vehid"])
        out = out + "\nECU ID    : " +  str(self.active_ecuid)
        out = out + "\nECUVE ID  : " +  str(self.active_ecuveid)
        out = out + "\nReference : " +  str(self.ecuveids[self.ids.ecuveids.text]["reference"])
        out = out + "\nVariant   : " +  str(self.ecuveids[self.ids.ecuveids.text]["variant"])
        out = out + "\n\nBus       : " +  str(self.hdrs[self.ids.ecuids.text][0])
        out = out + "\nTX Header : 0x" +  str(self.hdrs[self.ids.ecuids.text][1])
        out = out + "\nRX Header : 0x" +  str(self.hdrs[self.ids.ecuids.text][2])
        out = out + "\nProtocol  : " +  str(self.hdrs[self.ids.ecuids.text][3])
        out = out + "\nDialogType: " +  str(self.hdrs[self.ids.ecuids.text][4])
        out = out + "\nECU Code  : " +  str(self.hdrs[self.ids.ecuids.text][5])
        out = out + "\nDiagInit  : 0x" +  str(self.ecuveids[self.ids.ecuveids.text]["diaginit"])
        out = out + "\nReCo      : 0x" +  str(self.ecuveids[self.ids.ecuveids.text]["reco"])

        self.ids.lbl_readout.text = out


    def user_onecuveid(self):
        self.active_ecuveid = self.ecuveids[self.ids.ecuveids.text]["ecuveid"]
        self.ids.btn_next.disabled = False
        self.render_readout()


    def user_onecuid(self):
        ecuid = self.ecuids[self.ids.ecuids.text]
        self.active_ecuid = ecuid
        lis = self.mi.bmb.get_ecuveids_for_ecuid(ecuid)

        self.ecuveids = {}
        self.ids.ecuveids.values = []
        variant_count = 0
        
        ecuveids_temp = []

        for variant in lis:
            ecuveids_temp.append(lis[variant]["variant"] + " - " + str(lis[variant]["reference"]))
            self.ecuveids[lis[variant]["variant"] + " - " + str(lis[variant]["reference"])] = lis[variant]
            variant_count += 1
        
        self.ids.ecuveids.values = ecuveids_temp
        
        if len(self.ids.ecuveids.values) > 0:
            self.ids.ecuveids.text = self.ids.ecuveids.values[0]
            self.ids.ecuveids.disabled = False


    def user_onfamid(self):
        '''
        user changed famid, load ecuis
        '''
        famid = self.famids[self.ids.famids.text]

        self.ecuids = {}
        self.ids.ecuids.values = []

        ecuids_temp = []

        for bus in famid:
            options = famid[bus]["RECO"]
            for init_cmd in options:
                for ecu in options[init_cmd]:
                    name_id = ecu.split(":")
                    ecuids_temp.append(name_id[0])
                    self.ecuids[name_id[0]] = name_id[1]
                    self.hdrs[name_id[0]] = bus.split(":")

        self.ids.ecuids.values = ecuids_temp
        
        if len(self.ids.ecuids.values) > 0:
            self.ids.ecuids.text = self.ids.ecuids.values[0]
            self.ids.ecuids.disabled = False
        


    def user_onmodels(self):
        '''
        user changed model, load families
        '''
        model = self.models[self.ids.models.text]["vehid"]
        code = self.models[self.ids.models.text]["internal"]
        lis = self.mi.bmb.get_vehicle_ecu_list(model)

        self.ids.famids.values = []
        self.famids = {}

        values_temp = []

        ecu = list(lis.keys())
        ecu.sort()
        out = {}
        for e in ecu:
            if lis[e] == {}:
                continue
            if e == "fam" or e == "veh":
                continue
            if e == "prot":
                self.protocols[model] = lis[e]
                continue
            values_temp.append(e)
            self.famids[e] = lis[e]
        
        self.ids.famids.values = values_temp
        self.ids.famids.disabled = False


    def user_confirm(self):
        spec = { "PROT": 0, "VEH": "", "VIN": "", "VER": self.mi.bmb.version, "LID": {} , "ECU": {} }
        spec["VEH"] = str(self.models[self.ids.models.text]["vehid"])
        spec["PROT"] = self.protocols[self.models[self.ids.models.text]["vehid"]]
        out_spec = self.make_ecu_spec()
        spec["ECU"][out_spec["ECUNAME"]] = out_spec
        self.manager.current = "centre"
        self.manager.get_screen('centre').initiate(spec)
