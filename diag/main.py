import kivy
kivy.require('2.0.0') # replace with your current kivy version !


from kivy.app import App
from kivy.config import Config
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.properties import ObjectProperty, StringProperty, NumericProperty, ListProperty, DictProperty, BooleanProperty
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.clock import Clock
from kivy.factory import Factory
from kivy.uix.checkbox import CheckBox
from kivy.uix.spinner import Spinner
from kivy.uix.dropdown import DropDown
from kivy.uix.treeview import TreeView, TreeViewNode
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.popup import Popup
from kivy.uix.button import Button
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem, TabbedPanelHeader
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.core.window import Window
from kivy.uix.actionbar import ActionButton, ActionLabel
from kivy.uix.switch import Switch
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.recycleview.views import RecycleDataViewBehavior

# our screens
from centre import Centre
from choose import Choose
from discovery import Discovery
from settings import Setting
from progress import Progress
from selectveh import SelectVeh
from utilities import Utilities
from selectecu import SelectECU
from adapters import Adapters

import os, time, traceback, datetime, threading

# oleodiag library
from oleodiag.diag_translations import diag_translations
from oleodiag.diag_bramble import diag_bramble
from oleodiag.diag_adapter import diag_adapter
from oleodiag.diag_livedata import diag_livedata
from oleodiag.diag_discovery import diag_discovery
from oleodiag.diag_telecode import diag_telecode
from oleodiag.diag_acttest import diag_acttest
from oleodiag.diag_procedures import diag_procedures

from functools import partial

'''
SCREEN: MainScreen - on startup, ask the user what they want to do

Components:
- Simple screen with welcome text and 2 buttons
- POPUP: Load file, choosing an existing ECU cache
- Links to SCR:Choose after both

'''

class Main(GridLayout):
    prev = StringProperty()

class MainMenu(Screen):

    def back(self):
        self.log("Back")

    def log(self, x):
        print("[MAI] " + str(x))


class SaveDialog(FloatLayout):
    save = ObjectProperty(None)
    text_input = ObjectProperty(None)
    cancel = ObjectProperty(None)
    callback = ObjectProperty(None)
    def_text = StringProperty("")
    filext = StringProperty("")

class LoadDialog(FloatLayout):
    save = ObjectProperty(None)
    text_input = ObjectProperty(None)
    cancel = ObjectProperty(None)
    callback = ObjectProperty(None)
    def_text = StringProperty("")
    filext = StringProperty("")
    path = StringProperty("")

class FolderDialog(FloatLayout):
    save = ObjectProperty(None)
    text_input = ObjectProperty(None)
    cancel = ObjectProperty(None)
    callback = ObjectProperty(None)
    def_text = StringProperty("")
    filext = StringProperty("")
    path = StringProperty("")

class FaultDefault(GridLayout):
    callback = ObjectProperty()

class DGTabECUButton(TabbedPanelHeader):
    drawer = ObjectProperty()

    def on_release(self, *largs):
        if self.drawer.state == 'closed':
            # dispatch to children, not to self
            self.state = 'down'
            self.drawer.toggle_state()
        else:
            self.state ='normal'
            self.drawer.toggle_state()


class DGTabbedPanelItem(TabbedPanelItem): 
    dg_callback = ObjectProperty()

    def on_release(self, *largs):
        pass
      
    def on_release_allow(self, *largs):
        '''
        Overload of the original in tabbedPanelHeader to allow
        for cancelling of the event tree
        '''
        if self.parent:
            self.parent.tabbed_panel.switch_to(self)
        else:
            return super(DGTabbedPanelItem, self).on_release(largs)

class DGLabel(Label):
    pass

class DGLabelAS(DGLabel):
    pass

class DGLabelW(Label):
    pass

class DGButton(Button):
    pass

class DGToggleButton(ToggleButton):
    pass

class DGActionLabel(ActionLabel):
    pass

class DGActionButton(ActionButton):
    pass

class DGDropDown(DropDown):
    pass

class DGSpinner(Spinner):
    pass

class DDButton(Button):
    pass

class WaitPopup(Popup):
    status = StringProperty()


