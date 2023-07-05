# Fenice EVO handcart emergency charge script
# This script is meant to be used to charge the accumulator with the handcart when the main script is not working
# This script implements basic functions:
# - Sets charging settings interactivelt
# - Manages the TS on procedure with the BMS
# - Turns on the BRUSA
import atexit
import os
import re
import time

import RPi.GPIO as GPIO
import can
from can.listener import Listener
from cantools.database import Database

from settings import *

# from common.can_classes import Toggle, primary_ID_TS_STATUS, TsStatus

brusa_dbc_file = join(dirname(dirname(realpath(__file__))), "NLG5_BRUSA.dbc")
DBC_PRIMARY_PATH = join(dirname(realpath(__file__)), "can_eagle", "dbc", "primary", "primary.dbc")
dbc_brusa: Database = cantools.database.load_file(brusa_dbc_file)
dbc_primary: Database = cantools.database.load_file(DBC_PRIMARY_PATH)  # load the bms dbc file

DEFAULT_TARGET_V = 445  # Default battery target charging volts
DEFAULT_TARGET_A = 6  # Default battery charging current
DEFAULT_MAX_C_O = 16  # Default max current absorbed from the grid by the BRUSA

GPIO.setmode(GPIO.BCM)
GPIO.setup(21, GPIO.OUT)  # PON
GPIO.setup(20, GPIO.OUT)  # SD

GPIO.output(20, GPIO.HIGH)  # open sd relay
GPIO.output(21, GPIO.HIGH)  # disable PON

# GPIO.output(21, GPIO.HIGH)

def exit_handler():
    print("Quitting..")
    GPIO.output(20, GPIO.LOW)  # open sd relay
    GPIO.output(21, GPIO.LOW)  # disable PON
    GPIO.cleanup()

    data = nlg5_ctl.encode({
        'NLG5_C_C_EN': 0,  # enable
        'NLG5_C_C_EL': 0,  # clear error latch
        'NLG5_C_CP_V': 0,  # control pilot ventilation request(?)
        'NLG5_C_MR': 0,  # idk
        'NLG5_MC_MAX': 0,  # mains current max
        'NLG5_OV_COM': 0,  # output voltage set
        'NLG5_OC_COM': 0  # output current set
    })

    nlg5_ctl_msg = can.Message(arbitration_id=nlg5_ctl.frame_id,
                               data=data,
                               is_extended_id=False)

    bus.send(nlg5_ctl_msg)


atexit.register(exit_handler)

bus = can.interface.Bus(interface='socketcan',
                        channel='can0',
                        receive_own_messages=True)

BYPASS_TS_CHECK = False  # Warning, set to true if you want to avoid any check on the activation of the TS
# note that you should do the precharge to the accumulator manually

ts_status = TsStatus.OFF  # The TS status

nlg5_ctl = dbc_brusa.get_message_by_name('NLG5_CTL')
data_nlg5_off = nlg5_ctl.encode({
    'NLG5_C_C_EN': 0,  # enable
    'NLG5_C_C_EL': 0,  # clear error latch
    'NLG5_C_CP_V': 0,  # control pilot ventilation request(?)
    'NLG5_C_MR': 0,  # idk
    'NLG5_MC_MAX': 0,  # mains current max
    'NLG5_OV_COM': 0,  # output voltage set
    'NLG5_OC_COM': 0  # output current set
})

nlg5_ctl_msg = can.Message(arbitration_id=nlg5_ctl.frame_id,
                           data=data_nlg5_off,
                           is_extended_id=False)


class Can_rx_Listener(Listener):
    def on_message_received(self, msg):
        if msg.arbitration_id == primary_ID_TS_STATUS:
            message = dbc_primary.decode_message(msg.arbitration_id, msg.data)
            global ts_status
            ts_status = TsStatus(int(message.get('ts_status').value))


l = Can_rx_Listener()
notif = can.Notifier(bus, [l])

