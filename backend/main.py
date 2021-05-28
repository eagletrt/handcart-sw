"""@package Handcart backend
For more info read the ../../doc section, or contact matteo.bitussi@studenti.unitn.it
For test purposes, launch start-can.sh before launching this file

Notes:
    NLG5 - Stands for the BRUSA (also the charger)
    BMS (or BMS HV) - Stands for Battery Manage System (also the accumulator)
"""

import datetime
import can
from can.listener import Listener
import time
import threading
import queue
import flask
from flask import request, jsonify
import cantools

from can_cicd.naked_generator.Primary.py.Primary import *
from can_cicd.includes_generator.Primary.ids import *

brusa_dbc = cantools.database.load_file('NLG5_BRUSA.dbc')

FAST_CHARGE_AMPERE = 16
STANDARD_CHARGE_AMPERE = 6



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
    lastupdated = ""

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
        return not self.lastupdated == ""

    def doNLG5_ST(self, msg):
        """
        Processes a CAN Status message from Brusa
        :param msg: the Can message
        """
        self.lastupdated = msg.timestamp

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
        self.lastupdated = msg.timestamp
        self.act_NLG5_ACT_I = brusa_dbc.decode_message(msg.arbitration_id, msg.data)

    def doNLG5_ACT_II(self, msg):
        """
        Process a CAN ACT_II message from Brusa
        :param msg: the ACT_II can message
        """
        self.lastupdated = msg.timestamp
        self.act_NLG5_ACT_II = brusa_dbc.decode_message(msg.arbitration_id, msg.data)

    def doNLG5_TEMP(self, msg):
        """
        Process a CAN TEMP message from Brusa
        :param msg: the TEMP can message
        """
        self.lastupdated = msg.timestamp
        self.act_NLG5_TEMP = brusa_dbc.decode_message(msg.arbitration_id, msg.data)

    def doNLG5_ERR(self, msg):
        """
        Process a CAN ERR message from Brusa
        :param msg: the ERR can message
        """
        self.lastupdated = msg.timestamp
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
    lastupdated = ""

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
        return not self.lastupdated == ""

    def doHV_VOLTAGE(self, msg):
        """
        Processes th HV_VOLTAGE CAN message from BMS_HV
        :param msg: the HV_VOLTAGE CAN message
        """
        # someway somehow you have to extract:
        self.lastupdated = msg.timestamp

        self.act_pack_voltage = msg.data[0]
        self.all_voltage[self.lastupdated](msg.data[0])

        self.act_bus_voltage = msg.data[1]
        self.max_cell_voltage = msg.data[2]
        self.min_cell_voltage = msg.data[3]

    def doHV_CURRENT(self, msg):
        """
        Processes the HV_CURRENT CAN message from BMS_HV
        :param msg: the HV_CURRENT CAN message
        """
        self.lastupdated = msg.timestamp

        self.act_current = msg.data[0]
        self.all_current[self.lastupdated](msg.data[0])

    def doHV_TEMP(self, msg):
        """
        Processes the HV_TEMP CAN message from BMS_HV
        :param msg: the HV_TEMP CAN message
        """
        self.lastupdated = msg.timestamp
        self.act_average_temp = msg.data[0]
        self.all_temp[self.lastupdated](msg.data[0])

        self.min_temp = msg.data[1]
        self.max_temp = msg.data[2]

    def doHV_ERRORS(self, msg):
        """
        Processes the HV_ERRORS CAN message from BMS_HV
        :param msg: the HV_ERRORS CAN message
        """
        self.lastupdated = msg.timestamp
        pass

    def doHV_STATUS(self, msg):
        """
        Processes the HV_STATUS CAN message from BMS_HV
        :param msg: the HV_STATUS CAN message
        """
        self.lastupdated = msg.timestamp
        self.status = TsStatus.deserialize(msg.data)

    def do_CHG_SET_POWER(self, msg):
        """
        Processes the CHG_SET_POWER CAN message from BMS_HV
        :param msg: the CHG_SET_POWER CAN message
        """
        self.lastupdated = msg.timestamp
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
        self.lastupdated = msg.timestamp
        self.status = ChgStatus.deserialize(msg.data).status


