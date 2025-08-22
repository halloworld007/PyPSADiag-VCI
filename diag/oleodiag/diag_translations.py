import sys, sqlite3
from .diag import diag

class diag_translations(diag):
    '''
    Decode translations (e.g. @P3876-4@\\+@T.)
    into their final values for the current language
    '''
    osets = []
    fname = ""
    lng = "en"
    lngui = "en"
    lngsui = ["en"]
    lngs = ["en", "fr", "pl", "hu", "es", "de"]
    strs = {}
    path = "db/"
    ui_lng = {}
    ecu_lng = {}
    TRS_MISSING = "@MISSING-TRANS@"


    def __init__(self, lang = "en", path="db/", langui = "en"):
        self.lng = lang
        self.lngui = langui
        self.path = path

        path = self.path + "lng.db"

        try:
            self.lconn = sqlite3.connect(path, check_same_thread=False)
            self.lc = self.lconn.cursor()
        except:
            print("Unable to find database file at " + str(path))


    def log(self, x):
        if self.bb is None:
            print("[TRS] " + str(x))
        else:
            print("[TRS] " + str(x))
            self.bb.logger("[TRS] " + str(x))


    def get_ecu_lng(self):
        '''
        Get ALL ecu friendly names
        '''
        out = {}
        self.lc.execute("SELECT ecustr, " + self.lngui + " FROM ECU")
        rslt = self.lc.fetchall()
        for row in rslt:
            out[row[0]] = row[1]
        
        return out


    def db_get(self, tbl, cat, ref):
        '''
        Get a specific translation from the db
        '''
        self.lc.execute("SELECT " + self.lng + " FROM " + tbl + " WHERE catid = ? AND appid = ?", [cat, ref])
        rslt = self.lc.fetchone()
        if rslt is not None and len (rslt) > 0:
            if rslt[0] is None:
                return "NULL"
            else:
                return rslt[0]
        else:
            return self.TRS_MISSING


    def ui(self, x):
        '''
        Get a UI translation
        '''
        try:
            if x == None:
                x = ""
            x = str(x)
            self.lc.execute("SELECT " + self.lngui + " FROM INTF WHERE uistr = ?", [x])
            rslt = self.lc.fetchone()
            if rslt is not None and len (rslt) > 0:
                #self.log("From: " + str(x) + " to " + str(rslt[0]))
                return rslt[0]
            else:
                self.log("Missing UI translation: " + str(x))
                return str(x)
        except:
            self.log("Missing UI translation: " + str(x))
            return str(x)


    def ecu(self, x):
        '''
        Get an ECU descriptor
        '''
        try:
            self.lc.execute("SELECT " + self.lngui + " FROM ECU WHERE ecustr = ?", [x])
            rslt = self.lc.fetchone()
            if rslt is not None and len (rslt) > 0:
                return rslt[0]
            else:
                return x
        except:
            return x

    
    def get(self, ref, cat = 1):
        '''
        Get a translation from the database
        '''
        if ref == "":
            return ""
        ref = int(ref) - 1

        return self.db_get("APP", cat, ref)


    def decodalate(self, raw, spf=None):
        '''
        Decode & translate a string, parsing if necessary
        - If you expect sprintf (e.g. for units of parameters) supply them as a list to spf
        - The syntax for this is not completely known yet.
        '''
        #print("R:" + str(raw))
        if spf != None:
            if type(spf) != list:
                spf = [ spf ]
            spr = len(spf)
        spf_used = False
        segments = []
        out = ""
        if raw == "" or raw == '' or raw == None:
            if spf == None:
                return ""
            else:
                for s in spf:
                    segments.append(s)
                out = " ".join(segments)
                if len(out) > 1:
                    out = out[0].capitalize() + out[1:]
                #self.log("short - From: " + str(raw) + " to " + str(out))
                return out

        spl = raw.split("$")
        spi = len(spl)
        spu = 0         # num of SPFs used
        params = 0
        for ix in range(0,spi):
            if params != 0:
                params -= 1
                continue

            par = spl[ix]
            
            plen = len(par)

            if plen > 0:
                # count how many * there are
                # count how many \\* follow
                # count how many we specify???
                # any leftover get deleted
                buffer = ""
                params = 0
                par_dn = 0

                # raw text
                if par[0] == "Y":
                    segments.append(par[1:])
                    continue

                elif par[0] == "U" and par[1] == "n":
                    if len(par[0]) > 2:
                        segments.append("\n" + par[2:])
                    else:
                        segments.append("\n")
                    continue
                
                # raw text append
                elif par[0] == "\\":
                    if len(par) > 1:
                        if par[1] == "+":
                            segments.append(par[2:])
                        elif par[1] == "*":
                            # there was no asterisk, so it's assumed to be a unit
                            if len(segments) > 0 and spf != None and len(spf) > 0:
                                segments.append(segments[len(segments)-1])
                                if spu < spr:
                                    segments[len(segments)-2] = spf[spu]
                                else:
                                    segments[len(segments)-2] = ""
                            else:
                                segments[len(segments)-2]
                            #self.log("Algorithmic error: parameter wasn't parsed : " + str(raw))
                            continue
                        elif par[1] == "n":
                            segments.append(par)
                            continue
                        else:
                            self.log("Unknown sprintf command in " + str(raw))
                            continue
                    else:
                        continue

                # Get from dict and SPRINTF as needed
                elif "-" in par:
                    par_s = par.split("-")
                    ref = par_s[0][1:]  # ref
                    tbl = par_s[1]      # cat

                    # sometimes non-parameters have '-' in them
                    if ref == '' or tbl == '':
                        continue
                    
                    try:
                        res = self.get(int(ref), tbl)
                        #print(res)
                    except Exception:
                        res = ""
                        self.log(f"Unhandled exception parsing: {raw}, {ref}, {tbl} : " + str(sys.exc_info()[0]))
                    
                    buffer = res
                
                    if "*" in res:
                        # count number of *
                        oss = 0
                        nex = buffer.find("*", oss)

                        while nex != -1:
                            if nex + 1 < len(buffer):                                   
                                if self.int(buffer[nex+1]) != 0:
                                    params += 1      
                            oss = nex+1
                            nex = buffer.find("*", oss)     
      
                        # apply any parameters available
                        if params != 0:
                            par_dn = 0
                            if ix+par_dn+1 < len(spl):
                            
                                nex = spl[ix+par_dn+1]

                                if nex[0] == "\\":
                                    while nex[0] == "\\":
                                        if len(nex) < 3:
                                            # it is just \* which means user must specify
                                            if spf == None:
                                                buffer = buffer.replace("*" + str(par_dn+1), "")
                                            else:
                                                if spu < spr:
                                                    buffer = buffer.replace("*" + str(par_dn+1), spf[spu])
                                                    spu += 1
                                                else:
                                                    buffer = buffer.replace("*" + str(par_dn+1), "")
                                        else:
                                            buffer = buffer.replace("*" + str(par_dn+1), nex[2:])
                                        par_dn += 1
                                        if ix + par_dn + 1 < spi:
                                            nex = spl[ix+par_dn+1]
                                        else:
                                            break
                                elif nex[0] == "U":
                                    buffer = buffer.replace("*1", nex[2:])
                        
                        # delete ones without values
                        if par_dn < params:
                            for ip in range(par_dn,params+1):
                                buffer = buffer.replace("*" + str(ip), "")
                            
                    segments.append(buffer)
                
                else:
                    segments.append(par)
            
        if spf != None and spf_used == False:
            out = spf[0] + " ".join(segments)
            if len(out) > 1:
                out = out[0].capitalize() + out[1:]
            #self.log("From: " + str(raw) + " to " + str(out))
            return out
        else:
            out = " ".join(segments)
            if len(out) > 1:
                out = out[0].capitalize() + out[1:]
            #self.log("From: " + str(raw) + " to " + str(out))
            return out
        #except:
        #    self.log("Error whilst parsing : " + str(raw))
        #    return " ".join(segments)
