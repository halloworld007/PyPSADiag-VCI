GUI Overview
============
The main UI is based on Kivy, with some custom widgets and event handlers to allow for the advanced functionality needed. The core of the application is the screen manager, invoking each screen in turn as the user steps through the process. Operations which call functions in the diag library should be executed using **load()** to ensure they do not impinge on GUI functionality.


MainApp
-------
.. py:function:: load(function_A, function_B)

Used to manage a "queue" of functions to be executed in the background (using *queue_thread*) ALL functions which interface with the vehicle **must** be run in a background thread, using this function. We use a single queue to ensure that multiple functions don't attempt to write to the ECU simultaneously. Functions interfacing with the diag_bramble library also use this to make the UI more asynchronous.

This function takes two parameters
- function A to be called
- the "return" function B to be called when the function A returns (with anything returned by function A as a parameter)

When a function which is called using **load** returns, it must use a wrapper function (as Kivy is not thread-safe) to manipulate any part of the GUI or objects in GUI classes. This is simple to achieve, by having the "return" function B use the Kivy scheduler *Clock.schedule_once(partial(actual_return_function(parameters))*. Using **partial** is an effective way to transfer data through the thread queue to the eventual handler function.


Vehicle Selection
-----------------
This screen provides a translation between friendly vehicle names (e.g. Citroen, C5 2008-2016) and the internal names (X7) and number (42). The internal name doesn't change, but the number can change between database versions. There are a few vehicles with unknown designations - if you know them add them to **db/MODELS.csv** and the database can be updated.

On pressing next, this calls the diag_bramble function **get_vehicle_ecu_list** which takes the vehicle number (42) as a parameter. This will obtain a dictionary which is then passed to the **Choose** screen to let the user decide if they want to scan everything or only specific ECUs. The **Choose** screen returns a list of what the user ticked and then *returns to the SelectVeh screen object, but not the UI*. The **SelectVeh** class then constructs a list of ECUs to be scanned and passes that to **Discovery**.

**Choose** is an abstracted screen which allows selection of any type of item or object, and returns a list of what was chosen.


Discovery
---------
Connects to the adapter, and then verifies the user has switched the ignition ON. When the user confirms, the scan starts automatically. This calls functions in the **diag_discovery** library to run the Discovery process. Briefly, this tries to communicate with all ECUs which could be fitted to the vehicle (filtered previously by SelectVeh/Choose to only those the user desired). If any do not respond, they're ignored and the process continues. Once the scan is confirmed as complete, it moves automatically to the **Centre** screen.

This class/screen also handles parsing of a previous Discovery scan that was saved to a file. Discovery scans are simple JSON dumps of the scan results dictionary.


ECU Selection (SelectECU)
-------------------------
This is a Work-In-Progress, it allows selecting a specific ECU from the database [done] and connecting to it only [not done yet] (on the bench, for example) without needing a BSI. Currently this is only useful as an information utility (but that information is also available from the **Treeview** utility)


