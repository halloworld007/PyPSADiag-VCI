Discovery
=========

Every diagnostic session starts with a process called "Discovery". For those of you familiar with other software this is similar to "Global Test". You can proceed to either

- **New session** - a vehicle you have not diagnosed before, or one which has had an ECU added, replaced or upgraded
- **Saved session** - a vehicle you have previously diagnosed and saved. This also allows you to view stored fault history from a session without needing to be connected to the vehicle

Upon selecting a **New session** you are required to choose a vehicle and model. This will present you with a list of ECU types that were fitted to that model. If you only wish to interrogate a single, or a few ECUs you can select only those, or else scan for all possible devices. If the vehicle is in **economy mode** then some ECUs will not respond. It will depend on your adapter hardware & vehicle model as to whether you are able to detect all the ECUs which exist on your car.

Detection Stages
----------------

For each ECU "category" which could be fitted to your vehicle, a scan will be attempted. The following list indicates the status for each one.

- Not Present - there was no response from any of the available headers for that ECU category (e.g. BMF)
- Rejected - the ECU rejected a request to initiate the diagnostic session (this may be temporary)
- Invalid - the response from the headers did not match what was expected for this ECU category\*
- Not recognised - the ECU software ID does not match any of the listed versions for this vehicle type

\* this can happen if several ECU categories share the same headers, but only one is used on the vehicle. It can usually be ignored, unless you are having problems connecting to a particular ECU
