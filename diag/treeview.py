import tkinter as tk
from tkinter import messagebox
import tkinter.ttk as ttk
from tkinter.filedialog import askopenfilename
import json, yaml

import os, sys, inspect

from oleodiag.diag_bramble import diag_bramble
from oleodiag.diag_translations import diag_translations
from oleodiag.diag_adapter import *

'''
    Tool for visualising an ECU frame dump

    This helps to get an overview of all supported ECU services / frames / etc
    It also allows running known UDS commands using the Actia XS Evolution adapter
    It also lists fault codes for a specific ECU with all accessible information
'''

class Fault_Window():
    '''
    Display faults for a given ECU
    '''
    parent = None
    master = None
    exist = False

    def __init__(self, root, owner):
        self.master = root
        self.parent : Application = owner


    def destroyed(self, *largs):
        self.exist = False


    def createWin(self):
        if not self.exist:
            self.win = tk.Toplevel(self.master)
            self.win.wm_title("Fault Tree")
            self.win.bind("<Destroy>",self.destroyed)

            self.tvf = tk.Frame(self.win)
 
            # Set the treeview
            self.tree = ttk.Treeview(self.win, columns=('Code', 'Hex', 'Label', 'Description'))
    
            # Set the heading (Attribute Names)
            self.tree.heading('#0', text='Code')
            self.tree.heading('#1', text='Hex')
            self.tree.heading('#2', text="Label")
            self.tree.heading('#3', text="Desc")

            self.tree.column('#0', stretch=tk.YES)
            self.tree.column('#1', stretch=tk.YES)
            self.tree.column('#2', stretch=tk.YES)
            self.tree.column('#3', stretch=tk.YES)

            #self.tree.bind("<1>", self.on_tree_select)

            self.tree.pack(side='left', fill='y')

            self.vsb = ttk.Scrollbar(self.win, orient="vertical", command=self.tree.yview)
            self.vsb.pack(side='right', fill='y')
            self.tree.configure(yscrollcommand=self.vsb.set)

            self.exist = True

            self.update_data()


    def update_data(self, *largs):
        iid = 0

        if self.parent.chooseWin.active_ecuveid != -1 and self.parent.chooseWin.active_ecuid != -1:
            print(self.parent.chooseWin.active_ecuid)
            x = self.parent.bmb.get_dtc_all(self.parent.chooseWin.active_ecuid)

            ids = []
            order = []

            for y in x:
                ids.append(y["internal_code"])
                order.append(y["display_code"])

            dtc_set = self.parent.bmb.get_dtc_printout(self.parent.chooseWin.active_ecuid, self.parent.chooseWin.active_ecuveid, ids)


            for y in x:
                internal_code = y["internal_code"]
                v = y["display_code"]
                l = self.parent.trs.decodalate(y["dtclabel"])
                hlp = self.parent.trs.decodalate(y["dtchelp"])
                dsc = self.parent.trs.decodalate(y["descrip"])

                if v == "":
                    v = internal_code
                
                u = self.tree.insert('', 'end', iid=iid, text = v, values = (internal_code,l,dsc))
                iid += 1

                
                if internal_code not in dtc_set:
                    continue
                else:
                    try:
                        for char in dtc_set[internal_code]["chars"]:
                            self.tree.insert(u, 'end', iid=iid, text = char["title"], values = ("", char["value"], ""))
                            iid = iid + 1
                    except Exception:
                        pass


