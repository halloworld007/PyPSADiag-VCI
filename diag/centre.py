from kivy.app import App
from navigationdrawer import NavigationDrawer
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.properties import ObjectProperty, DictProperty, BooleanProperty, ColorProperty
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.clock import Clock
from kivy.uix.accordion import Accordion
from kivy.factory import Factory
from functools import partial
from kivy.uix.treeview import TreeView,TreeViewLabel
from kivy.uix.gridlayout import GridLayout
from kivy.uix.switch import Switch
from kivy.uix.recycleboxlayout import RecycleBoxLayout

from oleodiag.diag_telecode import TelecodeResult

from collections import OrderedDict
import copy, csv, datetime, os, re

'''
SCREEN: Centre

The main view, containing 

- the list of ECU's in a left navigation drawer
- a tabbed view for faults, live data, actuator tests, telecoding
'''

class WaitDialog():
    '''
    Wrapper class for the "please wait" dialog
    '''
    dialog = None


    def __init__(self):
        self.dialog = Factory.WaitPopup()

    def open(self, *largs):
        self.dialog.open()

    def dismiss(self, *largs):
        self.dialog.dismiss()
        self.set_status("")
    
    def set_status(self, txt):
        self.dialog.ids.stat.text = txt


class FloatInput(TextInput):
    '''
    Used for procedures to allow user
    to enter numbers only
    '''

    pat = re.compile('[^0-9]')
    def insert_text(self, substring, from_undo=False):
        pat = self.pat
        if '.' in self.text:
            s = re.sub(pat, '', substring)
        else:
            s = '.'.join(
                re.sub(pat, '', s)
                for s in substring.split('.', 1)
            )
        return super().insert_text(s, from_undo=from_undo)
    

class HexInput(TextInput):
    '''
    Used for procedures to allow user
    to enter hexadecimal characters only
    '''

    pat = re.compile('[^0-9a-fA-f]')
    def insert_text(self, substring, from_undo=False):
        pat = self.pat
        if '.' in self.text:
            s = re.sub(pat, '', substring)
        else:
            s = '.'.join(
                re.sub(pat, '', s)
                for s in substring.split('.', 1)
            )
        return super().insert_text(s, from_undo=from_undo)


