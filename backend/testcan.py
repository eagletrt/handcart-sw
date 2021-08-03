import cantools

from can_cicd.naked_generator.Primary.py.Primary import *
from can_cicd.includes_generator.Primary.ids import *
import can

data = TsStatus.serialize(Ts_Status.OFF.value)

bus = can.interface.Bus(interface='socketcan',
                        channel='can0',
                        receive_own_messages=True)


TS_OFF = can.Message(arbitration_id=ID_TS_STATUS, data=data)  # BMS TS OFF
NLG5_ST = can.Message(arbitration_id=0x610, data=[0xD8, 0, 0, 0])  # BRUSA STATUS con errore

# https://docs.python.org/3/library/enum.html#enum.Flag
e = 0    #Hv_Errors.LTC_PEC_ERROR | Hv_Errors.CELL_UNDER_VOLTAGE
a = HvErrors.serialize(warnings=e, errors=e)

BMS_ERR = can.Message(arbitration_id=ID_HV_ERRORS, data=a)

TS_ON = can.Message(arbitration_id=ID_TS_STATUS, data=TsStatus.serialize(Ts_Status.ON.value))  # BMS TS_ON

NLG5_ERR = can.Message(arbitration_id=0x614, data=[1,0,0,0,0], is_extended_id=False)

try:
    bus.send(TS_OFF)
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
    bus.send(BMS_ERR)
    print("Message sent on {}".format(bus.channel_info))
except can.CanError:
    print("Message NOT sent")

input("type to send TS_ON")
try:
    bus.send(TS_ON)
    print("Message sent on {}".format(bus.channel_info))
except can.CanError:
    print("Message NOT sent")

input("type to send NLG5_ERR")
try:
    bus.send(NLG5_ERR)
    print("Message sent on {}".format(bus.channel_info))
except can.CanError:
    print("Message NOT sent")
