import queue
import threading
import time

import can
from can import Listener

import common.accumulator.bms as bms
from common.charger.littlesic.LittleSIC import LittleSIC, ID_HYC_Ctrl, ID_HYC_Status, ID_HYC_Actual, \
    ID_HYC_Grid_Voltage, \
    ID_HYC_Maintenance2, ID_HYC_Temperature, ID_HYC_Version, ID_HYC_Error, ID_HYC_Warning, dbc_littlesic, \
    ID_HYC_Alive
from settings import *
from .can_classes import STATE
from .logging import tprint, P_TYPE


class CanListener:
    """
    That listener is called wether a can message arrives, then
    based on the msg ID, processes it, and save on itself the msg info.
    This class also stores all the data recived from the devices
    """
    FSM_stat: STATE = STATE.IDLE  # The actual state of the FSM (mirror the main variable)
    FSM_entered_stat = ""  # The moment in time the FSM has entered that state

    generic_error = False
    can_err = False
    target_v = ACC_DEFAULT_TARGET_V
    act_set_out_current = ACC_DEFAULT_CHG_CURRENT
    can_charger_charge_enabled = False

    charger = LittleSIC()
    bms_hv = bms.BMS_HV()

    feedbacks: list[float] = [0.0 for i in range(11)]

    # Maps the incoming can msgs to relative function
    doMsg = {
        # charger (littlesic)
        ID_HYC_Status: charger.do_HYC_Status,
        ID_HYC_Actual: charger.do_HYC_Actual,
        ID_HYC_Grid_Voltage: charger.do_HYC_Grid_Voltage,
        ID_HYC_Maintenance2: charger.do_HYC_Maintenance,
        ID_HYC_Temperature: charger.do_HYC_Temperature,
        ID_HYC_Version: charger.do_HYC_Version,
        ID_HYC_Error: charger.do_HYC_Error,
        ID_HYC_Warning: charger.do_HYC_Warnings,

        # TSAC mainboard (accumulator) on the primary bus
        primary_ID_TSAC_STATUS: bms_hv.doTSAC_STATUS,
        primary_ID_TSAC_MB_VOLTAGE: bms_hv.doTSAC_MB_VOLTAGE,
        primary_ID_TSAC_MB_CURRENT: bms_hv.doTSAC_MB_CURRENT,
        primary_ID_TSAC_MB_TEMP: bms_hv.doTSAC_MB_TEMP,
        primary_ID_TSAC_MB_ERROR: bms_hv.doTSAC_MB_ERROR,
        primary_ID_TSAC_MB_FEEDBACK: bms_hv.doTSAC_MB_FEEDBACK,
        primary_ID_TSAC_MB_VERSION: bms_hv.doTSAC_MB_VERSION,
    }
    # TSAC cellboards: one frame per board, the handler resolves the board from the id
    for _id in primary_ID_TSAC_CELLBOARD_VOLTAGE:
        doMsg[_id] = bms_hv.doTSAC_CELLBOARD_VOLTAGE
    for _id in primary_ID_TSAC_CELLBOARD_TEMP:
        doMsg[_id] = bms_hv.doTSAC_CELLBOARD_TEMP
    for _id in primary_ID_TSAC_CELLBOARD_BALANCING:
        doMsg[_id] = bms_hv.doTSAC_CELLBOARD_BALANCING
    for _id in primary_ID_TSAC_CELLBOARD_VERSION:
        doMsg[_id] = bms_hv.doTSAC_CELLBOARD_VERSION
    del _id

    # Function called when a new message arrive, maps it to
    # relative function based on ID
    def on_message_received(self, msg):
        """
        This function is called whether a new message arrives, it then
        calls the corresponding function to process the message
        """
        # print(f"[DEBUG] {msg}")
        handler = self.doMsg.get(msg.arbitration_id)
        if handler is None:
            return
        try:
            handler(msg)
        except Exception as e:
            tprint(f"dropping CAN id 0x{msg.arbitration_id:X} (len {len(msg.data)}): {e}", P_TYPE.ERROR)


def canSend(bus, msg_id, data, lock: threading.Lock, shared_data):
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
        # print("Can Error: Message not sent")
        # print(msg)
        with lock:
            shared_data.can_err = True
        # raise can.CanError


def canInit(listener):
    """
    Inits the canbus, connect to it, and links the canbus
    :param listener:
    :return:
    """
    try:
        bus = can.interface.Bus(interface="socketcan", channel=CAN_INTERFACE)
        # links the bus with the listener
        notif = can.Notifier(bus, [listener])

        return bus
    except ValueError:
        print("Can channel not recognized")
        # canread.can_err = True
        return False
    except can.CanError:
        # print("Can Error")
        # canread.can_err = True
        return False
    except NotImplementedError:
        print("Can interface not recognized")
        # canread.can_err = True
        return False


