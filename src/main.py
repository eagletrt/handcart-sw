"""@package Handcart backend
For more info read the ../../doc section, or contact matteo.bitussi@studenti.unitn.it
For test purposes, launch start-can.sh before launching this file

Notes:
    NLG5 - Stands for the BRUSA (also the charger)
    BMS (or BMS HV) - Stands for Battery Manage System (also the accumulator)
"""

import atexit
import datetime
import json
import logging
import queue
import struct
import threading
import time
from builtins import abs
from datetime import datetime, timedelta
from enum import Enum

import RPi.GPIO as GPIO
import can
import cantools
import flask
import pytz
from can.listener import Listener
from flask import render_template
from flask import request, jsonify

# from backend.common.methods.logging import log_error
from can_eagle.lib.primary.python.ids import *
from can_eagle.lib.primary.python.network import *

from can_eagle.lib.primary.python.ids import primary_ID_HV_FANS_OVERRIDE
from can_eagle.lib.primary.python.network import message_HV_FANS_OVERRIDE_conversion
from src.common.accumulator import BMS_HV, CAN_REQ_CHIMERA, ACCUMULATOR
from src.common.can import CanListener, thread_2_CAN
from src.common.server.server import thread_3_WEB
from src.common.settings import *


def log_error(error_string: str):
    try:
        f = open(ERROR_LOG_FILE_PATH, "a")
        time_now = datetime.now()
        error_msg = "[ERROR] " + str(time_now) + ": " + error_string
        print(error_msg)
        f.write(error_msg + "\n")
    except:
        pass


class PIN(Enum):
    RED_LED = 12  # 31
    GREEN_LED = 13  # 33
    BLUE_LED = 16  # 36
    SD_RELAY = 20
    PON_CONTROL = 21
    BUT_0 = 22
    BUT_1 = 23
    BUT_2 = 24
    BUT_3 = 26
    BUT_4 = 27
    BUT_5 = 19
    ROT_A = 18
    ROT_B = 17


class TSAL_COLOR(Enum):
    OFF = -1
    RED = 0
    GREEN = 1
    ORANGE = 2
    PURPLE = 3
    WHITE = 4
    YELLOW = 5


class STATE(Enum):
    """Enum containing the states of the backend's state-machine
    """
    CHECK = 0
    IDLE = 1
    PRECHARGE = 2
    READY = 3
    CHARGE = 4
    C_DONE = 5
    BALANCING = 6
    ERROR = -1
    EXIT = -2


# FSM vars
canread = CanListener()  # Access it ONLY with the FSM
precharge_asked = False  # True if precharge asked to bms
precharge_asked_time = 0  # time when the precharge has been asked
precharge_done = False

precharge_command = False  # True if received precharge command
start_charge_command = False  # True if received start charge command
stop_charge_command = False  # True if received stop charge command
shutdown_asked = False

balancing_asked_time = 0  # the time of the last precharge message has been sent
balancing_stop_asked = False
balancing_command = False

# IPC (shared between threads)
shared_data : CanListener = canread  # Variable that holds a copy of canread, to get the information from web thread
rx_can_queue = queue.Queue()  # Queue for incoming can messages
tx_can_queue = queue.Queue()  # Queue for outgoing can messages
com_queue = queue.Queue()  # Command queue
lock = threading.Lock()
can_forward_enabled = False  # Enable or disable the charge can messages from BMS_HV to BRUSA
forward_lock = threading.Lock()  # Lock to manage the access to the can_forward_enabled variable


def exit_handler():
    print("Quitting..")
    setLedColor(TSAL_COLOR.OFF)
    resetGPIOs()
    GPIO.cleanup()


def clrErr():
    """
    Function that clears all the errors in the FSM, use with care
    :return:
    """
    canread.brusa_err = False
    canread.bms_err = False
    canread.bms_err_str = ""
    canread.brusa_err_str_list = []
    canread.can_err = False


