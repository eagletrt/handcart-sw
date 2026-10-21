"""The charge state machine, rule by rule. Each test reads as one line of the spec."""

from dataclasses import replace

import pytest

from backend.core.fsm import ChargeFsm, Inputs
from backend.devices.charger import ChargerCommand
from shared.models import BmsSnapshot, ChargerSnapshot, ChargerState, Command, State, TsacState

CLOSED_LOOP = (("mushroom", 12.0), ("charger", 12.0), ("bms in", 11.9), ("bms out", 11.9))

BMS = BmsSnapshot(
    connected=True,
    state=TsacState.IDLE,
    ts_voltage=0.0,
    pack_voltage=546.0,
    cell_min=3.77,
    cell_max=3.81,
    cell_average=3.79,
    current=0.0,
    power=0.0,
    temp_min=24.0,
    temp_max=27.0,
    temp_average=25.0,
    ts_below_60v=True,
    cells=(),
    temps=(),
    balancing=(),
    errors=frozenset(),
)
CHARGER = ChargerSnapshot(
    connected=True,
    state=ChargerState.STANDBY,
    voltage=0.0,
    current=0.0,
    grid_voltages=(230.0, 230.0, 230.0),
    max_temperature=30.0,
    errors=frozenset(),
    warnings=frozenset(),
)


class Bench:
    """A ChargeFsm with healthy devices; each test changes only what it is about."""

    def __init__(self, cfg) -> None:
        self.cfg = cfg
        self.now = 0.0
        self.fsm = ChargeFsm(cfg, now=0.0)
        self.bms = BMS
        self.charger = CHARGER
        self.shutdown = CLOSED_LOOP
        self.target = cfg.charge.target_voltage_default
        self.current = cfg.charge.current_default

    def step(self, command: Command | None = None, after: float = 0.1):
        self.now += after
        inputs = Inputs(self.now, self.bms, self.charger, self.shutdown, self.target, self.current, command)
        return self.fsm.step(inputs)

    def go_to(self, state: State):
        """Walk the normal sequence up to a state."""
        out = self.step()  # CHECK -> IDLE
        if state is State.IDLE:
            return out
        self.step(Command.PRECHARGE)
        if state is State.PRECHARGE:
            return self.step()
        self.bms = replace(self.bms, state=TsacState.TS_ON)
        out = self.step()  # -> READY
        if state is State.READY:
            return out
        out = self.step(Command.START_CHARGE)
        assert out.state is state is State.CHARGE
        return out


@pytest.fixture
def bench(cfg) -> Bench:
    return Bench(cfg)


# sequence


def test_waits_in_check_until_both_devices_answer(bench):
    bench.charger = replace(CHARGER, connected=False)
    assert bench.step().state is State.CHECK
    bench.charger = CHARGER
    assert bench.step().state is State.IDLE


def test_resets_a_charger_in_error_before_leaving_check(bench):
    bench.charger = replace(CHARGER, state=ChargerState.ERROR)
    out = bench.step()
    assert out.state is State.CHECK
    assert out.charger is ChargerCommand.RESET_ERRORS


def test_normal_charge(bench):
    out = bench.go_to(State.CHARGE)
    assert out.ts_on and out.charger is ChargerCommand.CHARGE

    bench.charger = replace(CHARGER, state=ChargerState.RUNNING_VC, voltage=bench.target, current=0.05)
    out = bench.step()
    assert out.state is State.CHARGE_DONE
    assert out.ts_on and out.charger is ChargerCommand.STOP


def test_charge_stops_when_a_cell_reaches_the_limit(bench, cfg):
    bench.go_to(State.CHARGE)
    bench.bms = replace(bench.bms, cell_max=cfg.accumulator.max_cell_voltage)
    assert bench.step().state is State.CHARGE_DONE


def test_pause_keeps_the_ts_on(bench):
    bench.go_to(State.CHARGE)
    out = bench.step(Command.PAUSE_CHARGE)
    assert out.state is State.READY and out.ts_on


def test_stop_turns_the_ts_off(bench):
    bench.go_to(State.CHARGE)
    out = bench.step(Command.STOP)
    assert out.state is State.IDLE and not out.ts_on


def test_precharge_gives_up_after_the_timeout(bench, cfg):
    bench.go_to(State.PRECHARGE)
    out = bench.step(after=cfg.timing.bms_response_timeout + 0.1)
    assert out.state is State.IDLE
    assert "did not reach TS_ON" in out.message


def test_ready_goes_back_to_idle_if_the_bms_opens_the_airs(bench):
    bench.go_to(State.READY)
    bench.bms = replace(bench.bms, state=TsacState.IDLE)
    assert bench.step().state is State.IDLE


# commands


def test_a_command_in_the_wrong_state_is_refused_with_a_reason(bench):
    bench.go_to(State.IDLE)
    out = bench.step(Command.START_CHARGE)
    assert out.state is State.IDLE
    assert "not possible" in out.refusal
    assert out.message == out.refusal


