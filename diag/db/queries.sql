Get BLOCK info for block ids
:get_blocks:
    SELECT * FROM BLOCKNORM WHERE bloid IN (!)

;Get zones for an ECUVE simple
:get_zones_for_ecuve:
SELECT DISTINCT ZONES.zonename FROM ZONES
    INNER JOIN ECUSER ON ECUSER.serid = ZONES.serid
    WHERE ECUSER.ecuveid = ?

;Get ECUVE options for ECUID
:get_ecuve_from_ecu:
    SELECT * FROM ECUVEMAP
    INNER JOIN ECUVE ON ECUVE.ecuveid = ECUVEMAP.ecuveid
    WHERE ECUVEMAP.ecuid = ?

;Get ECU options for ECUVE
:get_ecu_from_ecuve:
    SELECT ecuid FROM ECUVEMAP
    WHERE ECUVEMAP.ecuveid = ?

;Get the fault frame for a given ECUVEID
:get_fault_frame_for_ecuve:
    SELECT FRAMES.ftype, FRAMES.frid, FRAPAS.*, PARAMS.parname, PARFORMAT.*, ZONES.zonename FROM FRAPAS
    INNER JOIN PARAMS on PARAMS.pid = FRAPAS.pid
    INNER JOIN FRAMES on FRAMES.frid = FRAPAS.frid 
    INNER JOIN ZONES on ZONES.zoneid = FRAMES.zoneid
    INNER JOIN ECUSER ON ECUSER.serid = ZONES.serid
    LEFT JOIN PARFORMAT ON PARFORMAT.pid = PARAMS.pid
    WHERE 
        ECUSER.ecuveid = ?
        AND ZONES.zonename IN ('RDCDTCI_PERMANENT','RDDTC','RDBI_FAULTREAD','RDDTCS','RDDTCSS','RDSDTC','RDTCBI_OC','RDTCI','RDTCI_02','RDTCI_04','RDTCS_SBDTC')
        /* 'RDSDTC_JDD'*/

;Get the fault request frame (query) for a given ECUVEID
:get_fault_clear_cmd:
SELECT ZONES.zonename,  PARAMS.parname, FRAPAS.val, FRAPAS.pos, FRAMES.ftype  FROM FRAPAS
    INNER JOIN PARAMS on PARAMS.pid = FRAPAS.pid
    INNER JOIN FRAMES on FRAMES.frid = FRAPAS.frid 
    INNER JOIN ZONES on ZONES.zoneid = FRAMES.zoneid
    INNER JOIN ECUSER ON ECUSER.serid = ZONES.serid
    LEFT JOIN PARFORMAT ON PARFORMAT.pid = PARAMS.pid
    WHERE 
        ECUSER.ecuveid = ?
        AND zonename IN ('CLRDTC_ALL_GODTC','CLRDTC_GDTC_FF00','CLRDTC_DINF_VALUE','CLRDTC','CLRDI_GDTC_FF00','CLRDTC_GroupOfDTC','CLRDTC_GDTC_TLGDP','CLRDTC_GDTC','CLRDTC_AFFICHEUR','CLRDTC_AUTORADIO','CLRDTC_CHANG_CD','CLRDTC_CLAVIER','CLRDTC_CMD_DEP_SOUS_VOLANT','CLRDTC_DEUX_TUNER_RADIO','CLRDTC_FONCT_APPEL_URG','CLRDTC_INFOS_VAN','CLRDTC_INPUT_AUDIO','CLRDTC_LECT_CD','CLRDTC_MOD_GPS','CLRDTC_MOD_GSM','CLRDTC_OUTPUT_AUDIO','CLRDTC_TUNER_TV_VAN','CLRDTC_VENTILO')

;Get a list of old TELESCR
:get_old_tlcd_screens:
    SELECT DISTINCT TLCDPROC.pname, TLCDPROC.rlabel, TLCDPROC.wlabel 
    FROM TLCDPROC
    INNER JOIN TLCDPROCMAP ON TLCDPROCMAP.prid = TLCDPROC.prid
    INNER JOIN TLCD ON TLCDPROCMAP.tlpid = tlcd.tlpid 
    LEFT JOIN TLCDVAL ON TLCDVAL.tlpid = TLCD.tlpid
    WHERE TLCD.ecuid = ?

;Get a list of old tlcd screens and their zones
:get_zones_for_old_tlcds:
SELECT DISTINCT TLCDPROC.pname, TLCDPROC.rlabel, TLCDPROC.wlabel, TLCDPROCMAP.rzone, TLCDPROCMAP.wzone 
    FROM TLCDPROC
    INNER JOIN TLCDPROCMAP ON TLCDPROCMAP.prid = TLCDPROC.prid
    INNER JOIN TLCD ON TLCDPROCMAP.tlpid = tlcd.tlpid 
    LEFT JOIN TLCDVAL ON TLCDVAL.tlpid = TLCD.tlpid
    WHERE TLCD.ecuid = ?

