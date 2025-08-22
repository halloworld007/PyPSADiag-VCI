from oleodiag.diag_bramble import diag_bramble
from oleodiag.diag_translations import diag_translations
from oleodiag.diag_livedata import diag_livedata
from oleodiag.diag_adapter import diag_adapter, actia_xs, elm327
from tkinter import *
from tkinter.messagebox import *
from tkinter.filedialog import *
from tkinter.ttk import *
from ttkwidgets import CheckboxTreeview
import yaml

class tk_live_data:
    '''
    Provides a simple UI for just doing live-data viewing
    without the full diagnostique process + UI
    '''
    
    def __init__(self, *largs):
        self.trs : diag_translations = diag_translations()
        self.bmb : diag_bramble = diag_bramble(self.trs)
        self.od_live_data : diag_livedata = None
        self.ada : diag_adapter = None
        self.tree_zones: dict = {}
        self.session_status = "stopped"

        self.is_collapsed = True

        self.internal_config = {
            "ecuid": None,
            "ecuveid": None,
            "params": {},
            "adapter": None
        }

    
    def toggle_expand_collapse(self):

        if self.is_collapsed:
            self.tree.expand_all()
            self.expand_collapse.configure(text="Collapse all")
        else:
            self.tree.collapse_all()
            self.expand_collapse.configure(text="Expand all")

        self.is_collapsed = not self.is_collapsed


    def load_spec(self):
        '''
        Load an ECU spec from a file
        '''
        source_file = askopenfilename()

        if source_file is None or source_file == "":
            return
        
        try:
            file_ptr = open(source_file, "r")
            new_config = yaml.safe_load(file_ptr)
            file_ptr.close()
        except:
            showerror(title = "Failed to open file", message="The file could not be opened or parsed correctly")
            return

        self.internal_config = new_config
        self.set_up()


    def toggle_view(self):
        '''
        Toggle whether only checked items are shown, or all of them
        '''
        checked_items = self.tree.get_checked()
        print("Filter to " + str(len(checked_items)) + " parameters")


    def spec_from_dialog(self):
        pass


    def set_log_directory(self):
        '''
        Set the folder to auto-generate logs in
        '''
        new_dir = askdirectory()
        if new_dir is None or new_dir == "":
            return
        
        self.log_directory = new_dir


    def create_log_file(self):

        if self.log_file != None:
            self.log_file.close()

        log_file_name = self.internal_config["VARIANT"] + ".log"

        self.log_file = None
        self.log_file = open(log_file_name, "w+")


    def start_pause_session(self):
        
        if self.session_status == "stopped":
            checked_items = self.tree.get_checked()
            zones_to_read = []

            # set up zones
            for param in self.lidata_params:
                if self.lidata_params[param]["iid"] in checked_items:
                    if self.lidata_params[param]["zone"] not in zones_to_read:
                        zones_to_read.append(self.lidata_params[param]["zone"])

            self.od_live_data.set_zone(zones_to_read)
            self.od_live_data.start()

            self.session_status = "running"



    def stop_session(self):
        
        if self.session_status == "running":
            self.od_live_data.stop()
            self.session_status = "stopped"


    def ui_tree_select(self, event, *largs):
        '''
        Called when user clicks on a treeview item
        '''
        item = self.tree.identify('item', event.x, event.y)
        
        for param in self.lidata_params:
            if self.lidata_params[param]["iid"] == item:
                self.status_bar_text.set(self.lidata_params[param]["desc"])

    
    def create_window(self, parent = None):
        if parent is None:
            self.win = Tk()
        else:
            self.win =  Toplevel(parent)
            self.win.bind("<Destroy>",self.destroyed)

        self.win.wm_title("Live Data Viewer")
        self.win.geometry("1000x600")

        self.tvf = Frame(self.win)

        # [Load SPEC]  [Hide Unselected/Show All]  [Expand All] [Set ECU]  [Log Directory]  ECU: BSI_X7_V1  [Start/Pause]
        self.nav_bar = Frame(self.tvf)
        self.ecu_name = StringVar(value="ECU: Not set")

        ecu_name = Label(self.nav_bar, textvariable=self.ecu_name)

        import_spec = Button(self.nav_bar, text="Load SPEC", command=self.load_spec)
        self.toggle_view = Button(self.nav_bar, text="Show only selected", command=self.toggle_view)
        self.expand_collapse = Button(self.nav_bar, text="Expand All", command=self.toggle_expand_collapse)
        set_ecu = Button(self.nav_bar, text="Set new ECU", command=self.spec_from_dialog)
        log_directory = Button(self.nav_bar, text="Set log directory", command=self.set_log_directory)
        self.btn_start_pause = Button(self.nav_bar, text="Start", command=self.start_pause_session)
        self.btn_stop = Button(self.nav_bar, text="Stop", command=self.stop_session)
    
        query_interval_lbl = Label(self.nav_bar, text="Interval (ms):")
        self.query_interval_txt = Entry(self.nav_bar)

        import_spec.grid(row=1, column=1)
        self.toggle_view.grid(row=1, column=2)
        self.expand_collapse.grid(row=1, column=3)
        set_ecu.grid(row=1, column=4)
        log_directory.grid(row=1, column=5)
        ecu_name.grid(row=1, column=6)
        self.btn_start_pause.grid(row=1, column=7)
        self.btn_stop.grid(row=1, column=8)

        # Set the treeview
        self.tree = CheckboxTreeview(self.tvf, columns=('Field', 'Value', 'Unit', 'Description'))

        self.status_bar_text = StringVar(value="Ready.")
        self.status_bar = Frame(self.win)
        self.status_label = Label(self.status_bar, textvariable=self.status_bar_text, justify=LEFT)
        self.status_label.bind('<Configure>', lambda e: self.status_label.config(wraplength=self.status_label.winfo_width()))
        self.status_label.pack(fill='both', expand=True)

        # Set the heading (Attribute Names)
        self.tree.heading('#0', text='Field')
        self.tree.heading('#1', text='Value')
        self.tree.heading('#2', text="Unit")
        self.tree.heading('#3', text="Description")

        self.tree.column('#0', stretch=YES, width=150)
        self.tree.column('#1', stretch=YES, width=50)
        self.tree.column('#2', stretch=YES, width=50)
        self.tree.column('#3', stretch=YES)

        self.tree.bind("<Button-1>", self.ui_tree_select)

        self.nav_bar.pack(side='top', fill='both')
        self.tree.pack(side='left', fill='both', expand=True)
        self.status_bar.pack(side='bottom', fill='x')

        self.vsb = Scrollbar(self.tvf, orient="vertical", command=self.tree.yview)
        self.vsb.pack(side='right', fill='y')
        self.tvf.pack(fill='both', expand=True)
        self.tree.configure(yscrollcommand=self.vsb.set)

        self.exist = True

    
    def set_up(self, ecu_spec: dict = None):
        '''
        Set up auxiliary libraries and internal data structures
        with a new ECU definition
        '''

        if self.ada is None:
            showerror(title="Adapter not configured", message="The adapter has not been configured yet")
            return False
                
        self.internal_config = ecu_spec
        self.internal_config["params"] = {}

        self.ecu_name.set("ECU: " + str(ecu_spec["VARIANT"]))


    def configure_internal(self):

        self.lidata_params: dict = {}
        self.tree_zones: dict = {}
        self.od_live_data = diag_livedata(self.trs, self.ada, self.bmb)

        ecuid = self.internal_config["ECUID"]
        ecuveid = self.internal_config["ECUVEID"]

        if "FRAME_TREE" not in self.internal_config:
            frame_tree = self.bmb.get_data_frames(ecuid, ecuveid)
            self.internal_config["FRAME_TREE"] = frame_tree

        self.od_live_data.set_tree(self.internal_config, self.lidata_update_callback)
        
        param_count = 0

        for zone in self.internal_config["FRAME_TREE"]["params"]:
            for par in self.internal_config["FRAME_TREE"]["params"][zone]["params"]:
                # If no label, only show in mode_advanced+
                field_label = ""
                if "label" in par and par["label"] != "":
                    field_label = par["label"]
                else:
                    continue
                    #field_label = par["parname"]

                zone_name = zone[:2]
                unit = par["unit"], 
                unit_formatted = self.trs.decodalate(par["unit"],"0")
                help_text = par["help"]
                parid = str(par["pid"])

                if zone not in self.tree_zones:
                    iid = self.tree.insert('', 'end', text = zone_name, values= ("", "", ""))
                    self.tree_zones[zone_name] = iid

                iid = self.tree.insert(self.tree_zones[zone_name], 'end', text = field_label, values= ("-", unit_formatted, help_text))

                self.lidata_params[parid] = {
                    "zone": zone_name,
                    "label": field_label,
                    "unit": unit,
                    "desc": help_text,
                    "iid": iid
                }
                param_count += 1
                #print(zone + ": " + field_label)

            
        print("Loaded "+ str(param_count) + " parameters")
        cache = open("tld.cache", "w+")
        yaml.safe_dump(self.internal_config, cache)
                

    def lidata_update_callback(self, *largs):
        '''
        Called when oleodiag.diag_livedata has new data
        '''
        print(largs)


    def initiate(self):
        pass


spec = {}

spec["ECUID"] = 2963
spec["ECUVEID"] = 15063
spec["FAMILY"] = "ABRASR"
spec["ECUNAME"] = "ESP81"
spec["VARIANT"] = "ESP81_X7_V1"
spec["TX_H"] = "6AD"
spec["RX_H"] = "68D"
spec["BUS"] = "DIAG"

ld = tk_live_data()
ld.create_window()
ld.ada = actia_xs(ld.bmb)
ld.set_up(spec)
ld.configure_internal()
ld.win.mainloop()
