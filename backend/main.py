#
#   Handcart backend
#   For more info read the ../../doc section, or contact matteo.bitussi@studenti.unitn.it
#   For test purposes, launch start-can.sh before launching this file
#

#   Notes
#       NLG5 - Stands for the BRUSA (also the charger)
#       BMS - Stands for Battery Manage System (also the accumulator)

from enum import Enum
import msgDef
import can
from can.listener import Listener
import argparse
import time
import threading
import queue

CAN_BMS_ID = 170  # 0xAA

BYTE_MASK = [
    0b00000001,
    0b00000010,
    0b00000100,
    0b00001000,
    0b00010000,
    0b00100000,
    0b01000000,
    0b10000000
]

# ID of BRUSA's can messages


class CAN_BRUSA_MSG_ID(Enum):
    NLG5_ERR = 0x614
    NLG5_TEMP = 0x613
    NLG5_ACT_I = 0x611
    NLG5_ACT_II = 0x612
    NLG5_ST = 0x610

# States of the backend's state-machine


class STATE(Enum):
    CHECK = 0
    IDLE = 1
    PRECHARGE = 2
    READY = 3
    CHARGE = 4
    C_DONE = 5
    ERROR = -1
    EXIT = -2


# ID's of BMS can messages
class BMS_MES_ID(Enum):
    CAN_OUT_CURRENT = 5
    CAN_OUT_PACK_VOLTS = 1
    CAN_OUT_PACK_TEMPS = 10
    CAN_OUT_WARNING = 9
    CAN_OUT_ERRORS = 8
    CAN_OUT_TS_ON = 3
    CAN_OUT_TS_OFF = 4

# The possible states of BMS


class BMS_STATE(Enum):
    TS_ON = 3
    TS_OFF = 4
    # Missing

# Backend Error codes, maybe we'll not use them, we'll se


class E_CODE(Enum):
    BATTERY_TEMP = 0
    OVERCHARGE = 0
    CURRENT_DRAWN = 0


# Gives the position of things in "NLG5_ST_POS" can message's data segment
# See BRUSA's can messages sheet for reference
# Maschera per fare l'and bit a bit
NLG5_ST_MASK = {
    "NLG5_S_HE": 0b10000000,
    "NLG5_S_ERR": 0b01000000,
    "NLG5_S_WAR": 0b00100000,
    "NLG5_S_FAN": 0b00010000,
    "NLG5_S_EUM": 0b00001000,
    "NLG5_S_UM_I": 0b00000100,
    "NLG5_S_UM_II": 0b00000010,
    "NLG5_S_CP_DT": 0b00000001,
    "NLG5_S_BPD_I": 0b10000000,
    "NLG5_S_BPD_II": 0b01000000,
    "NLG5_S_L_OV": 0b00100000,
    "NLG5_S_L_OC": 0b00010000,
    "NLG5_S_L_MC": 0b00001000,
    "NLG5_S_L_PI": 0b0000100,
    "NLG5_S_L_CP": 0b00000010,
    "NLG5_S_L_PMAX": 0b00000001,
    "NLG5_S_L_MC_MAX": 0b10000000,
    "NLG5_S_L_OC_MAX": 0b01000000,
    "NLG5_S_L_MO_MAX": 0b00100000,
    "NLG5_S_L_T_CPRIM": 0b00010000,
    "NLG5_S_L_T_POW": 0b00001000,
    "NLG5_S_L_T_DIO": 0b00000100,
    "NLG5_S_L_T_TR": 0b00000010,
    "NLG5_S_L_T_BATT": 0b00000001,
    "NLG5_S_AAC": 0b10000000
}

# Gives the position of things in  can message's data segment
# See BRUSA's can messages sheet for reference


class NLG5_ACT_I_POS(Enum):
    NLG5_MC_ACT = 0
    NLG5_MV_ACT = 16
    NLG5_OV_ACT = 32
    NLG5_OC_ACT = 48

# Gives the position of things in  can message's data segment
# See BRUSA's can messages sheet for reference


class NLG5_ACT_II_POS(Enum):
    NLG5_S_MC_M_CP = 0
    NLG5_S_MC_M_PI = 16
    NLG5_ABV = 24
    NLG5_AHC_EXT = 32
    NLG5_OC_BO = 48

# Gives the position of things in  can message's data segment
# See BRUSA's can messages sheet for reference


class NLG5_TEMP_POS(Enum):
    NLG5_P_TMP = 0
    NLG5_TMP_EXT1 = 16
    NLG5_TEMP_EXT2 = 32
    NLG5_TMP_EXT3 = 48

