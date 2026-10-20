"""alpitronic LittleSIC charger: reads its HYC_* frames into a ChargerSnapshot and builds its commands."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum

from cantools.database.can import Database

from backend.canbus import Frame, Signals, as_float, decode, encode

# In LittleSIC.dbc every flag of these two messages has scale 0, so a normal decode turns each set
# bit into 0. They are decoded raw until the DBC is fixed; tests/test_dbc_contract.py keeps an eye on it.
RAW_MESSAGES = ("HYC_Error", "HYC_Warning")


class ChargerState(IntEnum):
    """HYC_Status.status codes."""

    OFF = 0x00
    PRECHARGE = 0x01
    STANDBY = 0x03
    RUNNING = 0x06
    RUNNING_DERATING = 0x07
    RUNNING_VC = 0x08  # constant voltage
    RUNNING_VC_DERATING = 0x09
    RUNNING_SHUTDOWN = 0x0A
    ERROR = 0xFF

    @property
    def delivering(self) -> bool:
        return self in (self.RUNNING, self.RUNNING_DERATING, self.RUNNING_VC, self.RUNNING_VC_DERATING)


class ChargerCommand(IntEnum):
    """HYC_Ctrl.ctrlCmd codes."""

    STOP = 0x00
    RESET_ERRORS = 0x01
    CHARGE = 0x02
    DISCHARGE = 0x04


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


class LittleSic:
    def __init__(
        self, db: Database, presence_timeout: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._db = db
        self._presence_timeout = presence_timeout
        self._clock = clock
        self._last_seen: float | None = None

        self._state: ChargerState | None = None
        self._voltage: float | None = None
        self._current: float | None = None
        self._grid: tuple[float | None, float | None, float | None] = (None, None, None)
        self._temperatures: dict[str, float] = {}  # every sensor, by signal name
        self._errors: frozenset[str] = frozenset()
        self._warnings: frozenset[str] = frozenset()

        # which method reads which frame
        self._handlers: dict[int, Callable[[Signals], None]] = {}
        self._read("HYC_Status", self._on_status)
        self._read("HYC_Actual", self._on_actual)
        self._read("HYC_Grid_Voltage", self._on_grid)
        self._read("HYC_Temperature", self._on_temperatures)
        self._read("HYC_Maintenance2", self._on_temperatures)
        self._read("HYC_Error", self._on_errors)
        self._read("HYC_Warning", self._on_warnings)
        self._read("HYC_Version", lambda s: None)  # only a sign of life
        self._raw_ids = {db.get_message_by_name(name).frame_id for name in RAW_MESSAGES}

    def on_frame(self, frame: Frame) -> bool:
        """Update from a frame. False if the frame is not from the charger; raises if it is malformed."""
        handler = self._handlers.get(frame.id)
        if handler is None:
            return False
        handler(decode(self._db, frame, scaling=frame.id not in self._raw_ids))
        self._last_seen = self._clock()
        return True

    @property
    def connected(self) -> bool:
        return self._last_seen is not None and self._clock() - self._last_seen < self._presence_timeout

    def snapshot(self) -> ChargerSnapshot:
        return ChargerSnapshot(
            connected=self.connected,
            state=self._state,
            voltage=self._voltage,
            current=self._current,
            grid_voltages=self._grid,
            max_temperature=max(self._temperatures.values(), default=None),
            errors=self._errors,
            warnings=self._warnings,
        )

    # commands, all sent periodically

    def control(self, command: ChargerCommand) -> Frame:
        """What the charger should do, sent every few ms."""
        return encode(self._db, "HYC_Ctrl", ctrlCmd=command.value)

    def target(self, voltage: float, current: float) -> Frame:
        """Voltage and current setpoints."""
        return encode(self._db, "HYC_Target", uTarget=voltage, iTarget=current)

    def alive(self, fan_min: int, fan_max: int) -> Frame:
        """Keep-alive, with the fan duty range in percent."""
        return encode(self._db, "HYC_Alive", AliveCnt=0, fanMin=fan_min, fanMax=fan_max)

    # frame readers

    def _read(self, message: str, handler: Callable[[Signals], None]) -> None:
        self._handlers[self._db.get_message_by_name(message).frame_id] = handler

    def _on_status(self, s: Signals) -> None:
        code = int(as_float(s["status"]))
        self._state = ChargerState(code) if code in ChargerState else None

    def _on_actual(self, s: Signals) -> None:
        self._voltage = s["uActual"]
        self._current = s["iActual"]

    def _on_grid(self, s: Signals) -> None:
        self._grid = (s["u1"], s["u2"], s["u3"])

    def _on_temperatures(self, s: Signals) -> None:
        self._temperatures.update((name, as_float(value)) for name, value in s.items())

    def _on_errors(self, s: Signals) -> None:
        self._errors = frozenset(name for name, value in s.items() if value)

    def _on_warnings(self, s: Signals) -> None:
        self._warnings = frozenset(name for name, value in s.items() if value)
