from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.event import EventDispatcher
from kivy.properties import ObjectProperty, ListProperty, DictProperty
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.factory import Factory
from kivy.uix.image import Image
from kivy.clock import Clock
from functools import partial
import datetime, json

'''
SCREEN: Discovery

Scan the vehicle to find which ECU's are fitted, and supply 
necessary information to Centre

'''
import os.path


class Discovery(Screen):
    tree_in = DictProperty()
    tree_out = DictProperty()
    tree_mid = DictProperty()
    acc = None
    tree_lock = False
    widgets = ListProperty()

    def __init__(self, **kwargs):
        super(Discovery, self).__init__(**kwargs)
        self.acc = App.get_running_app()

    def log(self, x):
        self.acc.bmb.logger("[DSC] " + str(x))

    def set_up(self, tree):
        '''
        Set up the tree of data to process
        and prompt the user to do ignition stuff etc
        '''
        self.tree_lock = False
        self.tree_in = tree
        for x in self.widgets:
            for y in x:
                self.ids.disco_list.remove_widget(y)

    def abandon(self, *largs):
        self.tree_in = {}
        self.manager.current = 'main'


    def initiate(self):
        '''
        Show discovery screen
        '''
        self.manager.current = "discovery"
        if self.acc.glt.set_global_tree(self.tree_in):
            if self.acc.ada.connect():
                self.acc.alert(["discoverystart","discoveryecomode"], "discoveryplease", self.ignition_ok)
            else:
                self.log("Discovery tree was OK but adapter is not available")
                self.acc.alert("discoverynoadapter", "discoveryplease", self.abandon)
                self.manager.current = "selectveh"
                    
        else:
            self.acc.alert("discoveryerror", "discoveryplease", self.abandon)

    def ignition_ok(self, *largs):
        '''
        Trigger the start of the global test
        '''
        self.ids.discovery_tip.text = self.acc.trs.ui("discoverywait")        
        self.acc.load(partial(self.acc.glt.run_discovery, self.handle_gt_callback), self.handle_gt_done)

    def show_ecu(self, ecu, item):
        '''
        Given an item (entry from a globaltest tree), show it in view
        FAMILY  |   ECU NAME   |     ECU VARIANT    |    FAULTS
        
        BSI         BSI2010          BSI2010_X7_V2       2
        BSI         NO DETECT        -                   -
        BSI         BSI2010          NO RESPONSE         -

        VALID = Detected on the vehicle
        DETECTED = Responded to RECO request?
        '''

        fam = ""
        ecuvar = ""
        fau = ""

        if "STATUS" in item:
            if item["STATUS"] != "IDENTOK":
                ecu = self.acc.trs.ui("nodetect")
                ecuvar = "-"
                if item["STATUS"] == "NOTPRESENT":
                    ecu = self.acc.trs.ui("nopresent")

                if "ECUNAME" in item and item["ECUNAME"] is not None:
                    ecuvar = item["ECUNAME"]
        else:
            self.log("Invalid ECU identifier: " + str(item))
            return

        if "FAMILY" in item and item["FAMILY"] is not None:
            fam = item["FAMILY"]
        else:
            fam = ecu
            ecu = self.acc.trs.ui("nodetect")

        if "FAULTS" in item and item["FAULTS"] is not None:
            if item["FAULTS"] == -1:
                fau = "-"
            else:    
                fau = str(item["FAULTS"])
        else:
            fau = "-"

        if "VARIANT" in item and item["VARIANT"] is not None:
            ecuvar = item["VARIANT"]

        if os.path.isfile("img/" + str(fam).lower() + ".png"):
            img = "img/" + str(fam).lower() + ".png"
        else:
            img = "img/ecu_blank.png"

        l_img = Image(source=img)
        l_fam = Factory.DGLabel(text=fam)
        l_ecu = Factory.DGLabel(text=ecu)
        l_var = Factory.DGLabel(text=ecuvar)
        l_fau = Factory.DGLabel(text=fau)

        widg = [l_img, l_fam, l_ecu, l_var, l_fau]

        for wid in widg:
            self.ids.disco_list.add_widget(wid)

        self.widgets.append(widg)
        self.ids.disco_list.height = self.ids.disco_list.height + 60


    def handle_gt_done(self, tree, *largs):
        '''
        Called when the test function returns
        '''
        Clock.schedule_once(partial(self.process_gt_done, tree))


    def process_gt_done(self, tree, *largs):
     
        if tree == {}:
            self.acc.alert("discoveryfail")
            self.manager.current = "main"
            return

        self.log("Discovery completed. Switching to results view")

        self.save_global_results()

        self.manager.current = "centre"
        self.manager.get_screen('centre').initiate(self.acc.glt.globalResults)
                    

    def save_global_results(self, tree=None):
        '''
        Dump the global test results to a local file
        '''

        # file name
        # MARQUE_MODEL_VIN_Y_M_D
        # Citroen_C5 (X7)_VF7RWX_01_02_20.dsc

        fname = ""

        if tree is None:
            tree = self.acc.glt.globalResults

        try:
            now = datetime.datetime.now()

            veh_info = self.acc.bmb.get_vehicle_model(tree["VEH"])

            fname = str(now.day) + "_" + str(now.month) + "_" + str(now.year)

            if type(veh_info) == dict: 
                fname = fname + "_" + str(veh_info["marque"]) + "_" + str(veh_info["model"])
            else:
                fname = fname + "_" + str(veh_info) 

            if tree["VIN"] != "":
                fname = fname + "_" + str(tree["VIN"])

            fname = fname + ".dsc"

            direc = self.manager.get_screen("setting").settings["user_dir"] + self.manager.get_screen("setting").settings["discovery_dir"]
            
            if not os.path.isdir(direc):
                os.makedirs(direc)

            sfile = open(direc + fname, "w")
            json.dump(tree, sfile)
            self.log("Saved Discovery session to: " + str(fname))
            return True
        except:
            self.log("Couldn't save discovery results to directory in settings: " + str(fname))
            return False


    def load_previous_vehicle(self):
        '''
        Open a dialog to offer the user to select a filename to load
        '''
        self.acc.askfileload(callback=self.load_global_results)

    
    def load_global_results(self, filename):
        '''
        Load a previously cached Discovery instance
        '''
        if filename == "" or filename == None or not filename:
            self.manager.current = "main"
            return

        self.log("Loading previous session from: " + str(filename))

        try:
            sfile = open(filename, "r")
            globalResults = json.load(sfile)

            if "VER" in globalResults:
                if globalResults["VER"] == self.acc.bmb.version:
                    self.acc.bmb.set_lid_table(globalResults["LID"])
                    self.manager.current = "centre"
                    self.manager.get_screen('centre').initiate(globalResults)
                else:
                    self.log("Data loaded successfully, but library version " + str(self.acc.bmb.version) + " is not the same as the file was created with: " + str(globalResults["VER"]))
                    self.acc.alert("discoloadfailed")
                    self.manager.current = "main"
                    return
            else:
                self.acc.alert("discoloadfailed")
                self.log("Invalid data file requested for loading (no version) " + str(filename))
                self.manager.current = "main"
                return
        except:
            self.acc.alert("discoloadfailed")
            self.log("Invalid data file requested for loading (exception) " + str(filename))
            self.manager.current = "main"


    def process_gt_callback(self, *largs):
        '''
        Called by the diag library each time an ECU connection is made
        '''
        Clock.schedule_once(self.gt_callback)

    
    def gt_callback(self, *largs):
        if "ECU" not in self.tree_mid:
            return
        if "ECU" not in self.tree_out:
            self.tree_out["ECU"] = {}

        while self.tree_lock:
            #elevator music
            pass

        self.tree_lock = True

        for item in self.tree_mid["ECU"]:
            # look for new item
            if item not in self.tree_out["ECU"]:
                self.show_ecu(item, self.tree_mid["ECU"][item])
                self.tree_out["ECU"][item] = self.tree_mid["ECU"][item]
        
        self.tree_lock = False


    def handle_gt_callback(self, tree, *largs):
        '''
        Called from the background thread, no UI updating
        '''
        self.tree_mid = tree
        Clock.schedule_once(self.process_gt_callback, 1)