;Get a list of ECUs for reco matching
:get_reco_from_ecuname:
    SELECT ECUVE.ecuveid, variant, idreco, idreco_pos, idreco_len
    FROM ECUVE 
    INNER JOIN ECUVEMAP ON ECUVE.ecuveid = ECUVEMAP.ecuveid
    WHERE ecuname = ?
    AND ECUVEMAP.ecuid = ?

;Get a list of all frames/parameters for an ECU, as much data from ECUVE as poss
:dump_frames_all_data:
SELECT DISTINCT FRAPAS.*, FRAMES.*, ZONES.*, PARAMS.*, PARFORMULA.*, STATES.*, PARFORMAT.len_bytes, PARFORMAT.len_bits, PARFORMAT.bin_mask, PARFORMAT.byteorder, PARFORMAT.abs_no, PARFORMAT.dattype AS pf_dattype FROM FRAPAS
    INNER JOIN FRAMES ON FRAMES.frid = FRAPAS.frid 
    INNER JOIN ZONES ON ZONES.zoneid = FRAMES.zoneid 
    LEFT JOIN PARAMS ON FRAPAS.pid = PARAMS.pid 
    LEFT JOIN STATES ON STATES.pid = PARAMS.pid AND PARAMS.parname NOT IN ("SID_PR","RecordDataFilter","SIDRQ_NR", "SID_NR",  "SID")
    LEFT JOIN PARFORMAT ON PARFORMAT.pid = PARAMS.pid 
    LEFT JOIN PARFORMULA ON PARFORMULA.pid = PARAMS.pid
    WHERE FRAPAS.frid IN (SELECT DISTINCT FRAMES.frid FROM FRAMES 
    WHERE FRAMES.zoneid IN (SELECT DISTINCT ZONES.zoneid FROM ZONES
    INNER JOIN ECUSER ON ECUSER.serid = ZONES.serid   
    WHERE ECUSER.ecuveid = ?))

;Get a list of all param labels for an ECU
:match_edata_for_ecu_dump:
SELECT EDATA.* FROM EDATA 
WHERE EDATA.edatid IN (SELECT DIAGSCRDAT.edatid FROM DIAGSCRDAT
    LEFT JOIN DIAGSCR ON DIAGSCR.scrid = DIAGSCRDAT.scrid 
    LEFT JOIN ECU ON DIAGSCR.ecuid = ECU.ecuid 
    WHERE ECU.ecuid = ?) 
    UNION 
    SELECT EDATA.* FROM EDATA
    WHERE EDATA.edatid IN (SELECT TELESCRPARMAP.edatid FROM TELESCRPARMAP
    LEFT JOIN TELESCR ON TELESCR.scrid = TELESCRPARMAP.scrid 
    LEFT JOIN ECU ON TELESCR.ecuid = ECU.ecuid 
    WHERE ECU.ecuid = ?)

;Get a list of frames/parameters for an ECU, including states but will not include any without states (v slow)
:dump_frames_params_with_states_only:
SELECT FRAPAS.frid, ZONES.zonename, FRAMES.ftype, PARAMS.parname, STATES.statname, STATES.statval FROM FRAPAS
    INNER JOIN STATES ON STATES.pid = PARAMS.pid
	INNER JOIN PARAMS ON FRAPAS.pid = PARAMS.pid
    INNER JOIN FRAMES ON FRAPAS.frid = FRAMES.frid
    INNER JOIN ZONES ON ZONES.zoneid = FRAMES.zoneid
    INNER JOIN ECUSER ON ECUSER.serid = ZONES.serid
    WHERE ECUSER.ecuveid = ?
    ORDER BY FRAPAS.frid

;Get a list for global test including headers, ECUIDs
:get_veh_ecu_list:
SELECT DISTINCT ECUCATEGORY.category, ECUTYPE.ecuname, ECU.ecuid, ECUTYPE.ecuprot, ECUFAMILY.bus, ECUFAMILY.tx_h, ECUFAMILY.rx_h, ECUFAMILY.dialog, ECUFAMILY.target, ECUVE.reco_rq, ECUVE.init_rq    FROM ECU
    INNER JOIN ECUTYPE ON ECUTYPE.ecutyid = ECU.ecutyid 
    INNER JOIN ECUCATEGORY ON ECUCATEGORY.categoryid = ECUFAMILY.categoryid 
    INNER JOIN ECUFAMILY ON ECU.famid = ECUFAMILY.famid 
    INNER JOIN ECUVE ON ECUVE.ecuveid = ECUVEMAP.ecuveid
    INNER JOIN ECUVEMAP on ECUVEMAP.ecuid = ECU.ecuid 
    WHERE 
    ECUFAMILY.vehid = ?
    ORDER BY ECUCATEGORY.category, ECUVE.init_rq

;Get a list of RECO ids for the given ECU type
:get_ecu_reco_opts:
    SELECT DISTINCT ECUVE.ecuveid, ECUVE.variant, ECUVE.ecuname, ECUVE.idreco, ECUVE.idreco_pos, ECUVE.idreco_len 
    FROM ECUVE
    WHERE 
    ECUVE.ecuname IN (?) AND
    ECUVE.variant LIKE ?