class CanListener:
    """
    That listener is called wether a can message arrives, then
    based on the msg ID, processes it, and save on itself the msg info.
    This class also stores all the data recived from the devices
    """
    FSM_stat = -1  # The actual state of the FSM (mirror the main variable)
    FSM_entered_stat = "" # The moment in time the FSM has entered that state
    fast_charge = False

    can_err = False

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
        # BMS_HV
        ID_HV_VOLTAGE: bms_hv.doHV_VOLTAGE,
        ID_HV_CURRENT: bms_hv.doHV_CURRENT,
        ID_HV_ERRORS: bms_hv.doHV_ERRORS,
        ID_HV_TEMP: bms_hv.doHV_TEMP,
        ID_TS_STATUS: bms_hv.doHV_STATUS,
        ID_SET_CHG_POWER: bms_hv.do_CHG_SET_POWER,
        ID_CHG_STATUS: bms_hv.doCHG_STATUS
    }

    # Function called when a new message arrive, maps it to
    # relative function based on ID
    def on_message_received(self, msg):
        """
        This function is called whether a new message arrives, it then
        calls the corresponding function to process the message
        :param msg: the incoming message
        """
        print(msg)
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
        rx_can_queue.put(msg)


# FSM vars
canread = CanListener()  # Access it ONLY with the FSM
precharge_asked = False
precharge_done = False

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


def canSend(bus, msg_id, data):
    """
    Function to send a CAN message
    :param bus: the canbus object
    :param msg_id: the msg id
    :param data: the msg content
    """
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
    act_com = {"com-type": "", "value": False}  # Init
    if not com_queue.empty():
        act_com = com_queue.get()

    if act_com['com-type'] == "precharge" and act_com['value'] == True:
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
        ts_on_msg = can.Message(arbitration_id=ID_SET_TS_STATUS, data=[SetTsStatus.serialize(Ts_Status_Set.ON)])

        tx_can_queue.put(ts_on_msg)
        precharge_asked = True

    if canread.bms_hv.status == Ts_Status.ON:
        print("Precharge done, TS is on")
        precharge_done = True
        precharge_asked = False

    if precharge_done:
        return STATE.READY


def doReady():
    """
    Function that do the ready state of the state machine
    """
    if canread.bms_hv.status != Ts_Status.ON:
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


def doCharge():
    """
    Function that do the charge state of the state machine
    :return:
    """
    # canread has to forward charging msgs from bms to brusa
    global can_forward_enabled

    # Set Brusa's PON to 12v (relay)

    with forward_lock:
        can_forward_enabled = True

    CHARGE_COMPLETE = False

    if canread.bms_hv.chg_status == Status.CHG_OFF:
        CHARGE_COMPLETE = True
    # Check if voltage is cutoff voltage

    if CHARGE_COMPLETE:
        return STATE.C_DONE
    else:
        return STATE.CHARGE


def doC_done():
    """
    Function that do the charge done of the state machine
    :return:
    """
    # User decide wether charge again or going idle

    if not canread.bms_hv.chg_status == Status.CHG_OFF:
        # Req "CHG_OFF" to bms
        data = SetChgStatus.serialize(Status.CHG_OFF)
        msg = can.Message(arbitration_id=ID_SET_CHG_STATUS, data=data)
        tx_can_queue.put(msg)

    return STATE.C_DONE


def doError():
    """
    Do the error state of the state machine
    """
    global can_forward_enabled

    with forward_lock:
        can_forward_enabled = False


    # Send to BMS stacca stacca
    if not canread.bms_hv.status == Ts_Status.OFF.value:
        staccastacca()

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
    sts = SetTsStatus()
    data = sts.serialize(Ts_Status_Set.OFF.value)
    msg = can.Message(arbitration_id=ID_SET_TS_STATUS, data=data)
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
    if not com_queue.empty():
        act_com = com_queue.get()
        if act_com['com_type'] == 'fast-charge':
            canread.fast_charge = act_com['value']


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

        if act_stat != STATE.CHECK and (not canread.bms_hv.isConnected() or not canread.brusa.isConnected()):
            staccastacca()
            next_stat = doState.get(STATE.CHECK)
            continue

        # Checks errors
        if canread.brusa.error or canread.bms_hv.error or canread.can_err:
            next_stat = doState.get(STATE.ERROR)()
        else:
            next_stat = doState.get(act_stat)()

        if next_stat == STATE.EXIT:
            print("Exiting")
            return

        checkCommands()

        canread.FSM_stat = act_stat
        if act_stat != next_stat:
            canread.FSM_entered_stat = datetime.datetime.now().isoformat()
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
        # time.sleep(1)

        while not tx_can_queue.empty():
            act = tx_can_queue.get()
            canSend(canbus, act.arbitration_id, act.data)

        # Handles the brusa ctl messages
        with forward_lock:
            if time.time() - last_brusa_ctl_sent > 0.1:  # every tot time send a message
                NLG5_CTL = brusa_dbc.get_message_by_name('NLG5_CTL')
                if can_forward_enabled:
                    with lock:
                        if 0 < shared_data.bms_hv.req_chg_voltage <= 500 and shared_data.bms_hv.req_chg_current != 0:
                            if shared_data.fast_charge:
                                ampere = FAST_CHARGE_AMPERE
                            else:
                                ampere = STANDARD_CHARGE_AMPERE
                            data = NLG5_CTL.encode({
                                'NLG5_C_C_EN': 1,
                                'NLG5_C_C_EL': 0,
                                'NLG5_C_CP_V': 0,
                                'NLG5_C_MR': 0,
                                'NLG5_MC_MAX': ampere,
                                'NLG5_OV_COM': shared_data.bms_hv.req_chg_voltage,
                                'NLG5_OC_COM': shared_data.bms_hv.req_chg_current
                            })
                else:
                    data = NLG5_CTL.encode({
                        'NLG5_C_C_EN': 0,
                        'NLG5_C_C_EL': 0,
                        'NLG5_C_CP_V': 0,
                        'NLG5_C_MR': 0,
                        'NLG5_MC_MAX': 0,
                        'NLG5_OV_COM': 0,
                        'NLG5_OC_COM': 0
                    })
                NLG5_CTL_message = can.Message(arbitration_id=NLG5_CTL.frame_id, data=data)
                tx_can_queue.put(NLG5_CTL_message)
                last_brusa_ctl_sent = time.time()


