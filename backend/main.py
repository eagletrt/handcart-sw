"""@package Handcart backend
For more info read the ../../doc section, or contact matteo.bitussi@studenti.unitn.it
For test purposes, launch start-can.sh before launching this file

Notes:
    NLG5 - Stands for the BRUSA (also the charger)
    BMS (or BMS HV) - Stands for Battery Manage System (also the accumulator)
"""

import datetime
import json
import logging
import queue
import random
import struct
import threading
import time
from datetime import datetime, timedelta
from enum import Enum

import can
import cantools
import flask
import pytz
from can.listener import Listener
from flask import render_template
from flask import request, jsonify
import RPi.GPIO as GPIO

from can_cicd.includes_generator.Primary.ids import *
from can_cicd.naked_generator.Primary.py.Primary import *

brusa_dbc = cantools.database.load_file('NLG5_BRUSA.dbc')

GPIO.setmode(GPIO.BCM) # Set Pi to use pin number when referencing GPIO pins.

FAST_CHARGE_MAINS_AMPERE = 16
STANDARD_CHARGE_MAINS_AMPERE = 6

MAX_ACC_CHG_AMPERE = 12  # Maximum charging current of accumulator
STANDARD_ACC_CHG_AMPERE = 8  # Standard charging current of accumulator
MAX_TARGET_V_ACC = 430  # Maximum charging voltage of accumulator

CAN_DEVICE_TIMEOUT = 2000  # Time tolerated between two message of a device
CAN_ID_BMS_HV_CHIMERA = 0xAA
CAN_ID_ECU_CHIMERA = 0x55

led_blink = False

# BMS_HV_BYPASS = False # Use at your own risk

class PIN(Enum):
    RED_LED = 12 #31
    GREEN_LED = 13 #33
    BLUE_LED = 16 #36
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

class ACCUMULATOR(Enum):
    CHIMERA = 1
    FENICE = 2


class CAN_CHIMERA_MSG_ID(Enum):
    PACK_VOLTS = 0x01
    PACK_TEMPS = 0x0A
    TS_ON = 0x03
    TS_OFF = 0x04
    CURRENT = 0x05
    AVG_TEMP = 0x06
    MAX_TEMP = 0x07
    ERROR = 0x08
    WARNING = 0x09


class CAN_REQ_CHIMERA(Enum):
    REQ_TS_ON = 0x0A  # Remember to ask charge state with byte 1 set to 0x01
    REQ_TS_OFF = 0x0B


class STATE(Enum):
    """Enum containing the states of the backend's state-machine
    """
    CHECK = 0
    IDLE = 1
    PRECHARGE = 2
    READY = 3
    CHARGE = 4
    C_DONE = 5
    ERROR = -1
    EXIT = -2


class CAN_BRUSA_MSG_ID(Enum):
    """Enum containing the IDs of BRUSA's can messages"""
    NLG5_ERR = 0x614
    NLG5_TEMP = 0x613
    NLG5_ACT_I = 0x611
    NLG5_ACT_II = 0x612
    NLG5_ST = 0x610
    NLG5_CTL = 0x618


class BRUSA:
    """Class to store and process all the Brusa data
    """
    lastupdated = 1

    act_NLG5_ST_values = {}
    act_NLG5_ACT_I = {}
    act_NLG5_ACT_II = {}
    act_NLG5_TEMP = {}
    act_NLG5_ERR = {}

    error = False
    act_NLG5_ERR_str = []
    act_NLG5_ST_srt = []

    def isConnected(self):
        """Checks if Brusa is connected
        :return: True if Brusa is connected
        """
        return not self.lastupdated == 0

    def doNLG5_ST(self, msg):
        """
        Processes a CAN Status message from Brusa
        :param msg: the Can message
        """
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()

        self.act_NLG5_ST_values = brusa_dbc.decode_message(msg.arbitration_id, msg.data)
        for key in self.act_NLG5_ST_values:
            value = self.act_NLG5_ST_values[key]
            if (value == 1):
                signals = brusa_dbc.get_message_by_name('NLG5_ST').signals
                for s in signals:
                    if s.name == key:
                        self.act_NLG5_ST_srt.append(s.comment)
                        break

        if self.act_NLG5_ST_values['NLG5_S_ERR'] == 1:
            self.error = True

    def doNLG5_ACT_I(self, msg):
        """
        Process a CAN ACT_I message from Brusa
        :param msg: the ACT_I can message
        """
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()
        self.act_NLG5_ACT_I = brusa_dbc.decode_message(msg.arbitration_id, msg.data)

    def doNLG5_ACT_II(self, msg):
        """
        Process a CAN ACT_II message from Brusa
        :param msg: the ACT_II can message
        """
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()
        self.act_NLG5_ACT_II = brusa_dbc.decode_message(msg.arbitration_id, msg.data)

    def doNLG5_TEMP(self, msg):
        """
        Process a CAN TEMP message from Brusa
        :param msg: the TEMP can message
        """
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()
        self.act_NLG5_TEMP = brusa_dbc.decode_message(msg.arbitration_id, msg.data)

    def doNLG5_ERR(self, msg):
        """
        Process a CAN ERR message from Brusa
        :param msg: the ERR can message
        """
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()
        self.act_NLG5_ERR = brusa_dbc.decode_message(msg.arbitration_id, msg.data)
        self.act_NLG5_ERR_str = []

        for key in self.act_NLG5_ERR:
            value = self.act_NLG5_ERR[key]
            if value == 1:
                self.error = True
                signals = brusa_dbc.get_message_by_name('NLG5_ERR').signals
                for s in signals:
                    if s.name == key:
                        self.act_NLG5_ERR_str.append(s.comment)
                        break


