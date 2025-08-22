from kivy.app import App
from kivy.properties import ObjectProperty, StringProperty, DictProperty
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.clock import Clock
from kivy.factory import Factory

from functools import partial


class Adapters(Screen):
    parent_scr = StringProperty()
    mi = ObjectProperty()
    waitpp = None

    ports_int = {}
    devices_int = {}

    def log(self, x):
        print("[ADP] " + str(x))

    def __init__(self, **kwargs):
        '''
        '''
        self.mi = App.get_running_app()               
        super(Adapters, self).__init__(**kwargs)


    def show_adapters(self):
        '''
        Show the adapter options screen
        '''
        self.parent_scr = self.manager.current

        if self.mi.ada == None:
            self.mi.alert("adapterinvalid")
        
        self.ids.ada_vers.text = self.mi.ada.myref

        # available ports determined by adapter driver (ports = port > name, devices = name > port)
        self.ports_int, self.devices_int = self.mi.ada.get_com_ports()

        self.ids.com_ports.values = list(self.ports_int.values())

        if len(self.ports_int.values()) > 0:

            if self.manager.get_screen("setting").settings["com_port"] in self.ports_int:
                self.ids.com_ports.text = self.ports_int[self.manager.get_screen("setting").settings["com_port"]]
            else:
                self.ids.com_ports.text = self.ids.com_ports.values[0]
                # correct a missing com port
                self.mi.ada.set_com_port(self.ids.com_ports.values[0])

        self.manager.current = "adapters"


    def com_port_change(self):
        '''
        Update necessary places when user changes com port
        '''
        self.mi.ada.set_com_port(self.devices_int[self.ids.com_ports.text])
        self.manager.get_screen("setting").settings["com_port"] = self.devices_int[self.ids.com_ports.text]
        self.manager.get_screen("setting").save_settings()


    def test_connection(self):
        '''
        Test adapter connect()
        '''
        self.waitpp = Factory.WaitPopup()
        self.waitpp.open()
        self.mi.load(self.do_test_connect, self.test_connect_finish)


    def do_test_connect(self):
        '''
        Thread to check on the adapter
        '''

        if self.mi.ada == None:
            return "adapterinvalid"

        try:
            stat = self.mi.ada.connect()
        except:
            return "adapterinvalid"

        if stat:
            return "adapterok"
        else:
            return "adapterconnfail"


    def test_connect_finish(self, status, *largs):
        '''
        On return of the connect function
        '''
        Clock.schedule_once(self.waitpp.dismiss)
        Clock.schedule_once(partial(self.test_connect_alert, status))
        

    def test_connect_alert(self, status, *largs):
            '''
            Inform the user
            '''
            self.mi.alert(status,title="adaptertest")




    