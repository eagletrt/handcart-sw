import can
from enum import Enum

class CAN_MESSAGES_ID(Enum):
    CAN_OUT_CURRENT = 0x05
    CAN_OUT_PACK_VOLTS = 0x01
    CAN_OUT_PACK_TEMPS = 0x10
    CAN_OUT_WARNING = 0x09
    CAN_OUT_ERRORS = 0x08
    CAN_OUT_TS_ON = 0x03
    CAN_OUT_TS_OFF = 0x04

bus = can.interface.Bus(interface='socketcan',
              channel='can0',
              receive_own_messages=True)

while(1):
    msg = bus.recv()
    if msg.arbitration_id == 0xAA:
        if msg.data[0] == 10:
            print(msg)