def GPIO_setup():
    """
    This function is used to set-up the GPIO pins
    """
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(PIN.BUT_0.value, GPIO.OUT)
    GPIO.setup(PIN.BUT_1.value, GPIO.OUT)
    GPIO.setup(PIN.BUT_2.value, GPIO.OUT)
    GPIO.setup(PIN.BUT_3.value, GPIO.OUT)
    GPIO.setup(PIN.BUT_4.value, GPIO.OUT)
    GPIO.setup(PIN.BUT_5.value, GPIO.OUT)
    GPIO.setup(PIN.PON_CONTROL.value, GPIO.OUT)
    GPIO.setup(PIN.ROT_A.value, GPIO.OUT)
    GPIO.setup(PIN.ROT_B.value, GPIO.OUT)
    GPIO.setup(PIN.SD_RELAY.value, GPIO.OUT)
    GPIO.setup(PIN.GREEN_LED.value, GPIO.OUT)
    GPIO.setup(PIN.BLUE_LED.value, GPIO.OUT)
    GPIO.setup(PIN.RED_LED.value, GPIO.OUT)


def canSend(bus, msg_id, data):
    """
    Function to send a CAN message
    :param bus: the canbus object
    :param msg_id: the msg id
    :param data: the msg content
    """
    # doesn't check the msg before sending it
    msg = can.Message(arbitration_id=msg_id, data=data, is_extended_id=False)
    try:
        bus.send(msg)
        # print("Message sent on {}".format(canbus.channel_info))
        return True
    except can.CanError:
        # print("Can Error: Message not sent")
        # print(msg)
        with lock:
            shared_data.can_err = True
        # raise can.CanError


def doCheck():
    """
    Do check status of the state machine
    """
    # Make sure that acc is in ts off
    accumulator_sd()

    if canread.bms_hv.isConnected() and canread.brusa.isConnected():
        return STATE.IDLE
    else:
        return STATE.CHECK


def doIdle():
    """
    Do Idle status of the state machine
    :return:
    """
    global precharge_command, \
        precharge_asked, \
        precharge_done, \
        precharge_asked_time, \
        balancing_command

    precharge_asked = False
    precharge_done = False
    precharge_asked_time = 0

    GPIO.output(PIN.PON_CONTROL.value, GPIO.LOW)
    # Make sure that acc is in ts off
    accumulator_sd()

    if precharge_command:
        precharge_command = False
        return STATE.PRECHARGE

    if balancing_command:
        balancing_command = False
        return STATE.BALANCING

    return STATE.IDLE


def doPreCharge():
    """
    Function that do the precharge statusc
    """
    # ask pork to do precharge
    # Send req to bms "TS_ON"
    global precharge_asked, precharge_done, precharge_asked_time

    if canread.bms_hv.status == TsStatus.OFF and not precharge_asked:
        if canread.bms_hv.ACC_CONNECTED == ACCUMULATOR.FENICE:
            data = message_SET_TS_STATUS(ts_status_set=Toggle.ON)
            ts_on_msg = can.Message(arbitration_id=primary_ID_SET_TS_STATUS_HANDCART,
                                    data=data.serialize(),
                                    is_extended_id=False)
        else:
            ts_on_msg = can.Message(arbitration_id=0x55,
                                    data=[CAN_REQ_CHIMERA.REQ_TS_ON.value, 0x01, 0x00, 0x00],
                                    is_extended_id=False)

        tx_can_queue.put(ts_on_msg)
        precharge_asked = True
        precharge_asked_time = time.time()

    if canread.bms_hv.status == TsStatus.ON:
        print("Precharge done, TS is on")
        precharge_done = True
        precharge_asked = False
        precharge_asked_time = 0

    if precharge_done:
        return STATE.READY
    else:
        if canread.bms_hv.ACC_CONNECTED == ACCUMULATOR.FENICE and \
                time.time() - precharge_asked_time > BMS_PRECHARGE_STATUS_CHANGE_TIMEOUT:
            if precharge_asked and canread.bms_hv.status == TsStatus.PRECHARGE:
                return STATE.PRECHARGE
            else:
                return STATE.IDLE
        else:
            return STATE.PRECHARGE


