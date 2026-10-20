"""Simulated TSAC accumulator: answers TS and balancing requests and reports its cells like the real BMS."""

import math
import random
from typing import Any

from cantools.database.can import Database

from backend.canbus import Frame, decode, encode
from backend.devices.bms import TsacState
from shared.config import Accumulator
from sim.periodic import Periodic

CELL_CAPACITY = 13.5  # Ah
CELL_RESISTANCE = 0.00125  # ohm
BLEED_CURRENT = 0.2  # A through a balancing resistor
ECU_WATCHDOG = 1.0  # s without the EcuFsm heartbeat before the BMS opens the AIRs
AIRN_CHECK_TIME = 0.5  # s
AIRP_CHECK_TIME = 0.3  # s
PRECHARGE_TIME_CONSTANT = 0.4  # s

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
        if self.state is not TsacState.PRECHARGE:
            self.ts_voltage = self.pack_voltage if self.state is TsacState.TS_ON else self.ts_voltage * 0.9

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
        due = self._periodic.due
        frames = []
        if due("status", 0.1, now):
            boards = {f"cellboard{b + 1}Status": "IDLE" for b in range(self._pack.cellboards)}
            frames.append(encode(self._db, "TsacStatus", mainboardStatus=self.state.value, **boards))
        if due("pack", 0.1, now):
            cells = self.cell_voltages
            frames.append(encode(
                self._db, "TsacMainboardVoltageInfo", ts=self.ts_voltage, total=self.pack_voltage,
                cellSum=sum(cells), average=sum(cells) / len(cells), min=min(cells), max=max(cells),
            ))  # fmt: skip
            power = self.pack_voltage * self.current / 1000
            frames.append(encode(self._db, "TsacMainboardCurrentInfo", current=self.current, power=power))
        if due("temperatures", 0.5, now):
            t = self._temps
            frames.append(encode(
                self._db, "TsacMainboardTemperatureInfo", min=min(t), max=max(t), average=sum(t) / len(t),
                precharge=25.0, linearRegulator=30.0,
            ))  # fmt: skip
        if due("status flags", 0.5, now):
            frames.append(self._flags("TsacMainboardFeedback", tsLessThan60V=int(self.ts_voltage < 60)))
            frames.append(self._flags("TsacMainboardError", **{f: 1 for f in self.faults}))
            for name in ("TsacCellboardErrorA", "TsacCellboardErrorB", "TsacCellboardErrorC"):
                frames.append(self._flags(name))
        if due("cell voltages", 0.2, now):
            frames += self._per_cell_frames("Voltage", self.cell_voltages, self._pack.cells_per_cellboard)
        if due("cell temperatures", 1.0, now):
            frames += self._per_cell_frames("Temperature", self._temps, self._pack.temps_per_cellboard)
        if due("balancing", 0.5, now):
            frames += self._per_cell_frames("Balancing", self._balancing, self._pack.cells_per_cellboard)
        return frames

    def _flags(self, message: str, **set_flags: int) -> Frame:
        """A frame of flags, all 0 except the ones given."""
        signals = {s.name: 0 for s in self._db.get_message_by_name(message).signals}
        return encode(self._db, message, **(signals | set_flags))

    def _per_cell_frames(self, kind: str, values: list[Any], per_board: int) -> list[Frame]:
        """One frame per cellboard, or one per group of cells when the message is multiplexed."""
        frames = []
        for board in range(self._pack.cellboards):
            message = self._db.get_message_by_name(f"TsacCellboard{board + 1}{kind}")
            board_values = values[board * per_board : (board + 1) * per_board]
            groups: dict[int | None, dict[str, Any]] = {}
            for signal in message.signals:
                if signal.name.startswith("cell"):
                    value = board_values[int(signal.name.removeprefix("cell")) - 1]
                    signal_groups: list[int | None] = (
                        list(signal.multiplexer_ids) if signal.multiplexer_ids else [None]
                    )
                    for group in signal_groups:
                        groups.setdefault(group, {})[signal.name] = (
                            int(value) if kind == "Balancing" else value
                        )
            for group, signals in groups.items():
                mux = {} if group is None else {"group": group}
                frames.append(encode(self._db, message.name, **mux, **signals))
        return frames