# Gives the position of things in  can message's data segment
# See BRUSA's can messages sheet for reference


class NLG5_ERR_POS(Enum):
    NLG5_E_OOV = 0
    NLG5_E_MOV_II = 1
    NLG5_E_MOV_I = 2
    NLG5_E_SC = 3
    NLG5_E_P_OM = 4
    NLG5_E_P_MV = 5
    NLG5_E_OF = 6
    NLG5_E_MF = 7
    NLG5_E_B_P = 8
    NLG5_E_T_C = 9
    NLG5_E_T_POW = 10
    NLG5_E_T_DIO = 11
    NLG5_E_T_TR = 12
    NLG5_E_T_EXT1 = 13
    NLG5_E_T_EXT2 = 14
    NLG5_E_T_EXT3 = 15
    NLG5_E_F_CRC = 16
    NLG5_E_NV_CRC = 17
    NLG5_E_ES_CRC = 18
    NLG5_E_EP_CRC = 19
    NLG5_E_WDT = 20
    NLG5_E_INIT = 21
    NLG5_E_C_TO = 22
    NLG5_E_C_OFF = 23
    NLG5_E_C_TX = 24
    NLG5_E_C_RX = 25
    NLG5_E_SDT_BT = 26
    NLG5_E_SDT_BV = 27
    NLG5_E_SDT_AH = 28
    NLG5_E_SDT_CT = 29
    NLG5_W_PL_MV = 32
    NLG5_W_PL_BV = 33
    NLG5_W_PL_IT = 34
    NLG5_W_C_VOR = 35
    NLG5_W_CM_NA = 36
    NLG5_W_OD = 38
    NLG5_W_SC_M = 39

# Class that stores the info about the last related can msg


class VAL_NLG5_ST():
    lastUpdated = 0  # Last time it was updated in can timestamp
    NLG5_S_HE = False
    NLG5_S_ERR = False
    NLG5_S_WAR = False
    NLG5_S_FAN = False
    NLG5_S_EUM = False
    # eccetera

    def onNewMessage(self, data):
        self.NLG5_S_HE = data[0] & 0b00000001
        self.NLG5_S_ERR = data[0] & 0b00000010
        # eccetera
        pass
        # Class that stores the info about the last related can msg


class VAL_NLG5_ACT_I():
    lastUpdated = 0  # Last time it was updated in can timestamp
    NLG5_MC_ACT = 0
    NLG5_MV_ACT = 0
    NLG5_OV_ACT = 0
    NLG5_OC_ACT = 0

# Class that stores the info about the last related can msg


class VAL_NLG5_ACT_II():
    lastUpdated = 0  # Last time it was updated in can timestamp
    values = []

# Class that stores the info about the last related can msg


class VAL_NLG5_TEMP():
    lastUpdated = 0  # Last time it was updated in can timestamp
    values = []

# Class that stores the info about the last related can msg


class VAL_NLG5_ERR():
    lastUpdated = 0  # Last time it was updated in can timestamp
    error_check = False
    values = [32]  # contains all the values, see NLG5_ERR_POS
    for i in values:
        values = False

    def onNewMessage(self, data):
        pos = 0
        for i in range(5):
            for mask in BYTE_MASK:
                if pos != 30 and pos != 31:
                    res = data[i] & mask
                    if res:
                        self.error_check = True
                    self.values[pos] = res
                    pos += 1


# That listener is called wether a can message arrives, then
# based on the msg ID, processes it, and save on itself the msg info