def doReady():
    """
    Function that do the ready state of the state machine
    """
    global start_charge_command, precharge_asked

    if canread.bms_hv.status != TsStatus.ON:
        print("BMS_HV is not in TS_ON, going back idle")
        # note that errors are already managed in mainloop
        # staccastacca()
        return STATE.IDLE

    precharge_asked = False

    if start_charge_command:
        start_charge_command = False
        return STATE.CHARGE
    else:
        return STATE.READY


def doCharge():
    """
    Function that do the charge state of the state machine
    :return:
    """
    # canread has to forward charging msgs from bms to brusa
    global can_forward_enabled, stop_charge_command

    # Set Brusa's PON to 12v (relay)
    GPIO.output(PIN.PON_CONTROL.value, GPIO.HIGH)

    with forward_lock:
        can_forward_enabled = True

        if stop_charge_command:
            can_forward_enabled = False
            stop_charge_command = False
            return STATE.READY
        try:
            if canread.brusa.act_NLG5_ACT_I['NLG5_OV_ACT'] >= canread.target_v \
                    and canread.brusa.act_NLG5_ACT_I['NLG5_OC_ACT'] < 0.1:
                can_forward_enabled = False
                return STATE.C_DONE
        except KeyError:
            print("Error in reading can message from brusa")
            # canread.can_err = True da rimettere

    return STATE.CHARGE


def doC_done():
    """
    Function that do the charge done of the state machine
    :return:
    """
    # User decide wether charge again or going idle
    GPIO.output(PIN.PON_CONTROL.value, GPIO.LOW)

    return STATE.C_DONE


def do_balancing():
    global balancing_asked_time, balancing_stop_asked

    if balancing_stop_asked:
        balancing_stop_asked = False
        return STATE.IDLE

    if canread.bms_hv.ACC_CONNECTED == ACCUMULATOR.FENICE:
        if not canread.bms_hv.is_balancing \
                and (time.time() - balancing_asked_time) > RETRANSMIT_INTERVAL:
            tmp = message_SET_CELL_BALANCING_STATUS(set_balancing_status=Toggle.ON)
            message = can.Message(arbitration_id=primary_ID_SET_CELL_BALANCING_STATUS,
                                  data=tmp.serialize(),
                                  is_extended_id=False)
            tx_can_queue.put(message)
            balancing_asked_time = time.time()
        return STATE.BALANCING

    return STATE.IDLE


def doError():
    """
    Do the error state of the state machine
    """
    global can_forward_enabled

    with forward_lock:
        can_forward_enabled = False

    GPIO.output(PIN.PON_CONTROL.value, GPIO.LOW)
    GPIO.output(PIN.SD_RELAY.value, GPIO.LOW)

    # Send to BMS stacca stacca
    if not canread.bms_hv.status == TsStatus.OFF.value:
        staccastacca()

    if canread.brusa.error:
        pass
        # print("brusa error")
    if canread.bms_hv.error:
        print("bms error")
        pass
    if canread.can_err:
        # print("Can Error")
        pass

    if not com_queue.empty:
        act_com = com_queue.get()
        # wait for user command to clear errors or exit
        if act_com['com_type'] == 'error_clear' and act_com['value'] == True:
            clrErr()
            return STATE.CHECK
        else:
            return STATE.EXIT

    else:
        return STATE.ERROR


def doExit():
    """
    Function that does the state Exit of the state machine
    """
    exit(0)


def staccastacca():
    """
    Function that is to be called in an unsafe environment, this function
    will ask the BMS_HV to close the airs and it will disable the Brusa
    and all the devices. This will also open the SD_Relay
    """
    global precharge_asked, precharge_done, can_forward_enabled
    GPIO.output(PIN.PON_CONTROL.value, GPIO.LOW)
    GPIO.output(PIN.SD_RELAY.value, GPIO.LOW)

    accumulator_sd()

    # Set PON to off
    # Open shutdown
    precharge_asked = False
    precharge_done = False
    can_forward_enabled = False


