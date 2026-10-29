"""The data backend and frontend share: device snapshots, handcart states, commands and settings."""

from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, Field

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


class Sound(StrEnum):
    """What the buzzer can say. The melodies, and which one cuts which, are in backend/sounds."""

    STARTUP = "STARTUP"  # the backend started
    POWER_OFF = "POWER_OFF"  # reboot or shut down asked from the System page
    CONFIRM = "CONFIRM"  # a command reached the backend
    REFUSED = "REFUSED"  # a command was refused: why is on the screen
    PRECHARGE = "PRECHARGE"  # the precharge started: the TS is going on
    DISCHARGE = "DISCHARGE"  # the AIRs opened: the TS goes off, whatever the reason
    TS_ON = "TS_ON"  # the precharge is over: the TS is on
    CHARGE_DONE = "CHARGE_DONE"
    BALANCING_DONE = "BALANCING_DONE"
    FAILED = "FAILED"  # the precharge or the balancing did not happen: why is on the screen
    WARNING = "WARNING"  # not an error, but worth a look: a warm cell, a charger that does not deliver
    ERROR = "ERROR"  # entering ERROR, and again every so often while it lasts
    TICK = "TICK"  # one step of the encoder
    DEVICE_CONNECTED = "DEVICE_CONNECTED"  # the BMS or the charger started answering
    DEVICE_DISCONNECTED = "DEVICE_DISCONNECTED"  # the BMS or the charger stopped answering


# API


class Settings(BaseModel):
    target_voltage: float  # V
    max_current: float  # A
    balancing_threshold: float  # V, cells above the lowest + this are bled


class CommandRequest(BaseModel):
    command: Command


class SoundRequest(BaseModel):
    sound: Sound


LOWEST_TONE, HIGHEST_TONE = 500.0, 8000.0  # Hz: where a piezo buzzer's resonance can be


class ToneRequest(BaseModel):
    """A frequency for the buzzer: a tone to hear, or the resonance found."""

    frequency: float = Field(ge=LOWEST_TONE, le=HIGHEST_TONE)  # Hz
    seconds: float = Field(default=0.4, gt=0, le=3)  # of the tone; the resonance ignores it


class BuzzerInfo(BaseModel):
    resonance: float | None  # Hz where the buzzer is loudest; None until found (Debug window)


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
    balancing_done: bool = False  # back in IDLE because the BMS finished balancing, until the next change
    settings: Settings
    bms: BmsSnapshot
    charger: ChargerSnapshot
    shutdown: ShutdownLoop


class Severity(StrEnum):
    """How much an event matters: the operator sees the critical ones, the rest is there to look into."""

    INFO = "info"  # what happens normally: a command, a setting changed
    NOTICE = "notice"  # worth knowing when looking into a problem: a state change, a device lost
    CRITICAL = "critical"  # the operator must know: the handcart stopped on an error


class RecordedEvent(BaseModel):
    """One event of the record (backend/recorder.py): GET /api/events."""

    id: int
    time: float  # s since 1970
    kind: str  # "transition", "command", "refusal", "device", "errors", "settings", "system"
    severity: Severity
    source: str  # what noticed it: "fsm", "api", "bms", "charger", "backend"
    actor: str | None  # who did it, for what people do: "api" (until there is a login); None: the handcart
    cause_id: int | None  # the event that led to this one, when known: a command and its transition
    summary: str  # one line for the operator
    data: dict  # the details


class Sample(BaseModel):
    """The readings at one moment, while the handcart is doing something: GET /api/samples, for graphs."""

    time: float  # s since 1970
    state: State
    pack_voltage: float | None  # V
    current: float | None  # A, the BMS's
    cell_min: float | None  # V
    cell_max: float | None  # V
    temp_max: float | None  # °C
    charger_voltage: float | None  # V
    charger_current: float | None  # A


class SystemInfo(BaseModel):
    """The System page: this version, what is new on the branch, and what the last update did."""

    version: str  # "4df5420 2026-10-21": commit and date
    branch: str  # the branch the handcart follows
    updates: list[str]  # commits on the branch not installed yet, newest first: "abc1234 feat: ..."
    checked_at: str | None  # "12:23", when the branch was last looked at; None if never yet
    check_problem: str | None  # why the last check failed (no network, ...), or None
    last_update: str | None  # what the last ./handcart.py update did, or None if it never ran
    on_handcart: bool  # False on a computer: update, reboot and shut down are only for the handcart


class WifiNetwork(BaseModel):
    """One Wi-Fi network in range."""

    ssid: str  # its name
    signal: int  # %, 0-100
    secured: bool  # needs a password
    connected: bool  # the handcart is on it now
    saved: bool  # joined before: its password is saved, no need to type it again


class Address(BaseModel):
    """One of the handcart's IPv4 addresses, and what it is on: where to reach it over SSH."""

    name: str  # "Cable", "Wi-Fi", "Hotspot", "Tailscale", or the interface ("usb0") for anything else
    address: str  # "192.168.1.23"


class Hotspot(BaseModel):
    """The Wi-Fi network the handcart makes itself, on the Wi-Fi that is not on a network."""

    on: bool
    ssid: str  # to join it with
    password: str
    address: str | None  # the handcart's on it, "10.42.0.1": None while it is off


class NetworkInfo(BaseModel):
    """The System page's network part: the handcart's addresses and the Wi-Fi networks around."""

    wifi_on: bool  # the Wi-Fi radio is on
    addresses: list[Address]  # cable first, then Wi-Fi, hotspot, Tailscale; empty if it has none
    networks: list[WifiNetwork]  # the connected one first, then the strongest
    hotspot: Hotspot
    problem: str | None  # why the Wi-Fi cannot be read (not on the handcart, ...), or None


class WifiRadioRequest(BaseModel):
    on: bool


class HotspotRequest(BaseModel):
    on: bool


class HotspotDetails(BaseModel):
    """The hotspot's name and password, as changed on the screen (var/hotspot.json)."""

    ssid: str
    password: str


class WifiConnectRequest(BaseModel):
    ssid: str
    password: str | None = None  # None: the saved one, or an open network


class StreamMessage(BaseModel):
    """One message on /api/ws: the status, a press of the physical controls, or a sound the buzzer plays."""

    status: Status | None = None
    input: InputEvent | None = None
    sound: Sound | None = None
