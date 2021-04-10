"""@package Handcart backend
For more info read the ../../doc section, or contact matteo.bitussi@studenti.unitn.it
For test purposes, launch start-can.sh before launching this file

Notes:
    NLG5 - Stands for the BRUSA (also the charger)
    BMS (or BMS HV) - Stands for Battery Manage System (also the accumulator)
"""

from enum import Enum
import msgDef
import can
from can.listener import Listener
import time
import threading
import queue
import flask
from flask import request

CAN_BMS_ID = 170  # 0xAA

BYTE_MASK = [
    0b10000000,
    0b01000000,
    0b00100000,
    0b00010000,
    0b00001000,
    0b00000100,
    0b00000010,
    0b00000001
]


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


# ID of BRUSA's can messages
class CAN_BRUSA_MSG_ID(Enum):
    NLG5_ERR = 0x614
    NLG5_TEMP = 0x613
    NLG5_ACT_I = 0x611
    NLG5_ACT_II = 0x612
    NLG5_ST = 0x610
    NLG5_CTL = 0x618


# ID's of BMS can messages
class BMS_HV_MSG_ID(Enum):
    HV_VOLTAGE = 0
    HV_CURRENT = 0
    HV_TEMP = 0
    HV_STATUS = 0
    HV_ERROR = 0
    CHG_SET_CURRENT = 0
    CHG_SET_VOLTAGE = 0
    CHG_STATE = 0


# The possible states of BMS
class BMS_HV_STATE(Enum):
    TS_OFF = 0
    PRECHARGE = 0
    TS_ON = 0
    FATAL = 0


class BMS_HV_CHG_STATE(Enum):
    CHG_OFF = 0
    CHG_CC = 0
    CHG_CV = 0


# ids of handcart messages exiting
class HANDCART_MSG_ID(Enum):
    CHG_STATE_REQ = 0
    CHG_SETTINGS = 0
    TS_STATUS_REQ = 0


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


class BRUSA:
    lastupdated = 0
    connected = False

    # ST
    act_NLG5_ST_values = []

    # ACT_1
    NLG5_MC_ACT = 0
    NLG5_MV_ACT = 0
    NLG5_OV_ACT = 0
    NLG5_OC_ACT = 0

    # ACT_2
    NLG5_S_MC_M_CP = 0  # 16 bit
    NLG5_S_MC_M_PI = 0  # 8 bit
    NLG5_ABV = 0  # 8 bit
    NLG5_AHC_EXT = 0  # 16 bit
    NLG5_OC_BO = 0  # 16 bit

    # TEMP
    NLG5_P_TEMP = 0

    # ERR
    error = False
    act_NLG5_ERR_values = []
    act_NLG5_ERR_str = []

    # Handles Brusa CAN status messages
    def doNLG5_ST(self, msg):
        self.brusa_connected = True

        self.lastupdated = msg.timestamp
        pos = 0
        for i in range(4):
            for mask in BYTE_MASK:
                res = msg.data[i] & mask
                if res > 0:
                    self.act_NLG5_ST_values[pos] = True
                    # print("[ST] " + msgDef.NLG5_ST_DEF[pos])
                pos += 1

        if self.act_NLG5_ST_values[NLG5_ST_POS.NLG5_S_ERR.value]:
            self.error = True

    def doNLG5_ACT_I(self, msg):
        # Manca da trasformare i valori in bit in valori decimali
        self.lastupdated = msg.timestamp
        self.NLG5_MC_ACT = int.from_bytes(
            msg.data[:2], byteorder='big', signed=False) * 0.01
        self.NLG5_MV_ACT = int.from_bytes(
            msg.data[2:4], byteorder='big', signed=False) * 0.1
        self.NLG5_OV_ACT = int.from_bytes(
            msg.data[4:6], byteorder='big', signed=False) * 0.1
        self.NLG5_OC_ACT = int.from_bytes(
            msg.data[6:8], byteorder='big', signed=True) * 0.01

    def doNLG5_ACT_II(self, msg):
        self.lastupdated = msg.timestamp

        self.NLG5_S_MC_M_CP = int.from_bytes(
            msg.data[:2], byteorder='big', signed=False) * 0.1
        self.NLG5_S_MC_M_PI = int.from_bytes(
            msg.data[2:3], byteorder='big', signed=False) * 0.1
        self.NLG5_ABV = int.from_bytes(
            msg.data[3:4], byteorder='big', signed=False) * 0.1
        self.NLG5_AHC_EXT = int.from_bytes(
            msg.data[4:6], byteorder='big', signed=True) * 0.01
        self.NLG5_OC_BO = int.from_bytes(
            msg.data[6:8], byteorder='big', signed=False) * 0.01

    def doNLG5_TEMP(self, msg):
        self.lastupdated = msg.timestamp

        self.NLG5_P_TEMP = int.from_bytes(
            msg.data[:2], byteorder='big', signed=True) * 0.1

    # Handles brusa CAN error's message
    def doNLG5_ERR(self, msg):
        self.lastupdated = msg.timestamp

        pos = 0
        for i in range(5):
            for mask in BYTE_MASK:
                if pos != 30 and pos != 31:
                    res = msg.data[i] & mask
                    if res > 0:
                        self.error = True
                        self.act_NLG5_ERR_values[pos] = True
                    pos += 1

        if self.error:
            for i in range(40):
                if self.act_NLG5_ERR_values[i]:
                    self.act_NLG5_ERR_str.append(msgDef.NLG5_ERR_DEF[i])

    def __init__(self):
        for i in range(32):
            self.act_NLG5_ST_values.append(False)
        for i in range(40):
            self.act_NLG5_ERR_values.append(False)


