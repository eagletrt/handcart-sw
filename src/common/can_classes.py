from collections import OrderedDict
from enum import Enum

from cantools.database import Message

from settings import dbc_primary, CAN_MESSAGE_CHECK_ENABLED, dbc_brusa

"""
This file should be called only once, when the program starts.
"""


def get_key_by_value(d: OrderedDict, value: str):
    """
    Get the key of an element in OrderedDict by its value
    Args:
        d: the ordered dict to search in
        value: the value to search

    Returns:
        the key corresponding to the value searched
    """
    for k, v in d.items():
        if v == value:
            return k

    raise KeyError(f"No key found for value \"{k}\"")


# Used to verify that names are present in dbc

primary_ID_HV_TOTAL_VOLTAGE = dbc_primary.get_message_by_name("HV_TOTAL_VOLTAGE").frame_id
primary_ID_HV_CURRENT = dbc_primary.get_message_by_name("HV_CURRENT").frame_id
primary_ID_HV_ERRORS = dbc_primary.get_message_by_name("HV_ERRORS").frame_id
primary_ID_HV_CELLS_TEMP_STATS = dbc_primary.get_message_by_name("HV_CELLS_TEMP_STATS").frame_id
primary_ID_HV_STATUS = dbc_primary.get_message_by_name("HV_STATUS").frame_id
primary_ID_HV_CELLS_VOLTAGE = dbc_primary.get_message_by_name("HV_CELLS_VOLTAGE").frame_id
primary_ID_HV_CELLS_VOLTAGE_STATS = dbc_primary.get_message_by_name("HV_CELLS_VOLTAGE_STATS").frame_id
primary_ID_HV_CELLS_TEMP = dbc_primary.get_message_by_name("HV_CELLS_TEMP").frame_id
primary_ID_HV_BALANCING_STATUS = dbc_primary.get_message_by_name("HV_BALANCING_STATUS").frame_id
primary_ID_HV_FANS_STATUS = dbc_primary.get_message_by_name("HV_FANS_STATUS").frame_id
primary_ID_HANDCART_SET_SETTINGS = dbc_primary.get_message_by_name("HANDCART_SET_SETTINGS").frame_id
primary_ID_HV_SET_STATUS_HANDCART = dbc_primary.get_message_by_name("HV_SET_STATUS_HANDCART").frame_id
primary_ID_HV_SET_BALANCING_STATUS_HANDCART = dbc_primary.get_message_by_name("HV_SET_BALANCING_STATUS_HANDCART").frame_id
primary_ID_HANDCART_STATUS = dbc_primary.get_message_by_name("HANDCART_STATUS").frame_id
primary_ID_HANDCART_SETTINGS = dbc_primary.get_message_by_name("HANDCART_SETTINGS").frame_id
primary_ID_HV_SET_FANS_STATUS = dbc_primary.get_message_by_name("HV_SET_FANS_STATUS").frame_id
primary_ID_HV_ENERGY = dbc_primary.get_message_by_name("HV_ENERGY").frame_id

primary_ID_HV_MAINBOARD_VERSION = dbc_primary.get_message_by_name("HV_MAINBOARD_VERSION").frame_id
primary_ID_HV_CELLBOARD_VERSION = dbc_primary.get_message_by_name("HV_CELLBOARD_VERSION").frame_id
primary_ID_HV_DEBUG_SIGNALS = dbc_primary.get_message_by_name("HV_DEBUG_SIGNALS").frame_id
primary_ID_HV_FEEDBACK_STATUS = dbc_primary.get_message_by_name("HV_FEEDBACK_STATUS").frame_id
primary_ID_HV_FEEDBACK_TS_VOLTAGE = dbc_primary.get_message_by_name("HV_FEEDBACK_TS_VOLTAGE").frame_id
primary_ID_HV_MISC_VOLTAGE = dbc_primary.get_message_by_name("HV_FEEDBACK_MISC_VOLTAGE").frame_id
primary_ID_HV_FEEDBACK_SD_VOLTAGE = dbc_primary.get_message_by_name("HV_FEEDBACK_SD_VOLTAGE").frame_id
primary_ID_HV_HV_IMD_STATUS = dbc_primary.get_message_by_name("HV_IMD_STATUS").frame_id

# Instantiate some messages of the brusa
message_NLG5_CTL: Message = dbc_brusa.get_message_by_name('NLG5_CTL')
message_NLG5_ST: Message = dbc_brusa.get_message_by_name('NLG5_ST')
message_NLG5_ACT_I: Message = dbc_brusa.get_message_by_name('NLG5_ACT_I')
message_NLG5_ERR: Message = dbc_brusa.get_message_by_name('NLG5_ERR')

