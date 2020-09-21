
from enum import Enum

class STATE(Enum):
    CHECK = 0
    READY = 1
    CHARGE = 2
    C_DONE = 3
    ERROR = -1
    UNSAFE = -2
    EXIT = -3

class E_CODE(Enum):
    BATTERY_TEMP = 0
    OVERCHARGE = 0
    CURRENT_DRAWN = 0

act_stat = STATE.CHECK
last_err = 0

def doCheck():
    return "asd"
    pass

def doCharge():
    pass

def doError():
    pass

def doUnsafe():
    pass

doState = {
    STATE.CHECK : doCheck(),
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
