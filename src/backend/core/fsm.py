"""Charge state machine: from what the devices report and the operator asks, decides what the handcart does.

No CAN or GPIO here. step() takes the inputs and returns the outputs, so every rule can be tested on a laptop.

    CHECK -> IDLE -> PRECHARGE -> READY -> CHARGE -> CHARGE_DONE
               \\-> BALANCING          any state -> ERROR on a fault
"""

from dataclasses import dataclass
from enum import StrEnum

from backend.devices.bms import BmsSnapshot, TsacState
from backend.devices.charger import ChargerCommand, ChargerSnapshot, ChargerState
from shared.config import Config


class State(StrEnum):
    CHECK = "CHECK"  # waiting for the BMS and the charger
    IDLE = "IDLE"  # both present, TS off
    PRECHARGE = "PRECHARGE"  # the BMS is closing the AIRs
    READY = "READY"  # TS on, not charging
    CHARGE = "CHARGE"
    CHARGE_DONE = "CHARGE_DONE"  # target reached, TS still on
    BALANCING = "BALANCING"  # TS off, the BMS bleeds the highest cells
    ERROR = "ERROR"  # charger stopped, TS off, shutdown open, until a reset


class Command(StrEnum):
    PRECHARGE = "PRECHARGE"
    START_CHARGE = "START_CHARGE"
    PAUSE_CHARGE = "PAUSE_CHARGE"  # back to READY, TS stays on
    BALANCE = "BALANCE"
    STOP = "STOP"  # TS off and back to IDLE
    RESET = "RESET"  # leave ERROR, once its cause is gone


TS_ON_STATES = {State.PRECHARGE, State.READY, State.CHARGE, State.CHARGE_DONE}

ALLOWED = {
    State.CHECK: {Command.BALANCE},
    State.IDLE: {Command.PRECHARGE, Command.BALANCE},
    State.PRECHARGE: {Command.STOP},
    State.READY: {Command.START_CHARGE, Command.STOP},
    State.CHARGE: {Command.PAUSE_CHARGE, Command.STOP},
    State.CHARGE_DONE: {Command.START_CHARGE, Command.STOP},
    State.BALANCING: {Command.STOP},
    State.ERROR: {Command.RESET},
}

# BMS states with the AIRs (partly) closed: the TS discharge resistor must stay out
BMS_HV_STATES = {TsacState.AIRN_CHECK, TsacState.PRECHARGE, TsacState.AIRP_CHECK, TsacState.TS_ON}

DONE_CURRENT = 0.1  # A: at the target voltage and below this current, the charge is complete
DONE_VOLTAGE_MARGIN = 1.0  # V: this close to the target counts as reached


@dataclass(frozen=True)
class Inputs:
    now: float  # s, monotonic clock
    bms: BmsSnapshot
    charger: ChargerSnapshot
    shutdown: tuple[tuple[str, float | None], ...]  # (point, V) along the loop, in order; None = not read yet
    target_voltage: float  # V, chosen by the operator
    max_current: float  # A, chosen by the operator
    command: Command | None = None


@dataclass(frozen=True)
class Outputs:
    state: State
    message: str  # for the operator: what is happening, or why a command was refused
    ts_on: bool  # ask the BMS to close the AIRs
    charger: ChargerCommand
    balancing: bool  # ask the BMS to balance
    sd_relay_closed: bool
    charger_power: bool  # PON
    discharge: bool  # TS discharge resistor engaged