class CanListener():
    newBMSMessage = False
    newBRUSAMessage = False

    brusa_connected = False
    brusa_err = False
    brusa_err_str_list = []  # the list of errors in string format

    bms_err = False
    bms_stat = -1
    bms_connected = False
    bms_err_str = ""

    can_err = False
    cutoff_V = 330

    act_NLG5_ST = VAL_NLG5_ST()  # Instantiate the value
    act_NLG5_ACT_I = VAL_NLG5_ACT_I()
    act_NLG5_ERR = VAL_NLG5_ERR()

    def setTSON(self, msg):
        msg.data = []
        self.bms_stat = BMS_STATE.TS_ON

    def setTSOFF(self, msg):
        self.bms_stat = BMS_STATE.TS_OFF

    def setVolts(self, msg):
        pass

    def setCurrent(self, msg):
        pass

    def setError(self, msg):
        pass

    def setWarning(self, msg):
        pass

    def setPackTemp(self, msg):
        pass

    # Called on new BMS message, maps the related function based on
    # msg ID
    def serveBMSMessage(self, msg):
        self.newBMSMessage = True
        self.bms_connected = True
        self.msgTypeBMS.get(msg.data[0])(self, msg)

    # Handles Brusa CAN status messages
    def doNLG5_ST(self, msg):
        self.brusa_connected = True
        self.act_NLG5_ST.onNewMessage(msg.data)
        if self.act_NLG5_ST.NLG5_S_ERR == True:
            self.brusa_err = True

    def doNLG5_ACT_I(self, msg):
        # Manca da trasformare i valori in bit in valori decimali
        #act_NLG5_ACT_I.NLG5_MC_ACT = data[NLG5_ACT_I_POS.NLG5_MC_ACT]
        pass

    def doNLG5_ACT_II(self, msg):
        pass

    def doNLG5_TEMP(self, msg):
        pass

    def doNLG5_ERR(self, msg):
        self.act_NLG5_ERR.onNewMessage(msg.data)
        if self.act_NLG5_ERR.error_check:
            self.brusa_err = True
            for i in range(40):
                if self.act_NLG5_ERR.values[i]:
                    self.brusa_err_str_list.append(msgDef.NLG5_ERR_DEF[i])

    # Maps can msg's ID with the relative function,
    # Pls, whatch out on Enums, sometimes Enum don't match value
    msgTypeBMS = {
        BMS_MES_ID.CAN_OUT_PACK_VOLTS.value: setVolts,
        BMS_MES_ID.CAN_OUT_TS_ON.value: setTSON,
        BMS_MES_ID.CAN_OUT_TS_OFF.value: setTSOFF,
        BMS_MES_ID.CAN_OUT_CURRENT.value: setCurrent,
        BMS_MES_ID.CAN_OUT_ERRORS.value: setError,
        BMS_MES_ID.CAN_OUT_WARNING.value: setWarning,
        BMS_MES_ID.CAN_OUT_PACK_TEMPS.value: setPackTemp
    }

    # Maps the can msg to relative function
    doMsg = {
        CAN_BMS_ID: serveBMSMessage,
        CAN_BRUSA_MSG_ID.NLG5_ST.value: doNLG5_ST,
        CAN_BRUSA_MSG_ID.NLG5_ACT_I.value: doNLG5_ACT_I,
        CAN_BRUSA_MSG_ID.NLG5_ACT_II.value: doNLG5_ACT_II,
        CAN_BRUSA_MSG_ID.NLG5_ERR.value: doNLG5_ERR,
        CAN_BRUSA_MSG_ID.NLG5_TEMP.value: doNLG5_TEMP
    }

    def __init__(self):
        pass

    # Function called when a new message arrive, maps it to
    # relative function based on ID
    def on_message_received(self, msg):
        print("Received: " + msg)
        if self.doMsg.get(msg.arbitration_id) != None:
            self.doMsg.get(msg.arbitration_id)(self, msg)


class Can_rx_listener(Listener):
    def __init__(self):
        pass

    def on_message_received(self, msg):
        rx_can_queue.put(msg)


class DataHolder():
    brusa_err = False
    brusa_err_str_list = []  # the list of errors in string format
    bms_err = False
    bms_stat = -1
    brusa_connected = False
    bms_connected = False
    bms_err_str = ""
    can_err = False


PORK_CONNECTED = False
BRUSA_CONNECTED = False
act_stat = STATE.CHECK  # stores the status of the FSM
last_err = 0  # stores the value of the last error (not sure if we'll use this)
canread = CanListener()  # Access it ONLY with the FSM

# IPC
shared_data = DataHolder()
rx_can_queue = queue.Queue()
tx_can_queue = queue.Queue()
com_queue = queue.Queue()
lock = threading.Lock()

# function that clear all the errors stored
# USE WITH CARE


def clrErr():
    canread.brusa_err = False
    canread.bms_err = False
    canread.bms_err_str = ""
    canread.brusa_err_str_list = []
    canread.can_err = False

# connects to canbus, and liks the listener


def canInit(listener):
    try:
        canbus = can.interface.Bus(interface="socketcan", channel="can0")
        # links the bus with the listener
        notif = can.Notifier(canbus, [listener])

        return canbus
    except(ValueError):
        print("Can channel not recognized")
        return False
    except(can.CanError):
        print("Can Error")
        return False
    except(NotImplementedError):
        print("Can interface not recognized")
        return False

# Send can message


