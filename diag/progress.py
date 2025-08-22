from kivy.app import App
from kivy.properties import ObjectProperty, StringProperty, DictProperty, ListProperty
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar

class Progress(Screen):
    prg = 0
    bar = ObjectProperty()
    future = None

    def log(self, x):
        print("[PRG] " + str(x))

    def set_up(self, future):
        self.future = future    # fn to call at 100%

    def set_progress(self, pos):
        '''
        Set the value of progressbar and string
        '''
        if pos == 1:
            if self.future != None:
                self.future()
                return
        self.prg = pos * 100
        self.bar.value = self.prg
        self.ids.title_prg.text = str(round(self.prg))

    def calculate_progress(self, src, prg):
        '''
        Given a dict (must be identical length/params)
        calculate what the progress of the operation is
        If the value of the key is true, the operation
        will be considered complete for that key
        '''
        if len(src) != len(prg):
            return

        sm = len(src)
        valid = 0
        invalid = 0
        
        for key in src:
            if src[key]:
                valid = valid + 1
            else:
                invalid = invalid + 1

        if invalid + valid == sm:
            self.set_progress(valid / sm)