class HvStatus(Enum):
    # VAL_ 84 ts_status 0 "INIT" 1 "IDLE" 2 "AIRN_CLOSE" 3 "PRECHARGE" 4 "AIRP_CLOSE" 5 "TS_ON" 6 "FATAL_ERROR" ;
    INIT = get_key_by_value(
        dbc_primary.get_message_by_frame_id(primary_ID_HV_STATUS).signals[0].choices, "init")
    IDLE = get_key_by_value(
        dbc_primary.get_message_by_frame_id(primary_ID_HV_STATUS).signals[0].choices, "idle")
    AIRN_CLOSE = get_key_by_value(
        dbc_primary.get_message_by_frame_id(primary_ID_HV_STATUS).signals[0].choices, "airn_close")
    AIRP_CLOSE = get_key_by_value(
        dbc_primary.get_message_by_frame_id(primary_ID_HV_STATUS).signals[0].choices, "airp_close")
    PRECHARGE = get_key_by_value(
        dbc_primary.get_message_by_frame_id(primary_ID_HV_STATUS).signals[0].choices, "precharge")
    TS_ON = get_key_by_value(
        dbc_primary.get_message_by_frame_id(primary_ID_HV_STATUS).signals[0].choices, "ts_on")
    FATAL_ERROR = get_key_by_value(
        dbc_primary.get_message_by_frame_id(primary_ID_HV_STATUS).signals[0].choices, "fatal_error")


class Toggle(Enum):
    OFF = 0
    ON = 1


class HandcartStatus(Enum):
    NONE = get_key_by_value(
        dbc_primary.get_message_by_frame_id(primary_ID_HANDCART_SETTINGS).signals[5].choices, "none")
    CHECK = get_key_by_value(
        dbc_primary.get_message_by_frame_id(primary_ID_HANDCART_SETTINGS).signals[5].choices, "check")
    IDLE = get_key_by_value(
        dbc_primary.get_message_by_frame_id(primary_ID_HANDCART_SETTINGS).signals[5].choices, "idle")
    PRECHARGE = get_key_by_value(
        dbc_primary.get_message_by_frame_id(primary_ID_HANDCART_SETTINGS).signals[5].choices, "precharge")
    READY = get_key_by_value(
        dbc_primary.get_message_by_frame_id(primary_ID_HANDCART_SETTINGS).signals[5].choices, "ready")
    CHARGE = get_key_by_value(
        dbc_primary.get_message_by_frame_id(primary_ID_HANDCART_SETTINGS).signals[5].choices, "charge")
    CHARGE_DONE = get_key_by_value(
        dbc_primary.get_message_by_frame_id(primary_ID_HANDCART_SETTINGS).signals[5].choices, "charge_done")
    BALANCING = get_key_by_value(
        dbc_primary.get_message_by_frame_id(primary_ID_HANDCART_SETTINGS).signals[5].choices, "balancing")
    ERROR = get_key_by_value(
        dbc_primary.get_message_by_frame_id(primary_ID_HANDCART_SETTINGS).signals[5].choices, "error")


HvErrors = {
    # TODO: validate ?
    "errors_cell_low_voltage": "",
    "errors_cell_under_voltage": "",
    "errors_cell_over_voltage": "",
    "errors_cell_high_temperature": "",
    "errors_cell_over_temperature": "",
    "errors_over_current": "",
    "errors_can": "",
    "errors_int_voltage_mismatch": "",
    "errors_cellboard_comm": "",
    "errors_cellboard_internal": "",
    "errors_connector_disconnected": "",
    "errors_fans_disconnected": "",
    "errors_feedback": "",
    "errors_feedback_circuitry": "",
    "errors_eeprom_comm": "",
    "errors_eeprom_write": ""
}


def verify_HV_TOTAL_VOLTAGE() -> bool:
    msg = dbc_primary.get_message_by_frame_id(primary_ID_HV_TOTAL_VOLTAGE)
    s_names = []
    for s in msg.signals:
        s_names.append(s.name)

    res = "pack" in s_names
    res &= "sum_cell" in s_names
    res &= "bus" in s_names
    return res


def verify_HV_CURRENT() -> bool:
    msg = dbc_primary.get_message_by_frame_id(primary_ID_HV_CURRENT)
    s_names = []
    for s in msg.signals:
        s_names.append(s.name)

    res = "curernt" in s_names
    return res


