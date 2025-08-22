import os,sys,inspect
currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0,parentdir)

from diag_bramble import diag_bramble
from diag_translations import diag_translations
from diag_adapter import *

class proc_editor:
    '''
    (c) Diagnostique project 2021

    PROCEDURE_EDITOR / IMPORTER

    Utility to import custom/discovered procedures into the databases, usually laid out as actuator tests
    '''
    trs = None
    bmb = None


    def __init__(self):
        self.trs = diag_translations(lang="en_GB", path="../DU9/")
        self.bmb = diag_bramble(self.trs, path="../db/")


    def new_trans(self, en, fr=None, es=None):
        return en

    
    def generate(self):
        '''
        Do all the magic
        '''

        src = {}

        for row in data:
            vals = row.split("=")
            if vals[0] == "ECUIDS" or vals[0] == "ECUVEIDS":
                src[vals[0]] = vals[1].split(",")
            else:
                src[vals[0]] = vals[1]

        # convert actual strings to translations
        src["acthelp"] = self.new_trans(src["PROC_HELP"])
        src["title"] = self.new_trans(src["PROC_TITLE"])

        src["actendko"] = self.new_trans(src["PROC_ENDKO"])

        # generate all the internal ref names
        src["actname"] = src["PROC_NAME"]
        src["ctrlname"] = "ctl_" + src["PROC_NAME"]
        src["azonename"] = [ "SRBLID_" + src["PROC_NAME"] ,
                             "SRBLIDAR_" + src["PROC_NAME"],
                             "SRBLIDST_" + src["PROC_NAME"] ]
        


        # ACT TEST
        q = "INSERT INTO ACTTEST(actid,title,actname,acttype,actanim,acthelp,actuserinit,actuserstop,actrestart) VALUES(?,?,?,?,?,?,?,?,?)"


        # MAP_ECUACT
        q = "INSERT INTO MAP_ECUACT(ecuid,actid,scnid,ctrlid) "