def canSend(bus, msg_id, data):
    # doesn't check the msg before sending it
    msg = can.Message(arbitration_id=msg_id, data=data)
    try:
        bus.send(msg)
        # print("Message sent on {}".format(canbus.channel_info))
        return True
    except can.CanError:
        print("Can Error: Message not sent")
        canread.can_err = True
        raise can.CanError

# Checks if can is connected


def isPorkConnected():
    # canSend(BMS_HV, TS_STATUS_REQ)
    if (canread.bms_stat) != -1:
        print("Accumulator connected")
        return True
    else:
        return False

# Checks if brusa is connected


def isBrusaConnected():
    if canread.brusa_connected:
        print("Brusa connected")
        return True
    else:
        return False

# Do state CHECK


def doCheck():
    canread.pork_connected = isPorkConnected()
    canread.brusa_connected = isBrusaConnected()

    if canread.pork_connected and canread.pork_connected:
        return STATE.IDLE
    else:
        return STATE.CHECK

# Do state IDLE


def doIdle():
    if not com_queue.empty():
        act_com = com_queue.get()

    if act_com['com-type'] == "precharge" and act_com['value'] == True:
        return STATE.PRECHARGE
    else:
        return STATE.IDLE


def doPreCharge(data):
    # ask pork to do precharge
    # Send req to bms "TS_ON"
    # If response of HV_STATUS = TS_ON ok

    PRECHARGE_DONE = False

    if data.bms_stat == BMS_STATE.TS_ON:
        print("Precharge done, TS is on")
        PRECHARGE_DONE = True

    if PRECHARGE_DONE:
        return STATE.READY


def doReady():
    if not com_queue.empty():
        act_com = com_queue.get()

        if act_com['com-type'] == "charge" and act_com['value'] == True:
            return STATE.CHARGE

    else:
        return STATE.READY


def doCharge():
    # canread has to forward charging msgs from bms to brusa

    CHARGE_COMPLETE = False

    # Check if voltage is cutoff voltage

    if CHARGE_COMPLETE:
        return STATE.C_DONE
    else:
        return STATE.CHARGE


def doC_done():
    # User decide wether charge again, going idle, or charge again
    # Req "CHG_OFF" to bms
    pass


def doError():
    if canread.brusa_err:
        print("BRUSA Error: ")
        for i in canread.brusa_err_str_list:
            print(i)
    if canread.bms_err:
        print("Accumulator Error: ")
        print(canread.bms_err_str)
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
    exit(0)


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

lock = threading.Lock()


def thread_1_FSM(lock):
    # Pls read the infos about the state machine

    act_stat = STATE.CHECK
    while (1):
        time.sleep(1)
        # Controllo coda rec can messages, in caso li processo. Controllo anche errori
        if not rx_can_queue.empty():
            new_msg = rx_can_queue.get()
            canread.on_message_received(new_msg)

        # Checks errors
        if canread.brusa_err or canread.bms_err or canread.can_err:
            next_stat = doState.get(STATE.ERROR)()
        else:
            next_stat = doState.get(act_stat)()

        print("STATE: " + str(act_stat))

        if next_stat == STATE.EXIT:
            return
        act_stat = next_stat

        with lock:
            # Updates shared data with updated one
            shared_data.bms_err = canread.bms_err
            shared_data.bms_err_str = canread.bms_err_str
            shared_data.bms_stat = canread.bms_stat
            shared_data.bms_connected = canread.bms_connected
            shared_data.brusa_connected = canread.brusa_connected
            shared_data.brusa_err = canread.brusa_err
            shared_data.brusa_err_str_list = canread.brusa_err_str_list
            shared_data.can_err = canread.can_err


def thread_2_CAN(lock):
    can_r_w = Can_rx_listener()
    canbus = canInit(can_r_w)

    # Sends all messages in tx queue
    while not tx_can_queue.empty:
        time.sleep(1)
        act = tx_can_queue.get()
        canSend(canbus, act.id, act.data)


def thread_3_WEB(lock):
    while(1):
        time.sleep(1)
        with lock:
            print(shared_data.bms_connected)

# Usare le code tra FSM e CAN per invio e ricezione
# Processare i messaggi nella FSM e inoltrarli gia a posto


t1 = threading.Thread(target=thread_1_FSM, args=(lock,))
t2 = threading.Thread(target=thread_2_CAN, args=(lock,))
t3 = threading.Thread(target=thread_3_WEB, args=(lock,))

t1.start()
t2.start()
t3.start()