;Get a list of FRAMES which match the given zone name (useful for finding a parameters request frame)
:get_frames_for_zonename:
SELECT FRAPAS.frid, pos, val, ZONES.zonename, SERVICES.sername, FRAPAS.blo, FRAPAS.dyn, BLOCKNORM.blobytepos, BLOCKDYN.dynbytepos FROM FRAPAS
    INNER JOIN FRAMES ON FRAPAS.frid = FRAMES.frid
    INNER JOIN ZONES ON ZONES.zoneid = FRAMES.zoneid
    INNER JOIN ECUSER ON ECUSER.serid = ZONES.serid
    INNER JOIN SERVICES ON SERVICES.serid = ZONES.serid
    LEFT JOIN BLOCKDYN ON FRAPAS.dyn = BLOCKDYN.dynid
    LEFT JOIN BLOCKNORM ON FRAPAS.blo = BLOCKNORM.bloid
    WHERE ECUSER.ecuveid = ?
    AND ZONES.zonename = ?
    AND FRAMES.ftype = 0

;Get a list of FRAMES which match the given zone name (useful for finding a parameters request frame)
:get_frames_for_zonename_collated:
SELECT FRAPAS.frid, pos, val, ZONES.zonename, SERVICES.sername, FRAPAS.blo, FRAPAS.dyn, BLOCKNORM.blobytepos, BLOCKDYN.dynbytepos FROM FRAPAS
    INNER JOIN FRAMES ON FRAPAS.frid = FRAMES.frid
    INNER JOIN ZONES ON ZONES.zoneid = FRAMES.zoneid
    INNER JOIN ECUSER ON ECUSER.serid = ZONES.serid
    INNER JOIN SERVICES ON SERVICES.serid = ZONES.serid
    LEFT JOIN BLOCKDYN ON FRAPAS.dyn = BLOCKDYN.dynid
    LEFT JOIN BLOCKNORM ON FRAPAS.blo = BLOCKNORM.bloid
    WHERE ECUSER.ecuveid = ?
    AND ZONES.zonename IN (!)
    AND FRAMES.ftype = 0

;Get a list of ACTSTATUS for a given set of ctrlids
:get_ctrlstatus_from_ctrl:
    SELECT * FROM ACTSTATUS
    INNER JOIN MAP_ACTCTRLSTATUS ON MAP_ACTCTRLSTATUS.actstatid = ACTSTATUS.actstatid 
    WHERE MAP_ACTCTRLSTATUS.ctrlid IN (!)

;Get a list of frames matching the given zonename(s)
:get_all_frames_for_zonenames:
    SELECT FRAPAS.*, FRAMES.ftype, ZONES.zonename, PARAMS.parname, PARAMS.encode, STATES.statname, STATES.statdesc, STATES.statval, STATES.mini, STATES.maxi FROM FRAPAS
	INNER JOIN PARAMS ON FRAPAS.pid = PARAMS.pid
    INNER JOIN FRAMES ON FRAPAS.frid = FRAMES.frid
    INNER JOIN ZONES ON ZONES.zoneid = FRAMES.zoneid
    INNER JOIN ECUSER ON ECUSER.serid = ZONES.serid
    LEFT JOIN STATES ON PARAMS.pid = STATES.pid
    WHERE ECUSER.ecuveid = ? AND 
    ZONES.zonename IN(!)
    ORDER BY FRAPAS.frid, pos

;Get a list of zonenames a given ECU uses for act tests
:get_zonenames_for_ecu_act:
    SELECT DISTINCT ACTZONE.azonename, ACTCTRL.reqstatusparname 
    FROM ACTTEST  
    INNER JOIN ACTCTRL ON ACTCTRL.ctrlid = MAP_ECUACT.ctrlid
    INNER JOIN ACTZONE ON ACTZONE.azoneid = MAP_ACTCTRLZONE.azoneid 
    INNER JOIN MAP_ACTCTRLZONE ON MAP_ACTCTRLZONE.ctrlid = MAP_ECUACT.ctrlid 
    INNER JOIN ACTSCREEN ON ACTSCREEN.scrid = MAP_ACTTESTSCR.scrid 
    INNER JOIN MAP_ACTTESTSCR ON MAP_ACTTESTSCR.actid = MAP_ECUACT.actid
    INNER JOIN ACTSCN ON MAP_ECUACT.scnid = ACTSCN.scnid 
    INNER JOIN MAP_ECUACT ON MAP_ECUACT.actid = ACTTEST.actid 
    WHERE MAP_ECUACT.ecuid = ?

;Get a list of values for a given PID(s)
:get_states_for_pids:
    SELECT * FROM STATES
    WHERE STATES.pid IN (!)

;Get a list of ACTSTEP for a given set of scnids
:get_steps_from_scnids:
    SELECT * FROM ACTSTEP 
    INNER JOIN MAP_ACTSCNSTEP ON ACTSTEP.stepid = MAP_ACTSCNSTEP.stepid 
    WHERE MAP_ACTSCNSTEP.scnid IN (!)