def test_precharge_is_refused_with_the_loop_open(bench):
    bench.go_to(State.IDLE)
    bench.shutdown = (("mushroom", 0.0), ("charger", 0.0))
    out = bench.step(Command.PRECHARGE)
    assert out.state is State.IDLE
    assert "open at mushroom" in out.refusal


def test_charging_is_refused_with_a_target_above_the_limit(bench, cfg):
    bench.go_to(State.READY)
    bench.target = cfg.charge.target_voltage_max + 10
    out = bench.step(Command.START_CHARGE)
    assert out.state is State.READY
    assert "outside" in out.refusal


# faults


def assert_stopped_safely(out, reason: str) -> None:
    assert out.state is State.ERROR
    assert reason in out.message
    assert not out.ts_on
    assert out.charger is ChargerCommand.STOP
    assert not out.sd_relay_closed


def test_bms_error_while_charging(bench):
    bench.go_to(State.CHARGE)
    bench.bms = replace(bench.bms, errors=frozenset({"overvoltage"}))
    assert_stopped_safely(bench.step(), "overvoltage")


def test_bms_lost_while_charging(bench):
    bench.go_to(State.CHARGE)
    bench.bms = replace(bench.bms, connected=False)
    assert_stopped_safely(bench.step(), "BMS stopped responding")


def test_charger_lost_while_charging(bench):
    bench.go_to(State.CHARGE)
    bench.charger = replace(bench.charger, connected=False)
    assert_stopped_safely(bench.step(), "charger stopped responding")


def test_charger_error_while_charging(bench):
    bench.go_to(State.CHARGE)
    bench.charger = replace(bench.charger, errors=frozenset({"Error_Overtemperature"}))
    assert_stopped_safely(bench.step(), "Error_Overtemperature")


def test_loop_opening_while_charging(bench):
    bench.go_to(State.CHARGE)
    bench.shutdown = (("mushroom", 0.0), ("charger", 0.0))
    assert_stopped_safely(bench.step(), "open at mushroom")


def test_an_unknown_loop_reading_does_not_trip(bench):
    bench.go_to(State.CHARGE)
    bench.shutdown = (("mushroom", None), ("charger", 6.0))
    assert bench.step().state is State.CHARGE


def test_on_error_the_charger_power_is_cut_after_the_delay(bench, cfg):
    bench.go_to(State.CHARGE)
    bench.charger = replace(bench.charger, connected=False)
    assert bench.step().charger_power  # just stopped
    assert not bench.step(after=cfg.timing.charger_stop_delay + 0.01).charger_power


def test_a_cell_too_hot_stops_everything(bench, cfg):
    bench.go_to(State.CHARGE)
    bench.bms = replace(bench.bms, temp_max=cfg.accumulator.max_temperature + 1)
    out = bench.step()
    assert out.state is State.ERROR
    assert "temperature" in out.message
    assert not out.ts_on and not out.sd_relay_closed

    out = bench.step(Command.RESET)  # still hot: refused
    assert out.state is State.ERROR and "Still present" in out.refusal


def test_reset_is_refused_while_the_cause_is_there(bench):
    bench.go_to(State.CHARGE)
    bench.bms = replace(bench.bms, errors=frozenset({"overvoltage"}))
    bench.step()
    out = bench.step(Command.RESET)
    assert out.state is State.ERROR
    assert "Still present" in out.refusal

    bench.bms = replace(bench.bms, errors=frozenset(), state=TsacState.IDLE)
    assert bench.step(Command.RESET).state is State.CHECK


# balancing


def test_balancing_ends_when_the_bms_is_done(bench):
    bench.go_to(State.IDLE)
    out = bench.step(Command.BALANCE)
    assert out.state is State.BALANCING and out.balancing and not out.ts_on
    assert out.refusal is None

    bench.bms = replace(bench.bms, state=TsacState.BALANCING)
    assert bench.step().state is State.BALANCING
    bench.bms = replace(bench.bms, state=TsacState.IDLE)
    assert bench.step().state is State.IDLE


def test_balancing_without_the_bms_is_refused(bench):
    bench.bms = replace(BMS, connected=False)
    out = bench.step(Command.BALANCE)
    assert out.state is State.CHECK
    assert "BMS is not connected" in out.refusal


def test_balancing_works_without_the_charger(bench):
    bench.charger = replace(CHARGER, connected=False)
    assert bench.step(Command.BALANCE).state is State.BALANCING
    bench.bms = replace(bench.bms, state=TsacState.BALANCING)
    assert bench.step().state is State.BALANCING


# relays


def test_discharge_resistor_only_while_the_ts_is_off(bench):
    assert bench.step().discharge
    bench.go_to(State.PRECHARGE)
    assert not bench.step().discharge


def test_a_refusal_is_not_hidden_by_the_state_message(bench):
    bench.bms = replace(BMS, connected=False)  # CHECK keeps writing "Waiting for the BMS"
    out = bench.step(Command.PRECHARGE)
    assert out.state is State.CHECK
    assert "not possible" in out.message
