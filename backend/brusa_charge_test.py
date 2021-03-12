# Can send test
# Before use, pls run the script "start-can.sh"

import can
import time

bus = can.interface.Bus(interface='socketcan',
                        channel='can0',
                        receive_own_messages=True)

# msg = can.Message(arbitration_id=0xAA, data=[
#                  3, 0, 0, 0, 0, 0, 0, 0])  # BMS TS_ON
# msg2 = can.Message(arbitration_id=0x610, data=[
#                   0, 1, 0, 0, 0, 0, 0, 0])  # BRUSA STATUS
# msg3 = can.Message(arbitration_id=0x614, data=[0, 2, 0, 0, 0])  # BRUSA ERR


nlg5_ctl = can.Message(arbitration_id=0x618, data=[
                       0, 0, 0x14, 0x0F, 0XA0, 0, 0x0A], is_extended_id=True)
exit()
while(1):
    time.sleep(0.15)
    #can.send_periodic(bus, nlg5_ctl, 0.1)

    try:
        bus.send(nlg5_ctl)
        print("Message sent on {}".format(bus.channel_info))
    except can.CanError:
        print("Message NOT sent")

# try:
#    bus.send(msg2)
#    print("Message sent on {}".format(bus.channel_info))
# except can.CanError:
#    print("Message NOT sent")
