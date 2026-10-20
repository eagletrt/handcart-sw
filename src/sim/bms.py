"""Simulated TSAC accumulator: answers TS and balancing requests and reports its cells like the real BMS."""

import math
import random

from cantools.database.can import Database, Message

from backend.canbus import Frame, decode, encode
from backend.canbus.periodic import Periodic
from shared.config import Accumulator
from shared.models import TsacState

CELL_CAPACITY = 13.5  # Ah
CELL_RESISTANCE = 0.00125  # ohm
BLEED_CURRENT = 0.2  # A through a balancing resistor
ECU_WATCHDOG = 1.0  # s without the EcuFsm heartbeat before the BMS opens the AIRs
AIRN_CHECK_TIME = 0.5  # s
AIRP_CHECK_TIME = 0.3  # s
PRECHARGE_TIME_CONSTANT = 0.4  # s, the TS charging through the precharge resistor
DISCHARGE_TIME_CONSTANT = 0.5  # s, the TS emptying through the discharge resistor

HV_STATES = {TsacState.AIRN_CHECK, TsacState.PRECHARGE, TsacState.AIRP_CHECK, TsacState.TS_ON}


def open_circuit_voltage(state_of_charge: float) -> float:
    """A simple linear cell model: 3.45 V empty, 4.20 V full."""
    return 3.45 + 0.75 * state_of_charge


