from collections import OrderedDict
from enum import Enum

from settings import dbc_primary

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

    raise KeyError


class TsStatus(Enum):
    OFF = get_key_by_value(
        dbc_primary.get_message_by_name("TS_STATUS").signals[0].choices, "OFF")
    PRECHARGE = get_key_by_value(
        dbc_primary.get_message_by_name("TS_STATUS").signals[0].choices, "PRECHARGE")
    ON = get_key_by_value(
        dbc_primary.get_message_by_name("TS_STATUS").signals[0].choices, "ON")
    FATAL = get_key_by_value(
        dbc_primary.get_message_by_name("TS_STATUS").signals[0].choices, "FATAL")


class Toggle(Enum):
    OFF = 0
    ON = 1


HvErrors = {
    # TODO: validate ?
    "errors_CELL_LOW_VOLTAGE": None,
    "errors_CELL_UNDER_VOLTAGE": None,
    "errors_CELL_OVER_VOLTAGE": None,
    "errors_CELL_HIGH_TEMPERATURE": None,
    "errors_CELL_OVER_TEMPERATURE": None,
    "errors_OVER_CURRENT": None,
    "errors_CAN": None,
    "errors_INT_VOLTAGE_MISMATCH": None,
    "errors_CELLBOARD_COMM": None,
    "errors_CELLBOARD_INTERNAL": None,
    "errors_FEEDBACK": None,
    "errors_FEEDBACK_CIRCUITRY": None,
    "errors_EEPROM_COMM": None,
    "errors_EEPROM_WRITE": None
}

HvWarnings = {
    "warnings_CELL_LOW_VOLTAGE": None,
    "warnings_CELL_UNDER_VOLTAGE": None,
    "warnings_CELL_OVER_VOLTAGE": None,
    "warnings_CELL_HIGH_TEMPERATURE": None,
    "warnings_CELL_OVER_TEMPERATURE": None,
    "warnings_OVER_CURRENT": None,
    "warnings_CAN": None,
    "warnings_INT_VOLTAGE_MISMATCH": None,
    "warnings_CELLBOARD_COMM": None,
    "warnings_CELLBOARD_INTERNAL": None,
    "warnings_FEEDBACK": None,
    "warnings_FEEDBACK_CIRCUITRY": None,
    "warnings_EEPROM_COMM": None,
    "warnings_EEPROM_WRITE": None,
}

primary_ID_HV_VOLTAGE = dbc_primary.get_message_by_name("HV_VOLTAGE").frame_id
primary_ID_HV_CURRENT = dbc_primary.get_message_by_name("HV_CURRENT").frame_id
primary_ID_HV_ERRORS = dbc_primary.get_message_by_name("HV_ERRORS").frame_id
primary_ID_HV_TEMP = dbc_primary.get_message_by_name("HV_TEMP").frame_id
primary_ID_TS_STATUS = dbc_primary.get_message_by_name("TS_STATUS").frame_id
primary_ID_HV_CELLS_VOLTAGE = dbc_primary.get_message_by_name("HV_CELLS_VOLTAGE").frame_id
primary_ID_HV_CELLS_TEMP = dbc_primary.get_message_by_name("HV_CELLS_TEMP").frame_id
primary_ID_HV_CELL_BALANCING_STATUS = dbc_primary.get_message_by_name("HV_CELL_BALANCING_STATUS").frame_id
primary_ID_HV_FANS_OVERRIDE_STATUS = dbc_primary.get_message_by_name("HV_FANS_OVERRIDE_STATUS").frame_id
