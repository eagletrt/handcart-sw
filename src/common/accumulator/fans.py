import queue
import threading
import time

import can
import cantools.database.can

import common.handcart_can
from settings import *


def thread_fans(shared_data: common.handcart_can.CanListener,
                tx_can_queue: queue,
                lock: threading.Lock):
    while 1:
        time.sleep(.1)
        with lock:
            if shared_data.FSM_stat == STATE.ERROR or shared_data.bms_hv.max_temp > 50:
                if shared_data.bms_hv.fans_override_status == Toggle.ON:
                    m: cantools.database.can.message = dbc_primary.get_message_by_frame_id(
                        primary_ID_HV_SET_FANS_STATUS)

                    try:
                        data = m.encode(
                            {
                                "fans_override": Toggle.OFF.value,
                                "fans_speed": shared_data.bms_hv.fans_set_override_speed
                            }
                        )
                    except cantools.database.EncodeError:
                        shared_data.can_err = True

                    msg = can.Message(arbitration_id=m.frame_id,
                                      data=data,
                                      is_extended_id=False)
                    tx_can_queue.put(msg)
                return

            if (shared_data.bms_hv.fans_override_status !=
                    shared_data.bms_hv.fans_set_override_status):
                # Ask to override or disable override
                set_status = Toggle.OFF
                if shared_data.bms_hv.fans_set_override_status == Toggle.ON:
                    set_status = Toggle.ON

                m: cantools.database.can.message = dbc_primary.get_message_by_frame_id(primary_ID_HV_SET_FANS_STATUS)

                try:
                    data = m.encode(
                        {
                            "fans_override": set_status.value,
                            "fans_speed": shared_data.bms_hv.fans_set_override_speed
                        }
                    )
                except cantools.database.EncodeError:
                    shared_data.can_err = True

                msg = can.Message(arbitration_id=m.frame_id,
                                  data=data,
                                  is_extended_id=False)
                tx_can_queue.put(msg)

            if shared_data.bms_hv.fans_override_speed != shared_data.bms_hv.fans_set_override_speed:
                if shared_data.bms_hv.fans_override_status == Toggle.ON:
                    m: cantools.database.can.message = dbc_primary.get_message_by_frame_id(
                        primary_ID_HV_SET_FANS_STATUS)

                    try:
                        data = m.encode(
                            {
                                "fans_override": Toggle.ON.value,
                                "fans_speed": shared_data.bms_hv.fans_set_override_speed
                            }
                        )
                    except cantools.database.EncodeError:
                        shared_data.can_err = True

                    msg = can.Message(arbitration_id=m.frame_id,
                                      data=data,
                                      is_extended_id=False)
                    tx_can_queue.put(msg)
