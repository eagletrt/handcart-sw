# Can send test
# Before use, pls run the script "start-can.sh"

import os
import re
import time

import can

bus = can.interface.Bus(interface='socketcan',
                        channel='can0',
                        receive_own_messages=True)

nlg5_ctl = can.Message(arbitration_id=0x618, data=[
    0, 0x00, 0x0A, 0x10, 0x68, 0, 0x0A], is_extended_id=False)

CHG_V = int(450 / 0.1)
CHG_A = int(9 / 0.1)
MAX_C_O = int(16 / 0.1)

os.system('clear')
r_CHG_V = input("Charging voltage: ")
if r_CHG_V != "":
    if re.match('^[0-9]*$', r_CHG_V) and 0 < int(r_CHG_V) < 400:  # just numbers allowed
        CHG_V = int(int(r_CHG_V) / 0.1)
    else:
        print("[ERROR] invalid input")

r_CHG_A = input("Charging current: ")
if r_CHG_A != "":
    if re.match('^[0-9]*$', r_CHG_A) and 0 < int(r_CHG_A) < 16:
        CHG_A = int(int(r_CHG_A) / 0.1)
    else:
        print("[ERROR] invalid input")

r_MAX_C_O = input("Max current drawn from outlet: ")
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

os.system('clear')
print("When the charge starts, the program will wait 3 seconds, and then send the start command to BRUSA")
input("type something to start charging")

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