class ChargeFsm:
    def __init__(self, config: Config, now: float) -> None:
        self._cfg = config
        self.state = State.CHECK
        self.message = "Waiting for the BMS and the charger"
        self._since = now  # when the current state was entered
        self._balancing_seen = False  # the BMS has reported BALANCING since balancing was asked
        self._handlers = {
            State.CHECK: self._check,
            State.IDLE: self._idle,
            State.PRECHARGE: self._precharge,
            State.READY: self._ready,
            State.CHARGE: self._charge,
            State.CHARGE_DONE: self._charge_done,
            State.BALANCING: self._balancing,
            State.ERROR: self._error,
        }

    def step(self, inputs: Inputs) -> Outputs:
        command = inputs.command
        if command is not None and command not in ALLOWED[self.state]:
            self.message = f"{command} is not possible in {self.state}"
            command = None

        fault = None if self.state is State.ERROR else self._fault(inputs)
        if fault:
            self._go(State.ERROR, inputs.now, fault)
        elif command is Command.STOP:
            self._go(State.IDLE, inputs.now, "Stopped by the operator")
        else:
            self._handlers[self.state](inputs, command)

        return self._outputs(inputs)

    # one method per state: what makes it move on

    def _check(self, inputs: Inputs, command: Command | None) -> None:
        if command is Command.BALANCE and inputs.bms.connected:
            self._start_balancing(inputs)  # the charger is not needed to balance
        elif not inputs.bms.connected:
            self.message = "Waiting for the BMS"
        elif not inputs.charger.connected:
            self.message = "Waiting for the charger"
        elif inputs.charger.state is ChargerState.ERROR:
            self.message = "Resetting the charger"  # _outputs sends RESET_ERRORS while we wait here
        else:
            self._go(State.IDLE, inputs.now, "Ready to precharge")

    def _idle(self, inputs: Inputs, command: Command | None) -> None:
        if not (inputs.bms.connected and inputs.charger.connected):
            self._go(State.CHECK, inputs.now, "A device stopped responding")
        elif command is Command.PRECHARGE:
            problem = self._open_point(inputs) or self._setpoint_problem(inputs)
            if problem:
                self.message = f"Cannot precharge: {problem}"
            else:
                self._go(State.PRECHARGE, inputs.now, "Precharging")
        elif command is Command.BALANCE:
            self._start_balancing(inputs)

    def _precharge(self, inputs: Inputs, command: Command | None) -> None:
        if inputs.bms.state is TsacState.TS_ON:
            self._go(State.READY, inputs.now, "TS on")
        elif inputs.now - self._since > self._cfg.timing.bms_response_timeout:
            self._go(
                State.IDLE,
                inputs.now,
                f"The BMS did not reach TS_ON in {self._cfg.timing.bms_response_timeout:g} s",
            )

    def _ready(self, inputs: Inputs, command: Command | None) -> None:
        if inputs.bms.state is not TsacState.TS_ON:
            self._go(State.IDLE, inputs.now, "The BMS turned the TS off")
        elif command is Command.START_CHARGE:
            self._start_charging(inputs)

    def _charge(self, inputs: Inputs, command: Command | None) -> None:
        if inputs.bms.state is not TsacState.TS_ON:
            self._go(State.IDLE, inputs.now, "The BMS turned the TS off")
        elif command is Command.PAUSE_CHARGE:
            self._go(State.READY, inputs.now, "Charging paused")
        elif self._charge_complete(inputs):
            self._go(State.CHARGE_DONE, inputs.now, "Charge complete")

    def _charge_done(self, inputs: Inputs, command: Command | None) -> None:
        if inputs.bms.state is not TsacState.TS_ON:
            self._go(State.IDLE, inputs.now, "The BMS turned the TS off")
        elif command is Command.START_CHARGE:
            self._start_charging(inputs)

    def _balancing(self, inputs: Inputs, command: Command | None) -> None:
        if inputs.bms.state is TsacState.BALANCING:
            self._balancing_seen = True
        elif self._balancing_seen:
            self._go(State.IDLE, inputs.now, "Balancing complete")
        elif inputs.now - self._since > self._cfg.timing.bms_response_timeout:
            self._go(State.IDLE, inputs.now, "The BMS did not start balancing")

    def _error(self, inputs: Inputs, command: Command | None) -> None:
        if command is Command.RESET:
            # with the TS off and the charger unpowered, only the BMS can still tell what is wrong
            problem = self._bms_fault(inputs.bms)
            if problem:
                self.message = f"Still present: {problem}"
            else:
                self._go(State.CHECK, inputs.now, "Errors cleared")

    # transitions

    def _go(self, state: State, now: float, message: str) -> None:
        self.state = state
        self.message = message
        self._since = now

    def _start_charging(self, inputs: Inputs) -> None:
        problem = self._setpoint_problem(inputs)
        if problem:
            self.message = f"Cannot charge: {problem}"
        else:
            self._go(
                State.CHARGE,
                inputs.now,
                f"Charging to {inputs.target_voltage:g} V, at most {inputs.max_current:g} A",
            )

    def _start_balancing(self, inputs: Inputs) -> None:
        self._balancing_seen = False
        self._go(State.BALANCING, inputs.now, "Balancing")

    # checks

    def _fault(self, inputs: Inputs) -> str | None:
        """Why the handcart must stop now, or None."""
        if problem := self._bms_fault(inputs.bms):
            return problem
        if self.state in TS_ON_STATES | {State.BALANCING} and not inputs.bms.connected:
            return "The BMS stopped responding"
        if self.state in TS_ON_STATES:
            if not inputs.charger.connected:
                return "The charger stopped responding"
            if inputs.charger.state is ChargerState.ERROR or inputs.charger.errors:
                return "Charger: " + (", ".join(sorted(inputs.charger.errors)) or "in error")
            if point := self._open_point(inputs):
                return point
        if self.state is State.CHARGE and (problem := self._setpoint_problem(inputs)):
            return problem
        return None

    @staticmethod
    def _bms_fault(bms: BmsSnapshot) -> str | None:
        if bms.errors:
            return "BMS: " + ", ".join(sorted(bms.errors))
        if bms.state is TsacState.ERROR:
            return "BMS in error"
        return None

    def _open_point(self, inputs: Inputs) -> str | None:
        """The first point of the shutdown loop that reads open, if any. Unknown readings never trip."""
        for point, volts in inputs.shutdown:
            if volts is not None and volts < self._cfg.shutdown.open_below:
                return f"shutdown loop open at {point}"
        return None

    def _setpoint_problem(self, inputs: Inputs) -> str | None:
        low, high = self._cfg.charge.target_voltage_min, self._cfg.charge.target_voltage_max
        if not low <= inputs.target_voltage <= high:
            return f"target {inputs.target_voltage:g} V outside {low:g}-{high:g} V"
        current_max = self._cfg.charge.current_max
        if not 0 < inputs.max_current <= current_max:
            return f"current {inputs.max_current:g} A outside 0-{current_max:g} A"
        return None

    def _charge_complete(self, inputs: Inputs) -> bool:
        b, c = inputs.bms, inputs.charger
        if b.cell_max is not None and b.cell_max >= self._cfg.accumulator.max_cell_voltage:
            return True
        return (
            c.voltage is not None
            and c.current is not None
            and c.voltage >= inputs.target_voltage - DONE_VOLTAGE_MARGIN
            and c.current < DONE_CURRENT
        )

    # outputs

    def _outputs(self, inputs: Inputs) -> Outputs:
        ts_on = self.state in TS_ON_STATES
        in_error = self.state is State.ERROR

        if self.state is State.CHARGE:
            charger = ChargerCommand.CHARGE
        elif self.state is State.CHECK and inputs.charger.state is ChargerState.ERROR:
            charger = ChargerCommand.RESET_ERRORS  # CHECK waits for the charger to leave ERROR
        else:
            charger = ChargerCommand.STOP

        return Outputs(
            state=self.state,
            message=self.message,
            ts_on=ts_on,
            charger=charger,
            balancing=self.state is State.BALANCING,
            sd_relay_closed=not in_error,
            # on error, stop the charger first and cut its power a moment later
            charger_power=not (in_error and inputs.now - self._since >= self._cfg.timing.charger_stop_delay),
            discharge=not ts_on and inputs.bms.state not in BMS_HV_STATES,
        )
