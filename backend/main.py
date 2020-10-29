from enum import Enum
import msgDef


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
    UNSAFE = -2
    EXIT = -3

class E_CODE(Enum):
    BATTERY_TEMP = 0
    OVERCHARGE = 0
    CURRENT_DRAWN = 0

PORK_CONNECTED = False
BRUSA_CONNECTED = False
act_stat = STATE.CHECK
last_err = 0


def doCheck():
    # Checks pork attached
    PORK_CONNECTED = True #Come so quando il porco è connesso?
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
    #Get volt and A from pork
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


def doUnsafe():
    pass


def doExit():
    return STATE.EXIT


doState = {
    STATE.CHECK: doCheck(),
    STATE.IDLE: doIdle(),
    STATE.PRECHARGE: doPreCharge(),
    STATE.READY: doReady(),
    STATE.CHARGE: doCharge(),
    STATE.C_DONE: doC_done(),
    STATE.ERROR: doError(),
    STATE.UNSAFE: doUnsafe(),
    STATE.EXIT: doExit()
}


def __main__():
    while (1):
        next_stat = doState.get(STATE.CHECK)
        if next_stat == STATE.EXIT:
            return
        act_stat = next_stat

# __main__()
