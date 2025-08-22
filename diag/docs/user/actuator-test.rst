Actuator Tests
==============

This provides a list of functions that can be tested on the ECU, for example testing the cooling fan or illumination of a particular lamp. This function is not currently available for pre-2010 BSI units (except for a couple of tests).

Some tests have "conditions" that must be met before they will execute successfully (engine must be running, must *not* be running etc). If this error occurs, you will be informed with the error *Conditions not correct*. Consult online documentation for more information if you cannot deduce the conditions required.

Some Tests have "steps" to them. For example, it may open and then close a valve or actuator. These are indicated in the popup before starting the test, as the type is shown as "Stepped, " followed by the subtype. Currently, Diagnostique can execute only the first step. 

**NOTE:** Many tests will not operate at all in *economy mode*. It is not possible to exit economy mode, even with the diagnostic tool, unless the battery voltage exceeds 12.6v. On **some** BSIs you can effectively disable economy mode by switching the BSI to *showroom mode*. This is a "procedure" and is not yet implemented in Diagnostique. This feature *also* requires a battery voltage exceeding 12.6v. 
