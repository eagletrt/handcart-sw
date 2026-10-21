"""What the readings mean for the operator: plain functions of the status, no UI (tests/test_readings.py)."""

from shared.config import Accumulator
from shared.models import BmsSnapshot, ShutdownLoop


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


def error_kind(bms: BmsSnapshot, loop: ShutdownLoop, pack: Accumulator, open_below: float) -> str:
    """Which picture explains an error: "mushroom" (pressed), "cell" (over its voltage limit),
    "hot" (a cell too hot), or "loop" (open somewhere)."""
    if first_open(loop, open_below) == "mushroom":
        return "mushroom"
    if cell_overvoltage(bms, pack.max_cell_voltage):
        return "cell"
    if bms.temp_max is not None and bms.temp_max > pack.max_temperature:
        return "hot"
    return "loop"


def balancing_progress(start_delta: float, delta: float, threshold: float) -> float:
    """How far the balancing is, in %: 0 at the delta it started from, 100 at the threshold."""
    if start_delta <= threshold:
        return 100.0
    progress = (start_delta - delta) / (start_delta - threshold) * 100
    return max(0.0, min(100.0, progress))