class BMS_HV:
    lastupdated = 0
    connected = False

    all_voltage = {}
    all_current = {}
    all_temp = {}

    act_pack_voltage = -1
    act_bus_voltage = -1
    act_current = -1
    max_cell_voltage = -1
    min_cell_voltage = -1
    error = 0
    error_str = ""
    status = -1
    chg_status = -1
    req_current = -1
    req_voltage = -1
    act_average_temp = -1
    min_temp = -1
    max_temp = -1

    def doHV_VOLTAGE(self, msg):
        # someway somehow you have to extract:
        self.lastupdated = msg.timestamp

        self.act_pack_voltage = msg.data[0]
        self.all_voltage[self.lastupdated](msg.data[0])

        self.act_bus_voltage = msg.data[1]
        self.max_cell_voltage = msg.data[2]
        self.min_cell_voltage = msg.data[3]

    def doHV_CURRENT(self, msg):
        self.lastupdated = msg.timestamp

        self.act_current = msg.data[0]
        self.all_current[self.lastupdated](msg.data[0])

    def doHV_TEMP(self, msg):
        self.lastupdated = msg.timestamp
        self.act_average_temp = msg.data[0]
        self.all_temp[self.lastupdated](msg.data[0])

        self.min_temp = msg.data[1]
        self.max_temp = msg.data[2]

    def doHV_ERROR(self, msg):
        pass

    def doHV_STATUS(self, msg):
        pass

    def do_CHG_SET_CURRENT(self, msg):
        pass

    def doCHG_SET_VOLTAGE(self, msg):
        pass

    def doCHG_STATE(self, msg):
        pass


# That listener is called wether a can message arrives, then
# based on the msg ID, processes it, and save on itself the msg info
# It also contains all the useful info to be used in threads
class CanListener:
    FSM_stat = -1  # useful value
    fast_charge = False

    can_err = False

    brusa = BRUSA()
    bms_hv = BMS_HV()

    # Maps the can msg to relative function
    doMsg = {
        # brusa
        CAN_BRUSA_MSG_ID.NLG5_ST.value: brusa.doNLG5_ST,
        CAN_BRUSA_MSG_ID.NLG5_ACT_I.value: brusa.doNLG5_ACT_I,
        CAN_BRUSA_MSG_ID.NLG5_ACT_II.value: brusa.doNLG5_ACT_II,
        CAN_BRUSA_MSG_ID.NLG5_ERR.value: brusa.doNLG5_ERR,
        CAN_BRUSA_MSG_ID.NLG5_TEMP.value: brusa.doNLG5_TEMP,
        # BMS_HV
        BMS_HV_MSG_ID.HV_VOLTAGE.value: bms_hv.doHV_VOLTAGE,
        BMS_HV_MSG_ID.HV_CURRENT.value: bms_hv.doHV_CURRENT,
        BMS_HV_MSG_ID.HV_ERROR.value: bms_hv.doHV_ERROR,
        BMS_HV_MSG_ID.HV_TEMP.value: bms_hv.doHV_TEMP,
        BMS_HV_MSG_ID.HV_STATUS.value: bms_hv.doHV_STATUS,
        BMS_HV_MSG_ID.CHG_SET_CURRENT.value: bms_hv.do_CHG_SET_CURRENT,
        BMS_HV_MSG_ID.CHG_SET_VOLTAGE.value: bms_hv.doCHG_SET_VOLTAGE,
        BMS_HV_MSG_ID.CHG_STATE.value: bms_hv.doCHG_STATE
    }

    # Function called when a new message arrive, maps it to
    # relative function based on ID
    def on_message_received(self, msg):
        print(msg)
        if self.doMsg.get(msg.arbitration_id) is not None:
            self.doMsg.get(msg.arbitration_id)(msg)