def checkCommands():
    """
    This function checks for commands in the queue shared between the FSM and the server,
    i.e. if an "fast charge" command is found, the value of that command is set in the fsm
    """
    global precharge_command, \
        start_charge_command, \
        stop_charge_command, \
        shutdown_asked, \
        balancing_stop_asked, \
        balancing_command

    if not com_queue.empty():
        act_com = com_queue.get()
        print(act_com)

        if act_com['com-type'] == 'cutoff':
            if int(act_com['value']) > 200 and int(act_com['value'] < MAX_TARGET_V_ACC):
                canread.target_v = int(act_com['value'])
            else:
                print("cutoff command exceeds limits")

        if act_com['com-type'] == "precharge" and act_com['value'] is True:
            precharge_command = True

        if act_com['com-type'] == "charge" and act_com['value'] is True:
            start_charge_command = True

        if act_com['com-type'] == "charge" and act_com['value'] is False:
            stop_charge_command = True

        if act_com['com-type'] == "shutdown" and act_com['value'] is True:
            shutdown_asked = True

        if act_com['com-type'] == "balancing":
            if act_com['value'] is False:
                balancing_stop_asked = True
            if act_com['value'] is True:
                balancing_command = True

        if act_com['com-type'] == "fan-override-set-status":
            if act_com['value'] == False:
                canread.bms_hv.fans_set_override_status = Toggle.OFF
            if act_com['value'] == True:
                canread.bms_hv.fans_set_override_status = Toggle.ON

        if act_com['com-type'] == "fan-override-set-speed":
            if act_com['value'] != "":
                speed = int(act_com['value'])
                if (speed >= 0 and speed <= 100):
                    canread.bms_hv.fans_set_override_speed = int(speed) / 100

        if act_com['com-type'] == 'max-out-current':
            if 0 < act_com['value'] < 12:
                shared_data.act_set_out_current = act_com['value']
            else:
                print("max-out-current limits exceded")

        if act_com['com-type'] == "max-in-current":
            if 0 < act_com['value'] <= 16:
                shared_data.act_set_in_current = act_com['value']
            else:
                print("max-in-current limits exceded")


def accumulator_sd():  # accumulator shutdown
    if canread.bms_hv.status == TsStatus.ON:
        message = can.Message(arbitration_id=CAN_ID_ECU_CHIMERA, is_extended_id=False,
                              data=[CAN_REQ_CHIMERA.REQ_TS_OFF.value])
        tx_can_queue.put(message)

        if canread.bms_hv.ACC_CONNECTED == ACCUMULATOR.FENICE:
            tmp = message_SET_TS_STATUS(ts_status_set=Toggle.OFF)
            message = can.Message(arbitration_id=primary_ID_SET_TS_STATUS_HANDCART,
                                  data=tmp.serialize(),
                                  is_extended_id=False)
        tx_can_queue.put(message)


def balancing_disabled_check():
    if canread.bms_hv.is_balancing:
        tmp = message_SET_CELL_BALANCING_STATUS(set_balancing_status=Toggle.OFF)
        message = can.Message(arbitration_id=primary_ID_SET_CELL_BALANCING_STATUS,
                              data=tmp.serialize(),
                              is_extended_id=False)
        tx_can_queue.put(message)


def resetGPIOs():
    GPIO.output(PIN.PON_CONTROL.value, GPIO.LOW)
    GPIO.output(PIN.SD_RELAY.value, GPIO.HIGH)
    GPIO.output(PIN.GREEN_LED.value, GPIO.LOW)
    GPIO.output(PIN.BLUE_LED.value, GPIO.LOW)
    GPIO.output(PIN.RED_LED.value, GPIO.LOW)