class BMS_HV:
    """
    Class that stores and processes all the data of the BMS_HV
    """

    ACC_CONNECTED = ACCUMULATOR.FENICE  # Default fenice, if msgs from chimera received will be changed

    lastupdated = 0

    hv_voltage_history = []
    hv_current_history = []
    hv_temp_history = []

    act_pack_voltage = -1
    act_bus_voltage = -1
    act_current = -1
    act_power = -1
    max_cell_voltage = -1
    min_cell_voltage = -1
    error = False
    errors = 0
    warnings = None
    error_str = ""
    status = Ts_Status.OFF
    chg_status = -1
    req_chg_current = 0
    req_chg_voltage = 0
    act_average_temp = -1
    min_temp = -1
    max_temp = -1

    def isConnected(self):
        """
        Check if BMS_HV is connected
        :return: True if BMS_HV is connected
        """
        return not self.lastupdated == 0

    def doHV_VOLTAGE(self, msg):
        """
        Processes th HV_VOLTAGE CAN message from BMS_HV
        :param msg: the HV_VOLTAGE CAN message
        """
        # someway somehow you have to extract:
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()

        deserialized = HvVoltage.deserialize(msg.data)

        self.act_bus_voltage = deserialized.bus_voltage
        self.max_cell_voltage = deserialized.max_cell_voltage
        self.min_cell_voltage = deserialized.min_cell_voltage

        self.hv_voltage_history.append({"timestamp": self.lastupdated,
                                        "bus_voltage": self.act_bus_voltage,
                                        "max_cell_voltage": self.max_cell_voltage,
                                        "min_cell_voltage": self.max_cell_voltage})

    def doHV_CURRENT(self, msg):
        """
        Processes the HV_CURRENT CAN message from BMS_HV
        :param msg: the HV_CURRENT CAN message
        """

        deserialized = HvCurrent.deserialize(msg.data)
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()

        self.act_current = deserialized.current
        self.act_power = deserialized.power
        self.hv_current_history.append({
            "timestamp": self.lastupdated,
            "ampere": deserialized.current,
            "power": deserialized.power
        })

    def doHV_TEMP(self, msg):
        """
        Processes the HV_TEMP CAN message from BMS_HV
        :param msg: the HV_TEMP CAN message
        """

        deserialized = HvTemp.deserialize(msg.data)
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()

        self.act_average_temp = deserialized.average_temp
        self.hv_temp_history.append({"timestamp": self.lastupdated,
                                     "average_temp": deserialized.average_temp,
                                     "max_temp": deserialized.max_temp,
                                     "min_temp": deserialized.min_temp})

        self.min_temp = deserialized.min_temp
        self.max_temp = deserialized.max_temp

    def doHV_ERRORS(self, msg):
        """
        Processes the HV_ERRORS CAN message from BMS_HV
        :param msg: the HV_ERRORS CAN message
        """
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()

        deserialized = HvErrors.deserialize(msg.data)

        # TODO: ask BMS_HV status
        self.errors = Hv_Errors(deserialized.errors)
        self.warnings = deserialized.warnings

        if self.errors != 0:
            self.error = True

    def doHV_STATUS(self, msg):
        """
        Processes the HV_STATUS CAN message from BMS_HV
        :param msg: the HV_STATUS CAN message
        """
        print(msg.arbitration_id)
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()
        self.status = Ts_Status(TsStatus.deserialize(msg.data).ts_status)

    def do_CHG_SET_POWER(self, msg):
        """
        Processes the CHG_SET_POWER CAN message from BMS_HV
        :param msg: the CHG_SET_POWER CAN message
        """
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()
        power = SetChgPower.deserialize(msg.data)
        self.req_chg_current = power.current
        if power.voltage > 500:
            self.error = True
            self.error_str = "Required charging voltage exceeds 500 Volts"
        self.req_chg_voltage = power.voltage

    def doCHG_STATUS(self, msg):
        """
        Processes the CHG_STATUS CAN message from BMS_HV
        :param msg: the CHG_STATUS CAN message
        """
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()
        self.status = ChgStatus.deserialize(msg.data).status

    def do_CHIMERA(self, msg):
        """
        Processes a BMS HV message from CHIMERA accumulator
        """
        self.ACC_CONNECTED = ACCUMULATOR.CHIMERA

        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()

        if msg.data[0] == CAN_CHIMERA_MSG_ID.TS_ON.value:
            print("ts on message")
            self.status = Ts_Status.ON
        elif msg.data[0] == CAN_CHIMERA_MSG_ID.TS_OFF.value:
            self.status = Ts_Status.OFF
        elif msg.data[0] == CAN_CHIMERA_MSG_ID.ERROR.value:
            self.error = True
        elif msg.data[0] == CAN_CHIMERA_MSG_ID.PACK_VOLTS.value:
            self.act_bus_voltage = round((msg.data[1] << 16 | msg.data[2] << 8 | msg.data[3]) / 10000, 1)
            self.max_cell_voltage = round((msg.data[4] << 8 | msg.data[5]) / 10000, 2)
            self.min_cell_voltage = round((msg.data[6] << 8 | msg.data[7]) / 10000, 2)
            self.hv_voltage_history.append({"timestamp": self.lastupdated,
                                            "bus_voltage": self.act_bus_voltage,
                                            "max_cell_voltage": self.max_cell_voltage,
                                            "min_cell_voltage": self.max_cell_voltage})

        elif msg.data[0] == CAN_CHIMERA_MSG_ID.PACK_TEMPS.value:
            a = "<hhhx"
            self.act_average_temp, self.max_temp, self.min_temp = struct.unpack(a, msg.data)
            self.act_average_temp /= 100
            self.max_temp /= 100
            self.min_temp /= 100
            self.hv_temp_history.append({"timestamp": self.lastupdated,
                                         "average_temp": self.act_average_temp,
                                         "max_temp": self.max_temp,
                                         "min_temp": self.min_temp})

        elif msg.data[0] == CAN_CHIMERA_MSG_ID.CURRENT.value:
            self.act_current = (msg.data[1] << 8 | msg.data[2])/10
            self.act_power = (msg.data[3] << 8 | msg.data[4])
            self.hv_current_history.append({"timestamp": self.lastupdated,
                                            "current": self.act_current,
                                            "power": self.act_power})