class Can_rx_listener(Listener):
    volt_chg_req = 0
    current_chg_req = 0

    def __init__(self):
        pass

    def on_message_received(self, msg):
        rx_can_queue.put(msg)
        with forward_lock:
            if can_forward_enabled and (
                    msg.arbitration_id == BMS_HV_MSG_ID.CHG_SET_VOLTAGE or msg.arbitration_id == BMS_HV_MSG_ID.CHG_SET_CURRENT):
                tx_can_queue.put(self.canChgMsgBmstoBrusa(msg))

    # creates a message for brusa from bms chg request one
    def canChgMsgBmstoBrusa(self, bms_msg):
        if bms_msg.arbitration_id == BMS_HV_MSG_ID.CHG_SET_VOLTAGE:
            self.volt_chg_req = bms_msg.data[0]  # to be defined
        if bms_msg.arbitration_id == BMS_HV_MSG_ID.CHG_SET_CURRENT:
            self.current_chg_req = bms_msg.data[0]  # to be defined
        if self.volt_chg_req != 0 and self.current_chg_req != 0:
            return can.Message(arbitration_id=CAN_BRUSA_MSG_ID.NLG5_CTL, data=[])  # to be properly defined


class DataHolder:
    FSM_state = -1
    brusa_err = False
    brusa_err_str_list = []  # the list of errors in string format
    bms_err = False
    bms_stat = -1
    brusa_connected = False
    bms_connected = False
    bms_err_str = ""
    can_err = False
    act_NLG5_ST = None


PORK_CONNECTED = False
BRUSA_CONNECTED = False
canread = CanListener()  # Access it ONLY with the FSM
can_forward_enabled = False

# IPC
shared_data = canread
rx_can_queue = queue.Queue()
tx_can_queue = queue.Queue()
com_queue = queue.Queue()
lock = threading.Lock()
forward_lock = threading.Lock()

# FSM vars
precharge_asked = False

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
        with(lock):
            shared_data.can_err = True
        raise can.CanError


# Do state CHECK
def doCheck():
    if canread.bms_hv.connected and canread.brusa.connected:
        return STATE.IDLE
    else:
        return STATE.CHECK


# Do state IDLE
def doIdle():
    act_com = {"com-type": "", "value": False}  # Init
    if not com_queue.empty():
        act_com = com_queue.get()

    if act_com['com-type'] == "precharge" and act_com['value'] == True:
        return STATE.PRECHARGE
    else:
        return STATE.IDLE


# Do state PRECHARGE
def doPreCharge():
    # ask pork to do precharge
    # Send req to bms "TS_ON"
    PRECHARGE_DONE = False
    global precharge_asked

    if not precharge_asked:
        ts_on_msg = can.Message(arbitration_id=HANDCART_MSG_ID.TS_STATUS_REQ, data=[BMS_HV_STATE.TS_ON])
        tx_can_queue.put(ts_on_msg)
        precharge_asked = True

    if canread.bms_hv.status == BMS_HV_STATE.TS_ON:
        print("Precharge done, TS is on")
        PRECHARGE_DONE = True
        precharge_asked = False;

    if PRECHARGE_DONE:
        return STATE.READY


# Do state READY
def doReady():
    if canread.bms_hv.status != BMS_HV_STATE.TS_ON:
        print("BMS_HV is not in TS_ON, going back idle")
        # note that errors are already managed in mainloop
        return STATE.IDLE

    act_com = {"com-type": "", "value": False}  # Init
    if not com_queue.empty():
        act_com = com_queue.get()

        if act_com['com-type'] == "charge" and act_com['value'] == True:
            return STATE.CHARGE
        else:
            com_queue.put(act_com)

    else:
        return STATE.READY


# Do state CHARGE
def doCharge():
    # canread has to forward charging msgs from bms to brusa
    global can_forward_enabled

    with forward_lock:
        can_forward_enabled = True

    CHARGE_COMPLETE = False

    # Check if voltage is cutoff voltage

    if CHARGE_COMPLETE:
        return STATE.C_DONE
    else:
        return STATE.CHARGE


