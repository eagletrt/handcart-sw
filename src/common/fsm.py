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
    idle_asked = False
    ask_clear_error = False  # Se to true to ask to clear all errors and go back in check

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

    def clrErr(self):
        """
        Function that clears all the errors in the FSM, use with care
        :return:
        """
        self.canread.charger.error = False
        self.canread.bms_hv.error = False
        self.canread.can_err = False
        GPIO.output(PIN.SD_RELAY.value, GPIO.HIGH)
        self.canread.charger.reset_asked = True

    def balancing_disabled_check(self):
        if self.canread.bms_hv.is_balancing == Toggle.ON and \
                self.last_balancing_stop_asked_time != 0 and \
                (datetime.now() - self.last_balancing_stop_asked_time).seconds > CAN_RETRANSMIT_INTERVAL_CRITICAL:

            m: cantools.database.can.message = dbc_primary.get_message_by_frame_id(
                primary_ID_HV_SET_BALANCING_STATUS_HANDCART)
            try:
                data = m.encode(
                    {
                        "set_balancing_status": Toggle.OFF.value,
                        "balancing_threshold": ACC_BALANCING_THRESHOLD
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

        if self.com_queue.empty():
            return

        act_com = self.com_queue.get()
        if type(act_com) is not dict:
            return
        tprint(str(act_com), P_TYPE.DEBUG)

        try:
            com_type = act_com['com-type']
            value = act_com['value']
        except KeyError:
            tprint(f"Key error while trying to read command {act_com}", P_TYPE.ERROR)
            return

        if com_type == 'cutoff':
            if type(value) is not int:
                tprint(f"cutoff command value type is not int: {value}", P_TYPE.ERROR)
                return

            if ACC_MIN_TARGET_V < value < ACC_MAX_TARGET_V:
                self.canread.target_v = value
            else:
                tprint(f"cutoff command exceeds limits: {value}", P_TYPE.ERROR)

        if com_type == "precharge" and \
                value is True and \
                self.canread.FSM_stat == STATE.IDLE:
            self.precharge_command = True

        if com_type == "charge":
            if value is True:
                self.start_charge_command = True
            elif value is False:
                self.stop_charge_command = True

        if com_type == "ready" and value is True:
            self.ready_command = True

        if com_type == "shutdown" and value is True:
            self.idle_asked = True

        if com_type == "balancing":
            if value is False:
                self.balancing_stop_asked = True
            if value is True:
                self.balancing_command = True

        if com_type == "fan-override-set-status":
            if value is False:
                self.canread.bms_hv.fans_set_override_status = Toggle.OFF
            if value is True:
                self.canread.bms_hv.fans_set_override_status = Toggle.ON

        if com_type == "fan-override-set-speed":
            if type(value) is not int:
                tprint(f"fan-override-set-speed command value type is not int: {value}", P_TYPE.ERROR)
                return
            if ACC_MIN_FAN_SPEED <= value <= ACC_MAX_FAN_SPEED:
                self.canread.bms_hv.fans_set_override_speed = value / 100

        if com_type == 'max-out-current':
            if type(value) is not float:
                tprint(f"max-out-current command value type is not float: {value}", P_TYPE.ERROR)
                return
            if ACC_MIN_CHG_CURRENT < value <= ACC_MAX_CHG_CURRENT:
                self.canread.act_set_out_current = value
            else:
                print("max-out-current limits exceded")

        if com_type == "clear-errors" and value is True:
            self.ask_clear_error = True

    def doCheck(self):
        """
        Do check status of the state machine
        """
        # Make sure that acc is in ts off
        self.accumulator_sd()

        GPIO.output(PIN.PON_CONTROL.value, GPIO.HIGH)  # Enable PON

        # Check that charger is not charging
        if self.canread.charger.is_enabled():
            self.canread.can_charger_charge_enabled = False

        if self.balancing_command:
            self.balancing_command = False
            return STATE.BALANCING

        if self.canread.bms_hv.isConnected() and self.canread.charger.is_connected():
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

        # Check that charger is not charging
        if self.canread.charger.is_enabled():
            self.canread.can_charger_charge_enabled = False

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

        GPIO.output(PIN.DISCHARGE.value, GPIO.HIGH)  # pin discharge high (open discharge relay)

        # Check that charger is not charging
        if self.canread.charger.is_enabled():
            self.canread.can_charger_charge_enabled = False
            return STATE.IDLE

        if self.canread.bms_hv.status == HvStatus.IDLE and not self.precharge_asked:
            m = dbc_primary.get_message_by_frame_id(primary_ID_HV_SET_STATUS_HANDCART)

            try:
                data = m.encode(
                    {
                        "hv_status_set": Toggle.ON.value,
                    }
                )

                ts_on_msg = can.Message(arbitration_id=m.frame_id,
                                        data=data,
                                        is_extended_id=False)

                self.tx_can_queue.put(ts_on_msg)
            except cantools.database.EncodeError:
                self.canread.can_err = True

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
            if (time.time() - self.precharge_asked_time) > ACC_PRECHARGE_FINISH_TIMEOUT:
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

        # Check that charger is not charging
        if self.canread.charger.is_enabled():
            self.canread.can_charger_charge_enabled = False

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

        if self.canread.bms_hv.status != HvStatus.TS_ON:
            tprint(f"BMS_HV is not in TS_ON, it is in {self.canread.bms_hv.status} going back idle", P_TYPE.INFO)
            # note that errors are already managed in mainloop
            return STATE.IDLE

        with self.forward_lock:
            self.canread.can_charger_charge_enabled = True

            if self.stop_charge_command:
                self.canread.can_charger_charge_enabled = False
                self.stop_charge_command = False
                return STATE.READY

            if (self.canread.charger.act_voltage >= self.canread.target_v \
                and self.canread.charger.act_current < 0.1) or \
                    self.canread.bms_hv.max_cell_voltage >= ACC_MAX_CELL_VOLTAGE:
                self.canread.can_charger_charge_enabled = False
                return STATE.CHARGE_DONE

        return STATE.CHARGE

    def doC_done(self):
        """
        Function that do the charge done of the state machine
        :return:
        """

        # Check that charger is not charging
        if self.canread.charger.is_enabled():
            self.canread.can_charger_charge_enabled = False

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

        # Check that charger is not charging
        if self.canread.charger.is_enabled():
            self.canread.can_charger_charge_enabled = False

        if not self.canread.bms_hv.is_balancing == Toggle.ON \
                and (time.time() - self.balancing_asked_time) > CAN_RETRANSMIT_INTERVAL_NORMAL:
            m: cantools.database.can.message = dbc_primary.get_message_by_frame_id(
                primary_ID_HV_SET_BALANCING_STATUS_HANDCART)

            try:
                data = m.encode(
                    {
                        "set_balancing_status": Toggle.ON.value,
                        "balancing_threshold": ACC_BALANCING_THRESHOLD
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
            # Disable charging
            self.canread.can_charger_charge_enabled = False
            time.sleep(.2)  # give time to stop charging

        # Turn off charger
        GPIO.output(PIN.PON_CONTROL.value, GPIO.LOW)

        # Send stacca stacca to BMS
        if not self.canread.bms_hv.status == HvStatus.IDLE.value:
            self.accumulator_sd()  # Try to ask accumulator to TS OFF

        GPIO.output(PIN.SD_RELAY.value, GPIO.LOW)  # Turn off SD

        if self.canread.charger.error:
            pass
            # print("brusa error")
        if self.canread.bms_hv.error:
            # print("bms error")
            pass
        if self.canread.can_err:
            # print("Can Error")
            pass

        if self.ask_clear_error:
            self.clrErr()
            self.ask_clear_error = False
            return STATE.CHECK
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

            if act_stat != STATE.CHECK and act_stat != STATE.ERROR:
                if not self.canread.bms_hv.isConnected():
                    tprint("Going back to CHECK, BMS is not connected", P_TYPE.INFO)
                    next_stat = self.doState.get(STATE.CHECK)(self)
                if not self.canread.charger.is_connected() and act_stat != STATE.BALANCING:
                    # If not in check or error and charger is not present, AND not in balancing go to check
                    # You can do balancing even without the charger
                    tprint("Going back to CHECK, brusa is not connected", P_TYPE.INFO)
                    next_stat = self.doState.get(STATE.CHECK)(self)

            # Checks errors
            if next_stat is None:
                if self.canread.charger.error or self.canread.bms_hv.error or self.canread.can_err:
                    next_stat = self.doState.get(STATE.ERROR)(self)
                else:
                    next_stat = self.doState.get(act_stat)(self)

            # Discharge
            if self.canread.bms_hv.status not in [
                HvStatus.PRECHARGE,
                HvStatus.AIRN_CLOSE,
                HvStatus.AIRP_CLOSE,
                HvStatus.TS_ON]:
                # If ts is not on, discharge pin is LOW (discharge relay closed)
                GPIO.output(PIN.DISCHARGE.value, GPIO.LOW)

            if self.idle_asked:
                next_stat = STATE.IDLE
                self.idle_asked = False

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
