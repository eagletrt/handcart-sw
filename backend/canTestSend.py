# Can send test
# Before use, pls run the script "start-can.sh"

import can
import time

bus = can.interface.Bus(interface='socketcan',
                        channel='can0',
                        receive_own_messages=True)

msg = can.Message(arbitration_id=0xAA, data=[
                  3, 0, 0, 0, 0, 0, 0, 0])  # BMS TS_ON
msg2 = can.Message(arbitration_id=0x610, data=[
                   0, 0, 0, 0])  # BRUSA STATUS
msg3 = can.Message(arbitration_id=0x614, data=[
                   0, 0, 0x44, 0, 0x08])  # BRUSA ERR

msg4 = can.Message(arbitration_id=0x611, data=[
                   0, 0, 0x08, 0xF6, 0, 0x07, 0, 0])

try:
    bus.send(msg)
    print("Message sent on {}".format(bus.channel_info))
except can.CanError:
    print("Message NOT sent")

time.sleep(1)
try:
    bus.send(msg2)
    print("Message sent on {}".format(bus.channel_info))
except can.CanError:
    print("Message NOT sent")
time.sleep(1)

try:
    bus.send(msg3)
    print("Message sent on {}".format(bus.channel_info))
except can.CanError:
    print("Message NOT sent")

try:
    bus.send(msg4)
    print("Message sent on {}".format(bus.channel_info))
except can.CanError:
    print("Message NOT sent")
