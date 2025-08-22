from kivy.app import App
from kivy.properties import ObjectProperty, StringProperty, DictProperty, ListProperty
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.checkbox import CheckBox
from kivy.factory import Factory

'''
Screen: CHOOSE

Used to allow the user to pick all ECU's, or just a few
to either Discover, or fault read

- Supply a list of possible ECU's as input
- Returns a list of chosen ECU's as output

'''

class Choose(Screen):
    target = None
    options = {}
    chks = ListProperty()
    lbls = ListProperty()
    lblexp = ListProperty()
    checklist = ObjectProperty()
    sall = True

    def log(self, x):
        print("[SEL] " + str(x))

    def set_target(self, pointer):
        '''
        Set the function to be executed when the user clicks OK
        '''
        self.target = pointer

    def initiate(self, choices=None, defs=None):
        '''
        Add the contents of "choices" to the options list and 
        display the screen (after clearing previous)
        '''
        if choices == None:
            return

        x = 0
        for chk in self.chks:
            self.ids.checklist.remove_widget(chk)
            self.ids.checklist.remove_widget(self.lbls[x])
            self.ids.checklist.remove_widget(self.lblexp[x])
            x = x + 1

        self.options = choices
        self.sall = True
        self.chks = []
        self.lbls = []
        self.lblexp = []

        exp = ""

        for choice in self.options:
            chk = CheckBox(active=True)
            chk.bind(active=self.checked_changes)
            self.chks.append(chk)
            lbl = Factory.DGLabel(text=choice)
            lbl.bind(on_press=self.change_check)
            if defs != None:
                if choice in defs:
                    exp = defs[choice]
                else:
                    exp = ""
            lbl_exp = Factory.DGLabel(text=exp)
            self.lbls.append(lbl)
            self.lblexp.append(lbl_exp)
            self.ids.checklist.add_widget(chk)
            self.ids.checklist.add_widget(lbl)
            self.ids.checklist.add_widget(lbl_exp)
        
        # show myself
        self.manager.current = "choose"

    def checked_changes(self, choice, value):
        x = 0
        for chk in self.chks:
            if chk == choice:
                self.options[self.lbls[x].text] = value
                break
            x = x + 1

    def change_check(self, source):
        print("source")
        x = 0
        for lbl in self.lbls:
            if lbl == source:
                self.chks[x].value = not self.options[lbl.text]
                self.options[lbl.text] = not self.options[lbl.text]              
            x = x + 1

    def toggle_select(self):
        '''
        Select/deselect all
        '''
        if self.sall:           
            self.ids.selectall.text = App.get_running_app().trs.ui("selectall")
            for chk in self.chks:
                chk.active = False
            self.sall = False
        else:
            self.ids.selectall.text = App.get_running_app().trs.ui("deselectall")
            for chk in self.chks:
                chk.active = True
            self.sall = True


    def proceed(self):
        '''
        User clicked next, so call the pre-set callback
        with the state of the selections as a dict
        '''
        if self.target is not None:
            self.target(self.options)