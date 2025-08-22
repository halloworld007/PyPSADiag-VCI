from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen

class Utilities(Screen):
    def on_fault_lookup(self):
        pass

    def show_utilities(self):
        self.parent_scr = self.manager.current

        self.manager.current = "utilities"

    def decodalate(self, txt):
        self.ids.decodalated.text = App.get_running_app().trs.decodalate(txt)