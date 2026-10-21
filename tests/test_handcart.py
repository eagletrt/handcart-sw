"""The whole backend against the simulators, over an in-process CAN bus: a full charge, start to end."""

import can
import pytest

from backend.canbus.bus import receive, send
from backend.hal import Sound
from backend.hal.fake import FakeHal
from backend.handcart import Handcart
from shared.models import Command, InputEvent, State, TsacState
from sim.bms import SimBms
from sim.charger import SimCharger

TICK = 0.005  # s, like the backend


class Rig:
    """Handcart and simulators on one virtual bus, sharing a clock the test moves."""

    def __init__(self, cfg, primary, charger_db, speed: float) -> None:
        self.now = 0.0
        self.hal = FakeHal()
        self._handcart_bus = can.Bus(interface="virtual", channel="rig", receive_own_messages=False)
        self._sim_bus = can.Bus(interface="virtual", channel="rig", receive_own_messages=False)
        self.handcart = Handcart(
            cfg, self.hal, self._handcart_bus, self._handcart_bus, clock=lambda: self.now
        )
        self.bms = SimBms(primary, cfg.accumulator, speed=speed)
        self.charger = SimCharger(charger_db)

    def run(self, seconds: float, until: State | None = None) -> State:
        """Advance time; stop early once the handcart reaches `until`."""
        end = self.now + seconds
        while self.now < end:
            self.now += TICK
            for frame in receive(self._sim_bus):
                if not self.bms.on_frame(frame, self.now):
                    self.charger.on_frame(frame)
            current = self.charger.tick(TICK, self.bms.ts_voltage)
            self.bms.tick(self.now, TICK, current)
            for frame in self.bms.frames(self.now) + self.charger.frames(self.now):
                send(self._sim_bus, frame)
            state = self.handcart.tick().state
            if state is until:
                break
        return self.handcart.status().state

    def close(self) -> None:
        self._handcart_bus.shutdown()
        self._sim_bus.shutdown()


@pytest.fixture
def rig(cfg, primary, charger_db):
    rig = Rig(cfg, primary, charger_db, speed=300)  # a full charge in about 15 s of simulated time
    yield rig
    rig.close()


def test_full_charge(rig):
    assert rig.run(1.0, until=State.IDLE) is State.IDLE

    rig.handcart.request(Command.PRECHARGE)
    assert rig.run(3.0, until=State.READY) is State.READY
    assert rig.bms.state is TsacState.TS_ON
    assert rig.hal.sd_relay_closed and not rig.hal.discharge

    rig.handcart.request(Command.START_CHARGE)
    assert rig.run(3.0) is State.CHARGE
    assert rig.charger.current > 1.0

    assert rig.run(120, until=State.CHARGE_DONE) is State.CHARGE_DONE
    assert rig.hal.played[-1] is Sound.CHARGE_DONE
    status = rig.handcart.status()
    assert status.bms.pack_voltage == pytest.approx(status.settings.target_voltage, abs=3)

    rig.handcart.request(Command.STOP)
    assert rig.run(1.0) is State.IDLE
    assert rig.bms.state is TsacState.IDLE


def test_an_open_loop_while_charging_stops_everything(rig):
    rig.run(1.0, until=State.IDLE)
    rig.handcart.request(Command.PRECHARGE)
    rig.run(3.0, until=State.READY)
    rig.handcart.request(Command.START_CHARGE)
    rig.run(1.0)

    rig.hal.open_at = "mushroom"
    assert rig.run(1.0) is State.ERROR
    assert "mushroom" in rig.handcart.status().message
    assert rig.hal.played[-1] is Sound.ERROR
    assert rig.bms.state is TsacState.IDLE  # the BMS opened the AIRs when asked
    assert rig.charger.current < 1.0  # ramping down
    assert not rig.hal.sd_relay_closed


def test_settings_outside_the_limits_are_refused(rig, cfg):
    settings = rig.handcart.settings
    too_high = settings.model_copy(update={"target_voltage": cfg.charge.target_voltage_max + 1})
    assert rig.handcart.change_settings(too_high) is not None
    too_low = settings.model_copy(update={"balancing_threshold": cfg.accumulator.balancing_threshold_min / 2})
    assert rig.handcart.change_settings(too_low) is not None
    assert rig.handcart.settings == settings