def thread_2_CAN(shared_data: CanListener,
                 rx_can_queue: queue.Queue,
                 tx_can_queue: queue.Queue,
                 forward_lock: threading.Lock,
                 lock: threading.Lock,
                 command_queue: queue.Queue):
    """
    Thread managing the can connection, getting and sending messages
    """

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

    can_r_w = Can_rx_listener()
    canbus = canInit(can_r_w)
    something_attacched_to_bus = False

    # Charger periodic control message
    msg_charger_ctrl = can.Message(
        arbitration_id=ID_HYC_Ctrl,
        data=[0x00],
        is_extended_id=False
    )

    m_charger_alive = dbc_littlesic.get_message_by_name("HYC_Alive")
    enc_data = m_charger_alive.encode(
        {
            "AliveCnt": 0,
            "fanMin": 0,
            "fanMax": 100
        }
    )

    msg_charger_alive = can.Message(
        arbitration_id=ID_HYC_Alive,
        data=enc_data,
        is_extended_id=False
    )

    m_charger_target = dbc_littlesic.get_message_by_name("HYC_Target")
    enc_data = m_charger_target.encode(
        {
            "uTarget": 0,
            "iTarget": 0
        }
    )

    msg_charger_target = can.Message(
        arbitration_id=m_charger_target.frame_id,
        data=enc_data,
        is_extended_id=False
    )

    def modify_callback_charger_ctrl(msg: Message):
        with forward_lock:
            if shared_data.charger.reset_asked:
                msg.data[0] = 0x01
                # task_charger_ctrl.modify_data(msg_charger_ctrl)
                return

            if shared_data.can_charger_charge_enabled:
                if msg_charger_ctrl.data[0] != 0x02:
                    msg.data[0] = 0x02  # Start charge command
                    # task_charger_ctrl.modify_data(msg_charger_ctrl)
            else:
                if msg_charger_ctrl.data[0] != 0x00:
                    msg.data[0] = 0x00  # Stop charge command
                    # task_charger_ctrl.modify_data(msg_charger_ctrl)

    def modify_callback_charger_target(msg: Message):
        with forward_lock:
            m_charger_target = dbc_littlesic.get_message_by_name("HYC_Target")

            # Check voltage command
            if ACC_MIN_TARGET_V > shared_data.target_v > ACC_MAX_TARGET_V:
                shared_data.can_err = True
                return

            # Check current command
            if ACC_MIN_CHG_CURRENT > shared_data.act_set_out_current > ACC_MAX_CHG_CURRENT:
                shared_data.can_err = True
                return

            enc_data = m_charger_target.encode(
                {
                    "uTarget": shared_data.target_v,
                    "iTarget": shared_data.act_set_out_current
                }
            )
            msg.data = enc_data

    def modify_callback_charger_alive(msg: Message):
        with forward_lock:
            enc_data = m_charger_alive.encode(
                {
                    "AliveCnt": 0,
                    "fanMin": shared_data.charger.set_min_fan_speed,
                    "fanMax": shared_data.charger.set_max_fan_speed
                }
            )

            msg.data = enc_data

    def start_periodic_sends():
        task_charger_ctrl = canbus.send_periodic(
            msg_charger_ctrl, 0.01, modifier_callback=modify_callback_charger_ctrl)
        task_charger_target = canbus.send_periodic(
            msg_charger_target, 0.5, modifier_callback=modify_callback_charger_target
        )
        task_charger_alive = canbus.send_periodic(
            msg_charger_alive, .1, modifier_callback=modify_callback_charger_alive
        )

        if not isinstance(task_charger_ctrl, can.ModifiableCyclicTaskABC):
            shared_data.can_err = True
            tprint("The can interface doesn't seem to support modification", P_TYPE.ERROR)
            return

    with lock:
        if canbus == False:
            shared_data.can_err = True

    while 1:
        # This is just to avoid transmitting when there are no devices connected, to avoid filling the buffer
        if shared_data.FSM_stat == STATE.CHECK:
            if (not shared_data.bms_hv.isConnected()) and (not shared_data.charger.is_connected()):
                if something_attacched_to_bus is True:
                    canbus.stop_all_periodic_tasks()
                    something_attacched_to_bus = False
            else:
                if something_attacched_to_bus is False:
                    start_periodic_sends()
                    something_attacched_to_bus = True

        time.sleep(0.001)
        while not tx_can_queue.empty():
            act = tx_can_queue.get()
            if something_attacched_to_bus:
                canSend(canbus, act.arbitration_id, act.data, lock, shared_data)