def setLedColor(color):
    if color == TSAL_COLOR.OFF:
        GPIO.output(PIN.GREEN_LED.value, GPIO.LOW)
        GPIO.output(PIN.BLUE_LED.value, GPIO.LOW)
        GPIO.output(PIN.RED_LED.value, GPIO.LOW)
    if color == TSAL_COLOR.RED:  # TSON
        GPIO.output(PIN.GREEN_LED.value, GPIO.LOW)
        GPIO.output(PIN.BLUE_LED.value, GPIO.LOW)
        GPIO.output(PIN.RED_LED.value, GPIO.HIGH)
    elif color == TSAL_COLOR.ORANGE:  # ERROR
        GPIO.output(PIN.GREEN_LED.value, GPIO.HIGH)
        GPIO.output(PIN.BLUE_LED.value, GPIO.LOW)
        GPIO.output(PIN.RED_LED.value, GPIO.HIGH)
    elif color == TSAL_COLOR.PURPLE:  # TSON and CHARGING
        GPIO.output(PIN.GREEN_LED.value, GPIO.LOW)
        GPIO.output(PIN.BLUE_LED.value, GPIO.HIGH)
        GPIO.output(PIN.RED_LED.value, GPIO.HIGH)
    elif color == TSAL_COLOR.GREEN:  # TS OFF
        GPIO.output(PIN.GREEN_LED.value, GPIO.HIGH)
        GPIO.output(PIN.BLUE_LED.value, GPIO.LOW)
        GPIO.output(PIN.RED_LED.value, GPIO.LOW)
    elif color == TSAL_COLOR.WHITE:
        GPIO.output(PIN.GREEN_LED.value, GPIO.HIGH)
        GPIO.output(PIN.BLUE_LED.value, GPIO.HIGH)
        GPIO.output(PIN.RED_LED.value, GPIO.HIGH)
    elif color == TSAL_COLOR.YELLOW:
        GPIO.output(PIN.GREEN_LED.value, GPIO.HIGH)
        GPIO.output(PIN.BLUE_LED.value, GPIO.LOW)
        GPIO.output(PIN.RED_LED.value, GPIO.HIGH)


# Maps state to it's function
doState = {
    STATE.CHECK: doCheck,
    STATE.IDLE: doIdle,
    STATE.PRECHARGE: doPreCharge,
    STATE.READY: doReady,
    STATE.CHARGE: doCharge,
    STATE.C_DONE: doC_done,
    STATE.BALANCING: do_balancing,
    STATE.ERROR: doError,
    STATE.EXIT: doExit
}


# Backend Thread
def thread_1_FSM():
    """
    The thread that runs the backend state machine
    Pls read the documentation about the state machine
    """

    global shared_data, shutdown_asked, actual_fsm_state

    act_stat = STATE.CHECK
    canread.FSM_entered_stat = datetime.now().isoformat()
    print("Backend started")
    print("STATE: " + str(act_stat))

    while 1:
        time.sleep(0.001)
        # print("main")
        # Controllo coda rec can messages, in caso li processo. Controllo anche errori
        if not rx_can_queue.empty():
            new_msg = rx_can_queue.get()
            canread.on_message_received(new_msg)

        if act_stat != STATE.CHECK:
            if not canread.bms_hv.isConnected():
                next_stat = doState.get(STATE.CHECK)
            if (act_stat == STATE.CHARGE or act_stat == STATE.C_DONE) and not canread.brusa.isConnected():
                next_stat = doState.get(STATE.CHECK)

        if act_stat != STATE.BALANCING:
            # Check that balancing is disabled if not in balancing state
            balancing_disabled_check()

        # Checks errors
        if canread.brusa.error or canread.bms_hv.error or canread.can_err:
            next_stat = doState.get(STATE.ERROR)()
        else:
            next_stat = doState.get(act_stat)()

        if shutdown_asked:
            next_stat = STATE.IDLE
            shutdown_asked = False

        if next_stat == STATE.EXIT:
            print("Exiting")
            return

        checkCommands()

        canread.FSM_stat = act_stat
        if act_stat != next_stat:
            canread.FSM_entered_stat = datetime.now().isoformat()
            # print(canread.FSM_entered_stat)
            print("STATE: " + str(next_stat))

        act_stat = next_stat
        actual_fsm_state = next_stat

        with lock:
            shared_data = canread

