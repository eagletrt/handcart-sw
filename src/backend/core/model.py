"""Data types of the state machine: what goes in, what comes out, and what happens in between."""

from dataclasses import dataclass
from enum import Enum, auto

from backend.devices.charger import ChargerCommand
from shared.models import (
    BmsSnapshot,
    ChargerSnapshot,
    Command,
    Fault,
    ShutdownLoop,
    State,
)


@dataclass(frozen=True)
class Inputs:
    """Everything the machine knows at one step, collected by the backend loop from the devices and the UI."""

    now: float  # s, monotonic clock
    bms: BmsSnapshot
    charger: ChargerSnapshot
    shutdown: ShutdownLoop
    target_voltage: float  # V, set by the operator
    max_current: float  # A, set by the operator
    command: Command | None = None  # operator command received since the previous step


@dataclass(frozen=True)
class Outputs:
    """What the backend applies to the hardware and shows to the operator after one step."""

    state: State
    message: str  # for the operator: what is happening, or why a command was refused
    refusal: str | None  # why this step's command was refused; None if accepted or no command
    ts_on: bool  # ask the BMS to close the AIRs
    charger: ChargerCommand
    balancing: bool  # ask the BMS to balance the cells
    sd_relay_closed: bool  # shutdown relay
    charger_power: bool  # charger PON line
    discharge: bool  # TS discharge resistor engaged


class Event(Enum):
    """Something the inputs show is happening. Detected in events.py, acted on in rules.py."""

    FAULT = auto()  # the handcart must stop now: always leads to ERROR
    DEVICE_LOST = auto()  # the BMS or the charger stopped responding
    DEVICES_READY = auto()  # both respond and the charger is not in error
    TS_ON = auto()  # the BMS reports TS_ON
    TS_OFF = auto()  # the BMS reports anything but TS_ON
    PRECHARGE_TIMEOUT = auto()  # the BMS is stuck on the way to TS_ON
    TS_NOT_REACHED = auto()  # the BMS never started the precharge, or left it
    BALANCING_DONE = auto()
    BALANCING_NOT_STARTED = auto()
    CHARGE_COMPLETE = auto()
    CHARGE_DONE_TIMEOUT = auto()  # no new charge was started after the last one

    def __str__(self) -> str:
        return self.name


# What can move the machine: a detected event or an operator command
Trigger = Event | Command


@dataclass(frozen=True)
class Transition:
    """One change of state, as recorded in ChargeFsm.history."""

    time: float
    source: State
    trigger: Trigger
    target: State
    reason: str  # also shown to the operator
    fault: Fault | None = None  # set when target is ERROR

    def __str__(self) -> str:
        return f"{self.source} --{self.trigger}--> {self.target}: {self.reason}"