class TlcdRVRow(RecycleDataViewBehavior, BoxLayout):
    text_lbl = StringProperty()   
    values = ListProperty()
    callback = ObjectProperty()
    callhelp = ObjectProperty()
    txt = StringProperty()
    use = NumericProperty()
    param = StringProperty()
    home = ObjectProperty()

    dropdown_type = ObjectProperty()
    textbox_type = ObjectProperty()
    switch_type = ObjectProperty()

    manual_switch_toggle = False
    manual_cb_toggle = False

    '''
    DGSpinner:
            id: dropdown_type
            values: root.values
            text: root.txt
            size_hint_y: None
            height: 25
            on_text: root.callback(self.text)

        TextInput:
            id: textbox_type
            size_hint_x: 0
            size_hint_y: None
            text: root.txt
            height: sp(0)
            disabled: True
            on_text: root.callback(self.text)
        
        Switch:
            id: switch_type
            size_hint_y: 0
            size_hint_x: 0
            width: sp(0)
            height: sp(0)
            disabled: True
            '''


    def __init__(self, **kwargs):
        super(TlcdRVRow, self).__init__(**kwargs)

        self.dropdown_type = DGSpinner()
        self.dropdown_type.values = self.values
        self.dropdown_type.size_hint_y = None
        self.dropdown_type.height = 25
        self.dropdown_type.bind(on_text=self.cb_wrapper)

        self.switch_type = Switch()
        self.switch_type.size_hint_y = None
        self.switch_type.size_hint_x = None
        self.switch_type.height = 0
        self.switch_type.width = 0
        self.switch_type.bind(active=self.sw_toggle)

        self.textbox_type = TextInput()
        self.textbox_type.size_hint_y = None
        self.textbox_type.size_hint_x = None
        self.textbox_type.width = 0
        self.textbox_type.height = 0
        self.textbox_type.bind(on_text=self.cb_wrapper)
        
        self.ids.widges.add_widget(self.dropdown_type)
        self.ids.widges.add_widget(self.textbox_type)
        self.ids.widges.add_widget(self.switch_type)

        self.bind(values=self.on_update_of_rv)
        self.bind(text_lbl=self.on_update_of_rv)

        #print("init with " + str(self.use))
        #print(str(self.dropdown_type.size_hint_x))
        

    def cb_wrapper(self, *largs):
        
        if self.callback == None:
            #print("cb empty")
            return
        else:
            if self.use == 0:
                #print("cb0: " + str(self.dropdown_tyon_release(largs)pe.text))
                return self.callback(self.param, self.dropdown_type.text)
            else:
                #print("cb1: " + str(self.textbox_type.text))
                return self.callback(self.param, self.textbox_type.text)


    def sw_toggle(self, stat, *largs):
        '''
        Handle the switch toggle translation to absent / present
        '''
        print("Changing 1")
        if self.manual_switch_toggle:
            self.manual_switch_toggle = False
            return True

        if self.callback == None or self.home == None:
            #print("null cb")
            return

        print("Changing 2")

        state = stat.active

        if state:
            if self.values[1].upper() in self.home.TLCD_POS:
                self.callback(self.param, self.values[1])
            else:
                self.callback(self.param, self.values[0])
        else:
            if self.values[0].upper() in self.home.TLCD_NEG:
                self.callback(self.param, self.values[0])
            else:
                self.callback(self.param, self.values[1])
            

    def on_update_of_rv(self, *largs):
        '''
        Called when recycleview updates the fields
        The spinner/textbox is always set to the available values/selected value
        We have to manually set the switch
        '''
        self.dropdown_type.values = self.values
        self.dropdown_type.text = self.txt
        self.textbox_type.text = self.txt

        self.dropdown_type.bind(text=self.cb_wrapper)
        self.switch_type.bind(active=self.sw_toggle)
        self.textbox_type.bind(text=self.cb_wrapper)

        print("RV row change: " + str(self.use) + " - " + str(self.text_lbl) + " = " + str(self.txt.upper()))
        # 0 = opt, 1 = txt, 2 = sw

        if self.use == 0:
            self.dropdown_type.height = 25
            self.dropdown_type.size_hint_x = 1
            self.dropdown_type.disabled = False
            self.dropdown_type.opacity = 1

            self.switch_type.height = 0
            self.switch_type.size_hint_x = None
            self.switch_type.width = 0
            self.switch_type.opacity = 0
            self.switch_type.disabled = True

            self.textbox_type.height = 0
            self.textbox_type.size_hint_x = None
            self.textbox_type.width = 0
            self.textbox_type.opacity = 0
            self.textbox_type.disabled = True
        
        elif self.use == 1:
            # textbox
            self.switch_type.height = 0
            self.switch_type.size_hint_x = 0
            self.switch_type.width = 0
            self.switch_type.opacity = 0
            self.switch_type.disabled = True

            self.dropdown_type.height = 0
            self.dropdown_type.size_hint_x = None
            self.dropdown_type.width = 0
            self.dropdown_type.opacity = 0
            self.dropdown_type.disabled = True
            

            self.textbox_type.size_hint_x = 1
            self.textbox_type.height = 25
            self.textbox_type.opacity = 1
            self.textbox_type.disabled = False
        
        elif self.use == 2:
            # sw
            if self.txt.upper() in self.home.TLCD_POS:
                self.manual_switch_toggle = True
                self.switch_type.active = True
            else:
                self.manual_switch_toggle = True
                self.switch_type.active = False
                

            self.switch_type.height = 25
            self.switch_type.size_hint_x = 1
            self.switch_type.opacity = 1
            self.switch_type.disabled = False

            self.dropdown_type.size_hint_x = None
            self.dropdown_type.height = 0
            self.dropdown_type.width = 0
            self.dropdown_type.opacity = 0
            self.dropdown_type.disabled = True

            self.textbox_type.height = 0
            self.textbox_type.size_hint_x = None
            self.textbox_type.width = 0
            self.textbox_type.opacity = 0
            self.textbox_type.disabled = True

