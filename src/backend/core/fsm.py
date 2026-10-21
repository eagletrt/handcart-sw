"""Charge state machine: from what the devices report and the operator asks, decides what the handcart does.

No CAN or GPIO here. step() takes the inputs and returns the outputs, so every rule can be tested off the Pi.

    CHECK -> IDLE -> PRECHARGE -> READY -> CHARGE -> CHARGE_DONE
               \\-> BALANCING          any state -> ERROR on a fault
"""

from dataclasses import dataclass

from backend.devices.charger import ChargerCommand
from shared.config import Charge, Config
from shared.models import (
    BmsSnapshot,
    ChargerSnapshot,
    ChargerState,
    Command,
    Fault,
    ShutdownLoop,
    State,
    TsacState,
)

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
# BMS states on the way to TS_ON: the BMS has its own precharge timeout, so we keep waiting
BMS_PRECHARGE_STATES = {TsacState.AIRN_CHECK, TsacState.PRECHARGE, TsacState.AIRP_CHECK}

CHARGER_START_TIME = 10.0  # s: charging for this long with the charger not delivering is worth saying
NOT_DELIVERING = "The charger is not delivering: check its mains supply"
DONE_CURRENT = 0.1  # A: at the target voltage and below this current, the charge is complete
DONE_VOLTAGE_MARGIN = 1.0  # V: this close to the target counts as reached


@dataclass(frozen=True)
class Inputs:
    now: float  # s, monotonic clock
    bms: BmsSnapshot
    charger: ChargerSnapshot
    shutdown: ShutdownLoop
    target_voltage: float  # V, chosen by the operator
    max_current: float  # A, chosen by the operator
    command: Command | None = None


@dataclass(frozen=True)
class Outputs:
    state: State
    message: str  # for the operator: what is happening, or why a command was refused
    refusal: str | None  # why the command of this step was refused; None if accepted or no command
    ts_on: bool  # ask the BMS to close the AIRs
    charger: ChargerCommand
    balancing: bool  # ask the BMS to balance
    sd_relay_closed: bool
    charger_power: bool  # PON
    discharge: bool  # TS discharge resistor engaged


def setpoint_problem(limits: Charge, target_voltage: float, max_current: float) -> str | None:
    """Why the operator's setpoints cannot be used, or None."""
    low, high = limits.target_voltage_min, limits.target_voltage_max
    if not low <= target_voltage <= high:
        return f"target {target_voltage:g} V outside {low:g}-{high:g} V"
    if not 0 < max_current <= limits.current_max:
        return f"current {max_current:g} A outside 0-{limits.current_max:g} A"
    return None