def verify_HV_CELLS_TEMP_STATS() -> bool:
    msg = dbc_primary.get_message_by_frame_id(primary_ID_HV_CELLS_TEMP_STATS)
    s_names = []
    for s in msg.signals:
        s_names.append(s.name)

    res = "max" in s_names
    res &= "min" in s_names
    res &= "avg" in s_names
    return res


def verify_HV_CELLS_VOLTAGE() -> bool:
    msg = dbc_primary.get_message_by_frame_id(primary_ID_HV_CELLS_VOLTAGE)
    s_names = []
    for s in msg.signals:
        s_names.append(s.name)

    res = "start_index" in s_names
    res &= "voltage_0" in s_names
    res &= "voltage_1" in s_names
    res &= "voltage_2" in s_names
    return res


def verify_HV_CELLS_VOLTAGE_STATS() -> bool:
    msg = dbc_primary.get_message_by_frame_id(primary_ID_HV_CELLS_VOLTAGE_STATS)
    s_names = []
    for s in msg.signals:
        s_names.append(s.name)

    res = "max" in s_names
    res &= "min" in s_names
    res &= "delta" in s_names
    res &= "avg" in s_names
    return res


def verify_HV_CELLS_TEMP() -> bool:
    msg = dbc_primary.get_message_by_frame_id(primary_ID_HV_CELLS_TEMP)
    s_names = []
    for s in msg.signals:
        s_names.append(s.name)

    res = "start_index" in s_names
    res &= "temp_0" in s_names
    res &= "temp_1" in s_names
    res &= "temp_2" in s_names
    res &= "temp_3" in s_names
    return res


def verify_HV_BALANCING_STATUS() -> bool:
    msg = dbc_primary.get_message_by_frame_id(primary_ID_HV_BALANCING_STATUS)
    s_names = []
    for s in msg.signals:
        s_names.append(s.name)

    res = "cellboard_id" in s_names
    res &= "balancing_status" in s_names
    res &= "errors" in s_names
    res &= "balancing_cells" in s_names
    return res


def verify_HV_FANS_STATUS() -> bool:
    msg = dbc_primary.get_message_by_frame_id(primary_ID_HV_FANS_STATUS)
    s_names = []
    for s in msg.signals:
        s_names.append(s.name)

    res = "fans_override" in s_names
    res &= "fans_speed" in s_names
    return res


def verify_HANDCART_SET_SETTINGS() -> bool:
    msg = dbc_primary.get_message_by_frame_id(primary_ID_HANDCART_SET_SETTINGS)
    s_names = []
    for s in msg.signals:
        s_names.append(s.name)

    res = "target_voltage" in s_names
    res &= "fans_override" in s_names
    res &= "fans_speed" in s_names
    res &= "acc_charge_current" in s_names
    res &= "grid_max_current" in s_names
    res &= "status" in s_names
    return res


def verify_HV_SET_STATUS_HANDCART() -> bool:
    msg = dbc_primary.get_message_by_frame_id(primary_ID_HV_SET_STATUS_HANDCART)
    s_names = []
    for s in msg.signals:
        s_names.append(s.name)

    res = "hv_status_set" in s_names
    return res


def verify_HV_SET_BALANCING_STATUS() -> bool:
    msg = dbc_primary.get_message_by_frame_id(primary_ID_HV_SET_BALANCING_STATUS_HANDCART)
    s_names = []
    for s in msg.signals:
        s_names.append(s.name)

    res = "set_balancing_status" in s_names
    res &= "balancing_threshold" in s_names
    return res


def verify_HANDCART_STATUS() -> bool:
    msg = dbc_primary.get_message_by_frame_id(primary_ID_HANDCART_STATUS)
    s_names = []
    for s in msg.signals:
        s_names.append(s.name)

    res = "connected" in s_names
    return res


def verify_HANDCART_SETTINGS() -> bool:
    msg = dbc_primary.get_message_by_frame_id(primary_ID_HANDCART_SETTINGS)
    s_names = []
    for s in msg.signals:
        s_names.append(s.name)

    res = "target_voltage" in s_names
    res &= "fans_override" in s_names
    res &= "fans_speed" in s_names
    res &= "acc_charge_current" in s_names
    res &= "grid_max_current" in s_names
    res &= "status" in s_names
    return res


def verify_HV_SET_FANS_STATUS() -> bool:
    msg = dbc_primary.get_message_by_frame_id(primary_ID_HV_SET_FANS_STATUS)
    s_names = []
    for s in msg.signals:
        s_names.append(s.name)

    res = "fans_override" in s_names
    res &= "fans_speed" in s_names
    return res


