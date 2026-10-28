"""The charge state machine: its tables, then rule by rule. Each test reads as one line of the spec."""

from dataclasses import replace

import pytest

from backend.core import ChargeFsm, Event, Inputs
from backend.core.events import CHARGE_DONE_TIMEOUT, CHARGER_START_TIME, NOT_DELIVERING
from backend.core.rules import GUARDS, MODES, OVERRIDE_EVENTS, TRANSITIONS, TS_ON_STATES
from backend.devices.charger import ChargerCommand
from shared.models import BmsSnapshot, ChargerSnapshot, ChargerState, Command, Fault, State, TsacState

CLOSED_LOOP = (("mushroom", 12.0), ("charger", 12.0), ("BMS", 11.9), ("TSMS", 11.9))

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
        if state is State.CHARGE:
            return out
        self.bms = replace(self.bms, cell_max=self.cfg.accumulator.max_cell_voltage)
        out = self.step()
        assert out.state is state is State.CHARGE_DONE
        self.bms = replace(self.bms, cell_max=BMS.cell_max)
        return out


@pytest.fixture
def bench(cfg) -> Bench:
    return Bench(cfg)


# tables


def test_every_state_has_a_mode():
    assert set(MODES) == set(State)


def test_every_guard_has_a_transition():
    assert set(GUARDS) <= set(TRANSITIONS)


def test_every_state_can_get_back_to_idle():
    """No trap states: from anywhere there is a path to IDLE (a FAULT leads to ERROR from any other state)."""
    for start in State:
        seen, todo = {start}, [start]
        while todo:
            current = todo.pop()
            nexts = {target for (source, _), target in TRANSITIONS.items() if source is current}
            if current is not State.ERROR:
                nexts.add(State.ERROR)
            for target in nexts - seen:
                seen.add(target)
                todo.append(target)
        assert State.IDLE in seen, f"{start} cannot get back to IDLE"


def test_ts_on_states_leave_when_the_bms_turns_the_ts_off():
    # PRECHARGE waits for TS_ON, with its own timeouts
    for state in TS_ON_STATES - {State.PRECHARGE}:
        assert (state, Event.TS_OFF) in TRANSITIONS, state


def test_stop_from_every_active_state():
    for state in TS_ON_STATES | {State.BALANCING}:
        assert TRANSITIONS.get((state, Command.STOP)) is State.IDLE, state


def test_overriding_events_never_lead_to_a_ts_on_state():
    for (source, trigger), target in TRANSITIONS.items():
        if trigger in OVERRIDE_EVENTS:
            assert target not in TS_ON_STATES, (source, trigger, target)


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


def test_charge_is_not_complete_before_the_charger_starts(bench):
    bench.go_to(State.CHARGE)
    # TS at the target, but the charger still in STANDBY: 0 A only because it has not started yet
    bench.charger = replace(CHARGER, state=ChargerState.STANDBY, voltage=bench.target, current=0.0)
    assert bench.step().state is State.CHARGE


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
    assert out.message == "The BMS did not reach TS_ON: it is in IDLE"


def test_precharge_waits_while_the_bms_is_precharging(bench, cfg):
    bench.go_to(State.PRECHARGE)
    bench.bms = replace(bench.bms, state=TsacState.PRECHARGE)
    out = bench.step(after=cfg.timing.bms_response_timeout + 0.1)
    assert out.state is State.PRECHARGE and out.ts_on
    bench.bms = replace(bench.bms, state=TsacState.TS_ON)
    assert bench.step().state is State.READY


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


def test_precharge_is_refused_with_a_cell_at_the_limit(bench, cfg):
    bench.go_to(State.IDLE)
    bench.bms = replace(bench.bms, cell_max=cfg.accumulator.max_cell_voltage)
    out = bench.step(Command.PRECHARGE)
    assert out.state is State.IDLE and not out.ts_on
    assert "a cell is at" in out.refusal


def test_charging_again_is_refused_with_a_cell_at_the_limit(bench, cfg):
    bench.go_to(State.CHARGE_DONE)
    bench.bms = replace(bench.bms, cell_max=cfg.accumulator.max_cell_voltage)
    out = bench.step(Command.START_CHARGE)
    assert out.state is State.CHARGE_DONE
    assert out.charger is ChargerCommand.STOP
    assert "a cell is at" in out.refusal


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
    bench.charger = replace(
        bench.charger, state=ChargerState.ERROR, errors=frozenset({"Error_Overtemperature"})
    )
    assert_stopped_safely(bench.step(), "Error_Overtemperature")


