diag_bramble
~~~~~~~~~~~~
This library fetches data from the SQLite database(s) and converts it to semi-human readable and better organised Python-based dictionaries. These can easily be exported to json, yaml or any other interopability format. The main functions are as follows

* get_data_frames() - extract parameters for a given ECU, with any available formatting and state entries (for live data)
* get_params_from_telecoding() - abstracted function to get telecoding data for any age of ECU
* get_actuator_tests() - get actuator tests for a given ECU/ECUVE
* get_vehicle_ecu_list - get all ECUs that could be fitted to a vehicle, with headers/connection information

There are many more functions handling smaller functions, including decoding fault codes, translations, and building queries.

The raw SQL queries are stored in a separate file [queries.sql] to keep the python library code as clean as possible (because the queries are frequently long and complex). This uses a simple format which is parsed by the library at runtime into a dictionary.

For more information about the dictionaries returned by the main functions of the API, see the separate documentation/code comments

For an introduction to the type of data that can be obtained using diag_bramble, it is recommended to use Treeview to explore different vehicle types. From there, you can use the source code for that utility to understand how the data is queried, received and parsed.