;Get step data from step IDs
:get_act_step_data:
SELECT * FROM ACTSTEP
LEFT JOIN MAP_ACTSTEPPAR ON MAP_ACTSTEPPAR.stepid = ACTSTEP.stepid 
LEFT JOIN ACTPARAM ON ACTPARAM.actpid = MAP_ACTSTEPPAR.actpid 
WHERE ACTSTEP.stepid in (!)

;Get a breakdown of screens/ctrls etc for actuator tests for a given ECU
:get_ecu_act_data:
    SELECT ACTTEST.acttitle, ACTTEST.actname, ACTTEST.acttype, MAP_ECUACT.ctrlid, ACTSCN.scnid, ACTSCN.scnname, ACTSCREEN.scrlabel, ACTSCREEN.scrtype 
    FROM ACTTEST 
    INNER JOIN ACTSCREEN ON ACTSCREEN.scrid = MAP_ACTTESTSCR.scrid
    INNER JOIN MAP_ACTTESTSCR ON MAP_ACTTESTSCR.actid = MAP_ECUACT.actid
    INNER JOIN ACTSCN ON ACTSCN.scnid = MAP_ECUACT.scnid 
    INNER JOIN MAP_ECUACT ON MAP_ECUACT.actid = ACTTEST.actid 
    WHERE MAP_ECUACT.ecuid = ?

; Get parameters for a given ACTzoneid
:get_acttest_zones_for_ecu:
    SELECT MAP_ECUACT.ctrlid, ACTZONE.azoneid, ACTZONE.azonename, ACTZONE.azonerole, ACTPARAM.actparname, ACTPARAM.acttype, MAP_ACTZONEPAR.actzvalue
    FROM ACTTEST
    INNER JOIN ACTZONE ON ACTZONE.azoneid = MAP_ACTCTRLZONE.azoneid 
    INNER JOIN ACTPARAM ON ACTPARAM.actpid = MAP_ACTZONEPAR.actpid 
    INNER JOIN MAP_ACTZONEPAR ON MAP_ACTZONEPAR.azoneid = ACTZONE.azoneid 
    INNER JOIN MAP_ACTCTRLZONE ON MAP_ACTCTRLZONE.ctrlid = MAP_ECUACT.ctrlid 
    INNER JOIN MAP_ECUACT ON MAP_ECUACT.actid = ACTTEST.actid 
    WHERE MAP_ECUACT.ecuid = ?

;Get edata param info from a edatid
:get_edata_from_pid:
    SELECT EDATA.edatid, parname, EDATAVAL.dvname, EDATAVAL.dvlabel FROM EDATA
    INNER JOIN EDATAVALMAP ON EDATAVALMAP.edatid = EDATA.edatid 
    INNER JOIN EDATAVAL ON EDATAVAL.dvid = EDATAVALMAP.dvid 
    WHERE EDATA.edatid IN (!)

;comment
:get_dtc_all:
    SELECT DTC.dtcid, DTC.internal_code, DTC.display_code, DTC.dtclabel, DTC.dtchelp, DTC.descrip
    FROM DTC
    INNER JOIN DTC2GRP ON DTC2GRP.dtcid = DTC.dtcid 
    INNER JOIN ECU ON DTC2GRP.dtcgrpid = ECU.dtcgrpid 
    WHERE ECU.ecuid = ?
    ORDER BY DTC.internal_code

;Get supported FRAPAS for the given ECUVEID
:get_ecuframes:
    SELECT FRAMES.frid, ECUSER.ecuveid 
    FROM FRAMES
    INNER JOIN ZONES ON ZONES.zoneid = FRAMES.zoneid
    INNER JOIN ECUSER ON ECUSER.serid = ZONES.serid
    WHERE ECUSER.ecuveid = ?

;Get DTC properties and value names
:get_dtc_char:
   SELECT DTC2PROPERTY.dtcid, DTC.internal_code, DTC.ff, PROPERTY.label, PROPERTY.parname, PROPVAL.statname, PROPVAL.label as "vlabel"
    FROM PROPERTY
    INNER JOIN DTC ON DTC.dtcid = DTC2PROPERTY.dtcid 
    INNER JOIN DTC2PROPERTY ON DTC2PROPERTY.propid = PROPERTY.propid 
    INNER JOIN DTC2VAL on DTC2VAL.propid = PROPERTY.propid 
    INNER JOIN PROPVAL ON PROPVAL.provalid = DTC2VAL.provalid
    WHERE DTC2PROPERTY.dtcid IN (
		    SELECT DTC.dtcid
			    FROM DTC
			    INNER JOIN DTC2GRP ON DTC2GRP.dtcid = DTC.dtcid 
			    INNER JOIN ECU ON DTC2GRP.dtcgrpid = ECU.dtcgrpid 
    			WHERE ECU.ecuid = ? AND DTC.internal_code IN (!))

