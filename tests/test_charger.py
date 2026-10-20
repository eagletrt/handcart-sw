"""The LittleSIC turns HYC frames into a snapshot, and builds its control frames."""

import pytest

from backend.devices.charger import ChargerCommand, ChargerState, LittleSic


@pytest.fixture
def charger(charger_db, cfg, clock) -> LittleSic:
    return LittleSic(charger_db, cfg.timing.charger_presence_timeout, clock)


def _all_flags(charger_db, message: str, value: int) -> dict[str, int]:
    return {s.name: value for s in charger_db.get_message_by_name(message).signals}


def test_state_codes(charger, charger_frame):
    charger.on_frame(charger_frame("HYC_Status", status=0x06))
    snap = charger.snapshot()
    assert snap.state is ChargerState.RUNNING
    assert snap.state.delivering

    charger.on_frame(charger_frame("HYC_Status", status=0x03))
    assert not charger.snapshot().state.delivering


def test_undocumented_state_code_is_unknown(charger, charger_frame):
    charger.on_frame(charger_frame("HYC_Status", status=0x42))
    assert charger.snapshot().state is None


def test_output_and_grid(charger, charger_frame):
    charger.on_frame(charger_frame("HYC_Actual", uActual=550.0, iActual=8.0))
    charger.on_frame(charger_frame("HYC_Grid_Voltage", u1=230, u2=229, u3=231, f=50))
    snap = charger.snapshot()
    assert snap.voltage == pytest.approx(550.0, abs=1)
    assert snap.current == pytest.approx(8.0, abs=0.5)
    assert snap.grid_voltages == (230, 229, 231)


def test_errors(charger, charger_frame, charger_db):
    flags = _all_flags(charger_db, "HYC_Error", 0) | {"Error_Overtemperature": 1}
    charger.on_frame(charger_frame("HYC_Error", raw=True, **flags))
    assert charger.snapshot().errors == {"Error_Overtemperature"}


def test_warnings(charger, charger_frame, charger_db):
    flags = _all_flags(charger_db, "HYC_Warning", 0) | {"HEAT_SINK": 1}
    charger.on_frame(charger_frame("HYC_Warning", raw=True, **flags))
    assert charger.snapshot().warnings == {"HEAT_SINK"}


def test_presence_timeout(charger, charger_frame, clock, cfg):
    charger.on_frame(charger_frame("HYC_Status", status=0x03))
    assert charger.connected
    clock.now += cfg.timing.charger_presence_timeout + 0.01
    assert not charger.connected


def test_control_frames(charger, charger_db):
    assert charger.control(ChargerCommand.CHARGE).data == bytes([0x02])
    assert charger.control(ChargerCommand.STOP).data == bytes([0x00])

    target = charger_db.decode_message(*_unpack(charger.target(590, 6.0)))
    assert target["uTarget"] == pytest.approx(590, abs=1)
    assert target["iTarget"] == pytest.approx(6.0, abs=0.5)

    alive = charger_db.decode_message(*_unpack(charger.alive(20, 100)))
    assert (alive["fanMin"], alive["fanMax"]) == (20, 100)


def _unpack(frame):
    return frame.id, frame.data
