import queue
import threading
import time
from datetime import datetime

import can
from RPi import GPIO

from common.handcart_can import CanListener
from common.logging import P_TYPE, tprint
from settings import *


class FSM(threading.Thread):
    canread = CanListener()  # Access it ONLY with the FSM
    precharge_asked = False  # True if precharge asked to bms
    precharge_asked_time = 0  # time when the precharge has been asked
    precharge_done = False

    precharge_command = False  # True if received precharge command
    start_charge_command = False  # True if received start charge command
    stop_charge_command = False  # True if received stop charge command
    ready_command = False  # True if received a ready command, used only to go from CHARGE_DONE to READY
    shutdown_asked = False

    balancing_asked_time = 0  # the time of the last precharge message has been sent
    balancing_stop_asked = False
    balancing_command = False
    last_balancing_stop_asked_time: datetime = 0

    tx_can_queue: queue.Queue
    rx_can_queue: queue.Queue
    com_queue: queue.Queue
    lock: threading.Lock
    shared_data: CanListener = None
    forward_lock: threading.Lock  # Lock to manage the access to the can_forward_enabled variable

    def __init__(self,
                 tx_can_queue: queue.Queue,
                 rx_can_queue: queue.Queue,
                 com_queue: queue.Queue,
                 lock: threading.Lock,
                 shared_data: CanListener,
                 forward_lock: threading.Lock):

        super().__init__(args=(tx_can_queue,
                               rx_can_queue,
                               com_queue,
                               lock,
                               shared_data,
                               forward_lock))

        self.tx_can_queue = self._args[0]
        self.rx_can_queue = self._args[1]
        self.com_queue = self._args[2]
        self.lock = self._args[3]
        self.shared_data = self._args[4]
        self.forward_lock = self._args[5]

    def accumulator_sd(self):  # accumulator shutdown
        if self.canread.bms_hv.status == HvStatus.TS_ON:

            m: cantools.database.can.message = dbc_primary.get_message_by_frame_id(
                primary_ID_HV_SET_STATUS_HANDCART)

            try:
                data = m.encode(
                    {
                        "hv_status_set": Toggle.OFF.value,
                    }
                )
            except cantools.database.EncodeError:
                self.canread.can_err = True

            message = can.Message(arbitration_id=m.frame_id,
                                  data=data,
                                  is_extended_id=False)
            self.tx_can_queue.put(message)

    def staccastacca(self):
        """
        Function that is to be called in an unsafe environment, this function
        will ask the BMS_HV to close the airs and it will disable the Brusa
        and all the devices. This will also open the SD_Relay
        """
        GPIO.output(PIN.PON_CONTROL.value, GPIO.LOW)
        GPIO.output(PIN.SD_RELAY.value, GPIO.LOW)

        tprint("staccastacca done", P_TYPE.DEBUG)

        self.accumulator_sd()

        # Set PON to off
        # Open shutdown
        self.precharge_asked = False
        self.precharge_done = False
        self.canread.can_forward_enabled = False

    def clrErr(self):
        """
        Function that clears all the errors in the FSM, use with care
        :return:
        """
        self.canread.brusa_err = False
        self.canread.bms_err = False
        self.canread.bms_err_str = ""
        self.canread.brusa_err_str_list = []
        self.canread.can_err = False

    def balancing_disabled_check(self):
        if self.canread.bms_hv.is_balancing == Toggle.ON and \
                self.last_balancing_stop_asked_time != 0 and \
                (datetime.now() - self.last_balancing_stop_asked_time).seconds > RETRANSMIT_INTERVAL_CRITICAL:

            m: cantools.database.can.message = dbc_primary.get_message_by_frame_id(
                primary_ID_HV_SET_BALANCING_STATUS_HANDCART)
            try:
                data = m.encode(
                    {
                        "set_balancing_status": Toggle.OFF.value,
                        "balancing_threshold": 50
                    }
                )
            except cantools.database.EncodeError:
                self.canread.can_err = True

            message = can.Message(arbitration_id=m.frame_id,
                                  data=data,
                                  is_extended_id=False)
            self.tx_can_queue.put(message)
        self.last_balancing_stop_asked_time = datetime.now()

    def checkCommands(self):
        """
        This function checks for commands in the queue shared between the FSM and the server,
        i.e. if an "fast charge" command is found, the value of that command is set in the fsm
        """

        if not self.com_queue.empty():
            act_com = self.com_queue.get()
            tprint(str(act_com), P_TYPE.DEBUG)

            if act_com['com-type'] == 'cutoff':
                if int(act_com['value']) > 200 and int(act_com['value'] < MAX_TARGET_V_ACC):
                    self.canread.target_v = int(act_com['value'])
                else:
                    print("cutoff command exceeds limits")

            if act_com['com-type'] == "precharge" and \
                    act_com['value'] is True and \
                    self.canread.FSM_stat == STATE.IDLE:
                self.precharge_command = True

            if act_com['com-type'] == "charge" and act_com['value'] is True:
                self.start_charge_command = True

            if act_com['com-type'] == "charge" and act_com['value'] is False:
                self.stop_charge_command = True

            if act_com['com-type'] == "ready" and act_com['value'] is True:
                self.ready_command = True

            if act_com['com-type'] == "shutdown" and act_com['value'] is True:
                self.shutdown_asked = True

            if act_com['com-type'] == "balancing":
                if act_com['value'] is False:
                    self.balancing_stop_asked = True
                if act_com['value'] is True:
                    self.balancing_command = True

            if act_com['com-type'] == "fan-override-set-status":
                if act_com['value'] == False:
                    self.canread.bms_hv.fans_set_override_status = Toggle.OFF
                if act_com['value'] == True:
                    self.canread.bms_hv.fans_set_override_status = Toggle.ON

            if act_com['com-type'] == "fan-override-set-speed":
                if act_com['value'] != "":
                    speed = int(act_com['value'])
                    if 0 <= speed <= 100:
                        self.canread.bms_hv.fans_set_override_speed = int(speed) / 100

            if act_com['com-type'] == 'max-out-current':
                if 0 < act_com['value'] < 12:
                    self.canread.act_set_out_current = act_com['value']
                else:
                    print("max-out-current limits exceded")

            if act_com['com-type'] == "max-in-current":
                if 0 < act_com['value'] <= 16:
                    self.canread.act_set_in_current = act_com['value']
                else:
                    print("max-in-current limits exceded")

    def doCheck(self):
        """
        Do check status of the state machine
        """
        # Make sure that acc is in ts off
        self.accumulator_sd()

        if self.canread.bms_hv.isConnected() and self.canread.brusa.isConnected():
            self.precharge_command = False  # Clear before entering IDLE
            return STATE.IDLE
        else:
            return STATE.CHECK

    def doIdle(self):
        """
        Do Idle status of the state machine
        :return:
        """

        self.precharge_asked = False
        self.precharge_done = False
        self.precharge_asked_time = 0

        GPIO.output(PIN.PON_CONTROL.value, GPIO.LOW)
        # Make sure that acc is in ts off
        self.accumulator_sd()

        if self.precharge_command:
            self.precharge_command = False
            return STATE.PRECHARGE

        if self.balancing_command:
            self.balancing_command = False
            return STATE.BALANCING

        return STATE.IDLE

    def doPreCharge(self):
        """
        Function that do the precharge statusc
        """
        # ask pork to do precharge
        # Send req to bms "TS_ON"

        if self.canread.bms_hv.status == HvStatus.IDLE and not self.precharge_asked:
            m = dbc_primary.get_message_by_frame_id(primary_ID_HV_SET_STATUS_HANDCART)

            try:
                data = m.encode(
                    {
                        "hv_status_set": Toggle.ON.value,
                    }
                )
            except cantools.database.EncodeError:
                self.canread.can_err = True

            ts_on_msg = can.Message(arbitration_id=m.frame_id,
                                    data=data,
                                    is_extended_id=False)

            self.tx_can_queue.put(ts_on_msg)
            self.precharge_asked = True
            self.precharge_asked_time = time.time()

        if self.canread.bms_hv.status == HvStatus.TS_ON:
            tprint("Precharge done, TS is on", P_TYPE.INFO)
            self.precharge_done = True
            self.precharge_asked = False
            self.precharge_asked_time = 0

        if self.precharge_done:
            self.start_charge_command = False  # reset start charge command
            return STATE.READY
        else:
            if (time.time() - self.precharge_asked_time) > BMS_PRECHARGE_STATUS_CHANGE_TIMEOUT:
                if self.precharge_asked and \
                        (self.canread.bms_hv.status == HvStatus.PRECHARGE or
                         self.canread.bms_hv.status == HvStatus.AIRN_CLOSE or
                         self.canread.bms_hv.status == HvStatus.AIRP_CLOSE):
                    return STATE.PRECHARGE
                else:
                    return STATE.IDLE
            else:
                return STATE.PRECHARGE

    def doReady(self):
        """
        Function that do the ready state of the state machine
        """

        if self.canread.bms_hv.status != HvStatus.TS_ON:
            tprint(f"BMS_HV is not in TS_ON, it is in {self.canread.bms_hv.status} going back idle", P_TYPE.INFO)
            # note that errors are already managed in mainloop
            return STATE.IDLE

        self.precharge_asked = False

        if self.start_charge_command:
            self.start_charge_command = False
            return STATE.CHARGE
        else:
            return STATE.READY

    def doCharge(self):
        """
        Function that do the charge state of the state machine
        :return:
        """
        # canread has to forward charging msgs from bms to brusa

        # Set Brusa's PON to 12v (relay)
        GPIO.output(PIN.PON_CONTROL.value, GPIO.HIGH)

        if self.canread.bms_hv.status != HvStatus.TS_ON:
            tprint(f"BMS_HV is not in TS_ON, it is in {self.canread.bms_hv.status} going back idle", P_TYPE.INFO)
            # note that errors are already managed in mainloop
            return STATE.IDLE

        with self.forward_lock:
            self.canread.can_forward_enabled = True

            if self.stop_charge_command:
                self.canread.can_forward_enabled = False
                self.stop_charge_command = False
                return STATE.READY
            try:
                if (self.canread.brusa.act_NLG5_ACT_I['NLG5_OV_ACT'] >= self.canread.target_v \
                    and self.canread.brusa.act_NLG5_ACT_I['NLG5_OC_ACT'] < 0.1) or \
                        self.canread.bms_hv.max_cell_voltage >= MAX_ACC_CELL_VOLTAGE:
                    self.canread.can_forward_enabled = False
                    return STATE.CHARGE_DONE
            except KeyError:
                print("Error in reading can message from brusa")
                # canread.can_err = True da rimettere

        return STATE.CHARGE

    def doC_done(self):
        """
        Function that do the charge done of the state machine
        :return:
        """
        # User decide wether charge again or going idle
        GPIO.output(PIN.PON_CONTROL.value, GPIO.LOW)

        if self.canread.bms_hv.status != HvStatus.TS_ON:
            tprint(f"BMS_HV is not in TS_ON, it is in {self.canread.bms_hv.status} going back idle", P_TYPE.INFO)
            # note that errors are already managed in mainloop
            return STATE.IDLE

        if self.ready_command:
            self.ready_command = False
            return STATE.READY

        return STATE.CHARGE_DONE

    def do_balancing(self):
        if self.balancing_stop_asked:
            self.balancing_stop_asked = False
            return STATE.IDLE

        if not self.canread.bms_hv.is_balancing == Toggle.ON \
                and (time.time() - self.balancing_asked_time) > RETRANSMIT_INTERVAL_NORMAL:
            m: cantools.database.can.message = dbc_primary.get_message_by_frame_id(
                primary_ID_HV_SET_BALANCING_STATUS_HANDCART)

            try:
                data = m.encode(
                    {
                        "set_balancing_status": Toggle.ON.value,
                        "balancing_threshold": 50
                    }
                )
            except cantools.database.EncodeError:
                self.canread.can_err = True

            message = can.Message(arbitration_id=m.frame_id,
                                  data=data,
                                  is_extended_id=False)
            self.tx_can_queue.put(message)
            self.balancing_asked_time = time.time()
        return STATE.BALANCING

    def doError(self):
        """
        Do the error state of the state machine
        """

        with self.forward_lock:
            self.canread.can_forward_enabled = False

        GPIO.output(PIN.PON_CONTROL.value, GPIO.LOW)
        GPIO.output(PIN.SD_RELAY.value, GPIO.LOW)

        # Send to BMS stacca stacca
        if not self.canread.bms_hv.status == HvStatus.IDLE.value:
            self.staccastacca()

        if self.canread.brusa.error:
            pass
            # print("brusa error")
        if self.canread.bms_hv.error:
            # print("bms error")
            pass
        if self.canread.can_err:
            # print("Can Error")
            pass

        if not self.com_queue.empty:
            act_com = self.com_queue.get()
            # wait for user command to clear errors or exit
            if act_com['com_type'] == 'error_clear' and act_com['value'] == True:
                self.clrErr()
                return STATE.CHECK
            else:
                return STATE.EXIT

        else:
            return STATE.ERROR

    def doExit(self):
        """
        Function that does the state Exit of the state machine
        """
        exit(0)

        # Maps state to it's function

    doState = {
        STATE.CHECK: doCheck,
        STATE.IDLE: doIdle,
        STATE.PRECHARGE: doPreCharge,
        STATE.READY: doReady,
        STATE.CHARGE: doCharge,
        STATE.CHARGE_DONE: doC_done,
        STATE.BALANCING: do_balancing,
        STATE.ERROR: doError,
        STATE.EXIT: doExit
    }

    def run(self):
        """
        The thread that runs the backend state machine
        Pls read the documentation about the state machine
        """

        act_stat = STATE.CHECK
        self.canread.FSM_entered_stat = datetime.now().isoformat()
        tprint("Backend started", P_TYPE.INFO)
        # tprint("STATE: " + str(act_stat), P_TYPE.DEBUG)

        while 1:
            time.sleep(0.001)
            # Controllo coda rec can messages, in caso li processo. Controllo anche errori

            if not self.rx_can_queue.empty():
                msg_read = 0
                while msg_read < MAX_BATCH_CAN_READ and \
                        not self.rx_can_queue.empty():
                    new_msg = self.rx_can_queue.get()
                    self.canread.on_message_received(new_msg)
                    msg_read += 1

            if act_stat != STATE.BALANCING:
                # Check that balancing is disabled if not in balancing state
                self.balancing_disabled_check()

            next_stat = None

            if act_stat != STATE.CHECK:
                if not self.canread.bms_hv.isConnected():
                    tprint("Going back to CHECK, BMS is not connected", P_TYPE.INFO)
                    next_stat = self.doState.get(STATE.CHECK)(self)
                if (act_stat == STATE.CHARGE or act_stat == STATE.CHARGE_DONE) and not self.canread.brusa.isConnected():
                    tprint("Going back to CHECK, brusa is not connected", P_TYPE.INFO)
                    next_stat = self.doState.get(STATE.CHECK)(self)

            # Checks errors
            if next_stat is None:
                if self.canread.brusa.error or self.canread.bms_hv.error or self.canread.can_err:
                    next_stat = self.doState.get(STATE.ERROR)(self)
                else:
                    next_stat = self.doState.get(act_stat)(self)

            if self.shutdown_asked:
                next_stat = STATE.IDLE
                self.shutdown_asked = False

            if next_stat == STATE.EXIT:
                tprint("Exiting", P_TYPE.INFO)
                return

            self.checkCommands()

            self.canread.FSM_stat = act_stat
            if act_stat != next_stat:
                self.canread.FSM_entered_stat = datetime.now().isoformat()
                # print(self.canread.FSM_entered_stat)
                tprint("STATE: " + str(next_stat), P_TYPE.DEBUG)

            act_stat = next_stat

            with self.lock:
                # https://stackoverflow.com/questions/243836/how-to-copy-all-properties-of-an-object-to-another
                # -object-in-python
                # Magic
                self.shared_data.__dict__.update(self.canread.__dict__)
                # tprint(f"FSM shared data addr: {self.shared_data}", P_TYPE.DEBUG)
