# Can send test
# Before use, pls run the script "start-can.sh"

import can

bus = can.interface.Bus(interface='socketcan',
                        channel='can0',
                        receive_own_messages=True)

TS_ON = can.Message(arbitration_id=0x03, data=[
    0, 0, 0, 0, 0, 0, 0, 0])  # BMS TS_ON
NLG5_ST = can.Message(arbitration_id=0x610, data=[
    0, 0, 0, 0])  # BRUSA STATUS
NLG5_ERR = can.Message(arbitration_id=0x614, data=[
    0, 0, 0x44, 0, 0x08])  # BRUSA ERR
msg4 = can.Message(arbitration_id=0x611, data=[
    0, 0, 0x08, 0xF6, 0, 0x07, 0, 0])

try:
    bus.send(TS_ON)
    print("Message sent on {}".format(bus.channel_info))
except can.CanError:
    print("Message NOT sent")

input("")

try:
    bus.send(NLG5_ST)
    print("Message sent on {}".format(bus.channel_info))
except can.CanError:
    print("Message NOT sent")

input("")

try:
    bus.send(NLG5_ERR)
    print("Message sent on {}".format(bus.channel_info))
except can.CanError:
    print("Message NOT sent")

input("")

try:
    bus.send(msg4)
    print("Message sent on {}".format(bus.channel_info))
except can.CanError:
    print("Message NOT sent")
