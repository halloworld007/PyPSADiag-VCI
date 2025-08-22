Treeview
~~~~~~~~

This utility is a very flexible way to access and understand data from the databases. It also provides a simple console for sending raw UDS commands to/from ECUs (EvolutionXS only).

To get started, click **Choose ECU** and from the dropdown boxes select the vehicle and ECU type you are interested in. You will be presented with a detailed list of data related to diagnosis for the ECU

* Model Code - the internal PSA "project" reference for the vehicle
* Vehicle ID - the database number for the vehicle type
* ECU ID - the database reference for the ECU type
* ECUVEID - the database reference for the specific ECU version
* Reference - the software (usually) version of the ECU
* Variant - the unique database name for the specific ECU version

* Bus - which CAN network (or none) the ECU is diagnosed via
* TX Header - CAN message header to transmit diagnostic data
* RX Header - CAN message header to receive diagnostic data
* Protocol - The protocol used by the ECU (see Protocols)
* DialogType - see Protocols
* ECU Code - for specific dialog types only
* DiagInit - the command to send to get the ECU to enter diagnostic mode
* ReCo - "recognition" - the command to send to get the ECU to send its reference number / identify itself

From here you can either **Load Frames**, which will load all known frames into the main window as a "tree". You can also **Export available data** which will give a run down of the config options, actuator tests etc available for a specific ECU.

Finally, you can click **Fault Listing** in the main window, which will print a full list of faults and their descriptions for the specific ECU.


UDS Session
-----------

Provides a basic interface for manually using the EvolutionXS interface. You first need to set TX and RX headers, the target code (if needed), and the bus type. Then, send the DIAGINIT message for the ECU and on positive response, toggle Keep-Alive ON to keep the session open by pressing START (you can specify the KA message if it's different to the usual 3E).
