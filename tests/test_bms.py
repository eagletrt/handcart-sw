"""The BMS turns TSAC frames into a snapshot, and builds the commands the handcart sends."""

import pytest

from backend.canbus import Frame
from backend.devices.bms import Bms
from shared.models import TsacState


@pytest.fixture
def bms(primary, cfg, clock) -> Bms:
    return Bms(primary, cfg.accumulator, cfg.timing.bms_presence_timeout, clock)


def _all_flags(primary, message: str, value: int) -> dict[str, int]:
    return {s.name: value for s in primary.get_message_by_name(message).signals}


def test_starts_disconnected_and_empty(bms, cfg):
    snap = bms.snapshot()
    assert not snap.connected
    assert snap.state is None
    assert len(snap.cells) == cfg.accumulator.cells
    assert all(v is None for v in snap.cells)


def test_ignores_frames_from_other_devices(bms):
    assert bms.on_frame(Frame(0x7FF, b"\x00")) is False
    assert not bms.connected


def test_status_and_presence_timeout(bms, bms_frame, clock, cfg):
    assert bms.on_frame(
        bms_frame(
            "TsacStatus",
            mainboardStatus="TS_ON",
            **{f"cellboard{i}Status": "IDLE" for i in range(1, cfg.accumulator.cellboards + 1)},
        )
    )
    assert bms.snapshot().state is TsacState.TS_ON
    assert bms.connected

    clock.now += cfg.timing.bms_presence_timeout + 0.01
    assert not bms.connected


def test_back_after_being_away_its_old_state_is_forgotten(bms, bms_frame, clock, cfg):
    cellboards = {f"cellboard{i}Status": "IDLE" for i in range(1, cfg.accumulator.cellboards + 1)}
    bms.on_frame(bms_frame("TsacStatus", mainboardStatus="PRECHARGE", **cellboards))
    clock.now += cfg.timing.bms_presence_timeout + 0.01
    assert bms.snapshot().state is TsacState.PRECHARGE  # away: still the last one it said
    bms.on_frame(bms_frame("TsacMainboardCurrentInfo", current=0.0, power=0.0))  # back, not its status yet
    assert bms.connected and bms.snapshot().state is None
    bms.on_frame(bms_frame("TsacStatus", mainboardStatus="IDLE", **cellboards))
    assert bms.snapshot().state is TsacState.IDLE


def test_pack_readings(bms, bms_frame):
    # the DBC resolution is 0.5 V for pack voltages and 5 mV for cells
    bms.on_frame(
        bms_frame(
            "TsacMainboardVoltageInfo", ts=545.0, total=546.5, cellSum=546.0, average=3.79, min=3.75, max=3.82
        )
    )
    bms.on_frame(bms_frame("TsacMainboardCurrentInfo", current=8.0, power=4.4))
    snap = bms.snapshot()
    assert snap.pack_voltage == 546.5
    assert snap.current == pytest.approx(8.0, abs=0.1)


def test_cell_stats_come_from_the_cells_not_the_mainboard(bms, bms_frame):
    bms.on_frame(
        bms_frame(
            "TsacMainboardVoltageInfo", ts=545.0, total=546.5, cellSum=546.0, average=4.5, min=4.5, max=4.5
        )
    )
    cells = {"cell1": 3.75, "cell2": 3.80, "cell3": 3.85, "cell4": 3.80, "cell5": 3.80, "cell6": 3.80}
    bms.on_frame(bms_frame("TsacCellboard1Voltage", group=0, **cells))
    snap = bms.snapshot()
    assert snap.cell_min == pytest.approx(3.75, abs=0.01)
    assert snap.cell_max == pytest.approx(3.85, abs=0.01)
    assert snap.cell_average == pytest.approx(3.80, abs=0.01)


def test_cell_voltages_land_in_the_right_cellboard(bms, bms_frame, cfg):
    # group 1 of cellboard 2 carries cells 7..12 of that cellboard
    bms.on_frame(bms_frame("TsacCellboard2Voltage", group=1, **{f"cell{n}": 3.8 for n in range(7, 13)}))
    cells = bms.snapshot().cells
    first = cfg.accumulator.cells_per_cellboard + 6
    assert all(v == pytest.approx(3.8, abs=0.01) for v in cells[first : first + 6])
    assert cells[first - 1] is None and cells[first + 6] is None


def test_temperatures_of_the_last_group(bms, bms_frame, cfg):
    bms.on_frame(bms_frame("TsacCellboard6Temperature", group=9, cell46=30.0, cell47=31.0, cell48=32.0))
    temps = bms.snapshot().temps
    assert temps[-1] == pytest.approx(32.0, abs=0.5)
    assert len(temps) == cfg.accumulator.temps


def test_balancing_cells(bms, bms_frame, primary):
    flags = _all_flags(primary, "TsacCellboard1Balancing", 0) | {"cell3": 1}
    bms.on_frame(bms_frame("TsacCellboard1Balancing", **flags))
    balancing = bms.snapshot().balancing
    assert balancing[2] is True
    assert sum(balancing) == 1


def test_errors_appear_and_clear(bms, bms_frame, primary):
    flags = _all_flags(primary, "TsacMainboardError", 0)
    bms.on_frame(bms_frame("TsacMainboardError", **(flags | {"overvoltage": 1})))
    assert bms.snapshot().errors == {"overvoltage"}

    bms.on_frame(bms_frame("TsacMainboardError", **flags))
    assert bms.snapshot().errors == set()


def test_cellboard_errors_keep_their_board_in_the_name(bms, bms_frame, primary):
    flags = _all_flags(primary, "TsacCellboardErrorB", 0) | {"cellboard4CellOvervoltage": 1}
    bms.on_frame(bms_frame("TsacCellboardErrorB", **flags))
    assert bms.snapshot().errors == {"cellboard4CellOvervoltage"}


def test_commands(bms, primary, cfg):
    def decoded(frame: Frame) -> dict:
        return primary.decode_message(frame.id, frame.data)

    assert decoded(bms.ts_command(True))["status"] == 1
    assert decoded(bms.ts_command(False))["status"] == 0

    balancing = decoded(bms.balancing_command(True, threshold=0.020))
    assert balancing["start"] == 1
    assert balancing["threshold"] == pytest.approx(0.020)


def test_an_unknown_state_is_unknown_not_a_crash(bms, primary):
    status = primary.get_message_by_name("TsacStatus")
    bms.on_frame(Frame(status.frame_id, bytes([0x0F, 0, 0])))  # 15: no such state in the DBC
    snap = bms.snapshot()
    assert snap.state is None
    assert snap.connected  # the BMS is there, only its state is not understood
