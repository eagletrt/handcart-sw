# Can send test
# Before use, pls run the script "start-can.sh"

import can

bus = can.interface.Bus(interface='socketcan',
                        channel='can0',
                        receive_own_messages=True)

TS_ON = can.Message(arbitration_id=0xAA, data=[
    0x03, 0, 0, 0, 0, 0, 0, 0])  # BMS TS_ON
TS_OFF = can.Message(arbitration_id=0xAA, data=[
    0x04, 0, 0, 0, 0, 0, 0, 0])  # BMS TS_ON
NLG5_ST = can.Message(arbitration_id=0x610, data=[
    0, 0, 0, 0])  # BRUSA STATUS
NLG5_ERR = can.Message(arbitration_id=0x614, data=[
    0, 0, 0x44, 0, 0x08])  # BRUSA ERR
msg4 = can.Message(arbitration_id=0x611, data=[
    0, 0, 0x08, 0xF6, 0, 0x07, 0, 0])

input("Press for TS_OFF message")

try:
    bus.send(TS_OFF)
    print("Message sent on {}".format(bus.channel_info))
except can.CanError:
    print("Message NOT sent")

input("press for brusa status message")

try:
    bus.send(NLG5_ST)
    print("Message sent on {}".format(bus.channel_info))
except can.CanError:
    print("Message NOT sent")

input("Press for TS_ON message")

try:
    bus.send(TS_ON)
    print("Message sent on {}".format(bus.channel_info))
except can.CanError:
    print("Message NOT sent")
