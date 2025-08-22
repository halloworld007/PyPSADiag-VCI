"""
   SerialPort.py

   Copyright (C) 2024 - 2025 Marc Postema (mpostema09 -at- gmail.com)

   This program is free software; you can redistribute it and/or
   modify it under the terms of the GNU General Public License
   as published by the Free Software Foundation; either version 2
   of the License, or (at your option) any later version.

   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with this program; if not, write to the Free Software
   Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
   Or, point your browser to http://www.gnu.org/copyleft/gpl.html
"""

import time
import serial.tools.list_ports

from EcuSimulation import EcuSimulation
from VCIAdapter import VCIAdapter


class SerialPort():
    ecuSimulation = EcuSimulation()
    simulation = False
    use_vci = False

    def __init__(self, simulation: bool(), use_vci: bool() = False):
        self.serialPort = serial.Serial()
        self.simulation = simulation
        self.use_vci = use_vci
        self.vci_adapter = None
        
        if self.use_vci:
            self.vci_adapter = VCIAdapter()
            
    def set_use_vci(self, use_vci: bool):
        """Enable or disable VCI mode"""
        self.use_vci = use_vci
        if self.use_vci and not self.vci_adapter:
            self.vci_adapter = VCIAdapter()
        elif not self.use_vci and self.vci_adapter:
            self.vci_adapter.disconnect()
            self.vci_adapter = None

    # Get available Serial ports and put it in Combobox
    def fillPortNameCombobox(self, combobox):
        combobox.clear()
        
        # Add VCI option
        combobox.addItem("Evolution XS VCI", "VCI")
        
        # Add serial ports
        comPorts = serial.tools.list_ports.comports()
        nameList = list(port.device for port in comPorts)
        for name in nameList:
            combobox.addItem(name, name)

    def isOpen(self):
        if self.use_vci and self.vci_adapter:
            return self.vci_adapter.is_connected()
        return self.serialPort.isOpen() or self.simulation == True

    def close(self):
        if self.use_vci and self.vci_adapter:
            self.vci_adapter.disconnect()
        else:
            self.serialPort.close()

    def open(self, portNr, baudRate):
        # Check if VCI is selected
        if portNr == "VCI" or portNr == "Evolution XS VCI":
            self.use_vci = True
            if not self.vci_adapter:
                self.vci_adapter = VCIAdapter()
            return self.vci_adapter.connect()
        else:
            self.use_vci = False
            try:
                self.serialPort.port = portNr
                self.serialPort.baudrate = baudRate
                self.serialPort.timeout = 5.0
                self.serialPort.open()
                return True
            except serial.SerialException as e:
                print('Error opening port: ' + str(e))
                return False
                
    def configure_vci(self, tx_id, rx_id, protocol="uds", bus="auto", target=None, dialog_type="0"):
        """Configure VCI for ECU communication"""
        if self.use_vci and self.vci_adapter:
            return self.vci_adapter.configure(tx_id, rx_id, protocol, bus, target, dialog_type)
        return False

    def write(self, data):
        #print(data)
        self.serialPort.write(data)

    def readRawData(self):
        data = bytearray()
        runLoop = 50
        while runLoop > 0:
            dataLen = self.serialPort.in_waiting
            if dataLen > 1:
                subData = self.serialPort.read_until(expected=b"\r\n")
                if len(subData) > 0:
                    data.extend(subData)
                    if data.find(b"\r") != -1:
#                        print(data)
                        break
                    time.sleep(0.1)
                    runLoop = 10
            else:
                time.sleep(0.1)
                runLoop -= 1
        return data

    def readData(self):
        if self.simulation:
            return self.ecuSimulation.receive()
        else:
            data = self.readRawData()
            if len(data) == 0:
                return "Timeout"

            i = data.find(b"\r")
            decodedData = data[:i].decode("utf-8");
            return decodedData

    def sendReceive(self, cmd: str):
        if self.simulation:
            return self.ecuSimulation.sendReceive(cmd)
        elif self.use_vci and self.vci_adapter:
            # VCI communication
            return self.vci_adapter.send_receive(cmd)
        else:
            cmd += "\n"
            self.write(cmd.encode("utf-8"))
            return self.readData()