class LiDataZone(TabbedPanelItem):
    ppt = None

    def on_release(self, **kwargs):
        if self.ppt is not None:
            self.ppt(self.text)
        super(LiDataZone, self).on_release(**kwargs)


class LiDataRow(GridLayout):
    text_lbl = StringProperty()
    text_val = StringProperty()
    pid = StringProperty()
    text_help = StringProperty()
    chk = ObjectProperty()
    unit = StringProperty()     # store unit unformatted
    chk_callback = ObjectProperty()


    # Hack in order to bind to the checkbox change
    # property of a RecycleView row
    def __init__(self, **kwargs):
        super(LiDataRow, self).__init__(**kwargs)
        
        cb = CheckBox() #size_hint_x = 0.1,size_hint_y=None,height=30,halign= "right")
        cb.size_hint_x = 0.1
        cb.size_hint_y = None
        cb.height = 30
        cb.halign = "right"
        self.add_widget(cb)
        cb.bind(active=self.empty)
        self.chk = cb

    def empty(self, *largs):
        if self.chk_callback != None:
            self.chk_callback(self.chk.active)
        

class FaultDetailRow(GridLayout):
    fd_lbl = StringProperty()
    fd_val = StringProperty()

class SelDropDown(DropDown):
    pass

class ActPopup(Popup):
    callback_left = ObjectProperty()
    callback_right = ObjectProperty()

class FaultAccord(GridLayout):
    ppt = ObjectProperty()

class FaultBox(GridLayout, TreeViewNode):
    pass

class CheckLabel(GridLayout, Button):
    chk_id = StringProperty()
    chk_lbl = StringProperty()
    chk_grp = StringProperty()
    chk_sel = BooleanProperty(False)


class SwitchLabel(GridLayout):
    sw_id = StringProperty()
    sw_lbl = StringProperty()
    sw_act = BooleanProperty(False)

