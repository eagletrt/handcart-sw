"""HV BMS (TSAC): reads its CAN frames into a BmsSnapshot and builds the commands the handcart sends."""

import logging
import time
from collections.abc import Callable
from functools import partial

from cantools.database.can import Database

from backend.canbus import Frame, Signals, as_float, decode, encode
from shared.config import Accumulator
from shared.models import BmsSnapshot, TsacState

log = logging.getLogger(__name__)


class Bms:
    def __init__(
        self,
        db: Database,
        pack: Accumulator,
        presence_timeout: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._db = db
        self._pack = pack
        self._presence_timeout = presence_timeout
        self._clock = clock
        self._last_seen: float | None = None

        self._state: TsacState | None = None
        self._ts_voltage: float | None = None
        self._pack_voltage: float | None = None
        self._current: float | None = None
        self._power: float | None = None
        self._temp_min: float | None = None
        self._temp_max: float | None = None
        self._temp_average: float | None = None
        self._ts_below_60v: bool | None = None
        self._cells: list[float | None] = [None] * pack.cells
        self._temps: list[float | None] = [None] * pack.temps
        self._balancing = [False] * pack.cells
        self._mainboard_errors: frozenset[str] = frozenset()
        self._cellboard_errors: dict[
            str, frozenset[str]
        ] = {}  # per error message; each covers two cellboards

        # which method reads which frame
        self._handlers: dict[int, Callable[[Signals], None]] = {}
        self._read("TsacStatus", self._on_status)
        self._read("TsacMainboardVoltageInfo", self._on_voltages)
        self._read("TsacMainboardCurrentInfo", self._on_current)
        self._read("TsacMainboardTemperatureInfo", self._on_temperatures)
        self._read("TsacMainboardFeedback", self._on_feedback)
        self._read("TsacMainboardError", self._on_mainboard_errors)
        for name in ("TsacCellboardErrorA", "TsacCellboardErrorB", "TsacCellboardErrorC"):
            self._read(name, partial(self._on_cellboard_errors, name))
        for board in range(pack.cellboards):
            self._read(f"TsacCellboard{board + 1}Voltage", partial(self._on_cell_voltages, board))
            self._read(f"TsacCellboard{board + 1}Temperature", partial(self._on_cell_temperatures, board))
            self._read(f"TsacCellboard{board + 1}Balancing", partial(self._on_cell_balancing, board))

    def on_frame(self, frame: Frame) -> bool:
        """Update from a frame. False if the frame is not from the BMS; raises if it is malformed."""
        handler = self._handlers.get(frame.id)
        if handler is None:
            return False
        if self._last_seen is not None and not self.connected:
            # back after being away: the state it had is old (the AIRs may have opened meanwhile),
            # unknown until its next status
            self._state = None
        handler(decode(self._db, frame))
        self._last_seen = self._clock()
        return True

    @property
    def state(self) -> TsacState | None:
        """The last state the BMS reported; None until then, or if it is not one this code knows."""
        return self._state

    @property
    def connected(self) -> bool:
        return self._last_seen is not None and self._clock() - self._last_seen < self._presence_timeout

    def snapshot(self) -> BmsSnapshot:
        # min, max and average come from the cells: in TsacMainboardVoltageInfo the BMS sends a max stuck at
        # 4.5 V, which made every charge "complete" at once
        known = [v for v in self._cells if v is not None]
        return BmsSnapshot(
            connected=self.connected,
            state=self._state,
            ts_voltage=self._ts_voltage,
            pack_voltage=self._pack_voltage,
            cell_min=min(known, default=None),
            cell_max=max(known, default=None),
            cell_average=sum(known) / len(known) if known else None,
            current=self._current,
            power=self._power,
            temp_min=self._temp_min,
            temp_max=self._temp_max,
            temp_average=self._temp_average,
            ts_below_60v=self._ts_below_60v,
            cells=tuple(self._cells),
            temps=tuple(self._temps),
            balancing=tuple(self._balancing),
            errors=self._mainboard_errors.union(*self._cellboard_errors.values()),
        )

    # commands

    def ts_command(self, on: bool) -> Frame:
        """Ask the BMS to close the AIRs (precharge, then TS on) or to open them."""
        return encode(self._db, "BmsSet", status=int(on))

    def balancing_command(self, start: bool, threshold: float) -> Frame:
        """Start or stop passive balancing: cells above the lowest + threshold (V) are bled."""
        return encode(self._db, "RaspberryTsacBalancingSet", start=int(start), threshold=threshold)

    # frame readers

    def _read(self, message: str, handler: Callable[[Signals], None]) -> None:
        self._handlers[self._db.get_message_by_name(message).frame_id] = handler

    def _on_status(self, s: Signals) -> None:
        name = str(s["mainboardStatus"])
        if name not in TsacState.__members__:
            # a state this code does not know yet (newer firmware or libcan): unknown, never a crash
            log.warning("unknown BMS state %s", name)
            self._state = None
            return
        self._state = TsacState(name)

    def _on_voltages(self, s: Signals) -> None:
        self._ts_voltage = s["ts"]
        self._pack_voltage = s["total"]

    def _on_current(self, s: Signals) -> None:
        self._current = s["current"]
        self._power = s["power"]

    def _on_temperatures(self, s: Signals) -> None:
        self._temp_min = s["min"]
        self._temp_max = s["max"]
        self._temp_average = s["average"]

    def _on_feedback(self, s: Signals) -> None:
        self._ts_below_60v = bool(as_float(s["tsLessThan60V"]))

    def _on_mainboard_errors(self, s: Signals) -> None:
        self._mainboard_errors = _active(s)

    def _on_cellboard_errors(self, message: str, s: Signals) -> None:
        self._cellboard_errors[message] = _active(s)

    # Cell frames are multiplexed: each one carries a group of the board's cells, named cell1, cell2, ...
    # Only the cells in the frame are updated.

    def _on_cell_voltages(self, board: int, s: Signals) -> None:
        first = board * self._pack.cells_per_cellboard
        for cell, value in _cells(s):
            self._cells[first + cell] = value

    def _on_cell_temperatures(self, board: int, s: Signals) -> None:
        first = board * self._pack.temps_per_cellboard
        for cell, value in _cells(s):
            self._temps[first + cell] = value

    def _on_cell_balancing(self, board: int, s: Signals) -> None:
        first = board * self._pack.cells_per_cellboard
        for cell, value in _cells(s):
            self._balancing[first + cell] = bool(value)


def _active(s: Signals) -> frozenset[str]:
    """Names of the flags that are set in an error frame."""
    return frozenset(name for name, value in s.items() if as_float(value))


def _cells(s: Signals) -> list[tuple[int, float]]:
    """(index within the cellboard, value) for every cellN signal of a frame."""
    return [
        (int(name.removeprefix("cell")) - 1, as_float(v)) for name, v in s.items() if name.startswith("cell")
    ]