def test_charger_error_flags_alone_do_not_stop_the_precharge(bench):
    bench.go_to(State.PRECHARGE)
    bench.charger = replace(bench.charger, errors=frozenset({"DIAG_ERR1_CHRG_STOP"}))
    assert bench.step().state is State.PRECHARGE


def test_loop_opening_while_charging(bench):
    bench.go_to(State.CHARGE)
    bench.shutdown = (("mushroom", 0.0), ("charger", 0.0))
    assert_stopped_safely(bench.step(), "open at mushroom")


def test_the_kind_of_fault_is_kept_while_in_error(bench):
    # the frontend picks its picture from it (frontend.readings.error_kind)
    bench.go_to(State.CHARGE)
    bench.shutdown = (("mushroom", 0.0), ("charger", 0.0))
    bench.step()
    assert bench.fsm.fault is Fault.MUSHROOM
    bench.shutdown = (("mushroom", 12.0), ("charger", 12.0))
    bench.step(Command.RESET)
    assert bench.fsm.fault is None  # out of ERROR: no fault


def test_another_open_point_is_not_the_mushroom(bench):
    bench.go_to(State.CHARGE)
    bench.shutdown = (("mushroom", 12.0), ("charger", 0.0))
    bench.step()
    assert bench.fsm.fault is Fault.LOOP_OPEN


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


def test_a_precharge_that_never_ends_gives_up(bench, cfg):
    bench.go_to(State.PRECHARGE)
    bench.bms = replace(bench.bms, state=TsacState.PRECHARGE)
    out = bench.step(after=cfg.timing.precharge_timeout + 0.1)
    assert out.state is State.IDLE and not out.ts_on
    assert "Precharge not done" in out.message


def test_no_charge_before_every_cell_is_read(bench):
    bench.go_to(State.READY)
    bench.bms = replace(bench.bms, cells=(3.8, None, 3.81))
    out = bench.step(Command.START_CHARGE)
    assert out.state is State.READY
    assert out.refusal == "Cannot charge: 1 cells not read yet"
    bench.bms = replace(bench.bms, cells=(3.8, 3.79, 3.81))
    assert bench.step(Command.START_CHARGE).state is State.CHARGE


def test_a_charger_that_does_not_start_is_reported_not_a_fault(bench):
    bench.go_to(State.CHARGE)  # the charger stays in STANDBY: no mains, say
    out = bench.step(after=CHARGER_START_TIME + 0.1)
    assert out.state is State.CHARGE and out.message == NOT_DELIVERING
    bench.charger = replace(bench.charger, state=ChargerState.RUNNING, voltage=550.0, current=6.0)
    out = bench.step()
    assert out.message.startswith("Charging to")  # it started after all


# charge done


def test_charge_done_turns_the_ts_off_after_the_timeout(bench):
    bench.go_to(State.CHARGE_DONE)
    assert bench.step(after=CHARGE_DONE_TIMEOUT - 1).ts_on
    out = bench.step(after=2)
    assert out.state is State.IDLE and not out.ts_on
    assert bench.fsm.history[-1].trigger is Event.CHARGE_DONE_TIMEOUT


def test_top_off_from_charge_done(bench):
    bench.go_to(State.CHARGE_DONE)
    out = bench.step(Command.START_CHARGE)
    assert out.state is State.CHARGE and out.charger is ChargerCommand.CHARGE


# priorities


def test_the_ts_going_off_wins_over_a_command(bench):
    bench.go_to(State.READY)
    bench.bms = replace(bench.bms, state=TsacState.IDLE)
    out = bench.step(Command.START_CHARGE)
    assert out.state is State.IDLE and not out.ts_on


def test_pause_wins_over_charge_complete(bench, cfg):
    bench.go_to(State.CHARGE)
    bench.bms = replace(bench.bms, cell_max=cfg.accumulator.max_cell_voltage)
    assert bench.step(Command.PAUSE_CHARGE).state is State.READY


# history


def test_history_tells_the_story(bench):
    bench.go_to(State.CHARGE_DONE)
    assert [(t.source, t.target) for t in bench.fsm.history] == [
        (State.CHECK, State.IDLE),
        (State.IDLE, State.PRECHARGE),
        (State.PRECHARGE, State.READY),
        (State.READY, State.CHARGE),
        (State.CHARGE, State.CHARGE_DONE),
    ]


def test_a_broken_listener_does_not_stop_the_machine(bench):
    bench.fsm.on_transition(lambda transition: 1 / 0)
    bench.go_to(State.CHARGE_DONE)  # would raise if the exception escaped
