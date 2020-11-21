# Can send test
# Before use, pls run the script "start-can.sh"

import can

bus = can.interface.Bus(interface='socketcan',
              channel='can0',
              receive_own_messages=True)

msg = can.Message(arbitration_id=0xAA, data=[3, 0, 0, 0, 0, 0, 0, 0]) # BMS TS_ON
msg2 = can.Message(arbitration_id=0x610, data=[0, 0, 0, 0, 0, 0, 0, 0]) # BRUSA STATUS

try:
    bus.send(msg)
    print("Message sent on {}".format(bus.channel_info))
except can.CanError:
    print("Message NOT sent")

try:
    bus.send(msg2)
    print("Message sent on {}".format(bus.channel_info))
except can.CanError:
    print("Message NOT sent")