;Get values from STATES matching the DTC values
:get_dtc_charvalues:
    SELECT PARAMS.parname, STATES.statname, STATES.statval, STATES.mini, STATES.maxi, PARFORMAT.bin_mask
    FROM STATES
    INNER JOIN PARFORMAT ON PARAMS.pid = PARFORMAT.pid 
    INNER JOIN FRAPAS ON PARAMS.pid = FRAPAS.pid
    INNER JOIN PARAMS ON STATES.pid = PARAMS.pid
    INNER JOIN FRAMES ON FRAPAS.frid = FRAMES.frid 
    INNER JOIN ZONES ON ZONES.zoneid = FRAMES.zoneid
    INNER JOIN ECUSER ON ECUSER.serid = ZONES.serid
    WHERE ECUSER.ecuveid = ? 
    	AND 
		    PARAMS.parname IN (SELECT PROPERTY.parname
		    FROM PROPERTY
		    INNER JOIN DTC2PROPERTY ON DTC2PROPERTY.propid = PROPERTY.propid 
		    WHERE DTC2PROPERTY.dtcid IN (!))

;Get states for a set of edata parameters
:get_states_for_pids:
    SELECT DISTINCT * FROM STATES WHERE pid IN (!)

;Get value of certain positions in a FRAME
:get_frame_info:
    SELECT frid, pos, val FROM FRAPAS
    WHERE frid in (!) AND pos in (!)

;Get PARFORMAT for one or more pids
:get_parformats:
    SELECT * FROM PARFORMAT
    WHERE pid in (!)

;Get PARFORMULA for one or more pids
:get_parformulas:
    SELECT * FROM PARFORMULA
    WHERE pid IN (!)
    
;Get teledata for ECU
:get_teledata_for_ecu:
    SELECT EDATA.elabel, EDATA.ehelp, EDATA.eunit, EDATA.parname, EDATA.edatid, TELESCR.scrname, TELESCRPARMAP.runit, TELESCRPARMAP.wunit FROM EDATA
	INNER JOIN TELESCRPARMAP ON TELESCRPARMAP.edatid = EDATA.edatid 
	INNER JOIN TELESCR ON TELESCR.scrid = TELESCRPARMAP.scrid 
	WHERE 
	TELESCR.ecuid = ?

;Get teledata values for ecu
:get_teledataval:
    SELECT * FROM TELEVAL
	INNER JOIN TELEPARVALMAP ON TELEVAL.tleid = TELEPARVALMAP.tleid
	WHERE TELEPARVALMAP.edatid IN (!)
    
;Get EDATAVAL for given edatids
:get_edataval:
    SELECT * FROM EDATAVAL
	INNER JOIN EDATAVALMAP ON EDATAVAL.dvid = EDATAVALMAP.dvid
	WHERE EDATAVALMAP.edatid IN (!)

;Get a set of edata for the ECU
:get_edata_for_ecu:
	SELECT EDATA.elabel, EDATA.ehelp, EDATA.eunit, EDATA.parname, EDATA.edatid, DIAGSCR.scrname FROM EDATA
	INNER JOIN DIAGSCR ON DIAGSCR.scrid = DIAGSCRDAT.scrid 
	INNER JOIN DIAGSCRDAT ON EDATA.edatid = DIAGSCRDAT.edatid 
	WHERE 
	DIAGSCR.ecuid = ?

;Look up a set of edata parnames up in PARAMS (use above)
:match_edata_for_ecu:
    SELECT 
        DISTINCT FRAMES.frid, PARAMS.pid, PARAMS.parname, PARAMS.encode, ZONES.zonename, FRAPAS.*, PARAMS.dattype, BLOCKDYN.*
    FROM FRAMES
    INNER JOIN PARAMS ON PARAMS.pid = FRAPAS.pid
    INNER JOIN FRAPAS ON FRAPAS.frid = FRAMES.frid
    INNER JOIN ZONES ON ZONES.zoneid = FRAMES.zoneid
    INNER JOIN ECUSER ON ECUSER.serid = ZONES.serid 
    LEFT JOIN BLOCKDYN ON FRAPAS.dyn = BLOCKDYN.dynid
    WHERE
        ECUSER.ecuveid = ?
        AND 
        PARAMS.parname IN (!)

;Make sure we got all parameters for the relevant frame ids
:validate_edata_for_ecu:
    SELECT FRAPAS.*, ZONES.zonename, PARAMS.*, BLOCKDYN.*, PARFORMAT.* FROM FRAPAS 
    INNER JOIN PARAMS ON PARAMS.pid = FRAPAS.pid 
    INNER JOIN FRAMES ON FRAMES.frid = FRAPAS.frid
    INNER JOIN ZONES ON ZONES.zoneid = FRAMES.zoneid
    INNER JOIN PARFORMAT ON PARFORMAT.pid = FRAPAS.pid
    LEFT JOIN BLOCKDYN ON FRAPAS.dyn = BLOCKDYN.dynid 
    WHERE FRAPAS.frid IN (!)


;Get all zones supported by an ECUVEID, is used to speed up matching elsewhere
:get_ecuve_zones:
SELECT ZONES.zoneid FROM ZONES
        INNER JOIN ECUSER ON ECUSER.serid = ZONES.serid
        INNER JOIN SERVICES ON ECUSER.serid = SERVICES.serid
        WHERE ECUSER.ecuveid = ?

