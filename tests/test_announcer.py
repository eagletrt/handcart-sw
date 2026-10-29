"""When the buzzer speaks: one test per rule of the Announcer."""

from dataclasses import replace

import pytest
from test_fsm import BMS, CHARGER, CLOSED_LOOP

from backend.core import Event, Inputs, Transition
from backend.core.events import NOT_DELIVERING
from backend.sounds.announcer import ALARM_REPEAT, Announcer
from shared.models import Command, Sound, State, TsacState


@pytest.fixture
def announcer(cfg) -> Announcer:
    announcer = Announcer(cfg.accumulator)
    announcer.sounds(0.0, inputs(), State.IDLE, None, "")  # both devices answering from here on
    return announcer


def inputs(**bms_changes) -> Inputs:
    return Inputs(0.0, replace(BMS, **bms_changes), CHARGER, CLOSED_LOOP, 550.0, 6.0)


def moved(source: State, trigger, target: State) -> Transition:
    return Transition(1.0, source, trigger, target, "")


def test_the_devices_are_heard_coming_and_going(cfg):
    announcer = Announcer(cfg.accumulator)
    assert announcer.sounds(0.0, inputs(), State.CHECK, None, "") == [Sound.DEVICE_CONNECTED] * 2
    gone = inputs(connected=False)
    assert announcer.sounds(1.0, gone, State.CHECK, None, "") == [Sound.DEVICE_DISCONNECTED]


def test_the_ts_on_after_the_precharge(announcer):
    transition = moved(State.PRECHARGE, Event.TS_ON, State.READY)
    assert announcer.sounds(1.0, inputs(), State.READY, transition, "") == [Sound.TS_ON]


def test_pausing_the_charge_is_not_the_ts_on(announcer):
    transition = moved(State.CHARGE, Command.PAUSE_CHARGE, State.READY)
    assert announcer.sounds(1.0, inputs(), State.READY, transition, "") == []


def test_a_precharge_that_did_not_happen_is_a_failure(announcer):
    transition = moved(State.PRECHARGE, Event.TS_NOT_REACHED, State.IDLE)
    assert announcer.sounds(1.0, inputs(), State.IDLE, transition, "") == [Sound.FAILED]


def test_the_end_of_the_balancing(announcer):
    transition = moved(State.BALANCING, Event.BALANCING_DONE, State.IDLE)
    assert announcer.sounds(1.0, inputs(), State.IDLE, transition, "") == [Sound.BALANCING_DONE]


def test_the_alarm_sounds_again_while_in_error(announcer):
    entered = moved(State.CHARGE, Event.FAULT, State.ERROR)
    assert announcer.sounds(10.0, inputs(), State.ERROR, entered, "") == [Sound.ERROR]
    assert announcer.sounds(10.0 + ALARM_REPEAT - 1, inputs(), State.ERROR, None, "") == []
    assert announcer.sounds(10.0 + ALARM_REPEAT, inputs(), State.ERROR, None, "") == [Sound.ERROR]


def test_the_airs_opening_is_the_discharge(announcer):
    assert announcer.sounds(1.0, inputs(state=TsacState.TS_ON), State.READY, None, "") == []
    assert announcer.sounds(2.0, inputs(state=TsacState.IDLE), State.READY, None, "") == [Sound.DISCHARGE]


def test_a_charger_that_does_not_deliver_warns_once(announcer):
    assert announcer.sounds(1.0, inputs(), State.CHARGE, None, NOT_DELIVERING) == [Sound.WARNING]
    assert announcer.sounds(2.0, inputs(), State.CHARGE, None, NOT_DELIVERING) == []


def test_a_warm_cell_warns_once_until_it_cools_down(announcer, cfg):
    warm = cfg.accumulator.warm_temperature
    assert announcer.sounds(1.0, inputs(temp_max=warm + 0.5), State.IDLE, None, "") == [Sound.WARNING]
    assert announcer.sounds(2.0, inputs(temp_max=warm - 0.5), State.IDLE, None, "") == []  # not cool yet
    assert announcer.sounds(3.0, inputs(temp_max=warm + 0.5), State.IDLE, None, "") == []
    assert announcer.sounds(4.0, inputs(temp_max=warm - 2), State.IDLE, None, "") == []
    assert announcer.sounds(5.0, inputs(temp_max=warm + 0.5), State.IDLE, None, "") == [Sound.WARNING]
