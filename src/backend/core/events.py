"""Turns the inputs into events. Nothing here decides a transition: that is rules.TRANSITIONS."""

from shared.config import Config
from shared.models import ChargerState, Fault, State, TsacState

from .checks import (
    BMS_PRECHARGE_STATES,
    bms_fault,
    charge_complete,
    charging_message,
    delivering,
    open_point,
    setpoint_problem,
)
from .model import Event, Inputs
from .rules import TS_ON_STATES

CHARGER_START_TIME = 10.0  # s: charging this long with the charger not delivering is worth telling
CHARGE_DONE_TIMEOUT = 600.0  # s: after a charge, with no new one started, the TS goes off
NOT_DELIVERING = "The charger is not delivering: check its mains supply"


def detect_fault(cfg: Config, state: State, inputs: Inputs) -> tuple[Fault, str] | None:
    """Why the handcart must stop now, as (kind, message), or None."""
    if problem := bms_fault(cfg, inputs.bms):
        return problem
    if state in TS_ON_STATES | {State.BALANCING} and not inputs.bms.connected:
        return Fault.BMS_OFFLINE, "The BMS stopped responding"
    if state in TS_ON_STATES:
        if not inputs.charger.connected:
            return Fault.CHARGER_OFFLINE, "The charger stopped responding"
        # Only the ERROR state trips: HYC_Error flags can be set on a working charger
        if inputs.charger.state is ChargerState.ERROR:
            return Fault.CHARGER, "Charger: " + (", ".join(sorted(inputs.charger.errors)) or "in error")
        if point := open_point(cfg, inputs):
            kind = Fault.MUSHROOM if point == "mushroom" else Fault.LOOP_OPEN
            return kind, f"shutdown loop open at {point}"
    if state is State.CHARGE and (
        setpoints := setpoint_problem(cfg.charge, inputs.target_voltage, inputs.max_current)
    ):
        return Fault.SETPOINT, setpoints
    return None


def detect_events(
    cfg: Config, state: State, inputs: Inputs, elapsed: float, balancing_seen: bool
) -> list[tuple[Event, str]]:
    """The events of this step, each with its message for the operator.

    Most events are reported in every state; TRANSITIONS ignores those that mean nothing in the current one.
    Timeouts depend on the state, since `elapsed` is the time since the current state was entered.
    """
    bms, timing = inputs.bms, cfg.timing
    events: list[tuple[Event, str]] = []

    if not (bms.connected and inputs.charger.connected):
        events.append((Event.DEVICE_LOST, "A device stopped responding"))
    elif inputs.charger.state is not ChargerState.ERROR:
        events.append((Event.DEVICES_READY, "Ready to precharge"))

    if bms.state is TsacState.TS_ON:
        events.append((Event.TS_ON, "TS on"))
    else:
        events.append((Event.TS_OFF, "The BMS turned the TS off"))

    if reason := charge_complete(cfg, inputs):
        events.append((Event.CHARGE_COMPLETE, f"Charge complete: {reason}"))

    if state is State.PRECHARGE and bms.state is not TsacState.TS_ON:
        if bms.state in BMS_PRECHARGE_STATES:
            if elapsed > timing.precharge_timeout:
                events.append(
                    (
                        Event.PRECHARGE_TIMEOUT,
                        f"Precharge not done in {timing.precharge_timeout:g} s",
                    )
                )
        elif elapsed > timing.bms_response_timeout:
            # It never started, or it gave up on the way (its own precharge timeout, for one)
            where = bms.state or "an unknown state"
            events.append((Event.TS_NOT_REACHED, f"The BMS did not reach TS_ON: it is in {where}"))

    if state is State.BALANCING and bms.state is not TsacState.BALANCING:
        if balancing_seen:
            events.append((Event.BALANCING_DONE, "Balancing complete"))
        elif elapsed > timing.bms_response_timeout:
            events.append((Event.BALANCING_NOT_STARTED, "The BMS did not start balancing"))

    if state is State.CHARGE_DONE and elapsed > CHARGE_DONE_TIMEOUT:
        events.append(
            (
                Event.CHARGE_DONE_TIMEOUT,
                f"No new charge in {CHARGE_DONE_TIMEOUT:g} s: TS off",
            )
        )

    return events


def status_message(state: State, inputs: Inputs, elapsed: float, current: str) -> str | None:
    """The operator message for a step without transitions, or None to keep the current one."""
    bms, charger = inputs.bms, inputs.charger
    if state is State.CHECK:
        if not bms.connected:
            return "Waiting for the BMS"
        if not charger.connected:
            return "Waiting for the charger"
        if charger.state is ChargerState.ERROR:
            return "Resetting the charger"
    elif state is State.PRECHARGE and bms.state in BMS_PRECHARGE_STATES:
        return f"Precharging: BMS in {bms.state}"
    elif state is State.CHARGE:
        if not delivering(inputs) and elapsed > CHARGER_START_TIME:
            return NOT_DELIVERING  # not a fault, but the operator must know why the current is 0
        if delivering(inputs) and current == NOT_DELIVERING:
            return charging_message(inputs)  # it started after all
    return None
