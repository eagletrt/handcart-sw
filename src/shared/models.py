"""The data backend and frontend share: device snapshots, handcart states, commands and settings."""

from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel

# accumulator


class TsacState(StrEnum):
    """Mainboard states, named as in the libcan DBC (TsacStatus.mainboardStatus)."""

    INIT = "INIT"
    IDLE = "IDLE"
    ERROR = "ERROR"
    FLASH = "FLASH"
    BALANCING = "BALANCING"
    AIRN_CHECK = "AIRN_CHECK"
    PRECHARGE = "PRECHARGE"
    AIRP_CHECK = "AIRP_CHECK"
    TS_ON = "TS_ON"


@dataclass(frozen=True)
class BmsSnapshot:
    connected: bool
    state: TsacState | None
    ts_voltage: float | None  # V, after the AIRs
    pack_voltage: float | None  # V
    cell_min: float | None  # V
    cell_max: float | None  # V
    cell_average: float | None  # V
    current: float | None  # A, positive while charging
    power: float | None  # kW
    temp_min: float | None  # °C
    temp_max: float | None  # °C
    temp_average: float | None  # °C
    ts_below_60v: bool | None
    cells: tuple[float | None, ...]  # V, cellboard by cellboard
    temps: tuple[float | None, ...]  # °C, cellboard by cellboard
    balancing: tuple[bool, ...]  # True for the cells being bled
    errors: frozenset[str]  # active error flags, e.g. "overvoltage", "cellboard4CellOvervoltage"

    @property
    def cell_delta(self) -> float | None:
        if self.cell_min is None or self.cell_max is None:
            return None
        return self.cell_max - self.cell_min


# charger


class ChargerState(StrEnum):
    OFF = "OFF"
    PRECHARGE = "PRECHARGE"
    STANDBY = "STANDBY"
    RUNNING = "RUNNING"
    RUNNING_DERATING = "RUNNING_DERATING"
    RUNNING_VC = "RUNNING_VC"  # constant voltage
    RUNNING_VC_DERATING = "RUNNING_VC_DERATING"
    RUNNING_SHUTDOWN = "RUNNING_SHUTDOWN"
    ERROR = "ERROR"

    @property
    def delivering(self) -> bool:
        return self in (self.RUNNING, self.RUNNING_DERATING, self.RUNNING_VC, self.RUNNING_VC_DERATING)


@dataclass(frozen=True)
class ChargerSnapshot:
    connected: bool
    state: ChargerState | None  # None until the first status, or for an undocumented code
    voltage: float | None  # V, DC output
    current: float | None  # A, DC output, negative while discharging
    grid_voltages: tuple[float | None, float | None, float | None]  # V, per phase
    max_temperature: float | None  # °C, hottest sensor
    errors: frozenset[str]
    warnings: frozenset[str]


# handcart


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


# (point, V) along the shutdown loop, in loop order; None = not read yet
ShutdownLoop = tuple[tuple[str, float | None], ...]


class InputEvent(StrEnum):
    """The handcart's physical controls: four arrow buttons and an encoder that turns and clicks."""

    UP = "UP"
    DOWN = "DOWN"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    PRESS = "PRESS"  # encoder click: confirm
    TURN_CW = "TURN_CW"  # one encoder step clockwise
    TURN_CCW = "TURN_CCW"


# API


class Settings(BaseModel):
    target_voltage: float  # V
    max_current: float  # A
    balancing_threshold: float  # V, cells above the lowest + this are bled


class CommandRequest(BaseModel):
    command: Command


class Fault(StrEnum):
    """Why the handcart went to ERROR, for the picture the UI shows; the message says it in words."""

    MUSHROOM = "MUSHROOM"  # the shutdown loop open at the mushroom
    LOOP_OPEN = "LOOP_OPEN"  # open at another point
    BMS = "BMS"  # errors, or the ERROR state, reported by the BMS
    HOT = "HOT"  # a cell above the temperature limit
    BMS_OFFLINE = "BMS_OFFLINE"  # the BMS stopped answering
    CHARGER = "CHARGER"  # the charger in ERROR
    CHARGER_OFFLINE = "CHARGER_OFFLINE"  # the charger stopped answering
    SETPOINT = "SETPOINT"  # the setpoints went outside the limits while charging


class Status(BaseModel):
    """Everything the UI shows: GET /api/status, and every few hundred ms on /api/ws."""

    state: State
    message: str
    fault: Fault | None = None  # why it is in ERROR; None in every other state
    settings: Settings
    bms: BmsSnapshot
    charger: ChargerSnapshot
    shutdown: ShutdownLoop


class SystemInfo(BaseModel):
    """The System page: this version, what is new on the branch, and what the last update did."""

    version: str  # "4df5420 2026-10-21": commit and date
    branch: str  # the branch the handcart follows
    updates: list[str]  # commits on the branch not installed yet, newest first: "abc1234 feat: ..."
    checked_at: str | None  # "12:23", when the branch was last looked at; None if never yet
    check_problem: str | None  # why the last check failed (no network, ...), or None
    last_update: str | None  # what the last ./handcart.py update did, or None if it never ran
    on_handcart: bool  # False on a computer: update, reboot and shut down are only for the handcart


class StreamMessage(BaseModel):
    """One message on /api/ws: either the status, or a press of the physical controls."""

    status: Status | None = None
    input: InputEvent | None = None