def thread_led():
    global shared_data

    actual_state = STATE.IDLE
    blinking = False
    is_tsal_on = False
    tsal_actual_color = TSAL_COLOR.OFF

    while 1:
        time.sleep(.1)
        # if actual_state != shared_data.FSM_stat:
        actual_state = shared_data.FSM_stat
        if shared_data.FSM_stat == STATE.CHECK:
            blinking = False
            setLedColor(TSAL_COLOR.WHITE)
            tsal_actual_color = TSAL_COLOR.WHITE
        elif shared_data.FSM_stat == STATE.IDLE:
            blinking = False
            setLedColor(TSAL_COLOR.GREEN)
            tsal_actual_color = TSAL_COLOR.GREEN
        elif shared_data.FSM_stat == STATE.PRECHARGE or \
                shared_data.FSM_stat == STATE.READY:
            blinking = True
            setLedColor(TSAL_COLOR.RED)
            tsal_actual_color = TSAL_COLOR.RED
        elif shared_data.FSM_stat == STATE.CHARGE:
            blinking = True
            setLedColor(TSAL_COLOR.PURPLE)
            tsal_actual_color = TSAL_COLOR.PURPLE
        elif shared_data.FSM_stat == STATE.C_DONE:
            blinking = True
            setLedColor(TSAL_COLOR.RED)
            tsal_actual_color = TSAL_COLOR.RED
        elif shared_data.FSM_stat == STATE.ERROR:
            blinking = False
            setLedColor(TSAL_COLOR.ORANGE)
            tsal_actual_color = TSAL_COLOR.ORANGE

        if blinking:
            if is_tsal_on:
                setLedColor(TSAL_COLOR.OFF)
                is_tsal_on = False
            else:
                setLedColor(tsal_actual_color)
                is_tsal_on = True


def thread_fans():
    global shared_data
    while 1:
        time.sleep(.1)
        with lock:
            if actual_fsm_state == STATE.ERROR or shared_data.bms_hv.max_temp > 50:
                if shared_data.bms_hv.fans_override_status == Toggle.ON:
                    data = message_HV_FANS_OVERRIDE_conversion(fans_override=Toggle.OFF,
                                                               fans_speed=shared_data.bms_hv.fans_set_override_speed).convert_to_raw()
                    msg = can.Message(arbitration_id=primary_ID_HV_FANS_OVERRIDE,
                                      data=data.serialize(),
                                      is_extended_id=False)
                    tx_can_queue.put(msg)
                return

            if (shared_data.bms_hv.fans_override_status !=
                    shared_data.bms_hv.fans_set_override_status):
                # Ask to override or disable override
                set_status = Toggle.OFF
                if shared_data.bms_hv.fans_set_override_status:
                    set_status = Toggle.ON
                data = message_HV_FANS_OVERRIDE_conversion(fans_override=set_status,
                                                           fans_speed=shared_data.bms_hv.fans_set_override_speed).convert_to_raw()
                msg = can.Message(arbitration_id=primary_ID_HV_FANS_OVERRIDE,
                                  data=data.serialize(),
                                  is_extended_id=False)
                tx_can_queue.put(msg)

            if shared_data.bms_hv.fans_override_speed != shared_data.bms_hv.fans_set_override_speed:
                if shared_data.bms_hv.fans_override_status == Toggle.ON:
                    data = message_HV_FANS_OVERRIDE_conversion(fans_override=Toggle.ON,
                                                               fans_speed=shared_data.bms_hv.fans_set_override_speed).convert_to_raw()
                    msg = can.Message(arbitration_id=primary_ID_HV_FANS_OVERRIDE,
                                      data=data.serialize(),
                                      is_extended_id=False)
                    tx_can_queue.put(msg)


# Usare le code tra FSM e CAN per invio e ricezione
# Processare i messaggi nella FSM e inoltrarli gia a posto

if __name__ == "__main__":
    GPIO_setup()
    resetGPIOs()

    atexit.register(exit_handler)  # On exit of the program, execute the function

    t1 = threading.Thread(target=thread_1_FSM, args=())
    t2 = threading.Thread(target=thread_2_CAN, args=())
    t3 = threading.Thread(target=thread_3_WEB, args=(shared_data, lock, com_queue))
    t4 = threading.Thread(target=thread_led, args=())
    t5 = threading.Thread(target=thread_fans, args=())

    t1.start()
    t2.start()
    t3.start()
    if ENABLE_LED:
        setLedColor(TSAL_COLOR.OFF)
        t4.start()
    t5.start()