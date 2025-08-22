F.A.Qs
======

**Q: I changed something using Telecoding and now my ECU/car is doing weird things**
A: First, try to change the setting back using the interface. If that doesn't work, don't worry. Every action is logged, and the configuration read from the vehicle is always and automatically backed up in raw format before writing any changes. In the "logs" folder you will find a file with your VIN number with the extension .tll. Either follow the instructions below, or post on the forum to get help

This is an example of a line you will see: ''1613067156977,2974,13746,61B41819A000''
The first component is the timestamp of the action. The second is the ECUID and the third the ECUVEID. The fourth component is the raw data read from the ECU. In this example the data starts from the 4th byte "181...." where 61B4 is the read command (ReadDataByLocalIDOK = 61) and B4 is the memory zone. To write this back to the ECU you will need to change the 61 to "ReadDataByLocalID" which for KWP-on-CAN would be "3B". A little below the "read" line will be a line starting with this "3B" command where the software logged the data being written to the ECU. From these two lines, you should be able to work out the line that needs to be sent to the ECU.

**Q: What does it mean if a parameter is "Not available"?**
A: It means it's not supported or could not be read from the ECU

**Q: Why do some parameters not format properly?**
A: Because some parameter formats are not known - see also the HEXA problem

**Q: Why do some buttons not do anything?**
A: Because the GUI is still in development, and some menu items aren't connected to anything yet!