;Get all writable zones for an ECU
:get_rdb_for_old_tele:
SELECT DISTINCT zones.zoneid FROM ZONES 
	INNER JOIN PARAMS ON PARAMS.pid = FRAPAS.pid 
    INNER JOIN FRAPAS ON FRAPAS.frid = FRAMES.frid 
    INNER JOIN FRAMES ON FRAMES.zoneid = ZONES.zoneid
	WHERE 
	FRAMES.zoneid IN (!)	
    AND FRAMES.ftype = 1 
	AND zones.zonename LIKE "RDB%" 
	AND FRAPAS.pid IN (!)

;Get write and read services for all parameters linked to frames previously obtained
:get_read_and_write_svc_experimental:
SELECT FRAPAS.*, ZONES.zonename, ZONES.zoneid, PARAMS.*, BLOCKDYN.*, PARFORMAT.* FROM FRAPAS 
INNER JOIN PARAMS ON PARAMS.pid = FRAPAS.pid 
INNER JOIN FRAMES ON FRAMES.frid = FRAPAS.frid
INNER JOIN ZONES ON ZONES.zoneid = FRAMES.zoneid
INNER JOIN PARFORMAT ON PARFORMAT.pid = FRAPAS.pid
LEFT JOIN BLOCKDYN ON FRAPAS.dyn = BLOCKDYN.dynid 
WHERE
FRAPAS.pid IN (SELECT FRAPAS.pid FROM FRAPAS WHERE FRAPAS.frid IN (!))
AND 
FRAPAS.frid IN (SELECT FRAMES.frid FROM FRAMES
				INNER JOIN ZONES on FRAMES.zoneid = ZONES.zoneid 
				WHERE ZONES.serid IN (SELECT ECUSER.serid FROM ECUSER WHERE ECUSER.ecuveid = ?))
AND PARAMS.parname NOT LIKE "SID" AND PARAMS.parname NOT LIKE "LID"
        
;Get all writable zones
:get_wdb_for_old_tele:
SELECT DISTINCT params.pid, zones.zoneid
        FROM FRAMES
        INNER JOIN PARAMS ON PARAMS.pid = FRAPAS.pid 
        INNER JOIN FRAPAS ON FRAPAS.frid = FRAMES.frid 
        INNER JOIN ZONES ON ZONES.zoneid = FRAMES.zoneid
        WHERE FRAMES.zoneid IN (!)
	 	AND FRAMES.ftype = 0 AND zones.zonename LIKE "WDB%"

;Get a basic list of zones used by old telecoding parameters (to validate if there are any)
:get_tlcd_old_validate:
SELECT DISTINCT FRAMES.frid
        FROM FRAMES
        INNER JOIN TLCD ON PARAMS.parname = TLCD.pid
        INNER JOIN PARAMS ON PARAMS.pid = FRAPAS.pid 
        INNER JOIN FRAPAS ON FRAPAS.frid = FRAMES.frid 
        INNER JOIN ZONES ON ZONES.zoneid = FRAMES.zoneid
        INNER JOIN ECUSER ON ECUSER.serid = ZONES.serid
        INNER JOIN SERVICES ON ECUSER.serid = SERVICES.serid
        WHERE ECUSER.ecuveid = ? AND TLCD.ecuid = ? AND FRAMES.ftype = 1

;Get telecoding parameters and states from TLCD (old style telecoding)
:get_tlcd_old_xml:
    SELECT DISTINCT TLCD.*, TLCDVAL.*
    FROM TLCD
    LEFT JOIN TLCDVAL ON TLCDVAL.tlpid = TLCD.tlpid
    WHERE TLCD.ecuid = ?

;Get telecoding screen imposed parameters
:get_tlcd_imp_val:
SELECT * FROM TLCDPROCMAP WHERE ecuid = ?

;Get a set of REQ/ANSOK/KO frames for a given FRID
:get_fridset_from_frid:
    SELECT FRAPAS.*, FRAMES.ftype, PARAMS.parname FROM FRAPAS 
    INNER JOIN PARAMS ON FRAPAS.pid = PARAMS.pid
    INNER JOIN FRAMES ON FRAMES.frid = FRAPAS.frid
    WHERE FRAMES.zoneid IN (SELECT FRAMES.zoneid FROM FRAMES WHERE FRAMES.frid = ?)
    ORDER BY FRAPAS.pos

;Get a set of REQ/ANSOK/KO frames for a given FRID
:get_fridset_from_zone_list:
SELECT FRAPAS.*, FRAMES.ftype, PARAMS.parname, ZONES.zonename FROM FRAPAS
	INNER JOIN PARAMS ON FRAPAS.pid = PARAMS.pid
    INNER JOIN FRAMES ON FRAPAS.frid = FRAMES.frid
    INNER JOIN ZONES ON ZONES.zoneid = FRAMES.zoneid
    INNER JOIN ECUSER ON ECUSER.serid = ZONES.serid
    WHERE ECUSER.ecuveid = ? and ZONES.zonename IN(!)
    ORDER BY FRAPAS.frid, FRAMES.ftype, pos