# Do state CHARGE_DONE
def doC_done():
    # User decide wether charge again, going idle, or charge again
    # Req "CHG_OFF" to bms
    pass


# Do state ERROR
def doError():
    global can_forward_enabled

    with forward_lock:
        can_forward_enabled = False

    # Send to BMS stacca stacca
    if not canread.bms_hv.error:
        msg = can.Message(arbitration_id=HANDCART_MSG_ID.TS_STATUS_REQ, data=[BMS_HV_STATE.TS_OFF])
        tx_can_queue.put(msg)

    if canread.brusa.error:
        for i in canread.brusa.act_NLG5_ERR_str:
            print("[ERR] " + i)
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


# Do state EXIT
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


# Backend Thread
def thread_1_FSM(lock):
    # Pls read the infos about the state machine
    global shared_data

    act_stat = STATE.CHECK
    print("Backend started")
    print("STATE: " + str(act_stat))

    while 1:
        time.sleep(1)
        # Controllo coda rec can messages, in caso li processo. Controllo anche errori
        if not rx_can_queue.empty():
            new_msg = rx_can_queue.get()
            canread.on_message_received(new_msg)

        # Checks errors
        if canread.brusa.error or canread.bms_hv.error or canread.can_err:
            next_stat = doState.get(STATE.ERROR)()
        else:
            next_stat = doState.get(act_stat)()

        if next_stat == STATE.EXIT:
            print("Exiting")
            return

        canread.FSM_stat = act_stat
        if act_stat != next_stat:
            print("STATE: " + str(next_stat))

        act_stat = next_stat

        with lock:
            shared_data = canread


# Can thread
def thread_2_CAN(lock):
    can_r_w = Can_rx_listener()
    canbus = canInit(can_r_w)

    while 1:
        time.sleep(1)

        while not tx_can_queue.empty():
            act = tx_can_queue.get()
            canSend(canbus, act.id, act.data)


# Webserver thread
def thread_3_WEB(lock):
    app = flask.Flask(__name__)

    app.config["DEBUG"] = True

    @app.route('/', methods=['GET'])
    def home():
        return "Hello World"  # flask.render_template("index.html")

    @app.route('/command/', methods=['POST'])
    def recv_command():
        print(request.json())

    @app.route('/brusa/status/', methods=['GET'])
    def get_brusa_status():
        with lock:
            res = '{"timestamp":"' + \
                  str(shared_data.act_NLG5_ST.lastUpdated) + '",\n'
            res += '"status":[ \n'
            c = 0
            for i in shared_data.act_NLG5_ST.values:
                if i == True:
                    if c != 0:
                        res += ','
                    res += '{"desc":"' + msgDef.NLG5_ST_DEF[c] + '"}\n'
                    c += 1
            res += ']}'
        return res

    @app.route('/brusa/errors/', methods=['GET'])
    def get_brusa_errors():
        with lock:
            res = '{"timestamp":"' + \
                  str(shared_data.act_NLG5_ST.lastUpdated) + '",\n'
            res += '"errors":[ \n'
            c = 0
            for i in shared_data.brusa_err_str_list:
                if c != 0:
                    res += ','
                res += '{"desc":"' + i + '"}\n'
                c += 1
            res += ']}'
        return res

    @app.route('/handcart/status/', methods=['GET'])
    def get_hc_status():
        data = [{
            "timestamp": "2020-12-01:ora",
            "status": str(canread.FSM_stat),
            "entered": "2020-12-01:ora"
        }]
        resp = jsonify(data)
        resp.status_code = 200
        return resp

    def send_status():
        with lock:
            return "{\"timestamp\": \"2020-12-01:ora\", \"state\": \"" + str(canread.FSM_stat) + "\"}"


    @app.route('/command/handcart/', methods=['POST'])
    def send_command():
        print(request.data)
        # if req['com-type'] == 'start-cgh' and req['value'] == 'true':
        #    print('okka')
        return "ok"

    app.run(use_reloader=False)


# Usare le code tra FSM e CAN per invio e ricezione
# Processare i messaggi nella FSM e inoltrarli gia a posto

t1 = threading.Thread(target=thread_1_FSM, args=(lock,))
t2 = threading.Thread(target=thread_2_CAN, args=(lock,))
t3 = threading.Thread(target=thread_3_WEB, args=(lock,))

t1.start()
t2.start()
t3.start()
