"""The record: events and samples kept in SQLite, and what the handcart writes in it."""

import pytest
from test_handcart import Rig

from backend.recorder import KEEP_DAYS, Recorder
from shared.models import Command, Sample, Severity, State


@pytest.fixture
def recorder(tmp_path):
    return Recorder(tmp_path / "record.db", clock=lambda: 1000.0)


def sample(at: float) -> Sample:
    return Sample(
        time=at,
        state=State.CHARGE,
        pack_voltage=550.0,
        current=6.0,
        cell_min=3.8,
        cell_max=3.82,
        temp_max=30.0,
        charger_voltage=551.0,
        charger_current=6.1,
    )


def test_events_newest_first_and_by_severity(recorder):
    first = recorder.record("command", Severity.INFO, "api", "PRECHARGE", {"command": "PRECHARGE"}, "api")
    second = recorder.record("transition", Severity.CRITICAL, "fsm", "CHARGE → ERROR", cause_id=first)
    events = recorder.events()
    assert [e.id for e in events] == [second, first]
    assert events[1].data == {"command": "PRECHARGE"} and events[1].actor == "api"
    assert events[0].cause_id == first
    assert [e.id for e in recorder.events(at_least=Severity.CRITICAL)] == [second]
    assert [e.id for e in recorder.events(before_id=second)] == [first]


def test_the_ids_go_on_after_a_restart(tmp_path):
    path = tmp_path / "record.db"
    first = Recorder(path, clock=lambda: 1000.0)
    old_id = first.record("system", Severity.NOTICE, "backend", "Backend started")
    first.close()
    again = Recorder(path, clock=lambda: 1001.0)
    assert again.record("system", Severity.NOTICE, "backend", "Backend started") == old_id + 1


def test_old_rows_are_deleted_at_start(tmp_path):
    path = tmp_path / "record.db"
    old = Recorder(path, clock=lambda: 0.0)
    old.record("system", Severity.NOTICE, "backend", "Backend started")
    old.sample(sample(0.0))
    old.close()
    later = KEEP_DAYS * 24 * 3600 + 1
    again = Recorder(path, clock=lambda: later)
    assert again.events() == [] and again.samples(since=0) == []


def test_samples_in_a_time_range(recorder):
    for at in (10.0, 11.0, 12.0):
        recorder.sample(sample(at))
    assert [s.time for s in recorder.samples(since=11.0)] == [11.0, 12.0]
    assert [s.time for s in recorder.samples(since=0, until=11.0)] == [10.0, 11.0]


def test_the_writing_thread_writes_and_stops(recorder):
    recorder.start()
    recorder.record("system", Severity.NOTICE, "backend", "Backend started")
    recorder.close()
    assert len(recorder.events()) == 1


@pytest.fixture
def rig(cfg, primary, charger_db, recorder):
    rig = Rig(cfg, primary, charger_db, speed=300, recorder=recorder)
    yield rig
    rig.close()


def test_a_command_and_the_transition_it_caused(rig, recorder):
    rig.run(1.0, until=State.IDLE)
    rig.handcart.request(Command.PRECHARGE)
    command = next(e for e in recorder.events() if e.kind == "command")
    transition = recorder.events()[0]
    assert transition.kind == "transition" and transition.cause_id == command.id
    assert transition.data["from"] == "IDLE" and transition.data["to"] == "PRECHARGE"
    assert transition.data["readings"]["bms"]["connected"]


def test_a_refused_command_says_why(rig, recorder):
    rig.handcart.request(Command.START_CHARGE)  # in CHECK: not possible
    refusal, command = recorder.events()[:2]
    assert refusal.kind == "refusal" and refusal.cause_id == command.id
    assert "not possible" in refusal.summary


def test_a_device_lost_is_the_cause_of_what_follows(rig, recorder):
    rig.run(1.0, until=State.IDLE)
    rig.charger_unplugged = True
    rig.run(1.0, until=State.CHECK)
    transition = recorder.events()[0]
    lost = next(e for e in recorder.events() if e.summary == "Charger lost")
    assert transition.summary.startswith("IDLE → CHECK") and transition.cause_id == lost.id


def test_samples_only_while_doing_something(rig, recorder):
    rig.run(1.0, until=State.IDLE)
    rig.run(2.0)
    assert recorder.samples(since=0) == []  # IDLE: nothing to draw
    rig.handcart.request(Command.PRECHARGE)
    rig.run(3.0, until=State.READY)
    rig.run(2.0)
    assert len(recorder.samples(since=0)) >= 2


def test_a_charger_error_with_the_ts_on_is_critical_and_says_its_flags(rig, recorder):
    rig.run(1.0, until=State.IDLE)
    rig.handcart.request(Command.PRECHARGE)
    rig.run(3.0, until=State.READY)
    rig.charger.forced_error = True
    rig.run(2.0, until=State.ERROR)
    rig.run(1.5)  # HYC_Error comes every second, the state every 100 ms: the flags come after
    errors = next(e for e in recorder.events() if e.kind == "errors")
    assert errors.data["new"] == ["Interlock missing"]
    critical = recorder.events(at_least=Severity.CRITICAL)[0]
    assert critical.data["to"] == "ERROR" and critical.data["readings"]["charger"]["state"] == "ERROR"