class ChargeFsm:
    def __init__(self, config: Config, now: float) -> None:
        self._cfg = config
        self.state = State.CHECK
        self.message = "Waiting for the BMS and the charger"
        self._since = now  # when the current state was entered
        self.fault: Fault | None = None  # why it is in ERROR
        self._refusal: str | None = None  # why the command of the current step was refused
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
        self._refusal = None
        if command is not None and command not in ALLOWED[self.state]:
            self._refusal = f"{command} is not possible in {self.state}"
            command = None

        state_before = self.state
        fault = None if self.state is State.ERROR else self._fault(inputs)
        if fault:
            kind, message = fault
            self._go(State.ERROR, inputs.now, message)
            self.fault = kind
        elif command is Command.STOP:
            self._go(State.IDLE, inputs.now, "Stopped by the operator")
        else:
            self._handlers[self.state](inputs, command)

        if self._refusal and self.state is state_before:
            self.message = self._refusal  # the operator must see why the command did nothing
        return self._outputs(inputs)

    # one method per state: what makes it move on

    def _check(self, inputs: Inputs, command: Command | None) -> None:
        if command is Command.BALANCE and inputs.bms.connected:
            self._start_balancing(inputs)  # the charger is not needed to balance
        elif command is Command.BALANCE:
            self._refusal = "Cannot balance: the BMS is not connected"
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
            point = self._open_point(inputs)
            problem = f"shutdown loop open at {point}" if point else self._setpoint_problem(inputs)
            if problem:
                self._refusal = f"Cannot precharge: {problem}"
            else:
                self._go(State.PRECHARGE, inputs.now, "Precharging")
        elif command is Command.BALANCE:
            self._start_balancing(inputs)

    def _precharge(self, inputs: Inputs, command: Command | None) -> None:
        if inputs.bms.state is TsacState.TS_ON:
            self._go(State.READY, inputs.now, "TS on")
        elif inputs.bms.state in BMS_PRECHARGE_STATES:
            limit = self._cfg.timing.precharge_timeout
            if inputs.now - self._since > limit:  # the BMS stuck on the way: give up, the TS goes off
                self._go(State.IDLE, inputs.now, f"Precharge not done in {limit:g} s")
            else:
                self.message = f"Precharging: BMS in {inputs.bms.state}"
        elif inputs.now - self._since > self._cfg.timing.bms_response_timeout:
            # it never started, or it stopped on the way (back to IDLE, its own precharge timeout...)
            self._go(
                State.IDLE,
                inputs.now,
                f"The BMS did not reach TS_ON: it is in {inputs.bms.state or 'an unknown state'}",
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
        elif reason := self._charge_complete(inputs):
            self._go(State.CHARGE_DONE, inputs.now, f"Charge complete: {reason}")
        elif not self._delivering(inputs) and inputs.now - self._since > CHARGER_START_TIME:
            # not a fault (the TS is on, nothing is at risk), but the operator must know why 0 A
            self.message = NOT_DELIVERING
        elif self._delivering(inputs) and self.message == NOT_DELIVERING:
            self.message = self._charging_message(inputs)  # it started after all

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
                self._refusal = f"Still present: {problem[1]}"
            else:
                self._go(State.CHECK, inputs.now, "Errors cleared")

    # transitions

    def _go(self, state: State, now: float, message: str) -> None:
        self.state = state
        self.message = message
        self._since = now
        self.fault = None  # set right after, when the state is ERROR

    def _start_charging(self, inputs: Inputs) -> None:
        problem = self._setpoint_problem(inputs)
        missing = inputs.bms.cells.count(None)
        if problem is None and missing:
            # the cell max (which stops the charge at the limit) is not complete yet: a moment after the
            # BMS connects, until every group of cells has arrived
            problem = f"{missing} cells not read yet"
        if problem:
            self._refusal = f"Cannot charge: {problem}"
        else:
            self._go(State.CHARGE, inputs.now, self._charging_message(inputs))

    def _start_balancing(self, inputs: Inputs) -> None:
        self._balancing_seen = False
        self._go(State.BALANCING, inputs.now, "Balancing")

    # checks

    def _fault(self, inputs: Inputs) -> tuple[Fault, str] | None:
        """Why the handcart must stop now, as (kind, message for the operator), or None."""
        if problem := self._bms_fault(inputs.bms):
            return problem
        if self.state in TS_ON_STATES | {State.BALANCING} and not inputs.bms.connected:
            return Fault.BMS_OFFLINE, "The BMS stopped responding"
        if self.state in TS_ON_STATES:
            if not inputs.charger.connected:
                return Fault.CHARGER_OFFLINE, "The charger stopped responding"
            # only the ERROR state trips, as on master: HYC_Error flags can be set on a working charger
            if inputs.charger.state is ChargerState.ERROR:
                return Fault.CHARGER, "Charger: " + (", ".join(sorted(inputs.charger.errors)) or "in error")
            if point := self._open_point(inputs):
                kind = Fault.MUSHROOM if point == "mushroom" else Fault.LOOP_OPEN
                return kind, f"shutdown loop open at {point}"
        if self.state is State.CHARGE and (setpoints := self._setpoint_problem(inputs)):
            return Fault.SETPOINT, setpoints
        return None

    def _bms_fault(self, bms: BmsSnapshot) -> tuple[Fault, str] | None:
        limit = self._cfg.accumulator.max_temperature
        if bms.errors:
            return Fault.BMS, "BMS: " + ", ".join(sorted(bms.errors))
        if bms.state is TsacState.ERROR:
            return Fault.BMS, "BMS in error"
        if bms.temp_max is not None and bms.temp_max > limit:
            return Fault.HOT, f"Cell temperature {bms.temp_max:.1f} °C, above {limit:g} °C"
        return None

    def _open_point(self, inputs: Inputs) -> str | None:
        """The first point of the shutdown loop that reads open, if any. Unknown readings never trip."""
        for point, volts in inputs.shutdown:
            if volts is not None and volts < self._cfg.shutdown.open_below:
                return point
        return None

    def _setpoint_problem(self, inputs: Inputs) -> str | None:
        return setpoint_problem(self._cfg.charge, inputs.target_voltage, inputs.max_current)

    def _charge_complete(self, inputs: Inputs) -> str | None:
        """Why the charge is complete, or None."""
        b, c = inputs.bms, inputs.charger
        limit = self._cfg.accumulator.max_cell_voltage
        if b.cell_max is not None and b.cell_max >= limit:
            return f"a cell is at {b.cell_max:.3f} V (limit {limit:g} V)"
        # Only while the charger delivers: before it starts (STANDBY) the current is 0 too.
        if (
            self._delivering(inputs)
            and c.voltage is not None
            and c.current is not None
            and c.voltage >= inputs.target_voltage - DONE_VOLTAGE_MARGIN
            and c.current < DONE_CURRENT
        ):
            return f"{c.voltage:.1f} V reached, current below {DONE_CURRENT:g} A"
        return None

    def _charging_message(self, inputs: Inputs) -> str:
        return f"Charging to {inputs.target_voltage:g} V, at most {inputs.max_current:g} A"

    def _delivering(self, inputs: Inputs) -> bool:
        return inputs.charger.state is not None and inputs.charger.state.delivering

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
            refusal=self._refusal,
            ts_on=ts_on,
            charger=charger,
            balancing=self.state is State.BALANCING,
            sd_relay_closed=not in_error,
            # on error, stop the charger first and cut its power a moment later
            charger_power=not (in_error and inputs.now - self._since >= self._cfg.timing.charger_stop_delay),
            discharge=not ts_on and inputs.bms.state not in BMS_HV_STATES,
        )