class CanListener:
    """
    That listener is called wether a can message arrives, then
    based on the msg ID, processes it, and save on itself the msg info.
    This class also stores all the data recived from the devices
    """
    FSM_stat = STATE.IDLE  # The actual state of the FSM (mirror the main variable)
    FSM_entered_stat = ""  # The moment in time the FSM has entered that state
    fast_charge = False

    generic_error = False
    can_err = False
    target_v = MAX_TARGET_V_ACC

    brusa = BRUSA()
    bms_hv = BMS_HV()

    # Maps the incoming can msgs to relative function
    doMsg = {
        # brusa
        CAN_BRUSA_MSG_ID.NLG5_ST.value: brusa.doNLG5_ST,
        CAN_BRUSA_MSG_ID.NLG5_ACT_I.value: brusa.doNLG5_ACT_I,
        CAN_BRUSA_MSG_ID.NLG5_ACT_II.value: brusa.doNLG5_ACT_II,
        CAN_BRUSA_MSG_ID.NLG5_ERR.value: brusa.doNLG5_ERR,
        CAN_BRUSA_MSG_ID.NLG5_TEMP.value: brusa.doNLG5_TEMP,

        # BMS_HV Fenice
        ID_HV_VOLTAGE: bms_hv.doHV_VOLTAGE,
        ID_HV_CURRENT: bms_hv.doHV_CURRENT,
        ID_HV_ERRORS: bms_hv.doHV_ERRORS,
        ID_HV_TEMP: bms_hv.doHV_TEMP,
        ID_TS_STATUS: bms_hv.doHV_STATUS,
        ID_SET_CHG_POWER: bms_hv.do_CHG_SET_POWER,
        ID_CHG_STATUS: bms_hv.doCHG_STATUS,

        # BMS_HV Chimera
        CAN_ID_BMS_HV_CHIMERA: bms_hv.do_CHIMERA
    }

    # Function called when a new message arrive, maps it to
    # relative function based on ID
    def on_message_received(self, msg):
        """
        This function is called whether a new message arrives, it then
        calls the corresponding function to process the message
        :param msg: the incoming message
        """
        # print(msg.arbitration_id)
        if self.doMsg.get(msg.arbitration_id) is not None:
            self.doMsg.get(msg.arbitration_id)(msg)


class Can_rx_listener(Listener):
    """
    This class is a listener for the incoming can messages,
    it has to be linked to the canbus object.
    """

    def on_message_received(self, msg):
        """
        This method is called when a new message arrives to the interface,
        it then put the message in the rx queue
        :param msg: the incoming message
        """
        # print(msg)
        # print(msg)
        if msg.arbitration_id == 4:
            return
        rx_can_queue.put(msg)


# FSM vars
canread = CanListener()  # Access it ONLY with the FSM
precharge_asked = False  # True if precharge asked to bms
precharge_done = False
precharge_command = False  # True if received precharge command
start_charge_command = False  # True if received start charge command
stop_charge_command = False  # True if received stop charge command
shutdown_asked = False

# IPC (shared between threads)
shared_data = canread  # Variable that holds a copy of canread, to get the information from web thread
rx_can_queue = queue.Queue()  # Queue for incoming can messages
tx_can_queue = queue.Queue()  # Queue for outgoing can messages
com_queue = queue.Queue()  # Command queue
lock = threading.Lock()
can_forward_enabled = False  # Enable or disable the charge can messages from BMS_HV to BRUSA
forward_lock = threading.Lock()  # Lock to manage the access to the can_forward_enabled variable


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


