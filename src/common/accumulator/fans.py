import queue
import threading
import time

import can

from src.can_eagle.lib.primary.python.ids import primary_ID_HV_FANS_OVERRIDE
from src.can_eagle.lib.primary.python.network import message_HV_FANS_OVERRIDE_conversion, Toggle
from src.common.can import CanListener
from src.common.fsm import STATE


def thread_fans(shared_data: CanListener,
                tx_can_queue: queue,
                lock: threading.Lock):
    while 1:
        time.sleep(.1)
        with lock:
            if shared_data.FSM_stat == STATE.ERROR or shared_data.bms_hv.max_temp > 50:
                if shared_data.bms_hv.fans_override_status == Toggle.ON:
                    data = message_HV_FANS_OVERRIDE_conversion(
                        fans_override=Toggle.OFF,
                        fans_speed=shared_data.bms_hv.fans_set_override_speed).convert_to_raw()
                    msg = can.Message(arbitration_id=primary_ID_HV_FANS_OVERRIDE,
                                      data=data.serialize(),
                                      is_extended_id=False)
                    tx_can_queue.put(msg)
                return

            if (shared_data.bms_hv.fans_override_status !=
                    shared_data.bms_hv.fans_set_override_status):
                # Ask to override or disable override
                set_status = Toggle.OFF
                if shared_data.bms_hv.fans_set_override_status:
                    set_status = Toggle.ON
                data = message_HV_FANS_OVERRIDE_conversion(
                    fans_override=set_status,
                    fans_speed=shared_data.bms_hv.fans_set_override_speed).convert_to_raw()
                msg = can.Message(arbitration_id=primary_ID_HV_FANS_OVERRIDE,
                                  data=data.serialize(),
                                  is_extended_id=False)
                tx_can_queue.put(msg)

            if shared_data.bms_hv.fans_override_speed != shared_data.bms_hv.fans_set_override_speed:
                if shared_data.bms_hv.fans_override_status == Toggle.ON:
                    data = message_HV_FANS_OVERRIDE_conversion(
                        fans_override=Toggle.ON,
                        fans_speed=shared_data.bms_hv.fans_set_override_speed).convert_to_raw()
                    msg = can.Message(arbitration_id=primary_ID_HV_FANS_OVERRIDE,
                                      data=data.serialize(),
                                      is_extended_id=False)
                    tx_can_queue.put(msg)
