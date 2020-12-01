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

CAN_BMS_ID = 0xAA

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
class NLG5_ST_POS(Enum):
    NLG5_S_HE = 0
    NLG5_S_ERR = 1
    NLG5_S_WAR = 2
    NLG5_S_FAN = 3
    NLG5_S_EUM = 4
    NLG5_S_UM_I = 5
    NLG5_S_UM_II = 6
    NLG5_S_CP_DT = 7
    NLG5_S_BPD_I = 8
    NLG5_S_BPD_II = 9
    NLG5_S_L_OV = 10
    NLG5_S_L_OC = 11
    NLG5_S_L_MC = 12
    NLG5_S_L_PI = 13
    NLG5_S_L_CP = 14
    NLG5_S_L_PMAX = 15
    NLG5_S_L_MC_MAX = 16
    NLG5_S_L_OC_MAX = 17
    NLG5_S_L_MO_MAX = 18
    NLG5_S_L_T_CPRIM = 19
    NLG5_S_L_T_POW = 20
    NLG5_S_L_T_DIO = 21
    NLG5_S_L_T_TR = 22
    NLG5_S_L_T_BATT = 23
    NLG5_S_AAC = 31

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
    values = []

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
    values = []

# That listener is called wether a can message arrives, then
# based on the msg ID, processes it, and save on itself the msg info


class CanListener(Listener):
    newBMSMessage = False
    newBRUSAMessage = False

    brusa_err = False
    brusa_err_str_list = []  # the list of errors in string format
    bms_err = False
    bms_stat = -1
    brusa_connected = False
    bms_err_str = ""

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
        self.msgTypeBMS.get(msg.data[0])(self, msg)

    def doNLG5_ST(self, msg):
        self.brusa_connected = True
        self.act_NLG5_ST.values = msg.data

    def doNLG5_ACT_I(self, msg):
        # Manca da trasformare i valori in bit in valori decimali
        act_NLG5_ACT_I.NLG5_MC_ACT = data[NLG5_ACT_I_POS.NLG5_MC_ACT]

    def doNLG5_ACT_II(self, msg):
        pass

    def doNLG5_TEMP(self, msg):
        pass

    def doNLG5_ERR(self, msg):
        self.act_NLG5_ERR.values = msg.data
        c = -1
        for i in self.act_NLG5_ERR.values:
            c += 1
            if i == 1:
                self.brusa_err = 1
                self.brusa_err_str_list.append(NLG5_ERR_DEF[c])

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
        print(msg)
        self.doMsg.get(msg.arbitration_id)(self, msg)


class DataHolder():
    brusa_err = False
    brusa_err_str_list = []  # the list of errors in string format
    bms_err = False
    bms_stat = -1
    brusa_connected = False
    bms_err_str = ""


PORK_CONNECTED = False
BRUSA_CONNECTED = False
act_stat = STATE.CHECK  # stores the status of the FSM
last_err = 0  # stores the value of the last error (not sure if we'll use this)

instance_data = DataHolder()


# Checks if an error is found
def chkErr():
    if instance_data.brusa_err or instance_data.bms_err:
        return True
    else:
        return False

# function that clear all the errors stored
# USE WITH CARE


def clrErr():
    instance_data.brusa_err = False
    instance_data.bms_err = False
    instance_data.bms_err_str = ""
    instance_data.brusa_err_str_list = []

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
        raise can.CanError

# Checks if can is connected


def isPorkConnected(data):
    # canSend(BMS_HV, TS_STATUS_REQ)
    if (data.bms_stat) != -1:
        print("Accumulator connected")
        return True
    else:
        return False

# Checks if brusa is connected


def isBrusaConnected():
    if instance_data.brusa_connected:
        print("Brusa connected")
        return True
    else:
        return False

# Do state CHECK
def doCheck():
    PORK_CONNECTED = isPorkConnected()
    BRUSA_CONNECTED = isBrusaConnected()

    if PORK_CONNECTED and BRUSA_CONNECTED:
        return STATE.IDLE
    else:
        return STATE.CHECK

# Do state IDLE
def doIdle():
    a = input("Type y to start precharge")
    if a == "y":
        return STATE.PRECHARGE
    else:
        return STATE.IDLE


def doPreCharge(data):
    # ask pork to do precharge
    # Send req to bms "TS_ON"
    # If response of HV_STATUS = TS_ON ok

    PRECHARGE_DONE = False

    if (data.newMessage):
        if chkErr():
            return STATE.ERROR
        if (data.bms_stat == BMS_STATE.TS_ON):
            print("Precharge done, TS is on")
            PRECHARGE_DONE = True

    if PRECHARGE_DONE:
        return STATE.READY


def doReady():
    a = input("type y to start charging")

    if a == "y":
        return STATE.CHARGE
    else:
        return STATE.READY


def doCharge():
    # Get volt and A from pork
    # Forward V and A to BRUSA

    CHARGE_COMPLETE = True
    if CHARGE_COMPLETE:
        return STATE.C_DONE
    else:
        return STATE.CHARGE


def doC_done():
    # User decide wether charge again, going idle, or charge again
    # Req "CHG_OFF" to bms
    pass


def doError():
    if instance_data.brusa_err:
        print("BRUSA Error: ")
        for i in instance_data.brusa_err_str_list:
            print(i)
    if instance_data.bms_err:
        print("Accumulator Error: ")
        print(instance_data.bms_err_str)

    command = input(
        "Press c to continue and clear errors, otherwise program will quit")
    if command == 'c':
        clrErr()
        return STATE.CHECK
    else:
        return STATE.EXIT


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

def thread_1_FSM(data, lock):
    # Pls read the infos about the state machine
    act_stat = STATE.CHECK
    while (1):
        # Controllo coda rec can messages, in caso li processo. Controllo anche errori
        print("STATE: " + str(act_stat))
        next_stat = doState.get(act_stat)(data)
        if next_stat == STATE.EXIT:
            return
        act_stat = next_stat
        time.sleep(3)


def thread_2_CAN(data, lock):
    canRead = CanListener()
    canbus = canInit(canRead)

# Usare le code tra FSM e CAN per invio e ricezione
# Processare i messaggi nella FSM e inoltrarli gia a posto

def thread_3_WEB(data, lock):
    pass