CHG_V = DEFAULT_TARGET_V  # Default battery target charging volts
CHG_A = DEFAULT_TARGET_A  # Default battery charging current
MAX_C_O = DEFAULT_MAX_C_O  # Max current absorbed by the grid

os.system('clear')
r_CHG_V = input("Charging voltage (Default=" + str(CHG_V) + "): ")
if r_CHG_V != "":
    if re.match('^[0-9]*$', r_CHG_V) and 0 < int(r_CHG_V) < 440:  # just numbers allowed
        CHG_V = int(r_CHG_V)
    else:
        print("[ERROR] invalid input")

r_CHG_A = input("Charging current (Default=" + str(CHG_A) + "): ")
if r_CHG_A != "":
    if re.match('^[0-9]*$', r_CHG_A) and 0 < int(r_CHG_A) < 16:
        CHG_A = int(r_CHG_A)
    else:
        print("[ERROR] invalid input")

r_MAX_C_O = input("Max current drawn from outlet(Default=" + str(MAX_C_O) + "): ")
if r_MAX_C_O != "":
    if re.match('^[0-9]*$', r_MAX_C_O) and 0 < int(r_MAX_C_O) < 16:
        MAX_C_O = int(r_MAX_C_O)
    else:
        print("[ERROR] invalid input")

data_nlg5_off = nlg5_ctl.encode({
    'NLG5_C_C_EN': 0,  # enable
    'NLG5_C_C_EL': 0,  # clear error latch
    'NLG5_C_CP_V': 0,  # control pilot ventilation request(?)
    'NLG5_C_MR': 0,  # idk
    'NLG5_MC_MAX': MAX_C_O,  # mains current max
    'NLG5_OV_COM': CHG_V,  # output voltage set
    'NLG5_OC_COM': CHG_A  # output current set
})

nlg5_ctl_msg = can.Message(arbitration_id=nlg5_ctl.frame_id,
                           data=data_nlg5_off,
                           is_extended_id=False)

m: cantools.database.can.message = dbc_primary.get_message_by_name("SET_TS_STATUS_HANDCART")
data = m.encode(
    {
        "ts_status_set": Toggle.ON.value,
    }
)
bms_ts_on = can.Message(arbitration_id=m.frame_id,
                        data=data,
                        is_extended_id=False)

os.system('clear')
print("When the charge process starts, the program will wait 3 seconds and then send the start command to the BRUSA")
input("type something to send TS_ON to BMS")

if not BYPASS_TS_CHECK:
    try:
        bus.send(bms_ts_on)
        print("TS_ON sent on {}".format(bus.channel_info))
    except can.CanError:
        print("Message NOT sent")

    print("Waiting for BMS to finish precharge")

    while True:
        if ts_status == TsStatus.ON:
            break
        else:
            time.sleep(0.1)

print("Precharge done")
input("\nType something to start charging")

time.sleep(1)  # wait for pon to enable

t = time.time()
charging = False
while 1:
    time.sleep(0.10)
    if (not charging) and time.time() - t > 5:
        print("Charge enabled")
        data_chg = nlg5_ctl.encode({
            'NLG5_C_C_EN': 1,  # enable
            'NLG5_C_C_EL': 0,  # clear error latch
            'NLG5_C_CP_V': 0,  # control pilot ventilation request(?)
            'NLG5_C_MR': 0,  # idk
            'NLG5_MC_MAX': MAX_C_O,  # mains current max
            'NLG5_OV_COM': CHG_V,  # output voltage set
            'NLG5_OC_COM': CHG_A  # output current set
        })
        nlg5_ctl_msg = can.Message(arbitration_id=nlg5_ctl.frame_id,
                                   data=data_chg,
                                   is_extended_id=False)
        charging = True
    try:
        bus.send(nlg5_ctl_msg)
        print("Message sent on {}".format(bus.channel_info))
    except can.CanError:
        print("Message NOT sent")