class UDS_Interface():
    '''
    A simple interface for running raw diagnostic commands
    Automatic headers and keep-alives
    Entry of bytestring to send
    Textbox of response bytes
    '''
    parent = None
    master = None
    exist = False

    def __init__(self, root, owner):
        self.master = root
        self.parent = owner
        self.ada = actia_xs(self.parent.bmb)
        

    def destroyed(self, *largs):
        self.exist = False
        self.ada.disconnect()


    def createWin(self):
        if not self.exist:
            self.ada.connect()
            self.win = tk.Toplevel(self.master)
            self.win.wm_title("ECU Communications (ActiaXS only)")
            self.win.bind("<Destroy>",self.destroyed)

            info = tk.Label(self.win, text="Set Headers TX/RX/code/type:")
            info.grid(row=1, column=1, columnspan=1)

            self.hdr_tx = tk.Entry(self.win)
            self.hdr_tx.grid(row=1, column=2, columnspan=1)
            self.hdr_tx.insert(tk.END, "752")
            self.hdr_rx = tk.Entry(self.win)
            self.hdr_rx.grid(row=1, column=3, columnspan=1)
            self.hdr_rx.insert(tk.END, "652")

            self.hdr_ecucode = tk.Entry(self.win, width = 8)
            self.hdr_ecucode.grid(row=1, column=4)
            self.hdr_ecucode.insert(tk.END, "04")

            self.hdr_dlog_type = tk.Entry(self.win, width = 8)
            self.hdr_dlog_type.grid(row=1, column=5)
            self.hdr_dlog_type.insert(tk.END, "")

            self.pins = ttk.Combobox(self.win, values=["CAN IS 6/14", "CAN DIAG 3/8", "FIATCAN50 6/14", "FIATCAN50 3/8", "K-LINE"])
            self.pins.current(1)
            self.pins.grid(row=1, column=6)

            self.hdr_ok = tk.Button(self.win, text="Set", command=self.on_set)
            self.hdr_ok.grid(row=1, column=7)

            self.ka_txt = tk.Entry(self.win, width=8)
            self.ka_txt.grid(row=1, column=8)
            self.ka_txt.insert(tk.END, "3E")

            self.ka_ok = tk.Button(self.win, text="Start", command=self.on_ka)
            self.ka_ok.grid(row=1, column = 9)

            info = tk.Label(self.win, text="Send data:")
            info.grid(row=2, column=1, columnspan=1)

            self.cmd_win = tk.Entry(self.win, width=100)
            self.cmd_win.bind('<Return>',self.on_cmd)
            self.cmd_win.grid(row=2, column=2, columnspan = 6)

            self.cmd_ok = tk.Button(self.win, text="Send >", command=self.on_cmd)
            self.cmd_ok.grid(row=2, column=8)

            self.responses = tk.Text(self.win)
            self.responses.grid(row=3, column=1, columnspan = 9)

            self.exist = True


    def on_set(self):
        '''
        Set actia parameters
        '''
        bus = self.pins.current()

        tx_h = self.hdr_tx.get()
        rx_h = self.hdr_rx.get()
        ecucode = self.hdr_ecucode.get()
        dtype = self.hdr_dlog_type.get()

        if bus == 0:
            self.ada.configure(tx_h, rx_h, "IS", protocol = "DIAGONCAN")

        elif bus == 1:
            self.ada.configure(tx_h, rx_h, "DIAG", protocol = "DIAGONCAN")

        elif bus == 2:
            self.ada.configure(tx_h, rx_h, "DIAG", protocol = "KWPONCAN_FIAT", target = ecucode)

        elif bus == 3:
            self.ada.configure(tx_h, rx_h, "IS", protocol = "KWPONCAN_FIAT", target = ecucode)

        elif bus == 4:
            self.ada.configure(tx_h, rx_h, "IS", protocol = "PSA2000", target = ecucode, dialog_type=dtype)

        else:
            return


    def on_ka(self):
        '''
        Toggle keep - alive
        '''
        self.ka_cmd = self.ka_txt.get()
        
        if self.ka_ok['text'] == "Start":
            self.ka_ok['text'] = "Stop"
            self.ka = True
            self.master.after(3000, self.do_ka)
        else:
            self.ka_ok['text'] = "Start"
            self.ka = False


    def do_ka(self):
        if self.ka:
            self.ada.send_wait_reply_int("3E")
            print("[VCI] KA")

        self.master.after(3000, self.do_ka)


    def on_cmd(self, *largs):
        '''
        Send command to device
        '''
        cmd = self.cmd_win.get()
        self.responses.insert(tk.END, "\n> " + str(cmd))
        self.cmd_win.delete(0, 'end')
        
        rsp = self.ada.send_wait_reply_int(cmd)
        if not rsp:
            self.responses.insert(tk.END, "\n  NO DATA")
        else:
            self.responses.insert(tk.END, "\n  " + str(rsp))



