import queue
import threading
import time

import can
from can import Listener
from cantools.database import DecodeError

import common.accumulator.bms as bms
from common.charger.brusa.brusa import *
from settings import *
from .can_classes import STATE
from .logging import log_error, tprint


def do_HANDCART_SETTING_SET(msg: can.Message) -> list[dict[str, str | int]] | None:
    """
    Processes the HANDCART SETTING SET message from the telemetry and returns a list containing dict with the command
    for the FSM
    """
    if not ENABLE_TELEMETRY_SETTINGS:
        return

    try:
        data = dbc_primary.decode_message(msg.arbitration_id, msg.data)
    except DecodeError:
        raise can.CanError

    com_list = []
    com: dict[str, str | bool] = {}

    try:
        com['com-type'] = 'cutoff'
        com['value'] = int(data["target_voltage"])
        com_list.append(com)
        com = {}

        com['com-type'] = 'fan-override-set-status'
        fan_override_set_status = Toggle(int(data['fans_override'].value))
        com['value'] = True if fan_override_set_status == Toggle.ON else False
        com_list.append(com)
        com = {}

        com['com-type'] = 'fan-override-set-speed'
        com['value'] = int(data['fans_speed'] * 100)
        com_list.append(com)
        com = {}

        com['com-type'] = 'max-out-current'
        com['value'] = float(data['acc_charge_current'])
        com_list.append(com)
        com = {}

        com['com-type'] = 'max-in-current'
        com['value'] = int(data['grid_max_current'])
        com_list.append(com)

        req_status = HandcartStatus(int(data['status'].value))

        if req_status == HandcartStatus.BALANCING:
            com['com-type'] = 'balancing'
            com['value'] = True
        if req_status == HandcartStatus.IDLE:
            com['com-type'] = 'shutdown'
            com['value'] = True
        elif req_status == HandcartStatus.ERROR:
            # TODO ?
            pass
        elif req_status == HandcartStatus.READY:
            com['com-type'] = 'ready'
            com['value'] = True
        elif req_status == HandcartStatus.PRECHARGE:
            com['com-type'] = 'precharge'
            com['value'] = True
        elif req_status == HandcartStatus.CHARGE:
            com['com-type'] = 'charge'
            com['value'] = True
        elif req_status == HandcartStatus.CHARGE_DONE:
            com['com-type'] = 'charge'
            com['value'] = False

    except KeyError:
        raise can.CanError

    return com_list


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
    target_v = DEFAULT_TARGET_V_ACC
    act_set_out_current = DEFAULT_ACC_CHG_AMPERE
    act_set_in_current = DEFAULT_CHARGE_MAINS_AMPERE
    can_forward_enabled = False

    brusa = BRUSA()
    bms_hv = bms.BMS_HV()

    feedbacks: list[float] = [0.0 for i in range(11)]

    # Maps the incoming can msgs to relative function
    doMsg = {
        # brusa
        CAN_BRUSA_MSG_ID.NLG5_ST.value: brusa.doNLG5_ST,
        CAN_BRUSA_MSG_ID.NLG5_ACT_I.value: brusa.doNLG5_ACT_I,
        CAN_BRUSA_MSG_ID.NLG5_ACT_II.value: brusa.doNLG5_ACT_II,
        CAN_BRUSA_MSG_ID.NLG5_ERR.value: brusa.doNLG5_ERR,
        CAN_BRUSA_MSG_ID.NLG5_TEMP.value: brusa.doNLG5_TEMP,

        # BMS_HV Fenice
        primary_ID_HV_TOTAL_VOLTAGE: bms_hv.doHV_TOTAL_VOLTAGE,
        primary_ID_HV_CURRENT: bms_hv.doHV_CURRENT,
        primary_ID_HV_ENERGY: bms_hv.doHV_ENERGY,
        primary_ID_HV_ERRORS: bms_hv.doHV_ERRORS,
        primary_ID_HV_CELLS_TEMP_STATS: bms_hv.doHV_CELLS_TEMP_STATS,
        primary_ID_HV_STATUS: bms_hv.doHV_STATUS,
        primary_ID_HV_CELLS_VOLTAGE: bms_hv.doHV_CELLS_VOLTAGE,
        primary_ID_HV_CELLS_VOLTAGE_STATS: bms_hv.doHV_CELLS_VOLTAGE_STATS,
        primary_ID_HV_CELLS_TEMP: bms_hv.doHV_CELLS_TEMP,
        primary_ID_HV_BALANCING_STATUS: bms_hv.doHV_BALANCING_STATUS,
        primary_ID_HV_FANS_STATUS: bms_hv.doHV_FANS_STATUS,
        primary_ID_HV_MAINBOARD_VERSION: bms_hv.do_HV_MAINBOARD_VERSION,
        primary_ID_HV_CELLBOARD_VERSION: bms_hv.do_HV_CELLBOARD_VERSION
    }

    # Function called when a new message arrive, maps it to
    # relative function based on ID
    def on_message_received(self, msg):
        """
        This function is called whether a new message arrives, it then
        calls the corresponding function to process the message
        :param msg: the incoming message
        """
        # print(f"[DEBUG] {msg}")
        if self.doMsg.get(msg.arbitration_id) is not None:
            try:
                # message = dbc_primary.decode_message(msg.arbitration_id, msg.data)
                # print(f"[DEBUG] received message: {message}")
                self.doMsg.get(msg.arbitration_id)(msg)
            except KeyError:
                self.can_err = True


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
        canbus = can.interface.Bus(interface="socketcan", channel=CAN_INTERFACE)
        # links the bus with the listener
        notif = can.Notifier(canbus, [listener])

        return canbus
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
            if msg.arbitration_id == primary_ID_HANDCART_SET_SETTINGS:
                # tprint(str(msg), P_TYPE.DEBUG)
                try:
                    commands = do_HANDCART_SETTING_SET(msg)
                    if commands is not None:
                        for c in commands:
                            command_queue.put(c)
                except can.CanError:
                    shared_data.can_err = True

            rx_can_queue.put(msg)

    can_r_w = Can_rx_listener()
    canbus = canInit(can_r_w)

    with lock:
        if canbus == False:
            shared_data.can_err = True

    last_brusa_ctl_sent = 0
    last_hc_presence_sent = 0

    while 1:
        time.sleep(0.001)
        while not tx_can_queue.empty():
            act = tx_can_queue.get()
            canSend(canbus, act.arbitration_id, act.data, lock, shared_data)

        # Handles the brusa ctl messages
        with forward_lock:
            # TODO change to can library
            if time.time() - last_brusa_ctl_sent > 0.10:  # every tot time send a message
                if shared_data.can_forward_enabled:
                    with lock:
                        if 0 < shared_data.target_v <= MAX_TARGET_V_ACC \
                                and 0 <= shared_data.act_set_in_current <= MAX_CHARGER_GRID_CURRENT \
                                and 0 <= shared_data.act_set_out_current < MAX_ACC_CHG_AMPERE:

                            mains_ampere = shared_data.act_set_in_current
                            out_ampere = shared_data.act_set_out_current
                            try:
                                data = message_NLG5_CTL.encode({
                                    'NLG5_C_C_EN': 1,
                                    'NLG5_C_C_EL': 0,
                                    'NLG5_C_CP_V': 0,
                                    'NLG5_C_MR': 0,
                                    'NLG5_MC_MAX': mains_ampere,
                                    'NLG5_OV_COM': shared_data.target_v,
                                    'NLG5_OC_COM': out_ampere
                                })
                            except cantools.database.EncodeError:
                                shared_data.can_err = True
                        else:
                            shared_data.generic_error = True
                            tprint(f"Invalid settings for charging: {shared_data.target_v} V,"
                                   f" in current: {shared_data.act_set_in_current} A,"
                                   f" out current {shared_data.act_set_out_current}")
                            log_error(f"Invalid settings to charge accumulator, got "
                                      f"target volt:{shared_data.target_v}V, "
                                      f"in_current:{shared_data.act_set_in_current}A,"
                                      f"out_current:{shared_data.act_set_out_current}A")
                else:
                    # Brusa need to constantly keep to receive this msg, otherwise it will go in error
                    try:
                        data = message_NLG5_CTL.encode({
                            'NLG5_C_C_EN': 0,
                            'NLG5_C_C_EL': 0,
                            'NLG5_C_CP_V': 0,
                            'NLG5_C_MR': 0,
                            'NLG5_MC_MAX': 0,
                            'NLG5_OV_COM': 0,
                            'NLG5_OC_COM': 0
                        })
                    except cantools.database.EncodeError:
                        shared_data.can_err = True
                NLG5_CTL_message = can.Message(arbitration_id=message_NLG5_CTL.frame_id,
                                               data=data,
                                               is_extended_id=False)
                tx_can_queue.put(NLG5_CTL_message)
                last_brusa_ctl_sent = time.time()
            if time.time() - last_hc_presence_sent > 0.08:
                m: cantools.database.can.message = dbc_primary.get_message_by_frame_id(primary_ID_HANDCART_STATUS)

                try:
                    data = m.encode({
                        "connected": Toggle.ON.value
                    })
                except cantools.database.EncodeError:
                    shared_data.can_err = True

                status_message = can.Message(arbitration_id=m.frame_id,
                                             data=data,
                                             is_extended_id=False)
                tx_can_queue.put(status_message)

                # Send settings to telemetry
                m: cantools.database.can.message = dbc_primary.get_message_by_frame_id(primary_ID_HANDCART_SETTINGS)
                data_ = {
                    "target_voltage": shared_data.target_v,
                    "fans_override": shared_data.bms_hv.fans_set_override_status.value,
                    "fans_speed": shared_data.bms_hv.fans_set_override_speed,
                    "acc_charge_current": shared_data.act_set_out_current,
                    "grid_max_current": shared_data.act_set_in_current,
                    "status": shared_data.FSM_stat.value
                }
                # tprint(str(data_), P_TYPE.DEBUG)
                try:
                    data = m.encode(data_)
                except cantools.database.EncodeError:
                    shared_data.can_err = True

                status_message = can.Message(arbitration_id=m.frame_id,
                                             data=data,
                                             is_extended_id=False)
                tx_can_queue.put(status_message)
                last_hc_presence_sent = time.time()