def canInit(listener):
    """
    Inits the canbus, connect to it, and links the canbus
    :param listener:
    :return:
    """
    try:
        canbus = can.interface.Bus(interface="socketcan", channel="can0")
        # links the bus with the listener
        notif = can.Notifier(canbus, [listener])

        return canbus
    except ValueError:
        print("Can channel not recognized")
        canread.can_err = True
        return False
    except can.CanError:
        print("Can Error")
        canread.can_err = True
        return False
    except NotImplementedError:
        print("Can interface not recognized")
        canread.can_err = True
        return False


def GPIO_setup():
    """
    This function is used to set-up the GPIO pins
    """
    GPIO.setup(PIN.BUT_0.value, GPIO.OUT)
    GPIO.setup(PIN.BUT_1.value, GPIO.OUT)
    GPIO.setup(PIN.BUT_2.value, GPIO.OUT)
    GPIO.setup(PIN.BUT_3.value, GPIO.OUT)
    GPIO.setup(PIN.BUT_4.value, GPIO.OUT)
    GPIO.setup(PIN.BUT_5.value, GPIO.OUT)
    GPIO.setup(PIN.PON_CONTROL, GPIO.OUT)
    GPIO.setup(PIN.SD_RELAY, GPIO.OUT)
    GPIO.setup(PIN.ROT_A, GPIO.OUT)
    GPIO.setup(PIN.ROT_B, GPIO.OUT)


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
        print("Can Error: Message not sent")
        with(lock):
            shared_data.can_err = True
        raise can.CanError


def doCheck():
    """
    Do check status of the state machine
    """

    if canread.bms_hv.isConnected() and canread.brusa.isConnected():
        return STATE.IDLE
    else:
        return STATE.CHECK


def doIdle():
    """
    Do Idle status of the state machine
    :return:
    """
    global precharge_command

    # Shutdown pork
    accumulator_sd()

    if precharge_command:
        precharge_command = False
        return STATE.PRECHARGE

    return STATE.IDLE


def doPreCharge():
    """
    Function that do the precharge status
    """
    # ask pork to do precharge
    # Send req to bms "TS_ON"
    global precharge_asked, precharge_done

    if canread.bms_hv.status == Ts_Status.OFF and not precharge_asked:
        if canread.bms_hv.ACC_CONNECTED == ACCUMULATOR.FENICE:
            ts_on_msg = can.Message(arbitration_id=ID_SET_TS_STATUS,
                                    data=SetTsStatus.serialize(Ts_Status_Set.ON),
                                    is_extended_id=False)
        else:
            ts_on_msg = can.Message(arbitration_id=0x55,
                                    data=[CAN_REQ_CHIMERA.REQ_TS_ON.value, 0x01, 0x00, 0x00],
                                    is_extended_id=False)

        tx_can_queue.put(ts_on_msg)
        precharge_asked = True

    if canread.bms_hv.status == Ts_Status.ON:
        print("Precharge done, TS is on")
        precharge_done = True
        precharge_asked = False

    if precharge_done:
        return STATE.READY
    else:
        return STATE.PRECHARGE


def doReady():
    """
    Function that do the ready state of the state machine
    """
    global start_charge_command, precharge_asked

    if canread.bms_hv.status != Ts_Status.ON:
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
    GPIO.setmode(PIN.PON_CONTROL, GPIO.HIGH)

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
            canread.can_err = True

    return STATE.CHARGE


def doC_done():
    """
    Function that do the charge done of the state machine
    :return:
    """
    # User decide wether charge again or going idle
    GPIO.setmode(PIN.PON_CONTROL, GPIO.LOW)

    return STATE.C_DONE