class MainApp(App):

    trs: diag_translations = diag_translations(lang="en", path="db/")
    bmb: diag_bramble = diag_bramble(trs, path="db/")
    ada : diag_adapter = diag_adapter(bmb)
    glt: diag_discovery = None
    lidata: diag_livedata = None
    tlc: diag_telecode = None
    act: diag_acttest = None
    prc: diag_procedures = None
    log_visible = False
    log_popup = None
    version = "1.41.240604"
    appname = "Diagnostique"
    root_font = "GillSans"
    
    ready_to_work = False

    thread_callbacks = {}
    active_thread = None
    sm = None
    status_callbacks = []

    dlg_save = ObjectProperty()

    def log(self, x):
        self.bmb.logger("[APP] " + str(x))


    def build(self):       
        '''
        Initialise diag library and core kivy overrides
        '''
        self.m = Main()
        self.sm = self.m.ids.sm

        self.ada = self.ada.create_inst(self.sm.get_screen("setting").settings["adapter_type"])

        self.glt = diag_discovery(self.trs, self.ada, self.bmb)
        self.lidata = diag_livedata(self.trs, self.ada, self.bmb)
        self.tlc = diag_telecode(self.trs, self.ada, self.bmb)
        self.act = diag_acttest(self.trs, self.ada, self.bmb)
        self.prc = diag_procedures(self.trs, self.ada, self.bmb)

        self.log_popup = Factory.LogPopup()
        self.log_popup.ids.log_txt.text = ""
        self.title = self.appname
        self.log(self.appname + " version: " + str(self.version))
        self.ready_to_work = True
        
        try:
            direc = self.sm.get_screen("setting").settings["user_dir"] + self.sm.get_screen("setting").settings["log_dir"]
            now = datetime.datetime.now()
            fname = "diagnostique_" + str(now.day) + "_" + str(now.month) + "_" + str(now.year) + "_" + str(now.hour) + "_" + str(now.minute) + ".log"
            if not os.path.isdir(direc):
                os.makedirs(direc)
        except:
            print("[APP] Logging is not available for some reason")

        self.bmb.set_logfile(direc + fname)
        self.bmb.set_log_callback(self.logback)
        self.trs.bb = self.bmb

        Config.set('kivy','exit_on_escape',0)
        Config.set('kivy','default_font',"GillSansPSA")
        Config.set('kivy', 'desktop', 1)
        Window.size = (1000, 600)

        Window.clearcolor = (1, 1, 1, 1)        #white background
    
        return self.m


    def thread_return_check(self):
        '''
        Called every time a thread function finishes
        Checks if the queue is empty, to update global status flags
        '''
        try:
            self.log("Status update: " + str(len(thread_queue_functions)))
            for item in self.status_callbacks:
                if len(thread_queue_functions) > 0:
                    item(True)
                else:
                    item(False)
        except Exception:
            return

        
    def load(self, fn, r=-1, callback=None):
        global callback_on_finish, log_ptr
        '''
        Start a given function (fn) in a background thread
        We use this central coordination to ensure that functions are queued
        in their writing to the ECU, to avoid being in the situation of reading
        or executing multiple functions simultaenously.

        IMPORTANT: This means that any function talking to the ECU must not assume anything
        about the ECU's state (even if "theoretically" it has just communicated with it, something
        else might have used it in the meantime)

        The exception is live data - because that runs in its own thread (managed by its own class)
        it is the responsiblity of Centre/any other user to ensure that live data is toggled OFF before we try
        to do anything else with the ECU
        '''
        callback_on_finish = self.thread_return_check

        log_ptr = self.bmb

        if fn == False or fn == None:
            raise ValueError("passed function result instead of partial wrapped")

        if self.active_thread != None:
            if not self.active_thread.is_alive():
                # we haven't finished the previous job
                self.log("Async thread crashed. Restarting")
                try:
                    thread_queue_functions.pop(0)
                    thread_callback_functions.pop(0)
                except:
                    pass
                self.active_thread = threading.Thread(target=queue_thread, daemon=True)
                self.active_thread.start()
        else:
            self.active_thread = threading.Thread(target=queue_thread, daemon=True)
            self.active_thread.start()
            self.log("Async thread started OK")

        if hasattr(callback, '__call__'):
            thread_queue_functions.append(partial(fn, callback))
        else:
            thread_queue_functions.append(fn)
        thread_callback_functions.append(r)
        

    def toggle_log(self):
        '''
        Show/Hide the logging view popup
        '''
        if not self.log_visible:
            
            self.log_popup.open()
        else:
            self.log_popup.dismiss()

        self.log_visible = not self.log_visible

    
    def logback(self, x):
        '''
        Called by the logger to update the log window
        '''
        self.log_popup.ids.log_txt.text = self.log_popup.ids.log_txt.text + "\n" + str(x)

    
    def ask_home(self,sm):
        '''
        Work out what to do when the user clicks the home logo
        '''

        self.sm = sm
        if sm.current == "centre":
            self.yesno("quitsession", callbacky=self.go_home)
        elif sm.current == "adapters":
            sm.current = sm.get_screen("adapters").parent_scr
        elif sm.current == "utilities":
            sm.current = sm.get_screen("utilities").parent_scr
        elif sm.current == "selectveh":
            sm.current = "main"
        elif sm.current == "choose":
            sm.current = "main"
        elif sm.current == "selectecu":
            sm.current = "main"
        else:
            sm.current = "main"


    def go_home(self, *largs):
        self.sm.get_screen("centre").clean_exit()
        self.sm.current = "main"

    
    def discovery_save(self, *largs):
        '''
        Trigger discovery to save the current tree to disk
        '''
        self.sm.get_screen("centre").save_tree_if_possible()


    def close(self, *largs):
        '''
        Exit
        '''
        exit()


    def alert(self, msg, title="alerttitle", callback=None, *largs):
        '''
        Warning to the user, OK Only
        - Message and title are keys for trs.ui
        - Message can be a list or a string, list can contain arbitrary strings
        - Default callback is root.dismiss()
        '''
        pp = Factory.AutoPopup()
        if type(msg) is list:
            pp.ids.msg.text = ""
            for m in msg:
                l = self.trs.ui(m)
                if l == self.trs.TRS_MISSING:
                    l = m
                pp.ids.msg.text = pp.ids.msg.text + l + "\n"
        else:
            pp.ids.msg.text = self.trs.ui(msg)

        pp.title = self.trs.ui(title)
        if callback != None:
            # default is just root.dismiss
            pp.ids.btn_ok.bind(on_release=callback)
        pp.open()
        

    def yesno(self, msg, title: str = "yesnotitle", callbacky: callable=None, callbackn: callable=None, *largs):
        '''
        Ask the user to choose yes/no
        - Message and title are keys for trs.ui
        - Message can be a list or a string
        - Default callback is root.dismiss() for both
        '''
        pp = Factory.YesNoPopup()
        if type(msg) is list:
            pp.ids.msg.text = ""
            for m in msg:
                pp.ids.msg.text = pp.ids.msg.text + self.trs.ui(m) + "\n"
        else:
            pp.ids.msg.text = self.trs.ui(msg)
        pp.title = self.trs.ui(title)
        if callbacky != None:
            pp.ids.btn_yes.bind(on_release=callbacky)
        if callbackn != None:
            pp.ids.btn_no.bind(on_release=callbackn)
        pp.open()


    def user_input(self, msg, title: str = "inputtitle", callback: callable = None):
        '''
        Ask the user to input some text
        '''
        pp = Factory.TextPopup()
        pp.ids.msg.text = self.trs.ui(msg)
        pp.title = self.trs.ui(title)
        # bind to callback for OK
        pp.open()
        return pp.utxt


    def user_opt(self, msg, options, callbacksel: callable = None, callbacknosel: callable = None, *largs):
        '''
        Offer a user a choice of options using a Spinner
        '''
        pp = Factory.SpinPopup()
        if type(msg) is list:
            pp.ids.msg.text = ""
            for m in msg:
                l = self.trs.ui(m)
                if l == self.trs.TRS_MISSING:
                    l = m
                pp.ids.msg.text = pp.ids.msg.text + l + "\n"
        else:
            pp.ids.msg.text = self.trs.ui(msg)

        #pp.title = self.trs.ui(title)
        for item in options:
            pp.ids.utxt.values.append(item)
        
        pp.ids.utxt.text = pp.ids.utxt.values[0]

        if callbacksel != None:
            pp.ids.btn_yes.bind(on_release=partial(self.user_opt_return,callbacksel, pp))
        if callbacknosel != None:
            pp.ids.btn_no.bind(on_release=partial(callbacknosel,False))
        pp.open()


    def user_opt_return(self, callback, pp):
        callback(pp.ids.utxt.text)


    def askfile(self, filext=".cfg/.dsc", callback=None):
        '''
        Ask the user to select a file name to save
        '''
        content = SaveDialog(save=self.askfile_process, cancel=self.askfile_process, callback=callback, def_text="", filext=filext)
        self.dlg_save = Popup(title="Choose location", content=content,size_hint=(0.9, 0.9))
        self.dlg_save.open()

    def askfile_process(self, ref, path, name):
        if path == None:
            if ref.callback != None:
                ref.callback(False)
                self.dlg_save.dismiss()
        elif name == "" or name == None:
            self.alert("filedialog_choosename")
        else:
            ref.callback(path + "/" + name)
            self.dlg_save.dismiss()

    
    def askfileload(self, filext=".cfg/.dsc", callback=None):
        '''
        Ask the user a filename to load
        '''
        content = LoadDialog(save=self.askfileload_process, cancel=self.askfileload_process, callback=callback, def_text="", filext=filext, path=str(os.getcwd()))
        self.dlg_load = Popup(title="Choose file", content=content,size_hint=(0.9, 0.9))
        self.dlg_load.open()


    def askfileload_process(self, ref, path, name):
        if path == None:
            if ref.callback != None:
                ref.callback(False)
                self.dlg_load.dismiss()
        elif name == "" or name == None:
            self.alert("filedialog_choosename")
        else:
            ref.callback(name)
            self.dlg_load.dismiss()

    
    def askfolder(self, callback=None, start_dir=""):
        '''
        Ask the user a filename to load
        '''
        content = FolderDialog(save=self.askfolder_process, cancel=self.askfolder_process, callback=callback, def_text="", path=str(os.getcwd()))
        self.dlg_load = Popup(title="Choose folder", content=content,size_hint=(0.9, 0.9))
        self.dlg_load.open()


    def askfolder_process(self, ref, path, with_name):
        if path == None:
            if ref.callback != None:
                ref.callback(False)
                self.dlg_load.dismiss()
        elif with_name == "" or with_name == None:
            self.alert("filedialog_choosename")
        else:
            if ref.callback != None:
                ref.callback(with_name)
            self.dlg_load.dismiss()