;Get telecoding parameters (states later)
:get_tlcd_frapas_params:
    SELECT zones.zonename, FRAPAS.*, FRAMES.ftype, PARAMS.pid, PARAMS.dattype, PARAMS.parname, PARFORMAT.len_bytes, PARFORMAT.len_bits, PARFORMAT.bin_mask, PARFORMAT.byteorder, PARFORMAT.abs_no, PARFORMAT.dattype AS pf_dattype, PARFORMULA.*
    FROM FRAPAS 
    INNER JOIN FRAMES ON FRAPAS.frid = FRAMES.frid 
    INNER JOIN ZONES ON ZONES.zoneid = FRAMES.zoneid
    INNER JOIN PARAMS ON PARAMS.pid = FRAPAS.pid
    LEFT JOIN PARFORMAT ON PARAMS.pid = PARFORMAT.pid 
    LEFT JOIN PARFORMULA ON PARAMS.pid = PARFORMULA.pid
    WHERE ZONES.zoneid IN (SELECT DISTINCT FRAMES.zoneid
        FROM FRAPAS
        INNER JOIN TLCD ON PARAMS.parname = TLCD.pid
        INNER JOIN PARAMS ON FRAPAS.pid = PARAMS.pid
        INNER JOIN FRAMES ON FRAPAS.frid = FRAMES.frid 
        INNER JOIN ZONES ON ZONES.zoneid = FRAMES.zoneid
        INNER JOIN ECUSER ON ECUSER.serid = ZONES.serid
        INNER JOIN SERVICES ON ECUSER.serid = SERVICES.serid
        WHERE ECUSER.ecuveid = ?
        AND TLCD.ecuid = ?) 
        ORDER BY ZONES.zonename, FRAPAS.frid, FRAPAS.pos
	
;Get telecoding FRAME list to tell you which ones are write/response frames
:get_tlcd_frames:
    SELECT FRAPAS.frid, FRAPAS.pid, FRAPAS.pos, FRAPAS.val FROM FRAPAS 
    WHERE FRAPAS.pos = 1 
    AND 
    FRAPAS.frid IN(SELECT DISTINCT FRAMES.frid
    FROM FRAMES
    INNER JOIN TLCD ON PARAMS.parname = TLCD.pid
    INNER JOIN PARAMS ON PARAMS.pid = FRAPAS.pid 
    INNER JOIN FRAPAS ON FRAPAS.frid = FRAMES.frid 
    INNER JOIN ZONES ON ZONES.zoneid = FRAMES.zoneid
    INNER JOIN ECUSER ON ECUSER.serid = ZONES.serid
    INNER JOIN SERVICES ON ECUSER.serid = SERVICES.serid
    WHERE ECUSER.ecuveid = ?
    AND TLCD.ecuid = ?
)


;Given a FRAME id, get full frame str - includes lot of junk, no problem
:get_tlcd_frid:
SELECT PARAMS.parname, FRAPAS.val, STATES.stid, STATES.statval, FRAPAS.pos, FRAMES.ftype FROM 
FRAPAS 
INNER JOIN FRAMES ON FRAMES.frid = FRAPAS.frid
INNER JOIN STATES ON STATES.pid = PARAMS.pid
INNER JOIN PARAMS ON PARAMS.pid = FRAPAS.pid 
WHERE FRAPAS.frid = ?

;Very slow and doesnt really work anyway (legacy)
:get_dtc_everything:
    SELECT PROPERTY.label, PROPVAL.label, STATES.val, PARFORMAT.bin_mask, DTC.dtcid, PARAMS.pid
    FROM PROPERTY
        INNER JOIN PROPVAL ON DTC2VAL.provalid = PROPVAL.provalid 
        INNER JOIN DTC2PROPERTY ON DTC2PROPERTY.propid = PROPERTY.propid 
        INNER JOIN DTC2VAL ON DTC2VAL.propid = PROPERTY.propid 
        INNER JOIN DTC2GRP ON DTC2GRP.dtcid = DTC2PROPERTY.dtcid
        INNER JOIN DTC	   ON DTC.dtcid = DTC2PROPERTY.dtcid
        INNER JOIN ECU     ON ECU.dtcgrpid = DTC2GRP.dtcgrpid 
        INNER JOIN PARAMS  ON PARAMS.parname = PROPERTY.parname 
        INNER JOIN ECUSER  ON ECUSER.serid = ZONES.serid
        INNER JOIN ZONES   ON ZONES.zoneid = FRAMES.zoneid 
        INNER JOIN FRAMES  ON FRAMES.frid = FRAPAS.frid 
        INNER JOIN FRAPAS  ON PARAMS.pid = FRAPAS.pid 
        INNER JOIN STATES  ON STATES.pid = PARAMS.pid 
        INNER JOIN PARFORMAT ON PARFORMAT.pid = PARAMS.pid 
        WHERE ECU.ecuid = 4451 AND ECUSER.ecuveid = 14722 AND DTC.internal_code = 1579


