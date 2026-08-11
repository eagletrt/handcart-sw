from collections import OrderedDict
from enum import Enum

from cantools.database import Message

from settings import dbc_primary, CAN_MESSAGE_CHECK_ENABLED, dbc_brusa, ACC_CELLBOARD_COUNT

"""
This file should be called only once, when the program starts.

There are no longer any handcart-specific messages:
    * TS on/off  -> ``BmsSet``               (status: bool)
    * balancing  -> ``RaspberryBalancingSet`` (start / target / threshold)
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

    raise KeyError(f"No key found for value \"{value}\"")


def _mid(name: str) -> int:
    """Frame id of a primary message by name."""
    return dbc_primary.get_message_by_name(name).frame_id


def _signal(message_name: str, signal_name: str):
    msg = dbc_primary.get_message_by_name(message_name)
    for s in msg.signals:
        if s.name == signal_name:
            return s
    raise KeyError(f"Signal \"{signal_name}\" not found in \"{message_name}\"")


def _choice_key(message_name: str, signal_name: str, choice_name: str) -> int:
    """Integer value associated to a named choice of an enum signal (case-insensitive)."""
    for k, v in _signal(message_name, signal_name).choices.items():
        if str(v).lower() == choice_name.lower():
            return int(k)
    raise KeyError(f"Choice \"{choice_name}\" not found in {message_name}.{signal_name}")


# TSAC mainboard (accumulator) telemetry
primary_ID_TSAC_STATUS = _mid("TsacStatus")
primary_ID_TSAC_MB_VOLTAGE = _mid("TsacMainboardVoltageInfo")
primary_ID_TSAC_MB_CURRENT = _mid("TsacMainboardCurrentInfo")
primary_ID_TSAC_MB_TEMP = _mid("TsacMainboardTemperatureInfo")
primary_ID_TSAC_MB_ERROR = _mid("TsacMainboardError")
primary_ID_TSAC_MB_FEEDBACK = _mid("TsacMainboardFeedback")
primary_ID_TSAC_MB_VERSION = _mid("TsacMainboardVersion")

# TSAC cellboard telemetry (one frame per cellboard, indexes 0..ACC_CELLBOARD_COUNT-1)
primary_ID_TSAC_CELLBOARD_VOLTAGE = [_mid(f"TsacCellboard{i}Voltage") for i in range(1, ACC_CELLBOARD_COUNT + 1)]
primary_ID_TSAC_CELLBOARD_TEMP = [_mid(f"TsacCellboard{i}Temperature") for i in range(1, ACC_CELLBOARD_COUNT + 1)]
primary_ID_TSAC_CELLBOARD_BALANCING = [_mid(f"TsacCellboard{i}Balancing") for i in range(1, ACC_CELLBOARD_COUNT + 1)]
primary_ID_TSAC_CELLBOARD_VERSION = [_mid(f"TsacCellboard{i}Version") for i in range(1, ACC_CELLBOARD_COUNT + 1)]

# Cellboard errors are packed 2 boards per frame (A: 1&2, B: 3&4, C: 5&6)
primary_ID_TSAC_CELLBOARD_ERROR = [_mid("TsacCellboardErrorA"), _mid("TsacCellboardErrorB"),
                                   _mid("TsacCellboardErrorC")]

# Commands the handcart sends to the accumulator
primary_ID_BMS_SET = _mid("BmsSet")  # status: bool  -> TS on/off
primary_ID_ECU_STATUS = _mid("EcuFsm")  # vehicleStatus/krakenStatus enums -> ECU-alive heartbeat (BMS watchdog)
primary_ID_RASPBERRY_BALANCING_SET = _mid("RaspberryBalancingSet")  # start / target / threshold

# Instantiate some messages of the brusa (legacy charger, dbc still shipped)
message_NLG5_CTL: Message = dbc_brusa.get_message_by_name('NLG5_CTL')
message_NLG5_ST: Message = dbc_brusa.get_message_by_name('NLG5_ST')
message_NLG5_ACT_I: Message = dbc_brusa.get_message_by_name('NLG5_ACT_I')
message_NLG5_ERR: Message = dbc_brusa.get_message_by_name('NLG5_ERR')


class HvStatus(Enum):
    """Mainboard FSM state of the accumulator (TsacStatus.mainboardStatus)."""
    INIT = _choice_key("TsacStatus", "mainboardStatus", "INIT")
    IDLE = _choice_key("TsacStatus", "mainboardStatus", "IDLE")
    ERROR = _choice_key("TsacStatus", "mainboardStatus", "ERROR")
    FLASH = _choice_key("TsacStatus", "mainboardStatus", "FLASH")
    BALANCING = _choice_key("TsacStatus", "mainboardStatus", "BALANCING")
    AIRN_CHECK = _choice_key("TsacStatus", "mainboardStatus", "AIRN_CHECK")
    PRECHARGE = _choice_key("TsacStatus", "mainboardStatus", "PRECHARGE")
    AIRP_CHECK = _choice_key("TsacStatus", "mainboardStatus", "AIRP_CHECK")
    TS_ON = _choice_key("TsacStatus", "mainboardStatus", "TS_ON")


class Toggle(Enum):
    OFF = 0
    ON = 1


class HandcartStatus(Enum):
    """
    Internal states of the handcart backend.

    These used to be sourced from the (now removed) HANDCART_SETTINGS message; the
    handcart no longer broadcasts its state on CAN, so the values are just internal
    identifiers.
    """
    NONE = 0
    CHECK = 1
    IDLE = 2
    PRECHARGE = 3
    READY = 4
    CHARGE = 5
    CHARGE_DONE = 6
    BALANCING = 7
    ERROR = 8


# Errors / feedbacks dictionaries, built from the actual dbc signals so they stay in sync
bms_errors = {s.name: 0 for s in dbc_primary.get_message_by_name("TsacMainboardError").signals}
bms_feedbacks = {s.name: 0 for s in dbc_primary.get_message_by_name("TsacMainboardFeedback").signals}


def _verify_signals(message_name: str, expected: list[str]) -> bool:
    """Check that every name in ``expected`` is a signal of ``message_name``."""
    try:
        names = [s.name for s in dbc_primary.get_message_by_name(message_name).signals]
    except KeyError:
        print(f"[can_classes] missing message: {message_name}")
        return False

    ok = True
    for e in expected:
        if e not in names:
            print(f"[can_classes] {message_name} is missing signal: {e}")
            ok = False
    return ok


def verify_can_messages() -> bool:
    """Sanity check that the loaded primary dbc exposes everything the handcart needs."""
    ok = True
    ok &= _verify_signals("TsacStatus", ["mainboardStatus"])
    ok &= _verify_signals("TsacMainboardVoltageInfo", ["ts", "total", "cellSum", "average", "min", "max"])
    ok &= _verify_signals("TsacMainboardCurrentInfo", ["current", "power"])
    ok &= _verify_signals("TsacMainboardTemperatureInfo", ["min", "max", "average"])
    ok &= _verify_signals("TsacMainboardError", ["overvoltage", "undervoltage", "overtemperature"])
    ok &= _verify_signals("TsacMainboardFeedback", ["tsalGreen"])
    ok &= _verify_signals("TsacCellboard1Voltage", ["group", "cell1"])
    ok &= _verify_signals("TsacCellboard1Temperature", ["group", "cell1"])
    ok &= _verify_signals("TsacCellboard1Balancing", ["cell1"])
    ok &= _verify_signals("BmsSet", ["status"])
    ok &= _verify_signals("RaspberryBalancingSet", ["start", "target", "threshold"])
    return ok


if CAN_MESSAGE_CHECK_ENABLED:
    if not verify_can_messages():
        print("[can_classes] WARNING: primary dbc does not match the messages expected by the handcart")


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
