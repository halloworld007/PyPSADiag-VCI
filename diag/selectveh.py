from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.properties import ObjectProperty, StringProperty, DictProperty
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.factory import Factory
from kivy.clock import Clock
from pprint import pprint
'''
SCREEN: Vehicle Selection

Scan the vehicle to find which ECU's are fitted, and supply 
necessary information to Centre

'''

import os.path

class SelectVeh(Screen):
    vehs = DictProperty()
    veh_int = DictProperty()
    tree_frame = {}
    choice = {}
    waitpp = None
    done_final = False
    curr_marque = ""
    curr_model = ""
    first = True

    def log(self, x):
        print("[SVE] " + str(x)) 


    def initiate(self):
        '''
        Run to display the screen
        '''
        if self.first:
            self.ids.models.disabled = True
            self.first = False

        if self.vehs == {}:
            self.vehs = App.get_running_app().bmb.get_supported_models_list()
            self.ids.marques.values = list(self.vehs.keys())

        self.manager.current = "selectveh"


    def update_models(self):
        '''
        Update the model spinner to reflect change in marque
        '''
        if self.ids.models.disabled == True:
            self.ids.models.disabled = False

        self.ids.models.values = []
        self.veh_int = {}

        self.curr_marque = self.ids.marques.text

        if os.path.isfile("img/" + str(self.ids.marques.text).lower() + ".png"):
            App.get_running_app().m.ids.marque_logo.icon = "img/" + str(self.ids.marques.text).lower() + ".png"
        else:
            App.get_running_app().m.ids.marque_logo.icon = "img/mb.png"

        for v in self.vehs[self.ids.marques.text]:
            self.ids.models.values.append(v["label"] + " - " + v["internal"])
            self.veh_int[v["label"] + " - " + v["internal"]] = v["vehid"]

        self.ids.models.values.sort()


    def press_next(self):
        '''
        Get the list of ECU families for the given vehicle, to pass to
        Choose
        '''
        self.waitpp = Factory.WaitPopup()
        self.waitpp.open()
        self.done_final = False
        App.get_running_app().load(self.press_next_act, self.press_next_final_sch)


    def press_next_final_sch(self, *largs):
        '''
        Thread safe
        '''
        Clock.schedule_once(self.press_next_final)


    def press_next_final(self, *largs):
        '''
        Move to the next screen
        '''
        if self.waitpp != None:
            self.waitpp.dismiss()
        if self.done_final:
            self.manager.get_screen('choose').set_target(self.start_discovery)
            self.manager.get_screen('choose').initiate(self.choice, App.get_running_app().trs.get_ecu_lng())
        else:
            pp = Factory.AutoPopup()
            pp.ids.msg.text = App.get_running_app().trs.ui("datanoloaded")
            pp.title = App.get_running_app().trs.ui("waitplease")
            pp.open()


    def press_next_act(self):
        ''' Run as background thread '''
        acc = App.get_running_app()

        if acc.ready_to_work:
            if self.ids.models.text not in self.veh_int:
                self.done_final = False
                return

            veh = self.veh_int[self.ids.models.text]
            
            curr_model = self.ids.models.text
            tree = acc.bmb.get_vehicle_ecu_list(veh)
            ecu = list(tree.keys())
            ecu.sort()
            out = {}
            for e in ecu:
                if tree[e] == {}:
                    continue
                if e == "fam" or e == "prot" or e == "veh":
                    continue
                out[e] = True

            self.tree_frame = tree
            self.choice = out
            self.done_final = True
            
        else:
            self.done_final = False


    def start_discovery(self, ecus):
        '''
        Called by Choose with a list of ecus the user has chosen
        '''
        if self.tree_frame == {}:
            return   
        else:
            new_tree = { "prot": self.tree_frame["prot"], "veh": self.tree_frame["veh"]}
            for e in ecus:
                if ecus[e]:
                    new_tree[e] = self.tree_frame[e]
        
        self.manager.get_screen('discovery').set_up(new_tree)
        self.manager.get_screen('discovery').initiate()
