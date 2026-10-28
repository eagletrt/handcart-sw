"""Pure checks on the inputs. None of them depends on the state of the machine."""

from shared.config import Charge, Config
from shared.models import BmsSnapshot, Fault, TsacState

from .model import Inputs

# BMS states with the AIRs (partly) closed: the TS discharge resistor must stay out
BMS_HV_STATES = {
    TsacState.AIRN_CHECK,
    TsacState.PRECHARGE,
    TsacState.AIRP_CHECK,
    TsacState.TS_ON,
}
# BMS states on the way to TS_ON: the BMS has its own precharge timeout, so we keep waiting
BMS_PRECHARGE_STATES = {TsacState.AIRN_CHECK, TsacState.PRECHARGE, TsacState.AIRP_CHECK}

DONE_CURRENT = 0.1  # A: at the target voltage and below this current, the charge is complete
DONE_VOLTAGE_MARGIN = 1.0  # V: this close to the target counts as reached


def bms_fault(cfg: Config, bms: BmsSnapshot) -> tuple[Fault, str] | None:
    """A fault reported by the BMS or read from the cells, as (kind, message), or None."""
    limit = cfg.accumulator.max_temperature
    if bms.errors:
        return Fault.BMS, "BMS: " + ", ".join(sorted(bms.errors))
    if bms.state is TsacState.ERROR:
        return Fault.BMS, "BMS in error"
    if bms.temp_max is not None and bms.temp_max > limit:
        return Fault.HOT, f"Cell temperature {bms.temp_max:.1f} °C, above {limit:g} °C"
    return None


def open_point(cfg: Config, inputs: Inputs) -> str | None:
    """The first point of the shutdown loop that reads open, or None. Unknown readings never trip."""
    for point, volts in inputs.shutdown:
        if volts is not None and volts < cfg.shutdown.open_below:
            return point
    return None


def setpoint_problem(limits: Charge, target_voltage: float, max_current: float) -> str | None:
    """Why the operator's setpoints cannot be used, or None."""
    low, high = limits.target_voltage_min, limits.target_voltage_max
    if not low <= target_voltage <= high:
        return f"target {target_voltage:g} V outside {low:g}-{high:g} V"
    if not 0 < max_current <= limits.current_max:
        return f"current {max_current:g} A outside 0-{limits.current_max:g} A"
    return None


def cell_at_limit(cfg: Config, bms: BmsSnapshot) -> str | None:
    """Why the cells cannot take more charge, or None."""
    limit = cfg.accumulator.max_cell_voltage
    if bms.cell_max is not None and bms.cell_max >= limit:
        return f"a cell is at {bms.cell_max:.3f} V (limit {limit:g} V)"
    return None


def charge_complete(cfg: Config, inputs: Inputs) -> str | None:
    """Why the charge is complete, or None."""
    charger = inputs.charger
    if full := cell_at_limit(cfg, inputs.bms):
        return full
    # Only while the charger delivers: before it starts (STANDBY) the current is 0 too
    if (
        delivering(inputs)
        and charger.voltage is not None
        and charger.current is not None
        and charger.voltage >= inputs.target_voltage - DONE_VOLTAGE_MARGIN
        and charger.current < DONE_CURRENT
    ):
        return f"{charger.voltage:.1f} V reached, current below {DONE_CURRENT:g} A"
    return None


def delivering(inputs: Inputs) -> bool:
    return inputs.charger.state is not None and inputs.charger.state.delivering


def charging_message(inputs: Inputs) -> str:
    return f"Charging to {inputs.target_voltage:g} V, at most {inputs.max_current:g} A"
