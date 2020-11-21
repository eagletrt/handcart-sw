# Can read test
# Before use, pls run the script "start-can.sh"

import can
from enum import Enum
import threading
from can.listener import Listener

class CAN_MESSAGES_ID(Enum):
    CAN_OUT_CURRENT = 0x05
    CAN_OUT_PACK_VOLTS = 0x01
    CAN_OUT_PACK_TEMPS = 0x10
    CAN_OUT_WARNING = 0x09
    CAN_OUT_ERRORS = 0x08
    CAN_OUT_TS_ON = 0x03
    CAN_OUT_TS_OFF = 0x04

class CanReader(Listener):
    test = False
    def __init__(self):
        pass

    def on_message_received(self, msg):
        self.test = True


bus = can.interface.Bus(interface='socketcan',
              channel='can0',
              receive_own_messages=True)

listener = CanReader()

n = can.Notifier(bus, [listener])

while(1):
    print(listener.test)
    pass