def doError():
    """
    Do the error state of the state machine
    """
    global can_forward_enabled

    with forward_lock:
        can_forward_enabled = False

    GPIO.setmode(PIN.PON_CONTROL, GPIO.LOW)

    # Send to BMS stacca stacca
    if not canread.bms_hv.status == Ts_Status.OFF.value:
        staccastacca()

    if canread.brusa.error:
        for i in canread.brusa.act_NLG5_ERR_str:
            pass
            # print("[ERR] " + i)
    if canread.bms_hv.error:
        print("Accumulator Error: ")
        print(canread.bms_hv.error_str)
    if canread.can_err:
        print("Can Error")

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
    and all the devices
    """
    global precharge_asked, precharge_done, can_forward_enabled
    #FENICE
    sts = SetTsStatus()
    data = sts.serialize(Ts_Status_Set.OFF.value)
    msg = can.Message(arbitration_id=ID_SET_TS_STATUS, data=data, is_extended_id=False)
    tx_can_queue.put(msg)
    #CHIMERA
    msg = can.Message(arbitration_id=CAN_ID_ECU_CHIMERA, data=[CAN_REQ_CHIMERA.REQ_TS_OFF.value], is_extended_id=False)
    tx_can_queue.put(msg)

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
    global precharge_command, start_charge_command, stop_charge_command, shutdown_asked

    if not com_queue.empty():
        act_com = com_queue.get()
        print(type(act_com))
        if act_com['com-type'] == 'fast-charge':
            if act_com['value'] is False:
                canread.fast_charge = False
            if act_com['value'] is True:
                print("true")
                canread.fast_charge = True

        if act_com['com-type'] == 'cutoff':
            if int(act_com['value']) > 200 and int(act_com['value'] < 470):
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


def accumulator_sd(): # accumulator shutdown
    if canread.bms_hv.status == Ts_Status.ON:
        if canread.bms_hv.ACC_CONNECTED == ACCUMULATOR.CHIMERA:
            message = can.Message(arbitration_id=CAN_ID_ECU_CHIMERA, is_extended_id=False,
                                  data=[CAN_REQ_CHIMERA.REQ_TS_OFF.value])
            tx_can_queue.put(message)
        elif canread.bms_hv.ACC_CONNECTED == ACCUMULATOR.FENICE:
            if canread.bms_hv.ACC_CONNECTED == ACCUMULATOR.FENICE:
                message = can.Message(arbitration_id=ID_SET_TS_STATUS,
                                        data=SetTsStatus.serialize(Ts_Status_Set.OFF),
                                        is_extended_id=False)
                tx_can_queue.put(message)
        else:
            canread.generic_error


def initGPIOs():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(PIN.PON_CONTROL, GPIO.OUT)
    GPIO.setup(PIN.SD_RELAY, GPIO.OUT)
    GPIO.setup(PIN.GREEN_LED, GPIO.OUT)
    GPIO.setup(PIN.BLUE_LED, GPIO.OUT)
    GPIO.setup(PIN.RED_LED, GPIO.OUT)


def resetGPIOs():
    GPIO.output(PIN.PON_CONTROL, GPIO.LOW)
    GPIO.output(PIN.SD_RELAY, GPIO.LOW)
    GPIO.output(PIN.GREEN_LED, GPIO.LOW)
    GPIO.output(PIN.BLUE_LED, GPIO.LOW)
    GPIO.output(PIN.RED_LED, GPIO.LOW)


def setLedColor(color):
    if color == TSAL_COLOR.OFF:
        GPIO.output(PIN.GREEN_LED, GPIO.LOW)
        GPIO.output(PIN.BLUE_LED, GPIO.LOW)
        GPIO.output(PIN.RED_LED, GPIO.LOW)
    if color == TSAL_COLOR.RED:  # TSON
        GPIO.output(PIN.GREEN_LED, GPIO.LOW)
        GPIO.output(PIN.BLUE_LED, GPIO.LOW)
        GPIO.output(PIN.RED_LED, GPIO.HIGH)
    elif color == TSAL_COLOR.ORANGE:  # ERROR
        GPIO.output(PIN.GREEN_LED, GPIO.HIGH)
        GPIO.output(PIN.BLUE_LED, GPIO.LOW)
        GPIO.output(PIN.RED_LED, GPIO.HIGH)
    elif color == TSAL_COLOR.PURPLE:  # TSON and CHARGING
        GPIO.output(PIN.GREEN_LED, GPIO.LOW)
        GPIO.output(PIN.BLUE_LED, GPIO.HIGH)
        GPIO.output(PIN.RED_LED, GPIO.HIGH)
    elif color == TSAL_COLOR.GREEN:  # TS OFF
        GPIO.output(PIN.GREEN_LED, GPIO.HIGH)
        GPIO.output(PIN.BLUE_LED, GPIO.LOW)
        GPIO.output(PIN.RED_LED, GPIO.LOW)
    elif color == TSAL_COLOR.WHITE:
        GPIO.output(PIN.GREEN_LED, GPIO.HIGH)
        GPIO.output(PIN.BLUE_LED, GPIO.HIGH)
        GPIO.output(PIN.RED_LED, GPIO.HIGH)

# TODO: Thread per il lampeggio


# Maps state to it's function
doState = {
    STATE.CHECK: doCheck,
    STATE.IDLE: doIdle,
    STATE.PRECHARGE: doPreCharge,
    STATE.READY: doReady,
    STATE.CHARGE: doCharge,
    STATE.C_DONE: doC_done,
    STATE.ERROR: doError,
    STATE.EXIT: doExit
}

# Backend Thread
def thread_1_FSM():
    """
    The thread that runs the backend state machine
    Pls read the documentation about the state machine
    """

    global shared_data, shutdown_asked

    initGPIOs()
    resetGPIOs()

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

        if act_stat != STATE.CHECK and (not canread.bms_hv.isConnected() or not canread.brusa.isConnected()):
            staccastacca()
            next_stat = doState.get(STATE.CHECK)

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

        with lock:
            shared_data = canread


def thread_2_CAN():
    """
    Thread managing the can connection, getting and sending messages
    """
    can_r_w = Can_rx_listener()
    canbus = canInit(can_r_w)
    last_brusa_ctl_sent = 0

    while 1:
        time.sleep(0.001)
        # print("can")
        while not tx_can_queue.empty():
            act = tx_can_queue.get()
            canSend(canbus, act.arbitration_id, act.data)

        # Handles the brusa ctl messages
        with forward_lock:
            if time.time() - last_brusa_ctl_sent > 0.15:  # every tot time send a message
                NLG5_CTL = brusa_dbc.get_message_by_name('NLG5_CTL')
                if can_forward_enabled:
                    with lock:
                        if 0 < shared_data.target_v <= 500:
                            if shared_data.fast_charge:
                                mains_ampere = FAST_CHARGE_MAINS_AMPERE
                                out_ampere = MAX_ACC_CHG_AMPERE
                            else:
                                mains_ampere = STANDARD_CHARGE_MAINS_AMPERE
                                out_ampere = STANDARD_ACC_CHG_AMPERE

                            data = NLG5_CTL.encode({
                                'NLG5_C_C_EN': 1,
                                'NLG5_C_C_EL': 0,
                                'NLG5_C_CP_V': 0,
                                'NLG5_C_MR': 0,
                                'NLG5_MC_MAX': mains_ampere,
                                'NLG5_OV_COM': shared_data.target_v,
                                'NLG5_OC_COM': out_ampere
                            })
                        else:
                            shared_data.generic_error = True
                else:
                    # Brusa need to constantly keep to receive this msg, otherwise it will go in error
                    data = NLG5_CTL.encode({
                        'NLG5_C_C_EN': 0,
                        'NLG5_C_C_EL': 0,
                        'NLG5_C_CP_V': 0,
                        'NLG5_C_MR': 0,
                        'NLG5_MC_MAX': 0,
                        'NLG5_OV_COM': 0,
                        'NLG5_OC_COM': 0
                    })
                NLG5_CTL_message = can.Message(arbitration_id=NLG5_CTL.frame_id,
                                               data=data,
                                               is_extended_id=False)
                tx_can_queue.put(NLG5_CTL_message)
                last_brusa_ctl_sent = time.time()

def thread_3_WEB():
    """
    The webserver thread that runs the server serving the RESFUL requests
    :return:
    """
    app = flask.Flask(__name__)
    app.config["DEBUG"] = False
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    @app.route('/', methods=['GET'])
    def home():
        return render_template("index.html")

    @app.route('/warnings')
    def warnings():
        return render_template("warning.html")

    @app.route('/errors')
    def errors():
        return render_template("error.html")

    @app.route('/settings')
    def settings():
        return render_template("settings.html")

    @app.route('/charts')
    def charts():
        chart = request.args.get("chart")
        return render_template("charts.html", c=chart)

    @app.route('/brusa-info')
    def brusa_info():
        return render_template("brusa-info.html")

    def getLastNSeconds(n):
        now = datetime.now(pytz.timezone('Europe/Rome'))
        a = [(now - timedelta(seconds=i)) for i in range(n)]
        a.reverse()  # an array with the last n seconds form the older date to the now date

        return a

    # HANDCART-(backend)------------------------------------------------------------

    @app.route('/handcart/status', methods=['GET'])
    def get_hc_status():
        with lock:
            data = {
                "timestamp": datetime.now().isoformat(),
                "state": str(shared_data.FSM_stat.name),
                "entered": shared_data.FSM_entered_stat
            }
            resp = jsonify(data)
            resp.status_code = 200
            return resp

    # END-HANDCART-(backend)--------------------------------------------------------
    # BMS-HV------------------------------------------------------------------------

    @app.route('/bms-hv/status', methods=['GET'])
    def get_bms_hv_status():
        with lock:
            if shared_data.bms_hv.isConnected():
                res = {
                    "timestamp": shared_data.bms_hv.lastupdated,
                    "status": shared_data.bms_hv.status.name,
                    "accumulator": shared_data.bms_hv.ACC_CONNECTED.value
                }
                res = jsonify(res)
            else:
                res = {
                    "timestamp": shared_data.bms_hv.lastupdated,
                    "status": "OFFLINE"
                }
                res = jsonify(res)
                res.status_code = 450
        return res

    @app.route('/bms-hv/errors', methods=['GET'])
    def get_bms_hv_errors():
        with lock:
            if shared_data.bms_hv.isConnected():
                error_list = []

                for i in Hv_Errors:
                    if Hv_Errors(i) in Hv_Errors(shared_data.bms_hv.errors):
                        error_list.append(Hv_Errors(i).name)

                res = {
                    "timestamp": shared_data.brusa.lastupdated,
                    "errors": error_list
                }
                res = jsonify(res)
            else:
                res = jsonify("not connected")
                res.status_code = 450
        return res

    @app.route('/bms-hv/warnings', methods=['GET'])
    def get_bms_hv_warnings():
        data = {
            "timestamp": datetime.now().isoformat(),
            "warnings": [
                "i'm exploding",
                "500A output"
            ]
        }

        resp = jsonify(data)
        resp.status_code = 200
        return resp

    # BMS-VOLTAGE-DATA
    @app.route('/bms-hv/volt', methods=['GET'])
    def get_bms_hv_volt():
        if shared_data.bms_hv.isConnected():
            timestamp = datetime.now(pytz.timezone('Europe/Rome'))

            data = {
                "timestamp": timestamp.isoformat(),
                "data": shared_data.bms_hv.hv_voltage_history
            }

            resp = jsonify(data)
            resp.status_code = 200
        else:
            resp = jsonify("not connected")
            resp.status_code = 200
        return resp

    @app.route('/bms-hv/volt/last', methods=['GET'])
    def get_last_bms_hv_volt():
        if shared_data.bms_hv.isConnected():
            data = {
                "timestamp": shared_data.bms_hv.lastupdated,
                "pack_voltage": shared_data.bms_hv.act_bus_voltage,
                # this doesn't exist when asking for whole precedent data
                "bus_voltage": shared_data.bms_hv.act_bus_voltage,
                "max_cell_voltage": shared_data.bms_hv.max_cell_voltage,
                "min_cell_voltage": shared_data.bms_hv.min_cell_voltage
            }
            resp = jsonify(data)
            resp.status_code = 200
        else:
            resp = jsonify("bms hv is offline")
            resp.status_code = 450
        return resp

    @app.route('/bms-hv/ampere', methods=['GET'])
    def get_bms_hv_ampere():
        timestamp = datetime.now(pytz.timezone('Europe/Rome'))
        if shared_data.bms_hv.isConnected():
            data = {
                "timestamp": timestamp.isoformat(),
                "data": shared_data.bms_hv.hv_current_history
            }

            resp = jsonify(data)
            resp.status_code = 200
        else:
            resp = jsonify("bms hv is offline")
            resp.status_code = 450
        return resp

    @app.route('/bms-hv/ampere/last', methods=['GET'])
    def get_last_bms_hv_ampere():
        if shared_data.bms_hv.isConnected():
            data = {
                "timestamp": shared_data.bms_hv.lastupdated,
                "current": shared_data.bms_hv.act_current,
                "power": shared_data.bms_hv.act_power
            }

            resp = jsonify(data)
            resp.status_code = 200
        else:
            resp = jsonify("not connected")
            resp.status_code = 450
        return resp

    # BMS-TEMPERATURE-DATA
    @app.route('/bms-hv/temp', methods=['GET'])
    def get_bms_temp():
        if shared_data.bms_hv.isConnected():
            data = {
                "timestamp": shared_data.bms_hv.lastupdated,
                "data": shared_data.bms_hv.hv_temp_history
            }
            resp = jsonify(data)
            resp.status_code = 200
        else:
            resp = jsonify("not connected")
            resp.status_code = 450

        return resp

    @app.route('/bms-hv/temp/last', methods=['GET'])
    def get_last_bms_temp():
        if shared_data.bms_hv.isConnected():
            data = {
                "timestamp": shared_data.bms_hv.lastupdated,
                "average_temp": shared_data.bms_hv.act_average_temp,
                "max_temp": shared_data.bms_hv.max_temp,
                "min_temp": shared_data.bms_hv.min_temp
            }

            resp = jsonify(data)
            resp.status_code = 200
        else:
            resp = jsonify("bms hv is not connected")
            resp.status_code = 450
        return resp

    # BMS-CELLS-DATA
    @app.route('/bms-hv/cells', methods=['GET'])
    def get_bms_cells():
        data = {
            "timestamp": "2020-12-01:ora",
            "data": []
        }

        ncells = 108
        digits = 3
        min = 0
        max = 5
        n = 30

        last_n_seconds = getLastNSeconds(n)

        for timestamp in last_n_seconds:
            element = {
                "timestamp": timestamp,
                "cells": []
            }
            for i in range(1, ncells + 1):
                value = round(random.uniform(min, max), digits)
                cell = {
                    "id": i,
                    "voltage": value
                }
                element["cells"].append(cell)
            data["data"].append(element)

        c = request.args.get("cell")
        # get all data, if there's a parameter in the request, then it will return
        # a json with only the specified cell values
        if c != None and c != "":
            filtered = {
                "timestamp": "2020-12-01:ora",
                "data": []
            }

            for i in data["data"]:
                for j in i["cells"]:
                    if j["id"] == int(c):
                        element = {
                            "timestamp": i["timestamp"],
                            "voltage": j["voltage"]
                        }

                        filtered["data"].append(element)
                        break  # no need to cycle over the whole array

            resp = jsonify(filtered)
        else:
            resp = jsonify(data)

        resp.status_code = 200
        return resp

    @app.route('/bms-hv/cells/last', methods=['GET'])
    def get_last_bms_cells():
        timestamp = datetime.now(pytz.timezone('Europe/Rome'))
        data = {
            "timestamp": timestamp,
            "cells": []
        }

        ncells = 108
        digits = 3
        min = 0
        max = 5

        for i in range(1, ncells + 1):
            value = round(random.uniform(min, max), digits)
            cell = {
                "id": i,
                "voltage": value
            }
            data["cells"].append(cell)

        c = request.args.get("cell")
        # get all data, if there's a parameter in the request, then it will return
        # a json with only the specified cell values
        if c != None and c != "":
            filtered = {}
            for i in data["cells"]:
                if i["id"] == int(c):
                    filtered = {
                        "timestamp": timestamp,
                        "voltage": i["voltage"]
                    }

                    break  # no need to cycle over the whole array

            resp = jsonify(filtered)
        else:
            resp = jsonify(data)

        resp.status_code = 200
        return resp

    @app.route('/bms-hv/heat', methods=['GET'])
    def get_bms_heat():
        min = 20
        max = 250
        ncells = 108

        timestamp = datetime.now(pytz.timezone('Europe/Rome'))

        data = {
            "timestamp": timestamp,
            "data": []
        }

        for i in range(1, ncells + 1):
            value = random.randrange(min, max)
            element = {
                "cell": i,
                "temp": value
            }
            data["data"].append(element)

        resp = jsonify(data)
        resp.status_code = 200
        return resp

    # END-BMS-HV--------------------------------------------------------------------
    # BRUSA-------------------------------------------------------------------------

    @app.route('/brusa/status', methods=['GET'])
    def get_brusa_status():
        with lock:
            if shared_data.brusa.isConnected():
                res = {
                    "timestamp": shared_data.brusa.lastupdated,
                    "status": shared_data.brusa.act_NLG5_ST_values
                }

                res = jsonify(res)
            else:
                res = jsonify(
                    {
                        "timestamp": shared_data.brusa.lastupdated,
                        "status": {}
                    }
                )
                res.status_code = 450
        return res

    @app.route('/brusa/errors', methods=['GET'])
    def get_brusa_errors():
        with lock:
            if not shared_data.brusa.isConnected():
                res = jsonify("not connected")
                res.status_code = 450
                return res

            errorList = shared_data.brusa.act_NLG5_ERR_str
            res = {"timestamp": shared_data.brusa.lastupdated, "errors": errorList}
            return jsonify(res)

    @app.route('/brusa/info', methods=['GET'])
    def get_brusa_info():
        with lock:
            if not shared_data.brusa.isConnected():
                res = jsonify("not connected")
                res.status_code = 450
                return res

            res = {
                "timestamp": shared_data.brusa.lastupdated,
            }
            if shared_data.brusa.act_NLG5_ACT_I != {}:
                res["NLG5_MC_ACT"] = round(shared_data.brusa.act_NLG5_ACT_I['NLG5_MC_ACT'],2)
                res["NLG5_MV_ACT"] = round(shared_data.brusa.act_NLG5_ACT_I['NLG5_MV_ACT'],2)
                res["NLG5_OV_ACT"] = round(shared_data.brusa.act_NLG5_ACT_I['NLG5_OV_ACT'],2)
                res["NLG5_OC_ACT"] = round(shared_data.brusa.act_NLG5_ACT_I['NLG5_OC_ACT'],2)
            else:
                res["NLG5_MC_ACT"] = 0
                res["NLG5_MV_ACT"] = 0
                res["NLG5_OV_ACT"] = 0
                res["NLG5_OC_ACT"] = 0
            if shared_data.brusa.act_NLG5_ACT_II != {}:
                res["NLG5_S_MC_M_CP"] = round(shared_data.brusa.act_NLG5_ACT_II['NLG5_S_MC_M_CP'],2)
            else:
                res["NLG5_S_MC_M_CP"] = 0

            if shared_data.brusa.act_NLG5_TEMP != {}:
                res["NLG5_P_TMP"] = round(shared_data.brusa.act_NLG5_TEMP['NLG5_P_TMP'],2)
            else:
                res["NLG5_P_TMP"] = 0

            return jsonify(res)

    @app.route('/command/setting', methods=['GET'])
    def send_settings_command():
        with lock:
            # print(request.get_json())
            data = [{
                "com-type": "cutoff",
                "value": shared_data.target_v
            }, {
                "com-type": "fast-charge",
                "value": shared_data.fast_charge
            }]

            resp = jsonify(data)
            resp.status_code = 200
            return resp

    @app.route('/command/setting', methods=['POST'])
    def recv_command_setting():
        # print(request.get_json())
        command = request.get_json()
        if type(command) != dict:
            command = json.loads(command)
        # in this method and the below one there's
        com_queue.put(command)  # an error due to json is a dict not a string

        resp = jsonify(success=True)
        return resp

    @app.route('/command/action', methods=['POST'])
    def recv_command_action():
        # print(request.get_json())
        action = request.get_json()
        print(action)
        if type(action) != dict:
            action = json.loads(action)

        com_queue.put(action)  # same error above

        resp = jsonify(success=True)
        return resp

    # app.run(use_reloader=False)
    app.run(use_reloader=False, host="0.0.0.0", port=8080)  # to run on the pc ip


def thread_led():
    global shared_data

    actual_state = STATE.IDLE
    blinking = False
    is_tsal_on = False
    tsal_actual_color = TSAL_COLOR.OFF

    while 1:
        time.sleep(.1)
        if actual_state != shared_data.FSM_stat:
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
                setLedColor(TSAL_COLOR.ORANGE)
                tsal_actual_color = TSAL_COLOR.ORANGE
            elif shared_data.FSM_stat == STATE.C_DONE:
                blinking = True
                setLedColor(TSAL_COLOR.PURPLE)
                tsal_actual_color = TSAL_COLOR.PURPLE
            elif shared_data.FSM_stat == STATE.ERROR:
                blinking = False
                setLedColor(TSAL_COLOR.YELLOW)
                tsal_actual_color = TSAL_COLOR.YELLOW

        if blinking:
            if is_tsal_on:
                setLedColor(TSAL_COLOR.OFF)
            else:
                setLedColor(tsal_actual_color)


# Usare le code tra FSM e CAN per invio e ricezione
# Processare i messaggi nella FSM e inoltrarli gia a posto

t1 = threading.Thread(target=thread_1_FSM, args=())
t2 = threading.Thread(target=thread_2_CAN, args=())
t3 = threading.Thread(target=thread_3_WEB, args=())
t4 = threading.Thread(target=thread_led, args=())

t1.start()
t2.start()
t3.start()
t4.start()