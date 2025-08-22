from kivy.app import App
from kivy.properties import ObjectProperty, StringProperty, DictProperty
from kivy.uix.screenmanager import Screen
from kivy.clock import Clock
from kivy.factory import Factory

import json, os


class Setting(Screen):
    parent_scr = StringProperty()
    mi = ObjectProperty()
    waitpp = None

    def log(self, x):
        print("[SET] " + str(x))

    def __init__(self, **kwargs):
        '''
        Load settings from a file if it exists
        '''
        self.mi = App.get_running_app()

        self.settings = {
            "lngui" : "",
            "lngdiag" : "",
            "showhelp" : False,
            "autoload_tlcd" : False,
            "autoload_ident" : True,
            "user_mode" : self.mi.bmb.USER_MODE_ADVANCED,
            "user_dir" : "user/",
            "log_dir" : "log/",
            "discovery_dir" : "vehicles/",
            "vehlog_dir" : "trace/",
            "adapter_type" : ""
        }

        self.settings["ver"] = self.mi.version
        self.settings["lngui"] = self.mi.trs.lngui
        self.settings["lngdiag"] = self.mi.trs.lng
        self.settings["showhelp"] = True
        self.settings["autoload_tlcd"] = False
        self.settings["autoload_ident"] = False
        self.settings["autoload_actuators"] = False
        self.settings["user_mode"] = self.mi.bmb.USER_MODE_ADVANCED
        self.settings["user_dir"] = "user/"
        self.settings["adapter_type"] = self.mi.ada.default_type
        self.settings["com_port"] = ""

        self.settings["log_dir"] = "logs/"
        self.settings["discovery_dir"] = "vehicles/"
        self.settings["vehlog_dir"] = "trace/"

        try:
            sfile = open(self.settings["user_dir"] + "settings.json", "r")
            file_settings = json.load(sfile)
            if file_settings["ver"] == self.settings["ver"]:
                self.settings = file_settings
            else:
                self.log("Old settings have been invalidated")
                self.mi.alert("The program has updated - settings have been reset. Please go to the settings menu to re-set them.")
        except:
            self.log("No settings available, falling back to defaults") 

        self.mi.ada.set_com_port(self.settings["com_port"])    
        self.mi.trs.lng = self.settings["lngdiag"]
        super(Setting, self).__init__(**kwargs)


    def show_settings(self):
        self.waitpp = Factory.WaitPopup()
        self.waitpp.open()
        Clock.schedule_once(self.load_settings)


    def browse_user(self):
        '''
        Open a save file dialog to choose a folder
        '''
        self.mi.askfolder(self.browse_user_process, self.settings["user_dir"])


    def browse_user_process(self, folder, *largs):
        '''
        Handle returning of user select folder
        '''
        if not folder or folder == "":
            return
        
        if folder[-1] != "/" or folder[-1] != "\\":
            folder = folder + "/"
        
        self.settings["user_dir"] = folder
        self.ids.log_dir.text = self.settings["user_dir"]
        self.save_settings()

    
    def load_settings(self, *largs):
        '''
        Call this after displaying the popup
        '''

        self.ids.user_mode.values = list(self.mi.bmb.user_modes.values())

        self.parent_scr = self.manager.current

        self.ids.lngui.text = self.settings["lngui"]
        self.ids.lngdiag.text = self.settings["lngdiag"]
        self.ids.showhelp.active = self.settings["showhelp"]
        self.ids.autoload_tlcd.active = self.settings["autoload_tlcd"]
        self.ids.autoload_ident.active = self.settings["autoload_ident"]

        if self.settings["user_mode"] in self.mi.bmb.user_modes:
            self.ids.user_mode.text = self.mi.bmb.user_modes[self.settings["user_mode"]]
        else:
            self.settings["user_mode"] = self.mi.bmb.USER_MODE_ADVANCED
            self.ids.user_mode.text = self.mi.bmb.user_modes[self.settings["user_mode"]]

        self.ids.log_dir.text = self.settings["user_dir"]
        self.ids.adapter_type.text = self.settings["adapter_type"]

        self.manager.current = "setting"

        if self.waitpp is not None:
            self.waitpp.dismiss()


    def hide_settings(self):
        '''
        Save and apply settings
        '''
        self.manager.current = self.parent_scr

        atype = self.settings["adapter_type"]

        self.settings["lngui"] = self.ids.lngui.text
        self.settings["lngdiag"] = self.ids.lngdiag.text
        self.settings["showhelp"] = self.ids.showhelp.active
        self.settings["user_mode"] = list(self.mi.bmb.user_modes.values()).index(self.ids.user_mode.text) + 1

        if self.settings["user_mode"] < self.mi.bmb.USER_MODE_SIMPLE:
            # enforce this to avoid wasting effort
            self.settings["autoload_tlcd"] = False
        else:
            self.settings["autoload_tlcd"] = self.ids.autoload_tlcd.active
        self.settings["autoload_ident"] = self.ids.autoload_ident.active
        
        self.settings["user_dir"] = self.ids.log_dir.text
        self.settings["adapter_type"] = self.ids.adapter_type.text

        self.save_settings()

        # change the language of the diag stuff
        self.mi.trs.lng = self.settings["lngdiag"]

        if atype != self.settings["adapter_type"]:
            self.mi.alert("adaptertyperestart")


    def save_settings(self):
        try:
            if not os.path.isdir(self.settings["user_dir"] ):
                os.makedirs(self.settings["user_dir"])
            sfile = open(self.settings["user_dir"] + "settings.json", "w")
            json.dump(self.settings, sfile)
            self.log("Saved settings to " + str(self.settings["user_dir"] + "settings.json"))
        except:
            self.mi.alert("Settings could not be saved")
            self.log("Failed to write to settings file")
        
        
    def adapter_type_change(self):
        '''
        called when user changes adapter type
        '''
        pass