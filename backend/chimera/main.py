from enum import Enum
import msgDef
import can
from can.listener import Listener
import argparse

CAN_BMS_ID = 0xAA

class CAN_BRUSA_MSG_ID(Enum):
    NLG5_ERR = 0x614
    NLG5_TEMP = 0x613
    NLG5_ACT_I = 0x611
    NLG5_ACT_II = 0x612
    NLG5_ST = 0x610


class STATE(Enum):
    CHECK = 0
    IDLE = 1
    PRECHARGE = 2
    READY = 3
    CHARGE = 4
    C_DONE = 5
    ERROR = -1
    EXIT = -2


class BMS_MES_ID(Enum):
    CAN_OUT_CURRENT = 0x05
    CAN_OUT_PACK_VOLTS = 0x01
    CAN_OUT_PACK_TEMPS = 0x10
    CAN_OUT_WARNING = 0x09
    CAN_OUT_ERRORS = 0x08
    CAN_OUT_TS_ON = 0x03
    CAN_OUT_TS_OFF = 0x04


class E_CODE(Enum):
    BATTERY_TEMP = 0
    OVERCHARGE = 0
    CURRENT_DRAWN = 0


# Gives the position of things in can message's data segment
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


class NLG5_ACT_I_POS(Enum):
    NLG5_MC_ACT = 0
    NLG5_MV_ACT = 16
    NLG5_OV_ACT = 32
    NLG5_OC_ACT = 48


class NLG5_ACT_II_POS(Enum):
    NLG5_S_MC_M_CP = 0
    NLG5_S_MC_M_PI = 16
    NLG5_ABV = 24
    NLG5_AHC_EXT = 32
    NLG5_OC_BO = 48


class NLG5_TEMP_POS(Enum):
    NLG5_P_TMP = 0
    NLG5_TMP_EXT1 = 16
    NLG5_TEMP_EXT2 = 32
    NLG5_TMP_EXT3 = 48


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


class VAL_NLG5_ST():
    lastUpdated = 0  # Last time it was updated in can timestamp
    values = []


class VAL_NLG5_ACT_I():
    lastUpdated = 0  # Last time it was updated in can timestamp
    NLG5_MC_ACT = 0
    NLG5_MV_ACT = 0
    NLG5_OV_ACT = 0
    NLG5_OC_ACT = 0


class VAL_NLG5_ACT_II():
    lastUpdated = 0  # Last time it was updated in can timestamp
    values = []


class VAL_NLG5_TEMP():
    lastUpdated = 0  # Last time it was updated in can timestamp
    values = []


class VAL_NLG5_ERR():
    lastUpdated = 0  # Last time it was updated in can timestamp
    values = []


class CanListener(Listener):
    newBMSMessage = False
    newBRUSAMessage = False
    brusa_err = False
    brusa_err_str_list = []
    bms_err = False
    bms_stat = -1
    brusa_connected = False

    act_NLG5_ST = VAL_NLG5_ST()
    act_NLG5_ACT_I = VAL_NLG5_ACT_I()
    act_NLG5_ERR = VAL_NLG5_ERR()

    msgTypeBMS = {
        BMS_MES_ID.CAN_OUT_PACK_VOLTS: setVolts,
        BMS_MES_ID.CAN_OUT_TS_ON: setTS,
        BMS_MES_ID.CAN_OUT_TS_OFF: setTS,
        BMS_MES_ID.CAN_OUT_CURRENT: setCurrent,
        BMS_MES_ID.CAN_OUT_ERRORS: setError,
        BMS_MES_ID.CAN_OUT_WARNING: setWarning,
        BMS_MES_ID.CAN_OUT_PACK_TEMPS: setPackTemp
    }

    doMsg = {
        CAN_BMS_ID: self.serveBMSMessage,
        CAN_BRUSA_MSG_ID.NLG5_ST: self.doNLG5_ST,
        CAN_BRUSA_MSG_ID.NLG5_ACT_I: doNLG5_ACT_I,
        CAN_BRUSA_MSG_ID.NLG5_ACT_II: doNLG5_ACT_II,
        CAN_BRUSA_MSG_ID.NLG5_ERR: doNLG5_ERR,
        CAN_BRUSA_MSG_ID.NLG5_TEMP: doNLG5_TEMP
    }

    def __init__(self):
        pass

    def on_message_received(self, msg):
        doMsg.get(msg.arbitration_id)(msg)

    def serveBMSMessage(self, msg):
        self.newBMSMessage = True
        self.msgTypeBMS.get(msg.data[0])(msg)

    def doNLG5_ST(self, msg):
        act_NLG5_ST.values = msg.data

    def doNLG5_ACT_I(self, msg):
        # Manca da trasformare i valori in bit in valori decimali
        act_NLG5_ACT_I.NLG5_MC_ACT = data[NLG5_ACT_I_POS.NLG5_MC_ACT]

    def doNLG5_ERR(self, msg):
        self.act_NLG5_ERR.values = msg.data
        c = -1
        for i in self.act_NLG5_ERR.values:
            c += 1
            if i == 1:
                self.brusa_err = 1
                self.brusa_err_str_list.append(NLG5_ERR_DEF[c])


PORK_CONNECTED = False
BRUSA_CONNECTED = False
act_stat = STATE.CHECK
last_err = 0

canbus = can.interface.Bus()
canRead = CanListener()


def canInit():
    try:
        canbus = can.interface.Bus(interface="socketcan", channel="can0")
        notif = can.Notifier(bus, [canRead])  # links the bus with the listener
    except(ValueError):
        print("Can channel not recognized")
        return False
    except(can.CanError):
        print("Can Error")
        return False
    except(NotImplementedError):
        print("Can interface not recognized")
        return False


def canSend(msg_id, data):
    msg = can.Message(arbitration_id=msg_id, data=data)  # doesn't check the msg before sending it
    try:
        canbus.send(msg)
        # print("Message sent on {}".format(canbus.channel_info))
        return True
    except can.CanError:
        print("Can Error: Message not sent")
        raise can.CanError


def isPorkConnected():
    # canSend(BMS_HV, TS_STATUS_REQ)
    if (canRead.bms_stat) != -1:
        return True
    else:
        return False


def isBrusaConnected():
    if canRead.brusa_connected:
        return True
    else:
        return False


def doCheck():
    PORK_CONNECTED = isPorkConnected()
    BRUSA_CONNECTED = isBrusaConnected()

    if PORK_CONNECTED and BRUSA_CONNECTED:
        return STATE.IDLE
    else:
        return STATE.CHECK


def doIdle():
    a = input("Type y to start precharge")
    if a == "y":
        return STATE.PRECHARGE
    else:
        return STATE.IDLE


def doPreCharge():
    # ask pork to do precharge
    # Send req to bms "TS_ON"
    # If response of HV_STATUS = TS_ON ok

    PRECHARGE_DONE = False

    if (canRead.newMessage):
        if (canRead.bms_stat == TS_ON):
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
    pass


def doExit():
    exit(0)


doState = {
    STATE.CHECK: doCheck(),
    STATE.IDLE: doIdle(),
    STATE.PRECHARGE: doPreCharge(),
    STATE.READY: doReady(),
    STATE.CHARGE: doCharge(),
    STATE.C_DONE: doC_done(),
    STATE.ERROR: doError(),
    STATE.EXIT: doExit()
}


def __main__():
    while (1):
        next_stat = doState.get(STATE.CHECK)
        if next_stat == STATE.EXIT:
            return
        act_stat = next_stat

# __main__()

