# Can charge scritpt
# Before use, pls run the script "start-can.sh"

import os
import re
import time
import can
from can.listener import Listener
from RPi.GPIO import GPIO

GPIO.setmode(GPIO.BCM)
GPIO.setup(21, GPIO.OUT)
GPIO.output(21, GPIO.HIGH)

bus = can.interface.Bus(interface='socketcan',
                        channel='can0',
                        receive_own_messages=True)

ts_status = False
BYPASS_TS_CHECK = True  # True

nlg5_ctl = can.Message(arbitration_id=0x618, data=[
    0, 0x00, 0x0A, 0x10, 0x68, 0, 0x0A], is_extended_id=False)


class Can_rx_Listener(Listener):
    def on_message_received(self, msg):
        global ts_status
        if msg.arbitration_id == 0xAA:
            if msg.data[0] == 0x03:
                ts_status = True
                print("Asd")
            if msg.data[0] == 0x04:
                ts_status = False


l = Can_rx_Listener()
notif = can.Notifier(bus, [l])

CHG_V = int(443 / 0.1)
CHG_A = int(9 / 0.1)
MAX_C_O = int(16 / 0.1)
# ts_status = False # TS status, true if precharge done False otherwise
# BYPASS_TS_CHECK = False

os.system('clear')
r_CHG_V = input("Charging voltage (Default=" + str(CHG_V * 0.1) + "): ")
if r_CHG_V != "":
    if re.match('^[0-9]*$', r_CHG_V) and 0 < int(r_CHG_V) < 400:  # just numbers allowed
        CHG_V = int(int(r_CHG_V) / 0.1)
    else:
        print("[ERROR] invalid input")

r_CHG_A = input("Charging current (Default=" + str(CHG_A * 0.1) + "): ")
if r_CHG_A != "":
    if re.match('^[0-9]*$', r_CHG_A) and 0 < int(r_CHG_A) < 16:
        CHG_A = int(int(r_CHG_A) / 0.1)
    else:
        print("[ERROR] invalid input")

r_MAX_C_O = input("Max current drawn from outlet(Default=" + str(MAX_C_O * 0.1) + "): ")
if r_MAX_C_O != "":
    if re.match('^[0-9]*$', r_MAX_C_O) and 0 < int(r_MAX_C_O) < 16:
        MAX_C_O = int(int(r_MAX_C_O) / 0.1)
    else:
        print("[ERROR] invalid input")

b_CHG_V = CHG_V.to_bytes(2, 'big', signed=False)
b_CHG_A = CHG_A.to_bytes(2, 'big', signed=False)
b_MAX_C_O = MAX_C_O.to_bytes(2, 'big', signed=False)

b_CHG_ENABLED = 0x80

nlg5_ctl = can.Message(arbitration_id=0x618, data=[
    0, b_MAX_C_O[0], b_MAX_C_O[1], b_CHG_V[0], b_CHG_V[1], b_CHG_A[0], b_CHG_A[1]],
                       is_extended_id=False)

bms_ts_on = can.Message(arbitration_id=0x55, data=[0x0A, 0x01], is_extended_id=False)

os.system('clear')
print("When the charge starts, the program will wait 3 seconds, and then send the start command to BRUSA")
input("type something to send TS_ON to BMS")

try:
    bus.send(bms_ts_on)
    print("TS_ON sent on {}".format(bus.channel_info))
except can.CanError:
    print("Message NOT sent")

os.system('clear')
print("Waiting for BMS to finish precharge")

if not BYPASS_TS_CHECK:
    while True:
        if ts_status:
            break

os.system("clear")
print("Precharge done")
input("Type something to start charging")

t = time.time()
charging = False
while 1:
    time.sleep(0.10)
    if (not charging) and time.time() - t > 5:
        print("Charge enabled")
        nlg5_ctl.data[0] = b_CHG_ENABLED
        charging = True
    try:
        bus.send(nlg5_ctl)
        print("Message sent on {}".format(bus.channel_info))
    except can.CanError:
        print("Message NOT sent")