thread_queue_functions = []
thread_callback_functions = []
callback_on_finish = None
log_ptr = None


def queue_thread():
    while True:
        try:
            if len(thread_queue_functions) > 0:
                # run the function, log compeltion flag, delete it from queue
                if callback_on_finish is not None:
                    callback_on_finish()

                v = thread_queue_functions[0]()
                if hasattr(thread_callback_functions[0], '__call__'):
                    thread_callback_functions[0](v)

                thread_queue_functions.pop(0)
                thread_callback_functions.pop(0)

                if callback_on_finish is not None:
                    callback_on_finish()
            else:
                time.sleep(0.1)
        except:
            # must pop arrays, or we can get into endless loop here
            try:
                thread_queue_functions.pop(0)
                thread_callback_functions.pop(0)
                if callback_on_finish is not None:
                    callback_on_finish()
            except Exception:
                pass

            if log_ptr is not None:
                log_ptr.logger("[QTH] Unhandled exception in background thread:")
                log_ptr.logger("".join(traceback.format_exc()))
                log_ptr.logger("[QTH] Continuing in this state may be unsafe")

                try:
                    if len(thread_queue_functions) > 0:
                        thread_queue_functions.pop(0)

                    if len(thread_callback_functions) > 0:
                        thread_callback_functions.pop(0)

                    if callback_on_finish is not None:
                        callback_on_finish()

                except Exception:
                    log_ptr.logger(str(traceback.format_exc()))
                    log_ptr.logger("[QTH] Additionally, whilst trying to clear up the program encountered an unrecoverable error. Quit.")
                    exit()
            else:
                print("[QTH] Unhandled error in background thread and logging unavailable")
                print("".join(traceback.format_exc()))


if __name__ == '__main__':
    MainApp().run()
