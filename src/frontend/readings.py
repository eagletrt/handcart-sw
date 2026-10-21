"""What the readings mean for the operator: plain functions of the status, no UI (tests/test_readings.py)."""

from shared.config import Accumulator
from shared.models import BmsSnapshot, Fault, ShutdownLoop, State, Status

TS_ASKED_ON = {State.PRECHARGE, State.READY, State.CHARGE, State.CHARGE_DONE}


def first_open(loop: ShutdownLoop, open_below: float) -> str | None:
    """The first point of the shutdown loop without voltage: the loop is open just before it."""
    for point, volts in loop:
        if volts is not None and volts < open_below:
            return point
    return None


def overvoltage_cells(bms: BmsSnapshot, max_cell_voltage: float) -> set[int]:
    """The cells read above their limit, by index."""
    return {i for i, volts in enumerate(bms.cells) if volts is not None and volts > max_cell_voltage}


def hot_probes(bms: BmsSnapshot, max_temperature: float) -> set[int]:
    """The temperature probes above the limit, by index."""
    return {i for i, temp in enumerate(bms.temps) if temp is not None and temp > max_temperature}


def cell_overvoltage(bms: BmsSnapshot, max_cell_voltage: float) -> bool:
    """True if a cell is above its limit: read from the cells, or reported by the BMS."""
    if overvoltage_cells(bms, max_cell_voltage):
        return True
    # "overvoltage" from the mainboard, "cellboard1CellOvervoltage" ... from the cellboards
    return any(error == "overvoltage" or error.endswith("CellOvervoltage") for error in bms.errors)


def error_kind(fault: Fault | None, bms: BmsSnapshot, pack: Accumulator) -> str:
    """Which picture explains an error, from why the state machine stopped (Status.fault): "mushroom",
    "offline" (the BMS or the charger stopped answering), "cell" (over its voltage limit), "hot",
    "charger" (in error), "bms" (other BMS errors), or "loop" (open at another point, or anything else).

    Never from the loop read now: in ERROR the handcart opens its SD relay itself, so the loop reads open
    from there on whatever the cause was.
    """
    if fault is Fault.MUSHROOM:
        return "mushroom"
    if fault in (Fault.BMS_OFFLINE, Fault.CHARGER_OFFLINE):
        return "offline"
    if fault is Fault.HOT:
        return "hot"
    if fault is Fault.BMS and cell_overvoltage(bms, pack.max_cell_voltage):
        return "cell"
    if fault is Fault.BMS:
        return "bms"
    if fault is Fault.CHARGER:
        return "charger"
    return "loop"


def balancing_progress(start_delta: float, delta: float, threshold: float) -> float:
    """How far the balancing is, in %: 0 at the delta it started from, 100 at the threshold."""
    if start_delta <= threshold:
        return 100.0
    progress = (start_delta - delta) / (start_delta - threshold) * 100
    return max(0.0, min(100.0, progress))


def ts_discharging(state: State, bms: BmsSnapshot) -> bool:
    """The TS was turned off but still holds 60 V or more: the AIRs are open, the TS is still live.

    Only when the BMS says so: an unknown reading (None) shows as "HV ?" in the top bar instead.
    """
    return state not in TS_ASKED_ON and bms.ts_below_60v is False


def details_screen(fault: Fault | None) -> str:
    """The screen that shows more about an error: "cells", "charger" or "shutdown"."""
    if fault in (Fault.HOT, Fault.BMS, Fault.BMS_OFFLINE):
        return "cells"  # for a silent BMS, what it last sent
    if fault in (Fault.CHARGER, Fault.CHARGER_OFFLINE):
        return "charger"
    return "shutdown"


def waiting_for(status: Status) -> tuple[str, str]:
    """In CHECK, the main button says what is missing: (label, icon)."""
    bms, charger = status.bms.connected, status.charger.connected
    if not bms and not charger:
        return "Connect accumulator and charger", "cable"
    if not bms:
        return "Connect accumulator", "cable"
    if not charger:
        return "Connect charger", "ev_station"
    return "Resetting charger", "restart_alt"  # both there: CHECK waits for the charger to leave ERROR