class SimBms:
    def __init__(self, db: Database, pack: Accumulator, speed: float = 1.0, seed: int = 7) -> None:
        rnd = random.Random(seed)
        self._db = db
        self._pack = pack
        self._speed = speed  # charge and balancing run this many times faster than real life
        self._periodic = Periodic()

        self.state = TsacState.IDLE
        self.ts_voltage = 0.0
        self.current = 0.0
        self.faults: set[str] = set()  # TsacMainboardError flags to report, set from outside to test
        self._state_since = 0.0
        self._soc = [0.46 + rnd.uniform(-0.025, 0.025) for _ in range(pack.cells)]
        self._capacity = [CELL_CAPACITY * rnd.uniform(0.97, 1.03) for _ in range(pack.cells)]
        self._temps = [25 + rnd.uniform(-1.5, 1.5) for _ in range(pack.temps)]
        self._balancing = [False] * pack.cells

        self._ts_requested = False
        self._balancing_requested = False
        self._last_heartbeat = -math.inf

    @property
    def cell_voltages(self) -> list[float]:
        return [open_circuit_voltage(soc) + self.current * CELL_RESISTANCE for soc in self._soc]

    @property
    def pack_voltage(self) -> float:
        return sum(self.cell_voltages)

    # what the handcart sends

    def on_frame(self, frame: Frame, now: float) -> bool:
        try:
            name = self._db.get_message_by_frame_id(frame.id).name
        except KeyError:
            return False
        if name == "BmsSet":
            self._ts_requested = bool(decode(self._db, frame)["status"])
        elif name == "RaspberryTsacBalancingSet":
            self._balancing_requested = bool(decode(self._db, frame)["start"])
        elif name == "EcuFsm":
            self._last_heartbeat = now
        else:
            return False
        return True

    # the accumulator over time

    def tick(self, now: float, dt: float, charge_current: float) -> None:
        self.current = charge_current if self.state is TsacState.TS_ON else 0.0
        self._update_airs(now, dt)
        self._update_balancing(now, dt)
        for cell, soc in enumerate(self._soc):
            self._soc[cell] = soc + self.current * dt * self._speed / 3600 / self._capacity[cell]
        if self.state is TsacState.TS_ON:
            self.ts_voltage = self.pack_voltage
        elif self.state is not TsacState.PRECHARGE:
            self.ts_voltage *= math.exp(-dt / DISCHARGE_TIME_CONSTANT)

    def _update_airs(self, now: float, dt: float) -> None:
        elapsed = now - self._state_since
        lost_ecu = now - self._last_heartbeat > ECU_WATCHDOG
        if self.faults:
            self._enter(TsacState.ERROR, now)
            return
        if self.state is TsacState.ERROR:  # the faults are gone
            self._enter(TsacState.IDLE, now)
            return
        if self.state in HV_STATES and (not self._ts_requested or lost_ecu):
            self._enter(TsacState.IDLE, now)
        elif self.state is TsacState.IDLE and self._ts_requested and not lost_ecu:
            self._enter(TsacState.AIRN_CHECK, now)
        elif self.state is TsacState.AIRN_CHECK and elapsed > AIRN_CHECK_TIME:
            self._enter(TsacState.PRECHARGE, now)
        elif self.state is TsacState.PRECHARGE:
            self.ts_voltage += (self.pack_voltage - self.ts_voltage) * min(1.0, dt / PRECHARGE_TIME_CONSTANT)
            if self.ts_voltage > 0.95 * self.pack_voltage:
                self._enter(TsacState.AIRP_CHECK, now)
        elif self.state is TsacState.AIRP_CHECK and elapsed > AIRP_CHECK_TIME:
            self._enter(TsacState.TS_ON, now)

    def _update_balancing(self, now: float, dt: float) -> None:
        if self.state is TsacState.IDLE and self._balancing_requested:
            self._enter(TsacState.BALANCING, now)
        if self.state is not TsacState.BALANCING:
            self._balancing = [False] * self._pack.cells
            return
        lowest = min(self.cell_voltages)
        self._balancing = [v - lowest > self._pack.balancing_threshold for v in self.cell_voltages]
        if not any(self._balancing) or not self._balancing_requested:
            self._balancing_requested = False
            self._enter(TsacState.IDLE, now)
            return
        for cell, bleeding in enumerate(self._balancing):
            if bleeding:
                self._soc[cell] -= BLEED_CURRENT * dt * self._speed / 3600 / self._capacity[cell]

    def _enter(self, state: TsacState, now: float) -> None:
        if state is not self.state:
            self.state = state
            self._state_since = now

    # what the BMS sends

    def frames(self, now: float) -> list[Frame]:
        """The frames due at this time, each one at its own period."""
        due = self._periodic.due
        pack = self._pack
        frames = []
        if due("status", 0.1, now):
            boards = {f"cellboard{b + 1}Status": "IDLE" for b in range(pack.cellboards)}
            frames.append(encode(self._db, "TsacStatus", mainboardStatus=self.state.value, **boards))
        if due("pack", 0.1, now):
            frames.append(self._pack_voltages())
            power = self.pack_voltage * self.current / 1000
            frames.append(encode(self._db, "TsacMainboardCurrentInfo", current=self.current, power=power))
        if due("temperatures", 0.5, now):
            frames.append(self._pack_temperatures())
        if due("flags", 0.5, now):
            frames.append(self._flags("TsacMainboardFeedback", tsLessThan60V=int(self.ts_voltage < 60)))
            frames.append(self._flags("TsacMainboardError", **{fault: 1 for fault in self.faults}))
            for name in ("TsacCellboardErrorA", "TsacCellboardErrorB", "TsacCellboardErrorC"):
                frames.append(self._flags(name))
        if due("cell voltages", 0.2, now):
            frames += self._cell_frames("Voltage", self.cell_voltages, pack.cells_per_cellboard)
        if due("cell temperatures", 1.0, now):
            frames += self._cell_frames("Temperature", self._temps, pack.temps_per_cellboard)
        if due("balancing", 0.5, now):
            frames += self._balancing_frames()
        return frames

    def _pack_voltages(self) -> Frame:
        cells = self.cell_voltages
        return encode(
            self._db,
            "TsacMainboardVoltageInfo",
            ts=self.ts_voltage,
            total=self.pack_voltage,
            cellSum=sum(cells),
            average=sum(cells) / len(cells),
            min=min(cells),
            max=max(cells),
        )

    def _pack_temperatures(self) -> Frame:
        t = self._temps
        return encode(
            self._db,
            "TsacMainboardTemperatureInfo",
            min=min(t),
            max=max(t),
            average=sum(t) / len(t),
            precharge=25.0,
            linearRegulator=30.0,
        )

    def _flags(self, message: str, **set_flags: int) -> Frame:
        """A frame of flags, all 0 except the ones given."""
        signals = {s.name: 0 for s in self._db.get_message_by_name(message).signals}
        return encode(self._db, message, **(signals | set_flags))

    def _cell_frames(self, kind: str, values: list[float], per_board: int) -> list[Frame]:
        """Cell voltages or temperatures: each cellboard sends its cells a group at a time, one frame each."""
        frames = []
        for board in range(self._pack.cellboards):
            message = self._db.get_message_by_name(f"TsacCellboard{board + 1}{kind}")
            first = board * per_board
            for group, names in _cells_by_group(message).items():
                cells = {name: values[first + int(name.removeprefix("cell")) - 1] for name in names}
                frames.append(encode(self._db, message.name, group=group, **cells))
        return frames

    def _balancing_frames(self) -> list[Frame]:
        """One frame per cellboard, with a flag for each of its cells."""
        per_board = self._pack.cells_per_cellboard
        frames = []
        for board in range(self._pack.cellboards):
            first = board * per_board
            flags = {f"cell{n + 1}": int(self._balancing[first + n]) for n in range(per_board)}
            frames.append(encode(self._db, f"TsacCellboard{board + 1}Balancing", **flags))
        return frames


def _cells_by_group(message: Message) -> dict[int, list[str]]:
    """The cellN signals carried by each value of the multiplexer (the `group` signal)."""
    groups: dict[int, list[str]] = {}
    for signal in message.signals:
        for group in signal.multiplexer_ids or []:
            groups.setdefault(group, []).append(signal.name)
    return groups
