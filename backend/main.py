
from enum import Enum

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
act_stat = STATE.CHECK
last_err = 0

def doCheck():
    #Checks pork attached
    PORK_CONNECTED = True

    if PORK_CONNECTED:
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
    #ask pork to do precharge
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
    CHARGE_COMPLETE = True
    if CHARGE_COMPLETE:
        return STATE.C_DONE
    else:
        return STATE.CHARGE

def doC_done():
    #User decide wether charge again, going idle, or charge again
    pass

def doError():
    pass

def doUnsafe():
    pass

def doExit():
    return STATE.EXIT

doState = {
    STATE.CHECK : doCheck(),
    STATE.IDLE : doIdle(),
    STATE.PRECHARGE : doPreCharge(),
    STATE.READY : doReady(),
    STATE.CHARGE : doCharge(),
    STATE.C_DONE : doC_done(),
    STATE.ERROR : doError(),
    STATE.UNSAFE : doUnsafe(),
    STATE.EXIT : doExit()
}

def __main__():
    while(1):
        next_stat = doState.get(STATE.CHECK)
        if(next_stat == STATE.EXIT):
            return
        act_stat = next_stat

#__main__()
