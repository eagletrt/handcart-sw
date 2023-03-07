import queue
import threading
import time

import can
from can import Listener

from can_eagle.lib.primary.python.ids import *
import common.accumulator.bms as bms
from common.brusa.brusa import *
from common.settings import *
import common.fsm as fsm
from .logging import log_error
from can_eagle.lib.primary.python.network import message_HANDCART_STATUS

class CanListener:
    """
    That listener is called wether a can message arrives, then
    based on the msg ID, processes it, and save on itself the msg info.
    This class also stores all the data recived from the devices
    """
    FSM_stat = STATE.IDLE  # The actual state of the FSM (mirror the main variable)
    FSM_entered_stat = ""  # The moment in time the FSM has entered that state

    generic_error = False
    can_err = False
    target_v = DEFAULT_TARGET_V_ACC
    act_set_out_current = DEFAULT_ACC_CHG_AMPERE
    act_set_in_current = DEFAULT_CHARGE_MAINS_AMPERE

    brusa = BRUSA()
    bms_hv = bms.BMS_HV()

    # Maps the incoming can msgs to relative function
    doMsg = {
        # brusa
        CAN_BRUSA_MSG_ID.NLG5_ST.value: brusa.doNLG5_ST,
        CAN_BRUSA_MSG_ID.NLG5_ACT_I.value: brusa.doNLG5_ACT_I,
        CAN_BRUSA_MSG_ID.NLG5_ACT_II.value: brusa.doNLG5_ACT_II,
        CAN_BRUSA_MSG_ID.NLG5_ERR.value: brusa.doNLG5_ERR,
        CAN_BRUSA_MSG_ID.NLG5_TEMP.value: brusa.doNLG5_TEMP,

        # BMS_HV Fenice
        primary_ID_HV_VOLTAGE: bms_hv.doHV_VOLTAGE,
        primary_ID_HV_CURRENT: bms_hv.doHV_CURRENT,
        primary_ID_HV_ERRORS: bms_hv.doHV_ERRORS,
        primary_ID_HV_TEMP: bms_hv.doHV_TEMP,
        primary_ID_TS_STATUS: bms_hv.doHV_STATUS,
        primary_ID_HV_CELLS_VOLTAGE: bms_hv.doHV_CELLS_VOLTAGE,
        primary_ID_HV_CELLS_TEMP: bms_hv.doHV_CELLS_TEMP,
        primary_ID_HV_CELL_BALANCING_STATUS: bms_hv.doHV_BALANCING_STATUS,
        primary_ID_HV_FANS_OVERRIDE_STATUS: bms_hv.doHV_FANS_OVERRIDE_STATUS,

        # BMS_HV Chimera
        CAN_ID_BMS_HV_CHIMERA: bms_hv.do_CHIMERA
    }

    # Function called when a new message arrive, maps it to
    # relative function based on ID
    def on_message_received(self, msg):
        """
        This function is called whether a new message arrives, it then
        calls the corresponding function to process the message
        :param msg: the incoming message
        """
        # print(msg.arbitration_id)
        if self.doMsg.get(msg.arbitration_id) is not None:
            self.doMsg.get(msg.arbitration_id)(msg)


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
                 rx_can_queue: queue,
                 tx_can_queue: queue,
                 can_forward_enabled: bool,
                 forward_lock: threading.Lock,
                 lock: threading.Lock):
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

    with lock:
        if canbus == False:
            shared_data.can_err = True

    last_brusa_ctl_sent = 0
    last_hc_presence_sent = 0

    while 1:
        time.sleep(0.001)
        # print("can")
        while not tx_can_queue.empty():
            act = tx_can_queue.get()
            canSend(canbus, act.arbitration_id, act.data, lock, shared_data)

        # Handles the brusa ctl messages
        with forward_lock:
            if time.time() - last_brusa_ctl_sent > 0.15:  # every tot time send a message
                NLG5_CTL = brusa_dbc.get_message_by_name('NLG5_CTL')
                if can_forward_enabled:
                    with lock:
                        if 0 < shared_data.target_v <= MAX_TARGET_V_ACC \
                                and 0 <= shared_data.act_set_in_current <= 16 \
                                and 0 <= shared_data.act_set_out_current < 12:

                            mains_ampere = shared_data.act_set_in_current
                            out_ampere = shared_data.act_set_out_current
                            data = NLG5_CTL.encode({
                                'NLG5_C_C_EN': 1,
                                'NLG5_C_C_EL': 0,
                                'NLG5_C_CP_V': 0,
                                'NLG5_C_MR': 0,
                                'NLG5_MC_MAX': mains_ampere,
                                'NLG5_OV_COM': shared_data.target_v,
                                'NLG5_OC_COM': out_ampere
                            })
                        else:
                            shared_data.generic_error = True
                            log_error(f"Invalid settings to charge accumulator, got "
                                      f"target volt:{shared_data.target_v}V, "
                                      f"in_current:{shared_data.act_set_in_current}A,"
                                      f"out_current:{shared_data.act_set_out_current}A")
                else:
                    # Brusa need to constantly keep to receive this msg, otherwise it will go in error
                    data = NLG5_CTL.encode({
                        'NLG5_C_C_EN': 0,
                        'NLG5_C_C_EL': 0,
                        'NLG5_C_CP_V': 0,
                        'NLG5_C_MR': 0,
                        'NLG5_MC_MAX': 0,
                        'NLG5_OV_COM': 0,
                        'NLG5_OC_COM': 0
                    })
                NLG5_CTL_message = can.Message(arbitration_id=NLG5_CTL.frame_id,
                                               data=data,
                                               is_extended_id=False)
                tx_can_queue.put(NLG5_CTL_message)
                last_brusa_ctl_sent = time.time()
            if time.time() - last_hc_presence_sent > 0.5:
                if shared_data.bms_hv.ACC_CONNECTED == bms.ACCUMULATOR.FENICE:
                    tmp = message_HANDCART_STATUS(connected=True)
                    status_message = can.Message(arbitration_id=primary_ID_HANDCART_STATUS,
                                                 data=tmp.serialize(),
                                                 is_extended_id=False)
                    tx_can_queue.put(status_message)
                    last_hc_presence_sent = time.time()