class Load_ECU():
    '''
    Popup window to select ECU/ECUVE IDs in a nice manner
    '''
    parent = None
    master = None
    exist = False
    models = []
    ecuveids = []
    ecuids = []
    famids = []
    hdrs = []

    active_ecuid = -1
    active_ecuveid = -1

    def __init__(self, root, owner):
        self.master = root
        self.parent : Application = owner
        self.save_path = "treeview_data/"
        if not os.path.isdir(self.save_path):
            os.makedirs(self.save_path)
    

    def destroyed(self, *largs):
        self.exist = False
    

    def createWin(self):
        if not self.exist:
            self.win = tk.Toplevel(self.master)
            self.win.wm_title("ECU Selection")
            self.win.bind("<Destroy>",self.destroyed)

            info = tk.Label(self.win, text="Select the ECU using the boxes provided. Note that the reference number is usually for software, not hardware!", wraplength=400)
            info.grid(row=1, column=1, columnspan=1)

            model_vals = []
            models = self.parent.bmb.get_supported_models_list()
            for marque in models:
                for model in models[marque]:
                    model_name = marque + " " + model["label"]
                    self.models.append(model)
                    model_vals.append(model_name)
            
            if len(models) == 0:
                return

            self.veh_sel = ttk.Combobox(self.win, values=model_vals, width=45)
            self.veh_sel.bind("<<ComboboxSelected>>", self.on_veh_sel_change)
            self.veh_sel.grid(row=2, column=1)

            self.fam_sel = ttk.Combobox(self.win, values=[], state=tk.DISABLED, width=45)
            self.fam_sel.bind("<<ComboboxSelected>>", self.on_fam_sel_change)
            self.fam_sel.grid(row=3, column=1)

            self.ecu_sel = ttk.Combobox(self.win, values=[], state=tk.DISABLED, width=45)
            self.ecu_sel.bind("<<ComboboxSelected>>", self.on_ecu_sel_change)
            self.ecu_sel.grid(row=4,column=1)

            self.ecuve_sel = ttk.Combobox(self.win, values=[], state=tk.DISABLED, width=45)
            self.ecuve_sel.bind("<<ComboboxSelected>>", self.on_ecuve_sel_change)
            self.ecuve_sel.grid(row=5, column=1)

            self.do_load = tk.Button(self.win, text="Load Frames", command=self.load_ecu)
            self.do_load.grid(row=3, column=2)

            self.do_load_b = tk.Button(self.win, text="Export Available Data", command=self.export_ecu_data)
            self.do_load_b.grid(row=2, column=2)

            self.do_frame_get = tk.Button(self.win, text="Export YML", command=self.generate_ecu_tree)
            self.do_frame_get.grid(row=4, column=2)

            self.output = tk.Text(self.win)
            self.output.grid(row=6, column=1, columnspan=2)

            self.exist = True

    
    def generate_ecu_tree(self):
        spec = self.make_ecu_spec()
        self.parent.generate_ecu_tree(spec)
        messagebox.showinfo(title="Done", message="Data exported to YAML " + spec["VARIANT"] + " successfully")

    
    def load_ecu(self):
        if self.active_ecuveid == -1 or self.active_ecuid == -1:
            return
        self.parent.get_dgd(self.parent.save_path + str(self.ecuveids[self.ecuve_sel.current()]["variant"]), self.active_ecuveid)


    def export_ecu_data(self):
        '''
        Get a simple text list of available:
        - actuator tests
        - live data parameters
        - telecoding options
        '''
        if self.active_ecuveid == -1 or self.active_ecuid == -1:
            return

        tab = " -   "

        spec = self.make_ecu_spec()

        act = self.parent.bmb.get_actuator_tests(self.active_ecuid, self.active_ecuveid)
        tlc = self.parent.bmb.get_params_from_telecoding(self.active_ecuid, self.active_ecuveid, filt_level = self.parent.bmb.MODE_EXPERIMENTAL)
        par = self.parent.bmb.get_data_frames(self.active_ecuid, self.active_ecuveid, "parameters", True)       


        out = "Actuator Tests\n"
        out = out + "--------------\n"
        for screen in act:
            if "title" in act[screen]:
                out = out + act[screen]["title"] + "\n"


        out = out + "\n\nLive Parameters\n"
        out = out + "---------------\n"

        if not par:
            out = out + "None in database\n"
        else:
            for param in par["params"]:
                out = out + str(param) + " (" + str(par["params"][param]["label"]) + ")\n"


        out = out + "\n\nConfiguration Settings\n"
        out = out + "----------------------\n"

        if not tlc:
            out = out + "None in database\n"
        else:
            for param in tlc:
                out = out + str(param) + " (" + str(tlc[param]["label"]) + ")\n"

                if "states" in tlc[param]:
                    for state in tlc[param]["states"]:
                        out = out + tab + str(state["val"]) + ": " + str(state["label"]) + "\n"
    
        file_name = spec["VARIANT"] + "_overview.txt"

        f = open(self.save_path + file_name, "w")
        f.writelines(out)
        f.close()
        messagebox.showinfo(title="Done", message="Data exported to text file " + spec["VARIANT"] + "_overview.txt successfully")

    
    def make_ecu_spec(self):
        '''
        Make discovery ECU frame format
            STATUS  -> IDENTOK, 
            ECUID   -> ECUID number
            ECUVEID -> ECUVEID number
            FAMILY  -> e.g. "BMF"
            ECUNAME -> e.g. "BSI"
            VARIANT -> e.g. "BSI_X7_V1"
            TX_H    -> 752
            RX_H    -> 652
            BUS     -> DIAG/IS
            CMDS    -> result of get_ecu_diag_cmds(ecuveid)
            FAULTS  -> number of faults
            FAULT_TREE -> 
            FRAME_TREE -> result from get_data_frames(ecuid, ecuveid)
        '''
        spec = {}

        spec["ECUID"] = int(self.active_ecuid)
        spec["ECUVEID"] = int(self.active_ecuveid)
        spec["FAMILY"] = self.fam_sel.get()
        spec["ECUNAME"] = self.ecu_sel.get()
        spec["VARIANT"] = str(self.ecuveids[self.ecuve_sel.current()]["variant"])
        spec["TX_H"] = str(self.hdrs[self.ecu_sel.current()][1])
        spec["RX_H"] = str(self.hdrs[self.ecu_sel.current()][2])
        spec["BUS"] = str(self.hdrs[self.ecu_sel.current()][0])

        return spec

    
    def render_readout(self):
        '''
        Load the ECU stats to the text area
        '''
        self.output.delete('1.0', tk.END)

        out = "\nModel Code: " +  str(self.models[self.veh_sel.current()]["internal"])
        out = out + "\nVehicle ID: " +  str(self.models[self.veh_sel.current()]["vehid"])
        out = out + "\nECU ID    : " +  str(self.active_ecuid)
        out = out + "\nECUVE ID  : " +  str(self.active_ecuveid)
        out = out + "\nReference : " +  str(self.ecuveids[self.ecuve_sel.current()]["reference"])
        out = out + "\nVariant   : " +  str(self.ecuveids[self.ecuve_sel.current()]["variant"])

        out = out + "\n\nBus       : " +  str(self.hdrs[self.ecu_sel.current()][0])
        out = out + "\nTX Header : " +  str(self.hdrs[self.ecu_sel.current()][1])
        out = out + "\nRX Header : " +  str(self.hdrs[self.ecu_sel.current()][2])
        out = out + "\nProtocol  : " +  str(self.hdrs[self.ecu_sel.current()][3])
        out = out + "\nDialogType: " +  str(self.hdrs[self.ecu_sel.current()][4])
        out = out + "\nECU Code  : " +  str(self.hdrs[self.ecu_sel.current()][5])
        out = out + "\nDiagInit  : " +  str(self.ecuveids[self.ecuve_sel.current()]["diaginit"]) + " / " + str(self.ecuveids[self.ecuve_sel.current()]["init_ok"])
        out = out + "\nReCo      : " +  str(self.ecuveids[self.ecuve_sel.current()]["reco"]) + " / " + str(self.ecuveids[self.ecuve_sel.current()]["reco_ok"])

        self.output.insert(tk.END, out)


    def on_ecuve_sel_change(self, *largs):
        self.active_ecuveid = self.ecuveids[self.ecuve_sel.current()]["ecuveid"]
        self.render_readout()


    def on_ecu_sel_change(self, *largs):
        ecuid = self.ecuids[self.ecu_sel.current()]
        self.active_ecuid = ecuid
        lis = self.parent.bmb.get_ecuveids_for_ecuid(ecuid)

        self.ecuveids = []
        ecuve_values = []
        
        for variant in lis:
            ecuve_values.append(lis[variant]["variant"] + " - " + str(lis[variant]["reference"]))
            self.ecuveids.append(lis[variant])
        
        if len(ecuve_values) > 0:
            self.ecuve_sel['values'] = ecuve_values
            self.ecuve_sel['state'] = tk.NORMAL
            self.ecuve_sel.current(0)
            self.on_ecuve_sel_change()


    def on_fam_sel_change(self, *largs):
        '''
        user changed famid, load ecuis
        '''
        famid = self.famids[self.fam_sel.current()]

        self.ecuids = []
        self.hdrs = []
        ecu_values = []

        for bus in famid:
            options = famid[bus]["RECO"]
            for init_cmd in options:
                for ecu in options[init_cmd]:
                    name_id = ecu.split(":")
                    ecu_values.append(name_id[0])
                    self.ecuids.append(name_id[1])
                    self.hdrs.append(bus.split(":"))
        
        if len(ecu_values) > 0:
            self.ecu_sel['values'] = ecu_values
            self.ecu_sel['state'] = tk.NORMAL
            self.ecu_sel.current(0)
            self.on_ecu_sel_change()
        

    def on_veh_sel_change(self, *largs):
        '''
        user changed model, load families
        '''
        model = self.models[self.veh_sel.current()]["vehid"]
        lis = self.parent.bmb.get_vehicle_ecu_list(model)

        fam_values = []
        self.famids = []

        ecu = list(lis.keys())
        ecu.sort()

        for e in ecu:
            if lis[e] == {}:
                continue
            if e == "fam" or e == "prot" or e == "veh":
                continue
            fam_values.append(e)
            self.famids.append(lis[e])
        
        self.fam_sel['state'] = tk.NORMAL
        self.fam_sel['values'] = fam_values
        if len(fam_values) > 0:
            self.fam_sel.current(0)
            self.on_fam_sel_change()
    

