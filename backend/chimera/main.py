from enum import Enum
import msgDef
import can
from can.listener import Listener

CAN_BMS_ID = 0xAA


class BRUSA_CAN_MSG_ID(Enum):
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


class CanListener(Listener):
    newMessage = False
    brusa_err = False
    bms_err = False
    bms_stat = -1
    brusa_connected = False

    msgType = {
        BMS_MES_ID.CAN_OUT_PACK_VOLTS: setVolts(),
        BMS_MES_ID.CAN_OUT_TS_ON: setTS(),
        BMS_MES_ID.CAN_OUT_TS_OFF: setTS(),
        BMS_MES_ID.CAN_OUT_CURRENT: setCurrent(),
        BMS_MES_ID.CAN_OUT_ERRORS: setError(),
        BMS_MES_ID.CAN_OUT_WARNING: setWarning(),
        BMS_MES_ID.CAN_OUT_PACK_TEMPS: setPackTemp()
    }

    def __init__(self):
        pass

    def on_message_received(self, msg):
        if (msg.arbitration_id == CAN_BMS_ID):
            self.newMessage = True
            self.msgType.get(msg.data[0])


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


def doCheck():
    # Checks pork attached

    PORK_CONNECTED = True  # Come so quando il porco è connesso?
    BRUSA_CONNECTED = True

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