def verify_HV_CELLBOARD_VERSION() -> bool:
    msg = dbc_primary.get_message_by_frame_id(primary_ID_HV_CELLBOARD_VERSION)
    s_names = []
    for s in msg.signals:
        s_names.append(s.name)

    res = "cellboard_id" in s_names
    res &= "component_version" in s_names
    res &= "canlib_build_time" in s_names
    return res


def verify_HV_FEEDBACK_TS_VOLTAGE() -> bool:
    msg = dbc_primary.get_message_by_frame_id(primary_ID_HV_FEEDBACK_TS_VOLTAGE)
    s_names = []
    for s in msg.signals:
        s_names.append(s.name)

    res = "ts_over_60v_status" in s_names
    res &= "airn_status" in s_names
    res &= "airp_status" in s_names
    res &= "airp_gate" in s_names
    res &= "airn_gate" in s_names
    res &= "precharge_status" in s_names
    res &= "tsp_over_60v_status" in s_names
    return res


def verify_HV_FEEDBACK_MISC_VOLTAGE() -> bool:
    msg = dbc_primary.get_message_by_frame_id(primary_ID_HV_MISC_VOLTAGE)
    s_names = []
    for s in msg.signals:
        s_names.append(s.name)

    res = "implausibility_detected" in s_names
    res &= "imd_cockpit" in s_names
    res &= "tsal_green_fault_latched" in s_names
    res &= "bms_cockpit" in s_names
    res &= "ext_latched" in s_names
    res &= "tsal_green" in s_names
    res &= "imd_fault" in s_names
    res &= "check_mux" in s_names
    return res


def verify_HV_FEEDBACK_SD_VOLTAGE() -> bool:
    msg = dbc_primary.get_message_by_frame_id(primary_ID_HV_FEEDBACK_SD_VOLTAGE)
    s_names = []
    for s in msg.signals:
        s_names.append(s.name)

    res = "sd_end" in s_names
    res &= "sd_out" in s_names
    res &= "sd_in" in s_names
    res &= "sd_bms" in s_names
    res &= "sd_imd" in s_names
    return res


def verify_HV_IMD_STATUS() -> bool:
    msg = dbc_primary.get_message_by_frame_id(primary_ID_HV_HV_IMD_STATUS)
    s_names = []
    for s in msg.signals:
        s_names.append(s.name)

    res = "sd_end" in s_names
    res &= "sd_out" in s_names
    res &= "sd_in" in s_names
    res &= "sd_bms" in s_names
    res &= "sd_imd" in s_names
    res &= "imd_fault" in s_names
    res &= "imd_status" in s_names
    res &= "imd_details" in s_names
    res &= "imd_duty_cycle" in s_names
    res &= "imd_freq" in s_names
    res &= "imd_period" in s_names
    return res


def verify_HV_ENERGY() -> bool:
    msg = dbc_primary.get_message_by_frame_id(primary_ID_HV_ENERGY)
    s_names = []
    for s in msg.signals:
        s_names.append(s.name)

    res = "energy" in s_names
    return res


if CAN_MESSAGE_CHECK_ENABLED:
    verify_HV_TOTAL_VOLTAGE()
    verify_HV_CURRENT()
    verify_HV_CELLS_TEMP_STATS()
    verify_HV_CELLS_VOLTAGE()
    verify_HV_CELLS_VOLTAGE_STATS()
    verify_HV_CELLS_TEMP()
    verify_HV_BALANCING_STATUS()
    verify_HV_FANS_STATUS()
    verify_HANDCART_SET_SETTINGS()
    verify_HV_SET_STATUS_HANDCART()
    verify_HV_SET_BALANCING_STATUS()
    verify_HANDCART_STATUS()
    verify_HANDCART_SETTINGS()
    verify_HV_SET_FANS_STATUS()
    verify_HV_CELLBOARD_VERSION()
    verify_HV_FEEDBACK_TS_VOLTAGE()
    verify_HV_FEEDBACK_MISC_VOLTAGE()
    verify_HV_FEEDBACK_SD_VOLTAGE()
    verify_HV_IMD_STATUS()


class STATE(Enum):
    """Enum containing the states of the backend's state-machine
    It is inited with the values taken from the enum of the can message
    """
    CHECK = HandcartStatus.CHECK.value
    IDLE = HandcartStatus.IDLE.value
    PRECHARGE = HandcartStatus.PRECHARGE.value
    READY = HandcartStatus.READY.value
    CHARGE = HandcartStatus.CHARGE.value
    CHARGE_DONE = HandcartStatus.CHARGE_DONE.value
    BALANCING = HandcartStatus.BALANCING.value
    ERROR = HandcartStatus.ERROR.value
    EXIT = -1  # extra state for convenience