class Application(tk.Frame):
    def __init__(self, root):
        self.root = root
        self.trs : diag_translations = diag_translations(lang="en", path="db/")
        self.bmb : diag_bramble = diag_bramble(self.trs, "db/")
        self.chooseWin = Load_ECU(root, self)
        self.UDSWin = UDS_Interface(root, self)
        self.FaultWin = Fault_Window(root, self)
        self.initialize_user_interface()
        
        self.save_path = "treeview_data/"
        if not os.path.isdir(self.save_path):
            os.makedirs(self.save_path)


    def initialize_user_interface(self):
        # Configure the root object for the Application
        self.root.title("Diagnostique - ECU Tree Visualiser")
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1, minsize=200)
        self.root.config(background="light blue")

        self.tvf = tk.Frame(self.root)
 
        # Set the treeview
        self.tree = ttk.Treeview(self.tvf, columns=('Name', 'Pos', 'Value'))
 
        # Set the heading (Attribute Names)
        self.tree.heading('#0', text='Item')
        self.tree.heading('#1', text='ID')
        self.tree.heading('#2', text="Pos")
        self.tree.heading('#3', text="Val")

        self.tree.column('#0', stretch=tk.YES)
        self.tree.column('#1', stretch=tk.YES)
        self.tree.column('#2', stretch=tk.YES)
        self.tree.column('#3', stretch=tk.YES)

        self.tree.bind("<1>", self.on_tree_select)
 
        self.tvf.grid(row=0, columnspan=3, sticky='nsw')
        self.treeview = self.tree

        self.tree.pack(side='left', fill='y')

        self.vsb = ttk.Scrollbar(self.tvf, orient="vertical", command=self.tree.yview)
        self.vsb.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=self.vsb.set)

        self.panel = tk.Frame(self.root)
        self.panel.grid(row=0, column=3, rowspan=1, sticky='nsew')

        self.new_file = tk.Button(self.panel, text="Choose ECU", command=self.on_new)
        self.new_uds = tk.Button(self.panel, text="UDS Session", command=self.on_uds)
        self.new_file.grid(row=0, column=0)
        self.new_uds.grid(row=0, column=1)

        self.faults = tk.Button(self.panel, text="Fault Listing", command=self.on_faults)
        self.faults.grid(row=1, column=0)

        self.load = tk.Button(self.panel, text="Load DGD", command=self.on_load)
        self.load.grid(row=1, column=1)


        self.field_ref = {}
        fields = { "label": "Label", 
                    "unit": "Unit", 
                    "desc": "Desc:", 
                    "abs": "Abs", 
                    "lenbi": "Bits Len", 
                    "lenby": "Byte Len", 
                    "msk": "Mask", 
                    "type": "Type", 
                    "format": "Format", 
                    "map": "Mapping", 
                    "dynblock": "Dynamic Blk", 
                    "block": "Block" }
        i = 2
        for field in fields:
            self.lbl_format = tk.Label(self.panel, text=fields[field] + ":")
            self.field_ref[field] = tk.StringVar()
            self.lbl_entry = tk.Entry(self.panel, textvariable = self.field_ref[field])
            self.lbl_format.grid(row=i, column=0)
            self.lbl_entry.grid(row=i, column=1)
            i += 1
        #print(self.field_ref.keys())

        self.statusbar = tk.Label(self.root, text="0 zones", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.statusbar.grid(row=1, column=0, sticky='swe')
        self.statusbarb = tk.Label(self.root, text="Ready to work..  ", bd=1, relief=tk.SUNKEN, anchor=tk.E)
        self.statusbarb.grid(row=1, column=1, columnspan=3, sticky='sew')
 
        self.id = 0


    def get_dgd(self, variant, ecuveid):
        self.fname = variant
        self.on_load(self.bmb.dump_ecu_frames(ecuveid, True, variant + " - " + str(ecuveid)))

    
    def generate_ecu_tree(self, spec):
        spec["CMDS"] = self.bmb.get_ecu_diag_cmds(spec["ECUVEID"])
        spec["FAULTS"] = -1
        spec["STATUS"] = "IDENTOK"
        spec["FAULT_TREE"] = {}
        spec["FRAME_TREE"] = self.bmb.get_data_frames(spec["ECUID"], spec["ECUVEID"])

        f = open(self.save_path + spec["VARIANT"] + ".yml", "w")
        print("Exporting yaml " + spec["VARIANT"])
        yaml.dump(spec, f)
        f.close()


    def on_new(self):
        '''
        Called when user wants to open the choose ECU window
        '''       
        self.chooseWin.createWin()

    
    def on_uds(self):
        '''
        Called when user opens UDS session
        '''
        self.UDSWin.createWin()


    def on_faults(self):
        '''
        Breakdown of faults
        '''
        self.FaultWin.createWin()


    def on_tree_select(self, event):
        '''
        Called when a user clicks a tree item
        '''
        
        p = self.tree.identify('item', event.x, event.y)
        if p == "":
            return
        iid = int(p)
        if iid < len(self.iid):
            for field in self.field_ref:
                if field in self.data[self.iid[iid][0]][self.iid[iid][1]][self.iid[iid][2]]["!props"]:
                    val = self.data[self.iid[iid][0]][self.iid[iid][1]][self.iid[iid][2]]["!props"][field]
                    if field == "label" or field == "help" or field == "desc":
                        self.field_ref[field].set(self.trs.decodalate(val))
                    elif val is not None:
                        self.field_ref[field].set(val)
                    else:
                        self.field_ref[field].set("")
                else:
                    self.field_ref[field].set("")


    def on_load(self, data = None):
        '''
        Open a pre-saved ECU file (json)
        '''
        self.tree.delete(*self.tree.get_children())

        if data is None:
            fname = askopenfilename()

            if fname is None or fname == "" or fname == ():
                return False

            fd = open(fname, 'r')
            data = json.load(fd)
            self.fname = fname

        ALTIID_SEED = 25000
        self.iid = []
        altiid = ALTIID_SEED
        self.data = data
        cnt = 0

        for zone in data:
            if zone == "!props":
                continue
        
            z = self.treeview.insert('', 'end', iid=altiid, text = data[zone]["!props"]["zonename"], values = (str(zone)))
            altiid += 1

            for frid in data[zone]:
                if frid == "!props":
                    continue

                f = self.treeview.insert(z, 'end', iid=altiid, text = data[zone][frid]["!props"]["ftype"], values = (str(frid)))
                altiid += 1

                for pid in data[zone][frid]:
                    if pid == "!props":
                        continue
                    nxt = (zone,frid,pid)
                    self.iid.append(nxt)
                    if data[zone][frid][pid]["!props"]["name"] is None:
                        data[zone][frid][pid]["!props"]["name"] = "<unnamed>"

                    next_iid = len(self.iid)
                    if next_iid >= ALTIID_SEED:
                        self.log("The ALTIID_SEED ID requires increasing to accomodate the number of frames for this ECU, giving up")
                        return

                    try:
                        p = self.treeview.insert(f, 'end', iid=next_iid - 1, text = data[zone][frid][pid]["!props"]["name"], values = (str(pid), data[zone][frid][pid]["!props"]["pos"], data[zone][frid][pid]["!props"]["defval"]))
                    except:
                        pass

                    for sid in data[zone][frid][pid]:
                        if sid == "!props":
                            continue

                        if sid == None or sid == "null":
                            continue

                        s = self.treeview.insert(p, 'end', iid=altiid, text = data[zone][frid][pid][sid]["!props"]["name"], values = (str(sid), "", data[zone][frid][pid][sid]["!props"]["val"]))
                        altiid += 1
                        '''self.treeview.insert('', 'end', iid=self.iid, text="Item_" + str(self.id),
                                            values=("Name: " + self.name_entry.get(),
                                                    self.idnumber_entry.get()))'''
            cnt += 1

        self.statusbar['text'] = str(cnt) + " services loaded from " + str(self.fname)


app = Application(tk.Tk())
app.root.mainloop()
