Live Data
=========

This allows monitoring of parameters of the ECU in real-time, such as Fuel flow, air flow, or status of systems. Some parameters are displayed with a warning icon (!) next to them, or visibly unformatted. For these, the formatting for the parameter is not *officially* known, but has either been determined by the community or is not currently available (see the developer guide for more information).

The parameters are filtered by "memory zone" or part thereof in order to reduce the amount of data per-screen. Typically each "memory zone" will be a sort of category, for example one might contain all the air-condition related values.

You will (soon) be able to log all parameters (be aware this will generate a LOT of data for some ECUs), or only those selected. Note that if you start a logging session, any additional parameters you select/deselect will not be reflected in the log file. You must stop and start logging again to achieve this.

**IMPORTANT:** Some ECU's, such as the ABS/ESP systems, will NOT function properly with a live data session active. This means that driving the vehicle with live data active on the ABS ECU will **PREVENT THE ABS FROM WORKING**.

**IMPORTANT:** This function is **NOT** designed for continuous operation (e.g. to connect to a custom dash display) as it puts a high load on the ECU and network, and may cause random errors or harm the operation of the vehicle. BE CAREFUL.
