"""The rules of the machine, as tables: where each trigger leads, when a command is refused, what each
state outputs."""

from backend.devices.charger import ChargerCommand
from shared.config import Config
from shared.models import ChargerState, Command, State

from .checks import (
    BMS_HV_STATES,
    bms_fault,
    cell_at_limit,
    charging_message,
    open_point,
    setpoint_problem,
)
from .model import Event, Inputs, Outputs, Trigger

# A FAULT leads to ERROR from every state, so it is not listed here (see ChargeFsm.step).
TRANSITIONS: dict[tuple[State, Trigger], State] = {
    (State.CHECK, Event.DEVICES_READY): State.IDLE,
    (
        State.CHECK,
        Command.BALANCE,
    ): State.BALANCING,  # the charger is not needed to balance
    (State.IDLE, Event.DEVICE_LOST): State.CHECK,
    (State.IDLE, Command.PRECHARGE): State.PRECHARGE,
    (State.IDLE, Command.BALANCE): State.BALANCING,
    (State.PRECHARGE, Event.TS_ON): State.READY,
    (State.PRECHARGE, Event.PRECHARGE_TIMEOUT): State.IDLE,
    (State.PRECHARGE, Event.TS_NOT_REACHED): State.IDLE,
    (State.PRECHARGE, Command.STOP): State.IDLE,
    (State.READY, Event.TS_OFF): State.IDLE,
    (State.READY, Command.START_CHARGE): State.CHARGE,
    (State.READY, Command.STOP): State.IDLE,
    (State.CHARGE, Event.TS_OFF): State.IDLE,
    (State.CHARGE, Event.CHARGE_COMPLETE): State.CHARGE_DONE,
    (State.CHARGE, Command.PAUSE_CHARGE): State.READY,
    (State.CHARGE, Command.STOP): State.IDLE,
    (State.CHARGE_DONE, Event.TS_OFF): State.IDLE,
    (State.CHARGE_DONE, Event.CHARGE_DONE_TIMEOUT): State.IDLE,
    (
        State.CHARGE_DONE,
        Command.START_CHARGE,
    ): State.CHARGE,  # top-off without a new precharge
    (State.CHARGE_DONE, Command.STOP): State.IDLE,
    (State.BALANCING, Event.BALANCING_DONE): State.IDLE,
    (State.BALANCING, Event.BALANCING_NOT_STARTED): State.IDLE,
    (State.BALANCING, Command.STOP): State.IDLE,
    (State.ERROR, Command.RESET): State.CHECK,
}

# Events that win over an operator command arriving in the same step (no START_CHARGE with the TS
# already off). Every other event loses to the command (PAUSE_CHARGE beats CHARGE_COMPLETE).
OVERRIDE_EVENTS = {Event.DEVICE_LOST, Event.TS_OFF}

# The commands each state accepts, derived from TRANSITIONS so the two cannot disagree
ALLOWED_COMMANDS: dict[State, set[Command]] = {
    state: {trigger for (source, trigger) in TRANSITIONS if source is state and isinstance(trigger, Command)}
    for state in State
}


# Guards: why a command cannot be done now, or None. A command without a guard is always accepted.


def cannot_balance(cfg: Config, inputs: Inputs) -> str | None:
    return None if inputs.bms.connected else "Cannot balance: the BMS is not connected"


def cannot_precharge(cfg: Config, inputs: Inputs) -> str | None:
    point = open_point(cfg, inputs)
    problem = (
        f"shutdown loop open at {point}"
        if point
        else setpoint_problem(cfg.charge, inputs.target_voltage, inputs.max_current)
    )
    if problem is None:
        # The TS would be on for nothing: the charge could not start
        problem = cell_at_limit(cfg, inputs.bms)
    return f"Cannot precharge: {problem}" if problem else None


def cannot_charge(cfg: Config, inputs: Inputs) -> str | None:
    problem = setpoint_problem(cfg.charge, inputs.target_voltage, inputs.max_current)
    if problem is None:
        problem = cell_at_limit(cfg, inputs.bms)
    missing = inputs.bms.cells.count(None)
    if problem is None and missing:
        # Without every cell, the max cell voltage (which ends the charge) is not reliable yet
        problem = f"{missing} cells not read yet"
    return f"Cannot charge: {problem}" if problem else None


def cannot_reset(cfg: Config, inputs: Inputs) -> str | None:
    # With the TS off and the charger unpowered, only the BMS can still tell what is wrong
    problem = bms_fault(cfg, inputs.bms)
    return f"Still present: {problem[1]}" if problem else None


GUARDS = {
    (State.CHECK, Command.BALANCE): cannot_balance,
    (State.IDLE, Command.PRECHARGE): cannot_precharge,
    (State.READY, Command.START_CHARGE): cannot_charge,
    (State.CHARGE_DONE, Command.START_CHARGE): cannot_charge,
    (State.ERROR, Command.RESET): cannot_reset,
}


def command_reason(command: Command, inputs: Inputs) -> str:
    """The operator message once a command is accepted."""
    if command is Command.START_CHARGE:
        return charging_message(inputs)
    return {
        Command.PRECHARGE: "Precharging",
        Command.BALANCE: "Balancing",
        Command.PAUSE_CHARGE: "Charging paused",
        Command.STOP: "Stopped by the operator",
        Command.RESET: "Errors cleared",
    }[command]


# Outputs. Recomputed at every step, so a lost frame or a rebooted device gets the right command again.

#                      TS on  charger                balancing
MODES: dict[State, tuple[bool, ChargerCommand, bool]] = {
    State.CHECK: (False, ChargerCommand.STOP, False),
    State.IDLE: (False, ChargerCommand.STOP, False),
    State.PRECHARGE: (True, ChargerCommand.STOP, False),
    State.READY: (True, ChargerCommand.STOP, False),
    State.CHARGE: (True, ChargerCommand.CHARGE, False),
    State.CHARGE_DONE: (True, ChargerCommand.STOP, False),
    State.BALANCING: (False, ChargerCommand.STOP, True),
    State.ERROR: (False, ChargerCommand.STOP, False),
}

TS_ON_STATES = frozenset(state for state, (ts_on, _, _) in MODES.items() if ts_on)


def outputs(
    cfg: Config,
    state: State,
    entered_at: float,
    inputs: Inputs,
    message: str,
    refusal: str | None,
) -> Outputs:
    ts_on, charger, balancing = MODES[state]
    if state is State.CHECK and inputs.charger.state is ChargerState.ERROR:
        charger = ChargerCommand.RESET_ERRORS  # CHECK waits for the charger to leave its error
    in_error = state is State.ERROR
    return Outputs(
        state=state,
        message=message,
        refusal=refusal,
        ts_on=ts_on,
        charger=charger,
        balancing=balancing,
        sd_relay_closed=not in_error,
        # On error, stop the charger first and cut its power a moment later
        charger_power=not (in_error and inputs.now - entered_at >= cfg.timing.charger_stop_delay),
        discharge=not ts_on and inputs.bms.state not in BMS_HV_STATES,
    )