class Centre(Screen):
    mi = None
    tree = {}
    ecu_list = ObjectProperty()
    nav_widg = []
    active_ecu = None
    tlcd_warning_done = False
    missing = []

    optdown = ObjectProperty()

    # data from diaglib
    act_tests = {}
    tlcd_ui = {}

    # live data
    lidata_view = ObjectProperty()
    lidata_ptr = DictProperty()
    lidata_store = DictProperty()
    lidata_live = DictProperty()
    lidata_active = BooleanProperty(False)
    lidata_logptr = ObjectProperty()
    lidata_csvptr = ObjectProperty()
    lidata_logging = False
    lidata_selected = []                  # list of checkboxes active
    lidata_log = []                         # list of params to be logging
    lidata_logselonly = False               # must match default in UI

    # id
    id_view = ObjectProperty()
    id_ptr = DictProperty()
    ident_data = DictProperty()

    # tlcd
    tlcd_changes = {}
    tlcd_zones = {}
    tlcd_view = None
    tlcd_loaded = False
    tlcd_start_ecu = ""
    tlcd_export_cache = {}

    # act
    act_test_active = False
    act_test_start_ecu = ""
    act_test_has_steps = False

    #proc
    procedures = {}
    proc_variable_widgets = {}

    # disable actuator tests and telecoding on these, because BSI handles it better
    bsx_family = ["BSR", "BSM", "BSC"]

    # parameter value pairs that will show a switch instead of spinner
    TLCD_NEG = ["ABSENT", "NOT CONFIGURED", "NO", "INACTIVE", "FUNCTION MASKED"]
    TLCD_POS = ["PRESENT", "CONFIGURED", "YES", "ACTIVE", "FUNCTION DISPLAYED"]

    # adapter signal
    # Stop the user from initiating an action unless the 
    # adapter isn't being used. On init, it's the configuration
    # reading background function
    adapter_signal =  "tlcd_read"

    def log(self, x):
        log = "[CTR] " + str(x)
        self.mi.bmb.logger(log)

    def debug(self, x):
        print("[CTR] Debug: " + str(x))


    def tlcd_warning(self, tab):
        '''
        Warn the user (once) before switching to the TLCD box
        '''
        self.tlcd_waiting = True
        self.tab_change(tab)


    def clean_exit(self):
        '''
        End of session, shutdown live data/etc nicely
        '''
        if self.lidata_active:
            # stop it
            pass
        

    def tab_change(self, tab, *largs):
        '''
        Called when the user clicks on a tab
        '''

        # If live data is running, ask to kill it
        if self.lidata_active:
            self.mi.yesno("lidataendq",callbacky=partial(self.tab_change_lidata_kill,tab), callbackn=partial(self.tab_change_confirm,tab,False))
        else:
            self.tab_change_confirm(tab, True)
    

    def save_tree_if_possible(self, *largs):
        '''
        If a tree is loaded and active, save it to a file
        '''
        if self.manager.current == "centre":
            if self.tree != {}:
                if self.manager.get_screen("discovery").save_global_results(self.tree):
                    self.mi.alert("Updated save file")
                else:
                    self.mi.alert("Failed to update save file")


    def tab_change_lidata_kill(self, tab, *largs):

        #self.lidata_toggle(None, False)
        self.lidata_view.ids.lidata_comms.down = False
        self.tab_change_confirm(tab, True)


    def tab_change_confirm(self, tab, answer, *largs):
        '''
        Called when the user confirms a tab change prompt
        '''

        if len(largs) > 0:
            if largs[0]:
                self.tlcd_warning_done = True

        if answer:
            if self.tlcd_waiting:
                if not self.tlcd_warning_done:
                    self.mi.yesno("tlcd_warning","alerttitle", callbacky=partial(self.tab_change_confirm,tab, True, True), callbackn=partial(self.tab_change_confirm,tab,False, False))
                    return
                else:
                    self.tlcd_waiting = False
                    if not self.tlcd_loaded:
                        self.tlcd_start_ecu = self.active_ecu

                        if self.get_setting("user_mode") >= self.mi.bmb.USER_MODE_EXPERIMENTAL:
                            self.mi.load(partial(self.mi.bmb.get_params_from_telecoding, self.tree["ECU"][self.active_ecu]["ECUID"], self.tree["ECU"][self.active_ecu]["ECUVEID"], filt_level = self.mi.bmb.MODE_EXPERIMENTAL), self.thr_tlcd_sch)
                        else:
                            self.mi.load(partial(self.mi.bmb.get_params_from_telecoding, self.tree["ECU"][self.active_ecu]["ECUID"], self.tree["ECU"][self.active_ecu]["ECUVEID"]), self.thr_tlcd_sch)
                        self.waitpp.open()
            # yes   
            tab.on_release_allow()
                
        else:
            tab.state = 'normal'
            self.tlcd_waiting = False
            self.ids.tab_master.current_tab.state = 'down'
            return


    def reset_tabs(self):
        '''
        Reset all tab views when changing ECU
        '''
        self.ids.tab_faults.clear_widgets()
        self.ids.tab_livedata.clear_widgets()
        self.ids.tab_test.clear_widgets()
        self.ids.tab_tlcd.clear_widgets()
        self.ids.tab_ident.clear_widgets()
        self.ids.tab_proc.clear_widgets()

        p = Factory.FaultDefault()
        p.callback = self.dtc_refresh
        self.ids.tab_faults.add_widget(p)

        q = Factory.ActDefault()
        q.callback = self.act_load
        self.ids.tab_test.add_widget(q)


        self.ids.tab_livedata.add_widget(Factory.DGLabel(text = self.mi.trs.ui("livedataempty")))
        #self.ids.tab_test.add_widget(Factory.DGLabel(text = self.mi.trs.ui("testingempty")))
        self.ids.tab_tlcd.add_widget(Factory.DGLabel(text = self.mi.trs.ui("tlcdempty")))
        self.ids.tab_ident.add_widget(Factory.DGLabel(text= self.mi.trs.ui("idempty")))
        self.ids.tab_proc.add_widget(Factory.DGLabel(text = self.mi.trs.ui("procempty")))


        self.act_tests = {}


    def status_callback(self, status, *largs):
        '''
        Called when the background thread status changes
        '''
        Clock.schedule_once(partial(self.status_update,status, True))


    def status_update(self, status, force, *largs):
        '''
        Thread safe way to update the Status bar
        '''
        if status:
            if not force and self.ids.stat_adapter.text == "Ready.":
                return

            if self.ids.stat_adapter.text == "Operation in progress...":
                self.ids.stat_adapter.text = "...Operation in progress"
                Clock.schedule_once(partial(self.status_update,True,False), 1)
            else:
                self.ids.stat_adapter.text = "Operation in progress..."
                Clock.schedule_once(partial(self.status_update,True,False), 1)
                
        if not status and force:
            self.ids.stat_adapter.text = "Ready."



    def initiate(self, tree):
        '''
        Load the result of a global test (wherever it came from)
        and set up the UI
        '''
        self.waitpp = WaitDialog()
        self.waitpp.open()

        #self.ids.tab_master.default_tab = self.ids.tab_faults

        self.optdown = Factory.SelDropDown()
        self.optdown.ppt = self

        self.mi = App.get_running_app()
        self.tree = tree

        # reset warning for each vehicle
        self.tlcd_warning_done = False
        self.tlcd_waiting = False

        self.act_test_active = False

        self.mi.status_callbacks.append(self.status_callback)


        # reset UI
        for tup in self.nav_widg:
            self.ids.ecu_list.remove_widget(tup[0])
            self.ids.ecu_list.remove_widget(tup[1])        
        self.nav_widg = []
        self.missing = []
        self.reset_tabs()

        if tree is None or tree == {} or "ECU" not in tree:
            self.waitpp.dismiss()
            self.log("Invalid data supplied to initiate")
            self.mi.alert("centre_loaderror")
            self.manager.current = "main"
            return

        if "veh" in tree or "VEH" in tree:
            model = self.mi.bmb.get_vehicle_model(tree["VEH"])
            self.ids.stat_veh.text = self.mi.trs.ui("statvehicle") + ": " + str(model["model"])

        if "vin" in tree or "VIN" in tree:
            self.ids.stat_vin.text = self.mi.trs.ui("statvin") + str(tree["VIN"])

        for name in tree["ECU"]:
            
            # check if the ECUs have been correctly read
            if "STATUS" in tree["ECU"][name]:
                if tree["ECU"][name]["STATUS"] != self.mi.bmb.ECUIDENTOK:
                    # TODO: Display the actual status code
                    self.missing.append(name)
                    continue
         
            # Build the nav drawer list of ECUs
            btn = Factory.DGButton(text = name)
            btn.bind(on_release=partial(self.change_ecu, name))
            flt = tree["ECU"][name]["FAULTS"]
            if flt == -1:
                flt = self.mi.trs.ui("ecunofault")
            lbl = Label(text=str(flt))
            self.ids.ecu_list.add_widget(btn)
            self.ids.ecu_list.add_widget(lbl)

            self.nav_widg.append((btn, lbl, name))

        self.waitpp.dismiss()

        # If no valid ECUs
        if len(self.nav_widg) == 0:
            self.mi.alert("centrenovalidecu")
            self.manager.current = "main"
            return

        # show invalid or missing ecus at the bottom of the list
        for ecu in self.missing:
            ma = Factory.DGLabelW(text=ecu)
            mb = Factory.DGLabelW(text=self.mi.trs.ui("ecuinvalid"))
            self.ids.ecu_list.add_widget(ma)
            self.ids.ecu_list.add_widget(mb)
            self.nav_widg.append((ma, mb, ecu))

        # select the first ECU and loads its screens
        if len(self.nav_widg) == 0:
            self.log("Error whilst creating UI tree")
            self.log(str(self.nav_widg))
            self.mi.alert("centreloaderr")
            self.manager.current = "main"
            return

        self.active_ecu = self.nav_widg[0][2]
        self.change_ecu(self.active_ecu)


    def change_ecu(self, name, *largs):
        '''
        Handle the button press and determine what to switch to
        '''
        
        if name in self.tree["ECU"]:
            self.waitpp = WaitDialog()
            self.waitpp.open()
            Clock.schedule_once(partial(self.change_ecu_slow, name))
    

    def get_setting(self, key):
        if key in self.manager.get_screen("setting").settings:
            return self.manager.get_screen("setting").settings[key]
        else:
            self.log("Setting [" + str(key) + "] is not available")
            return ""


    def change_ecu_slow(self, name, *largs):
        '''
        Actually run the ECU change process
        '''

        self.log("Changing to ECU: " + str(name))

        if name in self.tree["ECU"]:

            # Hide dangerous things from inexperienced users
            if self.get_setting("user_mode") < self.mi.bmb.USER_MODE_ADVANCED:
                self.ids.tab_test.disabled = True
                self.ids.tab_tlcd.disabled = True
                self.ids.tab_proc.disabled = True
            else:
                self.ids.tab_test.disabled = False
                self.ids.tab_tlcd.disabled = False
                self.ids.tab_proc.disabled = False

            self.mi.lidata.reset()
            self.mi.tlc.reset()
            self.mi.prc.reset()

            self.lidata_active = False
            self.lidata_live = {}
            self.lidata_store = {}
            self.tlcd_ui = {}
            self.act_test = {}
            self.tlcd_loaded = False
            self.tlcd_waiting = False
            self.tlcd_zones = {}

            self.id_ptr = {}

            self.reset_tabs()
            
            self.active_ecu = name
            ecuid = self.tree["ECU"][self.active_ecu]["ECUID"]
            ecuveid = self.tree["ECU"][self.active_ecu]["ECUVEID"]
            ecuvar = self.tree["ECU"][self.active_ecu]["VARIANT"]

            self.ids.stat_ecu.text = self.mi.trs.ui("statecu") + str(ecuvar)

            # FAULTS
            # If there's faults to display
            if "FAULT_TREE" in self.tree["ECU"][self.active_ecu] and self.mi.bmb.int(self.tree["ECU"][self.active_ecu]["FAULTS"]) > 0:
                self.dtc_load(self.tree["ECU"][self.active_ecu])


            # ####################################################
            # LIVE DATA / ecu identification
            # ####################################################
            if "FRAME_TREE" in self.tree["ECU"][self.active_ecu]:
                if type(self.tree["ECU"][self.active_ecu]["FRAME_TREE"]) == dict:
                    frames = self.tree["ECU"][self.active_ecu]["FRAME_TREE"]
                    if "params" in frames:
                        if len(frames["params"]) > 0:
                            # if theres valid live data for this ecu
                            if not self.mi.lidata.set_tree(self.tree["ECU"][self.active_ecu], self.lidata_update):
                                self.log("Failed to create live data instance for " + str(self.active_ecu))
                            else:    
                                self.lidata_view = Factory.LiDataList()
                                self.lidata_view.ppt = self
                                self.ids.tab_livedata.add_widget(self.lidata_view)
                                #self.lidata_view.ids.lidata_page.data = []

                                self.lidata_view_zones = {}

                                for zone in frames["params"]:
                                    for par in frames["params"][zone]["params"]:
                                         # If no label, only show in mode_advanced+
                                        label_text = ""
                                        if "label" in par:
                                            if par["label"] != "":
                                                label_text = par["label"]
                                            elif self.get_setting("user_mode") > self.mi.bmb.USER_MODE_SIMPLE:
                                                label_text = par["parname"]
                                            else:
                                                continue
                                        elif self.get_setting("user_mode") > self.mi.bmb.USER_MODE_SIMPLE:
                                                label_text = par["parname"]
                                        else:
                                            continue

                                        # Sort by first 2 chars of zone
                                        # see if we need to add a tab
                                        if zone[:2] not in self.lidata_view_zones:
                                            item = Factory.LiDataZone()
                                            item.ppt = self.lidata_set_tab
                                            self.lidata_view.ids.tab_lidataz.add_widget(item)
                                            item.id = zone[:2]
                                            item.text = zone[:2]
                                            item.tab_height = 20
                                            self.lidata_view_zones[zone[:2]] = item 
                                        else:
                                            item = self.lidata_view_zones[zone[:2]]

                                        if label_text != "":
                                            item.ids.lidata_page.data.append({ "text_lbl": label_text, 
                                                                               "unit": par["unit"], 
                                                                               "text_val": self.mi.trs.decodalate(par["unit"],"-"),
                                                                               "text_help": par["help"],
                                                                               "pid": str(par["pid"]),
                                                                               "chk_callback": partial(self.lidata_selectcheck, str(par["parname"])) 
                                                                            })
                                            self.lidata_ptr[str(par["parname"])] = len(item.ids.lidata_page.data) - 1
                                            #self.log("added " + str(par["parname"]))

                    if "id" in frames:
                        # this needs to be a ScrollView Grid
                        id_page = Factory.IdentPage()
                        id_page.ppt = self
                        self.ids.tab_ident.add_widget(id_page)
                        self.id_view = id_page.ids.ident_list

                        if "IDENTIFICATION" not in self.tree["ECU"][self.active_ecu]:
                            self.tree["ECU"][self.active_ecu]["IDENTIFICATION"] = {}

                        for zone in frames["id"]:
                            for par in frames["id"][zone]["params"]:
                                if "label" in par:
                                    if par["label"] != "":
                                        label_text = par["label"]
                                    else:
                                        label_text = par["parname"]
                                else:
                                    label_text = par["parname"]

                                lbl = Factory.DGLabel(text=label_text, size_hint_y=None, height=50)
                                value_str = ""

                                if par["parname"] not in self.tree["ECU"][self.active_ecu]["IDENTIFICATION"]:
                                    self.tree["ECU"][self.active_ecu]["IDENTIFICATION"][par["parname"]] = {"label": label_text, "value": "" }
                                else:
                                    if self.tree["ECU"][self.active_ecu]["IDENTIFICATION"][par["parname"]]["value"] != "":
                                        value_str = self.tree["ECU"][self.active_ecu]["IDENTIFICATION"][par["parname"]]["value"]
                                
                                val = Factory.DGLabel(text=value_str)
                                self.id_ptr[par["parname"]] = val
                                self.id_view.add_widget(lbl)
                                self.id_view.add_widget(val)

                        do_cfg = True
                        self.id_view.height = self.id_view.minimum_height
                        if not self.mi.lidata.configured:
                            # only read ecu ident once, so no callback
                            if not self.mi.lidata.set_tree(self.tree["ECU"][self.active_ecu], None):
                                self.log("Failed to create live data instance for ID: " + str(self.active_ecu))
                                do_cfg = False

                        if do_cfg and self.get_setting("autoload_ident"):
                            self.mi.load(self.mi.lidata.read_ecu_ident, self.ident_response)


            # ACTUATOR TESTS
            if self.get_setting("autoload_actuators"):
                self.act_load()
            
            # TELECODING
            # this is a generic function to get the data, it triggers a callback which then 
            # requests the current configuration data from the ECU
            if self.get_setting("autoload_tlcd") and not self.tree["ECU"][self.active_ecu]["FAMILY"] not in self.bsx_family:
                self.log("Autoloading telecoding...")
                self.tlcd_start_ecu = self.active_ecu
                if self.get_setting("user_mode") >= self.mi.bmb.USER_MODE_EXPERIMENTAL:
                    self.mi.load(partial(self.mi.bmb.get_params_from_telecoding, ecuid, ecuveid, filt_level = self.mi.bmb.MODE_EXPERIMENTAL), self.thr_tlcd_sch)
                else:
                    self.mi.load(partial(self.mi.bmb.get_params_from_telecoding, ecuid, ecuveid), self.thr_tlcd_sch)

            # PROCEDURES
            # TODO: make this a configurable setting?
            if True:
                self.log("Autoloading procedures...")
                self.mi.load(partial(self.mi.bmb.get_procedures_for_ecu, self.tree["VEH"], self.tree["ECU"][self.active_ecu]["ECUNAME"]), partial(self.thr_prc_return, self.active_ecu))

            self.waitpp.dismiss()
        else:
            self.log("Mismatched ECU identifier in centre. Unexpected: " + str(name))
            self.waitpp.dismiss()
            return


    
    ##############################################

    #       ACTUATOR TESTS

    ##############################################
    
    def act_load(self, *largs):
        '''
        Trigger a background loading of the actuator tests from the database, if allowed
        '''
        ecuid = self.tree["ECU"][self.active_ecu]["ECUID"]
        ecuveid = self.tree["ECU"][self.active_ecu]["ECUVEID"]

        if not self.ids.tab_test.disabled and not self.tree["ECU"][self.active_ecu]["FAMILY"] in self.bsx_family:
            self.act_test_start_ecu = self.active_ecu
            self.mi.load(partial(self.mi.bmb.get_actuator_tests, ecuid, ecuveid), self.thr_act_tests_sch)


    def load_act_tests(self, *largs):
        '''
        Actually loads the result of get_actuator_tests into the UI

        Mainly, generate a list of buttons with the available tests at a high level.
        When a user selects one, we then load the given test into diag_acttest which
        will tell us what inputs we need to provide (if any, and co-ordinate steps/progress
        messages etc)
        '''

        if self.act_tests == {}:
            return

        # in case the ECU changed before we returned the thread
        if self.act_test_start_ecu != self.active_ecu:
            return

        self.tabtest = Factory.ActTestBox()
        self.tabtest.ppt = self
        self.ids.tab_test.add_widget(self.tabtest)

        self.log("Loading " + str(len(self.act_tests)) + " actuator tests")
        counter = 0

        screens = OrderedDict()
        for screen in self.act_tests:
            screens[self.act_tests[screen]["title"]] = screen
        scrs = list(screens.keys())
        scrs.sort()

        for scr in scrs:
            screen = screens[scr]
            if "disabled" in self.act_tests[screen]:
                self.log("Hidden actuator test " + str(screen) + " due to incompatible data")
                continue

            # filter numero relatif
            if "format" in self.act_tests[screen]:
                if "nr" in self.act_tests[screen]["format"]:
                    if str(self.act_tests[screen]["format"]["nr"]) == "-1":
                        # silently hide unsupported tests
                        continue

            lbl = Factory.DGLabelAS(text="[b]" + str(self.act_tests[screen]["title"]) + "[/b]", markup=True)
            lbl.shorten = True

            if "START" in self.act_tests[screen]["screens"]:
                ldc = Factory.DGLabelAS(text=self.act_tests[screen]["screens"]["START"]["label"])
                ldc.shorten = True
            else:
                ldc = Factory.DGASLabel()
            btn = Factory.DGButton(text="Open", size_hint_x=0.2)
            btn.bind(on_release=partial(self.btn_act_test,screen))

            self.tabtest.ids.act_list.add_widget(lbl)
            self.tabtest.ids.act_list.add_widget(ldc)
            self.tabtest.ids.act_list.add_widget(btn)

            counter += 1


    def btn_act_test(self, btn_id, *largs):
        '''
        Called when an actuator_test is pressed on
        '''
        if btn_id not in self.act_tests:
            return

        if self.act_test_active:
            return
        
        self.act_test_active = True
        self.act_test_has_steps = False

        self.mi.act.set_up(btn_id, self.act_tests[btn_id], self.tree["ECU"][self.active_ecu])
        ret = self.mi.act.init_test()
        
        if ret["STATUS"] == "OK" or ret["STATUS"] == "OKSTEP":
            # offer user button to START          
            self.act_pp = Factory.ActPopup()

            # labels
            if "START" in self.act_tests[btn_id]["screens"]:
                self.act_pp.ids.user_status_val.text = self.act_tests[btn_id]["screens"]["START"]["label"]
            else:
                self.act_pp.ids.user_status_val.text = self.mi.trs.ui("actstart")

            self.act_pp.ids.user_info_val.text = self.act_tests[btn_id]["title"]
            
            if ret["STATUS"] == "OKSTEP":
                self.act_test_has_steps = True
                self.act_pp.ids.user_type_val.text = "Stepped, " + str(self.act_tests[btn_id]["type"]).capitalize()
            else:
                self.act_test_has_steps = False
                self.act_pp.ids.user_type_val.text = str(self.act_tests[btn_id]["type"]).capitalize()

            # buttons -> EXIT disabled / START enabled
            self.act_pp.ids.btn_left.disabled = False
            self.act_pp.ids.btn_left.text = self.mi.trs.ui("exit")
            self.act_pp.callback_left = self.act_pp.dismiss
            self.act_pp.ids.btn_right.disabled = False
            self.act_pp.ids.btn_right.text = self.mi.trs.ui("start")
            self.act_pp.callback_right = self.act_test_start
            self.act_pp.open()

        elif ret["STATUS"] == "ASK":
            self.log("Act request for parameters: " + str(ret))
            # ask user to choose
            if self.get_setting("user_mode") < self.mi.bmb.USER_MODE_EXPERIMENTAL:
                self.mi.alert("actpriverr")
            #self.act_pp = Factory.ActInfo()Unex
        
        else:
            self.mi.alert(["acterr", ret["STATUS"]])
        
        self.act_test_active = False


    def act_test_start(self, *largs):
        '''
        Handle the user clicking START on the popup
        '''
        self.act_pp.ids.btn_right.disabled = True
        self.act_pp.ids.btn_left.disabled = True

        self.mi.load(self.mi.act.begin_test, self.act_test_check)


    def act_test_stop(self, *largs):
        '''
        User asks to stop an actuator test
        '''
        self.act_pp.ids.btn_right.disabled = True
        self.mi.load(self.mi.act.stop_test, self.act_test_check)


    def act_test_check(self, stat, *largs):
        '''
        Handle the test start returning (test is underway, or ECU rejected it)
        '''
        if stat["STATUS"] == "OK":
            pl = stat["PAYLOAD"]
            typ = pl["type"]
            lbl = pl["label"]

            self.act_pp.ids.user_type_val.text = str(typ).capitalize()
            self.act_pp.ids.user_status_val.text = str(lbl)

            # errors on ECU appear here
            if typ == "INPROGRESS" and "INPROGRESS" in self.act_tests[self.mi.act.active_test]["screens"]:
                self.act_pp.ids.user_info_val.text = self.act_tests[self.mi.act.active_test]["screens"]["INPROGRESS"]["label"]
                self.act_pp.ids.btn_right.disabled = False
                self.act_pp.ids.btn_right.text = self.mi.trs.ui("stop")
                self.act_pp.callback_right = self.act_test_stop
                # schedule get status manually
                Clock.schedule_once(partial(self.mi.load, self.mi.act.get_status, self.act_test_check), 1)

            elif (typ == "STOPPED" or typ == "ENDED") and "ENDOK" in self.act_tests[self.mi.act.active_test]["screens"]:
                self.act_pp.ids.user_info_val.text = self.act_tests[self.mi.act.active_test]["screens"]["ENDOK"]["label"]
                self.act_pp.ids.btn_left.disabled = False
                self.act_pp.ids.btn_right.disabled = True

            elif (typ == "NOTSTARTED" or typ == "PROBLEM") and "ENDKO" in self.act_tests[self.mi.act.active_test]["screens"]:
                self.act_pp.ids.user_info_val.text = self.act_tests[self.mi.act.active_test]["screens"]["ENDKO"]["label"]
                self.act_pp.ids.btn_left.disabled = False
                self.act_pp.ids.btn_right.disabled = True
            else:
                self.act_pp.ids.user_info_val.text = self.mi.trs.ui(("actnoinfo"))
                self.act_pp.ids.btn_left.disabled = False
                self.act_pp.ids.btn_right.disabled = True
        
        else:
            # errors in software appear here
            self.act_pp.ids.user_status_val.text = stat["STATUS"]
            self.act_pp.ids.btn_left.disabled = False
            self.act_pp.ids.btn_right.disabled = True


    ##############################################

    #       FAULT CODES

    ##############################################

    def dtc_load(self, *largs):
        '''
        Load a fault tree into the UI
        '''
        if self.tree["ECU"][self.active_ecu]["FAULTS"] == -1:
            self.tree["ECU"][self.active_ecu]["FAULTS"] = 0

        for ecu in self.nav_widg:
            if ecu[2] == self.active_ecu:
                ecu[1].text = str(self.tree["ECU"][self.active_ecu]["FAULTS"])

        self.ids.tab_faults.clear_widgets()
        faults = self.tree["ECU"][self.active_ecu]["FAULT_TREE"]
        # factory an accordion box
        self.fault_scr = Factory.FaultAccord()
        self.fault_scr.ppt = self
        self.tv = TreeView(hide_root=True)
        
        self.fault_scr.ids.fault_tree.add_widget(self.tv)
        self.tv.size_hint_y = None
        self.tv.bind(minimum_height = self.tv.setter('height'))

        for fault in faults:
            if "dtclabel" not in faults[fault] or "print_code" not in faults[fault]:
                self.log("DTCs weren't processed correctly; received: " + str(faults[fault]))
                continue

            # UDS has a standardised way to translate them
            if self.tree.get("PROT", self.mi.tlc.PROTOCOL_KWP) == self.mi.tlc.PROTOCOL_UDS:
                dtc_print_code = self.mi.bmb.translate_dtc_prefix(faults[fault]["print_code"])
            else:
                dtc_print_code = faults[fault]["print_code"]

            mn = TreeViewLabel(text=f"[b]{dtc_print_code}[/b] " + str(faults[fault]["dtclabel"]), markup=True)
            mn.font_name = self.mi.root_font
            mn.color = [0, 0, 0, 1]
            self.tv.add_node(mn)
            ptr = Factory.FaultBox()
            self.tv.add_node(ptr, mn)

            # Characterisations
            if "chars" in faults[fault]:
                for char in faults[fault]["chars"]:
                    dat = Factory.DGLabel(text=char["title"], halign="left",padding_x=20)
                    val = Factory.DGLabel(text=char["value"][0])
                    ptr.ids.fault_chars.add_widget(dat)
                    ptr.ids.fault_chars.add_widget(val)
                if len(faults[fault]["chars"]) == 0:
                    ptr.ids.faultchar.text = ""
            else:
                ptr.ids.faultchar.text = "No characterisation"

            # Freeze frame
            if "fframe" in faults[fault]:
                for prm in faults[fault]["fframe"]:
                    # characterisation to prm
                    lbl = faults[fault]["fframe"][prm]["LABEL"]
                    vlu = faults[fault]["fframe"][prm]["VALUE"]
                    dat = Factory.DGLabel(text=lbl, halign="left",padding_x=20)
                    val = Factory.DGLabel(text=vlu)
                    ptr.ids.fault_freeze.add_widget(dat)
                    ptr.ids.fault_freeze.add_widget(val)
                    self.log("Adding " + str(lbl) + " : " + str(vlu))

                if len(faults[fault]["fframe"]) == 0:
                    ptr.ids.faultfreeze.text = "No freeze frame data"
            else:
                ptr.ids.faultfreeze.text = ""

        self.ids.tab_faults.add_widget(self.fault_scr)


    def dtc_clear_all(self, *largs):
        '''
        Called when the user asks to clear all stored faults in the ECU
        '''
        self.mi.yesno("clearfaults",callbacky=partial(self.mi.load, partial(self.mi.glt.clear_and_refresh,self.tree["ECU"][self.active_ecu]), self.dtc_cleared_return))


    def dtc_export_all(self, fname, *largs):
        '''
        Called when the user asks to export all fault data to text
        '''
        if not fname:
            # user cancelled
            return

        self.log("Export to : " + str(fname))
        try:
            out = open(fname, 'w')
            out.write(self.mi.appname + ": " + self.mi.version + "\n")
            out.write(self.ids.stat_veh.text + "\n")
            out.write(self.ids.stat_vin.text + "\n")
            out.write(self.ids.stat_ecu.text + "\n")
            out.write("Export: " + str(datetime.datetime.now()) + "\n")
            out.write("=======================================" + "\n")
            out.write("\n")
            flts = self.tree["ECU"][self.active_ecu]["FAULT_TREE"]

            for flt in flts:
                out.write( str(flts[flt]["print_code"]) + ": " + str(flts[flt]["dtclabel"]) + "\n")
                out.write("-----------------------------------------" + "\n")

                # Characterisations
                if "chars" in flts[flt]:
                    out.write("Characterisations" + "\n")
                    for char in flts[flt]["chars"]:
                        out.write(str(char["title"]) + ":       " + str(char["value"][0]) + "\n")
                else:
                    out.write("No characterisation data available\n")

                if "fframe" in flts[flt]:
                    if len(flts[flt]["fframe"]) > 0:
                        out.write("\n")
                        out.write("Freeze Frame" + "\n")

                        # Freeze frame
                        for prm in flts[flt]["fframe"]:
                            out.write(str(flts[flt]["fframe"][prm]["LABEL"]) + ":       " + str(flts[flt]["fframe"][prm]["VALUE"]) + "\n")
                    else:
                        out.write("No freeze frame data available\n")
                else:
                    out.write("No freeze frame data available\n")

                out.write("\n")
                out.write("\n")

            self.mi.alert("exporteddone")

        except Exception as error:
            self.log(str(error))
            self.mi.alert("exportedundone")
            return

    def dtc_refresh(self, *largs):
        '''
        Re-request fault information from the ECU
        '''
        self.mi.glt.prot = self.tree.get("PROT", self.mi.tlc.PROTOCOL_KWP)
        self.waitpp.set_status(self.mi.trs.ui("reading_faults"))
        self.waitpp.open()
        self.mi.load(partial(self.mi.glt.scan_ecu_faults, self.tree["ECU"][self.active_ecu]), self.dtc_load_return)


    def dtc_load_return(self, tree, *largs):
        Clock.schedule_once(partial(self.dtc_loaded, tree))


    def dtc_loaded(self, tree, *largs):
        '''
        Handle the DTC load thread returning
        '''
        self.waitpp.dismiss()
        
        if not tree or tree["FAULTS"] == "":
            self.mi.alert("dtcrefreshfail")
        else:
            self.tree["ECU"][self.active_ecu]["FAULTS"] = tree["FAULTS"]
            self.tree["ECU"][self.active_ecu]["FAULT_TREE"] = tree["FAULT_TREE"]
            self.dtc_load()


    def dtc_cleared_return(self, tree, *largs):

        Clock.schedule_once(partial(self.dtc_cleared, tree))


    def dtc_cleared(self, tree, *largs):
        '''
        Called when the thread clearing DTCs returns
        '''
        if not tree:
            self.mi.alert("dtcclearfail")
            return
        
        else:
            self.mi.alert("dtcclearok")
            self.tree["ECU"][self.active_ecu]["FAULTS"] = tree["FAULTS"]
            self.tree["ECU"][self.active_ecu]["FAULT_TREE"] = tree["FAULT_TREE"]
            self.dtc_load(tree)


    ###########################################

    #    PROCEDURES

    ###########################################


    def thr_prc_return(self, start_ecu, result, *largs):
        '''
        Handles the thread loading procedures returning
        '''
        if not result:
            self.log("No procedures returned for this ECU")
            return

        if start_ecu != self.tree["ECU"][self.active_ecu]["ECUNAME"]:
            self.log("ECU view changed during load process, abandoning data")
            return

        self.procedures = {}

        for procedure in result:
            self.procedures[procedure["prc_id"]] = procedure
        
        Clock.schedule_once(self.prc_update_ui)


    def prc_update_ui(self, *largs):
        '''
        Load procedures list into the UI
        We know that data is OK because it was checked previously
        '''
        self.tabpro = Factory.ActTestBox()
        self.tabpro.ppt = self
        self.ids.tab_proc.add_widget(self.tabpro)

        self.log("Loading " + str(len(self.procedures)) + " procedures")

        for procedure in self.procedures:
            lbl = Factory.DGLabelAS(text="[b]" + str(self.procedures[procedure]["label_en"]) + "[/b]", markup=True)
            lbl.shorten = True

            ldc = Factory.DGLabelAS(text=self.procedures[procedure]["help_en"])
            ldc.shorten = True

            btn = Factory.DGButton(text="Open", size_hint_x=0.2)
            btn.bind(on_release=partial(self.btn_start_proc, procedure))

            self.tabpro.ids.act_list.add_widget(lbl)
            self.tabpro.ids.act_list.add_widget(ldc)
            self.tabpro.ids.act_list.add_widget(btn)      
        

    def btn_start_proc(self, proc_id: int, *largs):
        '''
        Open a specified procedure
        '''

        # get data and set up diag_procedure
        self.active_procedure_data = self.mi.bmb.get_single_procedure(proc_id)
        start_step = self.mi.prc.set_tree(self.tree["ECU"][self.active_ecu], self.active_procedure_data)
        
        if not start_step:
            return False

        # offer user button to START          
        self.proc_popup = Factory.ActPopup()

        self.proc_popup.title = "Procedure"

        # show text from first step
        self.proc_popup.ids.user_info_val.text = self.active_procedure_data[start_step]["label"]
        self.proc_popup.ids.user_status_val.text = self.mi.trs.ui("ready")

        self.log("Preparing for procedure: " + str(proc_id) + ": " + self.active_procedure_data[start_step]["label"])

        # will fail after the first time, but don't care
        try:
            self.proc_popup.ids.content_frame.remove_widget(self.proc_popup.ids.user_type_lbl)
            self.proc_popup.ids.content_frame.remove_widget(self.proc_popup.ids.user_type_val)
        except:
            pass

        # remove any previous boxes
        for entry in self.proc_variable_widgets:
            self.proc_popup.ids.content_frame.remove_widget(entry[0])
            self.proc_popup.ids.content_frame.remove_widget(entry[1])
        self.proc_variable_widgets = {}

        # buttons -> EXIT disabled / START enabled
        self.proc_popup.ids.btn_left.disabled = False
        self.proc_popup.ids.btn_left.text = self.mi.trs.ui("exit")
        self.proc_popup.callback_left = self.proc_popup.dismiss
        self.proc_popup.ids.btn_right.disabled = False
        self.proc_popup.ids.btn_right.text = self.mi.trs.ui("start")
        self.proc_popup.callback_right = partial(self.proc_next, self.active_procedure_data[start_step]["next_step"])
        self.proc_popup.open()


    def proc_next(self, next_step: int, *largs):
        '''
        Actually start the procedure
        '''
        
        if self.active_procedure_data[next_step]["category"] == self.mi.prc.category_ids["normal"]:

            # check if we need variables
            if "variables" in self.active_procedure_data[next_step]:
                for variable in self.active_procedure_data[next_step]["variables"]:
                    varname = variable
                    vardesc = self.active_procedure_data[next_step]["variables"][variable]["label"]
                    vartype = self.active_procedure_data[next_step]["variables"][variable]["type"]

                    lbl = Factory.DGLabelW(text = vardesc)

                    if vartype == "I":
                        txt = FloatInput(multiline = False)
                    elif vartype == "R":
                        txt = HexInput(multiline = False)

                    self.proc_popup.ids.content_frame.add_widget(lbl)
                    self.proc_popup.ids.content_frame.add_widget(txt)
                    self.proc_variable_widgets[varname] = (txt, lbl)

                self.proc_popup.callback_right = partial(self.proc_with_values_next, next_step)

            else:
                self.log("Proceeding to step " + str(next_step) + " with no variables")
                self.proc_popup.ids.user_info_val.text = self.active_procedure_data[next_step]["label"]
                self.proc_popup.ids.user_status_val.text = self.mi.trs.ui("inprogress")
                self.proc_popup.ids.btn_right.disabled = True
                self.mi.load(self.mi.prc.do_step(next_step, None, self.proc_callback))

        else:
            self.log("Don't know how to move to step category " + str(self.active_procedure_data[next_step]["category"]))


    def proc_with_values_next(self, next_step: int, *largs):
        '''
        Called when the user has filled in the value boxes
        '''
        variables = {}
        self.proc_popup.ids.btn_right.disabled = True

        # get values and remove the boxes
        for entry in self.proc_variable_widgets:
            variables[entry] = self.proc_variable_widgets[entry][0].text
            self.proc_popup.ids.content_frame.remove_widget(self.proc_variable_widgets[entry][0])
            self.proc_popup.ids.content_frame.remove_widget(self.proc_variable_widgets[entry][1])
        self.proc_variable_widgets = {}

        self.proc_popup.ids.user_status_val.text = self.mi.trs.ui("inprogress")
        self.proc_popup.ids.user_info_val.text = self.active_procedure_data[next_step]["label"]
        self.log("Proceeding to step " + str(next_step) + " with variables: " + str(variables))

        self.mi.load(partial(self.mi.prc.do_step, next_step, variables, self.proc_callback))

    
    def proc_callback(self, status: bool, message: str = "", next_step: int = None, *largs):
        '''
        Passed to the diag_procedures library, called when status changes
        or to move to the next step
        '''

        self.proc_popup.ids.user_status_val.text = message

        # move to next step
        if status and next_step != None:
            #self.proc_popup.ids.user_info_val.text = self.active_procedure_data[next_step]["label"]
            self.proc_popup.ids.btn_right.disabled = False
            self.proc_popup.callback_right = partial(self.proc_next, next_step)

        if status and next_step == None:
            self.log("Valid status but no next step provided")

        else:
            self.log("Procedure operation exited with failure")
            return False
                


    ###########################################

    #    TELECODING

    ###########################################
    
    def load_tlcd(self, *largs):
        '''
        Load telecoding into the UI

        This is kivy_scheduled by the callback that's triggered when the thread
        loading the data from the database is complete.

        This loads a fairly "safe" set of telecoding parameters, i.e. the ones
        we can be sure actually are right
        '''
        
        self.adapter_signal = "free"

         # in case the ECU changed before we returned the thread
        if self.tlcd_start_ecu != self.active_ecu:
            self.log(str(self.tlcd_start_ecu) + " is not the same as " + str(self.active_ecu))
            self.waitpp.dismiss()  
            return

        self.log("Loading in telecoding")

        self.changes = {}
        self.tlcd_lookup = {}
        self.tlcd_export_cache = {}

        # create the tab view
        self.tlcd_view = Factory.TlcdList()
        self.ids.tab_tlcd.add_widget(self.tlcd_view)
        self.tlcd_view.ppt = self
        self.tlcd_tabs = []

        self.tlcd_zones = {}
        unread_params = 0
        ui_params = len(self.tlcd_ui)

        # configure tlc object
        if ui_params > 0:
            self.log("Scan telecoding parameters: " + str(ui_params))

            for param in self.tlcd_ui:
                if param not in self.mi.tlc.params:
                    # remove it
                    self.log("Deleted because it has no value: " + str(param))
                    unread_params += 1
                    if param in self.tlcd_lookup:
                        self.log("Lost reference to parameter " + str(param) + " so removed from UI")
                        self.tlcd_view.ids.tab_tlcd.ids[zone].ids.tlcd_page.data.pop(self.tlcd_lookup[param][0])
                        self.tlcd_lookup.pop(param, None)
                    continue

                if len(self.tlcd_ui[param]["read"]) > 0:
                    zone = str(self.tlcd_ui[param]["read"][0]["zone"][:2])
                else:
                    self.log("Parameter " + str(param) + " has no valid zones")
                    continue

                if zone == "":
                    self.log("Invalid zone specified in " + str(param))
                    continue

                if zone not in self.tlcd_zones:
                    # need to make a new sub tab
                    ntab = Factory.TlcdTabView()
                    ntab.id = zone
                    ntab.text = zone
                    ntab.tab_height = 20
                    self.tlcd_view.ids.tab_tlcd.add_widget(ntab)
                    self.tlcd_zones[zone] = ntab
                
                if param not in self.tlcd_lookup:
                    entry = { "callback": self.tlcd_spin_chg,
                              "callhelp": partial(self.tlcd_help,param),
                              "txt" : self.mi.tlc.params[param],
                              "use" : 0,
                              "param" : param,
                              "home" : self
                            }

                    lbl = self.tlcd_ui[param]["label"]
                    vals = []

                    if lbl == "":
                        # -- Show unnamed parameters with their param_name
                        lbl = param

                    if self.tlcd_ui[param]["states"] == []:
                        # -- Just a textbox
                        entry["use"] = 1 #textbox

                    else:
                        # -- Add options
                        for stat in self.tlcd_ui[param]["states"]:
                            vals.append(stat["label"])

                        if self.mi.tlc.params[param] in vals:
                            if len(vals) == 2:
                                if vals[0].upper() in self.TLCD_NEG or vals[0].upper() in self.TLCD_POS:
                                    if vals[1].upper() in self.TLCD_POS or vals[1].upper() in self.TLCD_NEG:
                                        entry["use"] = 2 # switch

                            entry["txt"] = self.mi.tlc.params[param]

                        else:
                            self.log("WARNING: The value read from the ECU '" + str(self.mi.tlc.params[param]) + "' was not matched by any available value. Will not be displayed")
                            continue

                    # position in data, param value according to ECU, zone ID
                    self.tlcd_lookup[param] = {"pos" : len(self.tlcd_zones[zone].ids.tlcd_page.data), "og": self.mi.tlc.params[param], "view": zone, "zone": str(self.tlcd_ui[param]["read"][0]["zone"]) }

                    entry["text_lbl"] = lbl
                    entry["values"] = vals

                    self.tlcd_zones[zone].ids.tlcd_page.data.append(entry)

                    # cache for export if user asks
                    self.tlcd_export_cache[param] = [ zone, param, lbl, self.mi.tlc.params[param] ]

                    self.tlcd_zones[zone].text = zone + " (" + str(len(self.tlcd_zones[zone].ids.tlcd_page.data)) + ")"
                    
                else:
                    ix = self.tlcd_lookup[param]
                    self.tlcd_zones[zone].ids.tlcd_page.data[ix["pos"]]["txt"] = self.mi.tlc.params[param]
                    
                    # update export cache
                    try:
                        self.tlcd_export_cache[param][3] = self.mi.tlc.params[param]
                    except:
                        self.log("Internal error: parameter " + str(param) + " was not found in export cache")

            shown_parameters = ui_params - unread_params
            self.log("Telecoding actually rendered " + str(shown_parameters) + " parameters")

        self.waitpp.dismiss()      
        #Clock.schedule_once(self.tlcd_force_refresh)


    def tlcd_force_refresh(self, *largs):
        for zone in self.tlcd_zones:
            self.tlcd_zones[zone].ids.tlcd_page.refresh_from_viewport()   
        #Clock.schedule_once(self.tlcd_force_refresh) 
                        
            
    def tlcd_spin_chg(self, ref, *largs):
        '''
        Called when the user changes a tlcd spinner
        # TODO: Implement color-recognition of OG and new value/changed parameters
        '''        
        key = self.tlcd_lookup[ref]
        self.tlcd_zones[key["view"]].ids.tlcd_page.data[key["pos"]]["txt"] = largs[0]  

        # param
        if ref not in self.tlcd_changes:
            if key["og"] != largs[0]:
                self.tlcd_changes[ref] = { "old" : key["og"], "new" : largs[0], "zone": key["zone"] }
            else:
                # flagged as change but not actually a valid one
                return
        else:
            if self.tlcd_changes[ref]["old"] == largs[0]:
                # user has changed back to existing setting, delete change
                self.tlcd_changes.pop(ref, None)
            else:
                self.tlcd_changes[ref]["new"] == largs[0]
      
        self.tlcd_view.ids.txt_changes.text = str(len(self.tlcd_changes)) + self.mi.trs.ui("tlcdchanges")  
        self.log("Staged change frame " + str(ref )+ " from OG " + str(key["og"]) + " to " + str(largs[0]))


    def tlcd_help(self, key="", *largs):
        '''
        Show the help text for the parameter, if available
        '''
        if key in self.tlcd_ui:
            hlp = self.tlcd_ui[key]["help"]
            if hlp == "":
                hlp = self.mi.trs.ui("nohelpforthis")
            self.tlcd_view.ids.help_box.text = "[b]" + str(key) + ":[/b] " + hlp.replace("\\n", "\n")
        else:
            self.tlcd_view.ids.help_box.text = self.mi.trs.ui("nohelpforthis")

    
    def tlcd_refresh(self, *largs):
        '''
        Attempt to re-load data from the ECU
        '''
         # in case the ECU changed before we returned the thread
        self.tlcd_start_ecu = self.active_ecu
        self.waitpp.open()
        self.mi.load(partial(self.mi.tlc.read_all_configuration, self.thr_tlcd_update),self.thr_tlcd_done)


    def thr_act_tests_sch(self, tree, *largs):
        '''
        Handles the thread loading actuator tests returning
        '''
        self.act_tests = tree
        Clock.schedule_once(self.load_act_tests)


    def thr_tlcd_sch(self, resp, *largs):
        '''
        Handles the thread loading telecoding returning
        This means we can load the actual data from the ECU
        '''
        if not resp:
            Clock.schedule_once(self.waitpp.dismiss)
            Clock.schedule_once(partial(self.mi.alert, "tlcdempty", "alerttitle", None))
            return

        self.tlcd_ui = resp

        protocol = self.tree.get("PROT", self.mi.tlc.PROTOCOL_KWP)
        self.mi.tlc.set_up(self.tree["ECU"][self.active_ecu], self.tlcd_ui, vin = self.tree["VIN"], prot = protocol)
        self.mi.load(partial(self.mi.tlc.read_all_configuration, self.thr_tlcd_update),self.thr_tlcd_done)


    def thr_tlcd_update(self, zone, *largs):
        '''
        '''
        Clock.schedule_once(partial(self.thr_tlcd_update_ui,zone))


    def thr_tlcd_update_ui(self, zone, *largs):
        '''
        '''
        self.waitpp.set_status(f"[i]{self.mi.trs.ui('readingzone')}{zone}...[/i]")


    def thr_tlcd_done(self, *largs):
        '''
        Handles the thread reading ECU memory zones returning
        '''
        if largs[0] == False:
            Clock.schedule_once(self.waitpp.dismiss)
            Clock.schedule_once(partial(self.mi.alert, "tlcdreadfail", "alerttitle", None))
        else:
            self.tlcd_loaded = True
            Clock.schedule_once(self.load_tlcd)


    def tlcd_ecu_write(self, *largs):
        '''
        User has confirmed they want us to save the changes to the ECU memory
        '''
        if len(self.tlcd_changes) == 0:
            self.mi.alert("nochangetowrite")
            return

        for change in self.tlcd_changes:
            self.log(f"Will update: {change} from {self.tlcd_changes[change]['old']} to {self.tlcd_changes[change]['new']}")

        self.waitpp.open()
        self.mi.load(partial(self.mi.tlc.write_change_list, self.tlcd_changes, self.tlcd_opt_callback), self.tlcd_ecu_write_done)


    def tlcd_opt_callback(self, options, callback, *largs):
        '''
        Open a popup asking the user to choose from a list of options
        '''
        # must schedule because this is called by a foreign thread
        Clock.schedule_once(partial(self.mi.user_opt, "choosetlcdframe", options, callback, callback))


    def tlcd_ecu_write_ui(self, status: dict, *largs):
        '''
        Update the UI to an ECU write returning

        status is a dictionary

        [zone_name] => ( result_string, read_service_frid )
        '''

        total_response = 0
        traceability = 0
        total_response_string = ""

        for zone, result in status.items():
            if result[0] == TelecodeResult.OK_AUTH:
                self.log(f"Need to write traceability for {zone}")
                traceability += 1

            elif result[0] != TelecodeResult.OK:
                self.log(f"Zone write failed => {zone} = {result}")
                try:
                    total_response_string = f"{zone} => {result[0].name}\n"
                except Exception:
                    total_response_string = f"{zone} => {result}\n"
                total_response += 1

        if total_response == 0:
            self.mi.alert("tlcddone")

        elif total_response < len(status):
            self.mi.alert("The write was partially successful:\n" + total_response_string)

        else:
            self.mi.alert("All writes failed to complete:\n" + total_response_string)

        # reset the changes view
        self.tlcd_changes = {}
        self.tlcd_view.ids.txt_changes.text = str(len(self.tlcd_changes)) + self.mi.trs.ui("tlcdchanges")  

        read_back_zones = list(status.keys())

        # ask to write traceability if needed
        if (traceability > 0) & (total_response == 0):
            #self.mi.yesno("tlcd_need_trace", callbacky = partial(
            self.tlcd_ecu_write_traceability(read_back_zones)
        else:
            self.tlcd_read_back(read_back_zones)


    def tlcd_read_back(self, zones: list, *largs):
        '''
        Read back the zones given by zones
        '''
        self.log(f"Reading back zones: {zones}")
        self.waitpp.open()
        self.waitpp.set_status("reading back affected zones...")
        self.mi.load(partial(self.mi.tlc.read_memory_zones, zones), self.thr_tlcd_done)


    def tlcd_ecu_write_traceability(self, read_after_zones: list, *largs):
        '''
        Trigger writing of the traceability zone
        '''
        self.waitpp.open()
        self.mi.load(partial(self.mi.tlc.do_write_secure_telecoding), partial(self.tlcd_ecu_trace, read_after_zones))


    def tlcd_ecu_trace(self, read_after_zones: list, result, *largs):
        '''
        Called when writing the traceability zone returns
        '''
        Clock.schedule_once(self.waitpp.dismiss)
        self.log(f"ECU traceability zone returned {result} on zones {read_after_zones}")
        if result in (TelecodeResult.OK, TelecodeResult.OK_AUTH):
            Clock.schedule_once(partial(self.mi.alert, "tracedone"))
        else:
            Clock.schedule_once(partial(self.mi.alert, "tracefail"))

        if read_after_zones is not None and len(read_after_zones) > 0:
            Clock.schedule_once(partial(self.tlcd_read_back, read_after_zones))
        

    def tlcd_ecu_write_done(self, status, *largs):
        '''
        Handles the return of the background function writing to the ECU
        '''
        Clock.schedule_once(partial(self.tlcd_ecu_write_ui, status))
            

    def tlcd_export_config(self, fname, *largs):
        '''
        Export all configuration data for this ECU to a backup file (csv)
        '''      
        if not self.tlcd_loaded:
            return

        if len(self.tlcd_export_cache) == 0:
            self.mi.alert("No parameters to export")
        
        fileobj = open(fname, "w", newline = '')
        csvobj = csv.writer(fileobj, delimiter=' ', quotechar='|', quoting=csv.QUOTE_MINIMAL)

        for line in self.tlcd_export_cache:
            csvobj.writerow(line)

        fileobj.close()

        self.mi.alert("Exporting telecoding configuration done")


    def tlcd_export_do(self, fname, *largs):
        pass


    ##############################################

    #       LIVE DATA

    ##############################################

    def ident_refresh(self, *largs):
        '''
        Re-read identity information from the ECU
        '''
        self.mi.load(self.mi.lidata.read_ecu_ident, self.ident_response)


    def ident_export_all(self, fname, header=True):
        '''
        Export ECU identity information
        '''

        if not fname:
            # user cancelled
            return

        fname = fname + ".txt"
        self.log("Export to : " + str(fname))

        try:
            out = open(fname, 'w')
        except Exception:
            self.mi.alert("Unable to open file path: " + str(fname))
            return

        if "IDENTIFICATION" not in self.tree["ECU"][self.active_ecu]:
            self.mi.alert("You must read the identification data before trying to export it")
            return

        if header:
            out.write("ECU Identification data\n")
            out.write(self.mi.appname + ": " + self.mi.version + "\n")
            out.write(self.ids.stat_veh.text.replace("[b]", "").replace("[/b]", "") + "\n")
            out.write(self.ids.stat_vin.text.replace("[b]", "").replace("[/b]", "") + "\n")
            out.write(self.ids.stat_ecu.text.replace("[b]", "").replace("[/b]", "") + "\n")
            out.write("Export: " + str(datetime.datetime.now()) + "\n")

        out.write("=======================================" + "\n")
        out.write("\n")

        for parm in self.tree["ECU"][self.active_ecu]["IDENTIFICATION"]:
            out.write(self.tree["ECU"][self.active_ecu]["IDENTIFICATION"][parm]["label"] + ": " + self.tree["ECU"][self.active_ecu]["IDENTIFICATION"][parm]["value"])
            out.write("\n")

        self.mi.alert("exporteddone")


    def ident_response(self, *largs):
        '''
        Handles the return of the thread reading identification from the ECU
        '''
        Clock.schedule_once(self.ident_update)

    
    def ident_update(self, *largs):
        '''
        Update the identification GUI
        '''
        self.ident_data = self.mi.lidata.get_ident()

        if not self.ident_data:
            self.mi.alert("lidataidenterr")
            self.log("Failed to read identification from ECU")
            return False

        if "IDENTIFICATION" not in self.tree["ECU"][self.active_ecu]:
            self.tree["ECU"][self.active_ecu]["IDENTIFICATION"] = {}
        
        for param in self.ident_data:
            if param in self.id_ptr:
                self.id_ptr[param].text = self.ident_data[param]["VALUE"]

                if param not in self.tree["ECU"][self.active_ecu]["IDENTIFICATION"]:
                    self.tree["ECU"][self.active_ecu]["IDENTIFICATION"][param] = {"label": param }

                self.tree["ECU"][self.active_ecu]["IDENTIFICATION"][param]["value"] = self.ident_data[param]["VALUE"]

    
    def lidata_logging_toggle(self, btn, *largs):
        '''
        Manage starting/stopping of logging and file headers
        '''

        if self.lidata_logging:
            self.lidata_logptr.close()
            self.lidata_logging = False
            btn.text = self.mi.trs.ui("startlog")
            
        else:
            if not self.lidata_active:
                self.mi.alert("lidatanotactive")
                return

            if self.lidata_logselonly and len(self.lidata_selected) == 0:
                self.mi.alert("lidatamustselect")
                return

            fname = self.mi.appname + "_livedata_" + str(self.mi.bmb.millis()) + ".csv"

            direc = self.get_setting("user_dir") + self.get_setting("vehlog_dir")
            if not os.path.isdir(direc):
                os.makedirs(direc)
            log_path = direc + fname
            
            try:
                self.lidata_logptr = open(log_path, "w")
            except Exception:
                self.mi.alert("Unable to open file path: " + str(log_path))
                self.log("Unable to open log data file path")
                return False

            self.log("Logging live data to " + log_path)

            self.lidata_csvptr = csv.writer(self.lidata_logptr, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL)
            self.lidata_csvptr.writerow([self.mi.appname, 
                                         self.mi.version, 
                                         self.tree["VEH"], 
                                         self.tree["VIN"], 
                                         self.get_setting("adapter_type"), 
                                         self.tree["ECU"][self.active_ecu]["ECUID"], 
                                         self.tree["ECU"][self.active_ecu]["ECUVEID"]])
            
            if self.optdown.ids.logall.ids.chk.active:
                # log ALL data
                self.lidata_log = list(self.lidata_store.keys())
                self.lidata_csvptr.writerow(list(self.lidata_store.keys()))
            else:
                # log SELECTED data
                self.lidata_log = self.lidata_selected
                self.lidata_csvptr.writerow(self.lidata_selected)

            self.lidata_logging = True
            btn.text = self.mi.trs.ui("stoplog")


    def lidata_update(self, *largs):
        '''
        Handles the reading thread notifying of updated data
        Simple translator function from one thread to another
        '''
        # Wait until we get the semaphore
        if self.mi.lidata.access_flag:
            Clock.schedule_once(self.lidata_update)
            return

        self.mi.lidata.access_flag = True
        ret = self.mi.lidata.get_tree()
        self.mi.lidata.access_flag = False

        if not ret:
            # sometimes we will get a read return after disabling live data (because threading and semaphores)
            # here we avoid showing an error message unless its an unintentional end of session
            if self.lidata_active:
                self.lidata_view.ids.lidata_comms.ids.swit.active = False
                Clock.schedule_once(partial(self.mi.alert,"lidatafail","alerttitle", None))
        else:
            self.lidata_live = ret
            Clock.schedule_once(self.lidata_update_screen)


    def lidata_update_screen(self, *largs):
        '''
        Takes the data from the ECU and displays it
        Also write to the logfile if we are logging
        '''

        logrow = {}
        logrol = []
        changes = 0

        for parm in self.lidata_live:
            if parm not in self.lidata_store:
                self.lidata_store[parm] = ""

            # only update if the value changed
            if self.lidata_live[parm]["VALUE"] != self.lidata_store[parm]:
                if parm not in self.lidata_ptr:
                    #self.log("Missing parameter " + str(parm))
                    continue

                # get the zone it's in
                if self.lidata_live[parm]["ZONE"] not in self.lidata_view_zones:
                    continue

                # check the zone is visible
                if self.lidata_view.ids.tab_lidataz.current_tab.text != self.lidata_live[parm]["ZONE"][:2]:
                    continue

                changes += 1
                if self.lidata_ptr[parm] < len(self.lidata_view.ids.tab_lidataz.current_tab.ids.lidata_page.data):
                    if self.lidata_live[parm]["STATUS"] == "HEXFIX":
                        self.lidata_view.ids.tab_lidataz.current_tab.ids.lidata_page.data[self.lidata_ptr[parm]]["text_val"] = str(self.lidata_live[parm]["VALUE"]) + " (!)"
                    else:
                        self.lidata_view.ids.tab_lidataz.current_tab.ids.lidata_page.data[self.lidata_ptr[parm]]["text_val"] = self.lidata_live[parm]["VALUE"]         
                    
                # store must mirror whats on the UI
                self.lidata_store[parm] = self.lidata_live[parm]["VALUE"]
            
            if self.lidata_logging:
                try:
                    f = self.lidata_log.index(parm)
                    logrow[f] = self.lidata_live[parm]["VALUE"]
                except ValueError:
                    continue
                    
        if self.lidata_logging:
            ctr = 0
            logrol.append(self.mi.bmb.millis())
            for index in logrow:
                if index == ctr:
                    logrol.append(logrow[index])
                else:
                    logrol.append("")
                ctr += 1
            
            if len(logrow) != len(self.lidata_log):
                self.log("Logging mismatch between array sizes - some parameters missed.")

            self.lidata_csvptr.writerow(logrol)
        
        if changes > 0:
            self.lidata_view.ids.tab_lidataz.current_tab.ids.lidata_page.refresh_from_data()


    def lidata_toggle(self, item, state):
        '''
        En/disable the thread reading data
        ''' 

        if self.lidata_active:
            self.lidata_view.ids.lidata_comms.disabled = True
            # non-blocking
            self.log("Terminating live data session")
            self.mi.lidata.stop()
            self.lidata_active = False
            self.lidata_view.ids.btn_log_toggle.disabled = True
            self.lidata_view.ids.lidata_comms.disabled = False
            self.log("Lidata deactivate")
            return True

        if state:
            self.lidata_view.ids.lidata_comms.disabled = True
            self.waitpp = WaitDialog()
            self.waitpp.open()
            self.mi.load(self.mi.lidata.start, self.lidata_toggle_response)     
            self.log("Lidata try activate")
            return

        self.log("Lidata event ignored")


    def lidata_toggle_response(self, success, *largs):
        '''
        Change the slider back to Off if starting the daemon failed
        '''
        Clock.schedule_once(partial(self.lidata_toggle_handler, success))

    
    def lidata_set_tab(self, zone, *largs):
        '''
        Tell the lidata reader to only request this zone
        '''
        self.mi.lidata.set_zone(zone)


    def lidata_toggle_handler(self, success, *largs):
        if not success: 
            self.lidata_view.ids.lidata_comms.state = "normal"
            self.lidata_view.ids.lidata_comms.disabled = False
            self.waitpp.dismiss()
            self.lidata_active = False
            self.mi.alert("lidataerr")
            self.log("lidata activate NOK")
            return
        else:
            self.lidata_view.ids.btn_log_toggle.disabled = False
            self.lidata_view.ids.lidata_comms.disabled = False
            self.lidata_active = True
            self.log("lidata activated OK")
            self.waitpp.dismiss()


    def lidata_resetview(self, *largs):
        '''
        Reset the viewport from showing only ticked items
        '''
        pass


    def lidata_show_selected(self, *largs):
        self.log("Live data show selected not implemented")


    def lidata_hide_selected(self, *largs):
        self.log("Live data hide selected not implemented")


    def lidata_selectcheck(self, ref, chk, *largs):
        '''
        ref - The PARNAME of the parameter that was checked
        chk - TRUE if its been checked, FALSE if not
        '''
        try:
            if chk and ref not in self.lidata_selected:
                self.lidata_selected.append(ref)
            elif not chk and ref in self.lidata_selected:
                self.lidata_selected.remove(ref)
        except:
            self.log("Unexpected error in Centre@selectcheck")
            return

    def lidata_log_selected(self, state, *largs):
        '''
        TRUE: Log only those ticked
        FALSE: Log everything
        '''
        self.lidata_logselonly = state
    
        


    
