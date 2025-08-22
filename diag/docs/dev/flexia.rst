Flexia
======



DIY protocol for serial device
------------------------------

Implemented over serial/USB

- Set active bus   --> "PM" = CAN_DIAG / "PS" = CAN_IS
  Response OK      --> 1.0M or 1.0S

- Set headers with --> ">TX_H:RX_H" ....  ">75F:65F"
  Response OK      --> ">75F:65F" (mirror what was sent)

- Any other input is treated as a string to send, adapter adds headers and UDS length itself
  for example send("21FE") is what input the adapter will get
- Reading back data expects the whole message as one long string (after multiframes have been joined)
- Read data newline terminated with \n, but \r\n will be handled too (\r and \n will be removed)
- Read back data can have RX_H in first bytes like 65F:61FEXXXXX
- Adapter give 7F0000 or no response if there is an error (wrong command)