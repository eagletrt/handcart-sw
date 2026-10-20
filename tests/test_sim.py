"""The simulators speak the same protocol as the real devices: the backend's own readers understand them."""

import pytest

from backend.devices.bms import Bms, TsacState
from backend.devices.charger import ChargerCommand, ChargerState, LittleSic
from sim.bms import SimBms
from sim.charger import SimCharger

TICK = 0.01


@pytest.fixture
def sim_bms(primary, cfg) -> SimBms:
    return SimBms(primary, cfg.accumulator)


def run(sim_bms: SimBms, seconds: float, start: float = 0.0, handcart=(), current: float = 0.0) -> float:
    """Advance the simulated BMS, delivering the handcart's frames at every tick. Returns the end time."""
    now = start
    while now < start + seconds:
        now += TICK
        for frame in handcart:
            sim_bms.on_frame(frame, now)
        sim_bms.tick(now, TICK, current)
    return now


def test_bms_frames_are_read_by_the_backend(sim_bms, primary, cfg, clock):
    bms = Bms(primary, cfg.accumulator, cfg.timing.bms_presence_timeout, clock)
    for frame in sim_bms.frames(now=0.0):
        assert bms.on_frame(frame), f"frame {frame.id:#x} not understood"
    snap = bms.snapshot()
    assert snap.state is TsacState.IDLE
    assert None not in snap.cells and None not in snap.temps
    assert snap.pack_voltage == pytest.approx(sum(snap.cells), abs=1)


def test_ts_on_needs_the_request_and_the_ecu_heartbeat(sim_bms, primary, cfg, clock):
    bms = Bms(primary, cfg.accumulator, cfg.timing.bms_presence_timeout, clock)
    ts_on = bms.ts_command(True)

    run(sim_bms, 2.0, handcart=[ts_on])
    assert sim_bms.state is TsacState.IDLE  # no heartbeat: the watchdog keeps the AIRs open

    run(sim_bms, 2.0, handcart=[ts_on, bms.ecu_heartbeat()])
    assert sim_bms.state is TsacState.TS_ON
    assert sim_bms.ts_voltage == pytest.approx(sim_bms.pack_voltage, rel=0.01)


def test_balancing_ends_by_itself(primary, cfg, clock):
    sim_bms = SimBms(primary, cfg.accumulator, speed=1000)
    bms = Bms(primary, cfg.accumulator, cfg.timing.bms_presence_timeout, clock)
    start = bms.balancing_command(True)

    now = run(sim_bms, 0.1, handcart=[start])
    assert sim_bms.state is TsacState.BALANCING
    run(sim_bms, 60, start=now)
    assert sim_bms.state is TsacState.IDLE
    cells = sim_bms.cell_voltages
    assert max(cells) - min(cells) <= cfg.accumulator.balancing_threshold + 0.001


def test_a_fault_puts_the_bms_in_error(sim_bms):
    sim_bms.faults = {"overvoltage"}
    run(sim_bms, 0.1)
    assert sim_bms.state is TsacState.ERROR


def test_charger_frames_are_read_by_the_backend(charger_db, cfg, clock):
    sim = SimCharger(charger_db)
    charger = LittleSic(charger_db, cfg.timing.charger_presence_timeout, clock)

    sim.on_frame(charger.target(590, 6.0))
    sim.on_frame(charger.control(ChargerCommand.CHARGE))
    for _ in range(300):  # 3 s: enough to ramp up to 6 A
        sim.tick(TICK, pack_voltage=550.0)

    for frame in sim.frames(now=0.0):
        assert charger.on_frame(frame), f"frame {frame.id:#x} not understood"
    snap = charger.snapshot()
    assert snap.state is ChargerState.RUNNING
    assert snap.current == pytest.approx(6.0, abs=0.5)
    assert snap.errors == set()


def test_charger_tapers_close_to_the_target(charger_db, cfg, clock):
    sim = SimCharger(charger_db)
    charger = LittleSic(charger_db, cfg.timing.charger_presence_timeout, clock)
    sim.on_frame(charger.target(590, 6.0))
    sim.on_frame(charger.control(ChargerCommand.CHARGE))
    for _ in range(300):
        current = sim.tick(TICK, pack_voltage=589.0)
    assert sim.state is ChargerState.RUNNING_VC
    assert current < 6.0