def test_an_accepted_command_beeps_a_refused_one_does_not(rig):
    assert rig.handcart.request(Command.PRECHARGE) is not None  # still in CHECK: refused
    assert Sound.CONFIRM not in rig.hal.played
    rig.run(1.0, until=State.IDLE)
    assert rig.handcart.request(Command.PRECHARGE) is None
    assert rig.hal.played[-1] is Sound.CONFIRM


def test_a_command_is_answered_right_away(rig):
    assert "not possible" in rig.handcart.request(Command.START_CHARGE)  # still in CHECK
    rig.run(1.0, until=State.IDLE)
    assert rig.handcart.request(Command.PRECHARGE) is None
    assert rig.handcart.status().state is State.PRECHARGE


def test_no_update_or_reboot_while_the_ts_is_on(rig):
    rig.run(1.0, until=State.IDLE)
    assert rig.handcart.maintenance_problem() is None
    rig.handcart.request(Command.PRECHARGE)
    rig.run(3.0, until=State.READY)
    assert "Stop first" in rig.handcart.maintenance_problem()


def test_turning_the_encoder_ticks(rig):
    rig.hal.press(InputEvent.TURN_CW)
    rig.handcart.tick()
    assert rig.hal.played[-1] is Sound.TICK


class UnpluggedBus(can.BusABC):
    """A bus no one acks: the kernel queue is full, every send fails like on the Pi."""

    def __init__(self) -> None:
        super().__init__(channel="unplugged")

    def send(self, msg, timeout=None):
        raise can.CanOperationError("Failed to transmit: No buffer space available [Error Code 105]")

    def _recv_internal(self, timeout):
        return None, False


def test_the_backend_keeps_running_with_the_can_unplugged(cfg):
    now = 0.0
    bus = UnpluggedBus()
    handcart = Handcart(cfg, FakeHal(), bus, bus, clock=lambda: now)
    for _ in range(1000):  # 5 s of ticks, every frame refused
        now += TICK
        handcart.tick()
    assert handcart.status().state is State.CHECK  # waiting for the BMS, not crashed


def test_the_balancing_request_is_repeated_while_balancing(cfg, primary, charger_db, monkeypatch):
    rig = Rig(cfg, primary, charger_db, speed=1)  # real speed: the balancing lasts much longer than the test
    try:
        assert rig.run(1.0, until=State.IDLE) is State.IDLE
        settings = rig.handcart.settings.model_copy(update={"balancing_threshold": 0.020})
        assert rig.handcart.change_settings(settings) is None
        balancing = primary.get_message_by_name("RaspberryTsacBalancingSet")
        requests = []  # (time, threshold)
        on_frame = rig.bms.on_frame

        def spy(frame, now):
            if frame.id == balancing.frame_id:
                requests.append((now, balancing.decode(frame.data)["threshold"]))
            return on_frame(frame, now)

        monkeypatch.setattr(rig.bms, "on_frame", spy)
        rig.handcart.request(Command.BALANCE)
        rig.run(5.0)
        assert rig.handcart.status().state is State.BALANCING
        later = [t for t, _ in requests if t > requests[0][0] + 0.5]  # after the first burst
        assert len(later) >= 4  # about one per second
        assert all(threshold == pytest.approx(0.020) for _, threshold in requests)  # the operator's
    finally:
        rig.close()


def test_the_settings_are_kept_across_restarts(cfg, tmp_path):
    path = tmp_path / "settings.json"
    bus = UnpluggedBus()
    first = Handcart(cfg, FakeHal(), bus, bus, settings_file=path)
    changed = first.settings.model_copy(update={"target_voltage": cfg.charge.target_voltage_min})
    assert first.change_settings(changed) is None
    again = Handcart(cfg, FakeHal(), bus, bus, settings_file=path)
    assert again.settings == changed


def test_saved_settings_outside_the_limits_are_not_used(cfg, tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"target_voltage": 9999, "max_current": 6, "balancing_threshold": 0.01}')
    bus = UnpluggedBus()
    handcart = Handcart(cfg, FakeHal(), bus, bus, settings_file=path)
    assert handcart.settings.target_voltage == cfg.charge.target_voltage_default