def thread_3_WEB():
    """
    The webserver thread that runs the server serving the RESFUL requests
    :return:
    """
    app = flask.Flask(__name__)

    app.config["DEBUG"] = True

    @app.route('/', methods=['GET'])
    def home():
        return "Hello World"  # flask.render_template("index.html")

    @app.route('/handcart/status/', methods=['GET'])
    def get_hc_status():
        with lock:
            data = {
                "timestamp": datetime.datetime.now().isoformat(),
                "state": str(shared_data.FSM_stat),
                "entered": shared_data.FSM_entered_stat
            }
            resp = jsonify(data)
            resp.status_code = 200
            return resp

    @app.route('/bms-hv/status/', methods=['GET'])
    def get_bms_hv_status():
        with lock:
            if shared_data.bms_hv.isConnected():
                res = {"timestamp": shared_data.bms_hv.lastupdated,
                       "status": shared_data.bms_hv.status}
                res = jsonify(res)
            else:
                res = jsonify("not connected")
                res.status_code = 400
        return res

    @app.route('/bms-hv/errors/', methods=['GET'])
    def get_bms_hv_errors():
        with lock:
            if shared_data.bms_hv.isConnected():
                error_list = shared_data.bms_hv.error_str

                res = {"timestamp": shared_data.brusa.lastupdated,
                       "status": error_list}
                res = jsonify(res)
            else:
                res = jsonify("not connected")
                res.status_code = 400
        return res

    @app.route('/brusa/status/', methods=['GET'])
    def get_brusa_status():
        with lock:
            if shared_data.brusa.isConnected():
                status_list = shared_data.brusa.act_NLG5_ST_srt

                res = {"timestamp": shared_data.brusa.lastupdated,
                       "status": status_list}
                res = jsonify(res)
            else:
                res = jsonify("not connected")
                res.status_code = 400
        return res

    @app.route('/brusa/errors/', methods=['GET'])
    def get_brusa_errors():
        with lock:
            if not shared_data.brusa.isConnected():
                res = jsonify("not connected")
                res.status_code = 400
                return res

            errorList = shared_data.brusa.act_NLG5_ERR_str
            res = {"timestamp": time.time(), "errors": errorList}
            return jsonify(res)



    @app.route('/command/setting/', methods=['POST'])
    def recv_command_setting():
        print(request.get_json())
        j = request.get_json()

        command = jsonify(j)
        com_queue.put(command)

        resp = jsonify(success=True)
        return resp

    @app.route('/command/action/', methods=['POST'])
    def recv_command_action():
        print(request.get_json())
        j = request.get_json()

        command = jsonify(j)
        com_queue.put(command)

        resp = jsonify(success=True)
        return resp

    app.run(use_reloader=False)


# Usare le code tra FSM e CAN per invio e ricezione
# Processare i messaggi nella FSM e inoltrarli gia a posto

t1 = threading.Thread(target=thread_1_FSM, args=(lock,))
t2 = threading.Thread(target=thread_2_CAN, args=(lock,))
t3 = threading.Thread(target=thread_3_WEB, args=(lock,))

t1.start()
t2.start()
t3.start()


