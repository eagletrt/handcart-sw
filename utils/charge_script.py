# Fenice EVO handcart emergency charge script
# This script is meant to be used to charge the accumulator with the handcart when the main script is not working
# This script implements basic functions:
# - Sets charging settings interactivelt
# - Manages the TS on procedure with the BMS
# - Turns on the BRUSA

import os
import re
import time
from os.path import join, dirname, realpath

import RPi.GPIO as GPIO
import can
import cantools
from can.listener import Listener
from cantools.database import Database

from common.can_classes import Toggle, primary_ID_TS_STATUS, TsStatus

brusa_dbc_file = join(dirname(dirname(realpath(__file__))), "NLG5_BRUSA.dbc")
DBC_PRIMARY_PATH = join(dirname(realpath(__file__)), "src", "can_eagle", "dbc", "primary", "primary.dbc")
dbc_brusa: Database = cantools.database.load_file(brusa_dbc_file)
dbc_primary: Database = cantools.database.load_file(DBC_PRIMARY_PATH)  # load the bms dbc file

DEFAULT_TARGET_V = 443  # Default battery target charging volts
DEFAULT_TARGET_A = 9  # Default battery charging current
DEFAULT_MAX_C_O = 16  # Default max current absorbed from the grid by the BRUSA

GPIO.setmode(GPIO.BCM)
#GPIO.setup(21, GPIO.OUT)  # SD relay
GPIO.setup(20, GPIO.OUT)  # PON control
#GPIO.output(21, GPIO.HIGH)
GPIO.output(20, GPIO.HIGH)

bus = can.interface.Bus(interface='socketcan',
                        channel='can0',
                        receive_own_messages=True)

BYPASS_TS_CHECK = False  # Warning, set to true if you want to avoid any check on the activation of the TS
# note that you should do the precharge to the accumulator manually

ts_status = TsStatus.OFF # The TS status

nlg5_ctl = can.Message(arbitration_id=0x618,
                       data=[0, 0x00, 0x0A, 0x10, 0x68, 0, 0x0A],
                       is_extended_id=False)


class Can_rx_Listener(Listener):
    def on_message_received(self, msg):
        # TODO move to fenice
        if msg.arbitration_id == primary_ID_TS_STATUS:
            message = dbc_primary.decode_message(msg.arbitration_id, msg.data)
            global ts_status
            ts_status = TsStatus(int(message.get('ts_status').value))


l = Can_rx_Listener()
notif = can.Notifier(bus, [l])

CHG_V = int(DEFAULT_TARGET_V / 0.1)  # Default battery target charging volts
CHG_A = int(DEFAULT_TARGET_A / 0.1)  # Default battery charging current
MAX_C_O = int(DEFAULT_MAX_C_O / 0.1)  # Max current absorbed by the grid

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

nlg5_ctl = can.Message(
    arbitration_id=0x618,
    data=[0, b_MAX_C_O[0], b_MAX_C_O[1], b_CHG_V[0], b_CHG_V[1], b_CHG_A[0], b_CHG_A[1]],
    is_extended_id=False)

m: cantools.database.can.message = dbc_primary.get_message_by_name("SET_TS_STATUS_HANDCART")
data = m.encode(
    {
        "ts_status_set": Toggle.OFF.value,
    }
)
bms_ts_on = can.Message(arbitration_id=m.frame_id,
                        data=data,
                        is_extended_id=False)

os.system('clear')
print("When the charge process starts, the program will wait 3 seconds and then send the start command to the BRUSA")
input("type something to send TS_ON to BMS")

try:
    bus.send(bms_ts_on)
    print("TS_ON sent on {}".format(bus.channel_info))
except can.CanError:
    print("Message NOT sent")

print("Waiting for BMS to finish precharge")

if not BYPASS_TS_CHECK:
    while True:
        if ts_status == TsStatus.ON:
            break
        else:
            time.sleep(0.1)

print("Precharge done")
input("\nType something to start charging")

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

nlg5_ctl.data[0] = 0
bus.send(nlg5_ctl)