;Get telecoding parameters, values and states for an ECU/ECUVEID pair (legacy)
:get_tlcd_all:
    SELECT DISTINCT FRAPAS.frid, PARAMS.pid, PARAMS.parname, TLCD.help, TLCD.tlabel, TLCDVAL.vname, TLCDVAL.vlabel, FRAPAS.pos, STATES.statval, PARFORMAT.bin_mask, PARFORMAT.abs_no 
    FROM TLCDVAL
    INNER JOIN PARFORMAT ON PARAMS.pid = PARFORMAT.pid
    INNER JOIN TLCD ON TLCDVAL.tlpid = TLCD.tlpid
    INNER JOIN STATES ON STATES.statname = TLCDVAL.vname 
    INNER JOIN PARAMS ON PARAMS.parname = TLCD.pid
    INNER JOIN FRAPAS ON FRAPAS.pid = PARAMS.pid
    WHERE 
        FRAPAS.frid IN (SELECT DISTINCT FRAMES.frid
        FROM FRAMES
        INNER JOIN TLCD ON PARAMS.parname = TLCD.pid
        INNER JOIN PARAMS ON PARAMS.pid = FRAPAS.pid 
        INNER JOIN FRAPAS ON FRAPAS.frid = FRAMES.frid 
        INNER JOIN ZONES ON ZONES.zoneid = FRAMES.zoneid
        INNER JOIN ECUSER ON ECUSER.serid = ZONES.serid
        INNER JOIN SERVICES ON ECUSER.serid = SERVICES.serid
        WHERE ECUSER.ecuveid = ?
        AND TLCD.ecuid = ?
        AND FRAMES.ftype = 1)
        AND TLCD.ecuid = ?
    ORDER BY FRAPAS.frid, FRAPAS.pos

;Get all parameters attached to a write service for an ECUVEID
:get_params_with_write_svc:
SELECT EDATA.* FROM EDATA 
WHERE EDATA.edatid IN (SELECT DIAGSCRDAT.edatid FROM DIAGSCRDAT
    LEFT JOIN DIAGSCR ON DIAGSCR.scrid = DIAGSCRDAT.scrid 
    LEFT JOIN ECU ON DIAGSCR.ecuid = ECU.ecuid 
    WHERE ECU.ecuid = ?)
AND EDATA.edatid IN (SELECT EDATA.edatid FROM EDATA 
WHERE edata.parname IN (SELECT params.parname
        FROM FRAMES
        INNER JOIN SERVICES on SERVICES.serid = ZONES.serid
        INNER JOIN ECUSER on SERVICES.serid = ECUSER.serid
        INNER JOIN PARAMS ON PARAMS.pid = FRAPAS.pid 
        INNER JOIN FRAPAS ON FRAPAS.frid = FRAMES.frid 
        INNER JOIN ZONES ON ZONES.zoneid = FRAMES.zoneid
        WHERE ECUSER.ecuveid = ?
	 	AND FRAMES.ftype = 0 AND zones.zonename LIKE "WDB%"))

;Get all writeable parameters for a given ECUVEID
:get_params_from_ecuveid_only:
SELECT EDATA.* FROM EDATA 
WHERE EDATA.edatid IN (SELECT EDATA.edatid FROM EDATA 
WHERE edata.parname IN (SELECT params.parname
        FROM FRAMES
        INNER JOIN SERVICES on SERVICES.serid = ZONES.serid
        INNER JOIN ECUSER on SERVICES.serid = ECUSER.serid
        INNER JOIN PARAMS ON PARAMS.pid = FRAPAS.pid 
        INNER JOIN FRAPAS ON FRAPAS.frid = FRAMES.frid 
        INNER JOIN ZONES ON ZONES.zoneid = FRAMES.zoneid
        WHERE ECUSER.ecuveid = ?
	 	AND FRAMES.ftype = 0 AND zones.zonename LIKE "WDB%"))

;Get procedures for a given ECU
:get_procs_for_ecu_veh:
SELECT PRC.prc_id, label_en, help_en FROM PRC
	INNER JOIN PRCVEHECUMAP ON PRCVEHECUMAP.prcid = PRC.prc_id
    WHERE PRCVEHECUMAP.veh = ? AND PRCVEHECUMAP.ecuname = ?

;Get steps and commands for a given procedure
:get_proc_properties:
SELECT * FROM PRCSTEP
    LEFT JOIN PRCCMD ON PRCSTEP.step_id  = PRCCMD.step
    LEFT JOIN PRCRESPONSE ON PRCSTEP.step_id  = PRCRESPONSE.step_parent
    WHERE PRCSTEP.prcid = ?

;Get all rows of ECUVE which match with ECUs on the vehicle by vehid
:get_ecuvetable_for_vehid:
SELECT ECUVE.*, ECUTYPE.ecuname AS ecutyname FROM ECUVE 
INNER JOIN ECUVEMAP ON ECUVE.ecuveid = ECUVEMAP.ecuveid 
INNER JOIN ECU ON ECU.ecuid = ECUVEMAP.ecuid 
INNER JOIN ECUTYPE ON ECUTYPE.ecutyid = ECU.ecutyid 
INNER JOIN ECUFAMILY ON ECU.famid = ECUFAMILY.famid 
WHERE ECUFAMILY.vehid = ?
