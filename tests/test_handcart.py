"""The whole backend against the simulators, over an in-process CAN bus: a full charge, start to end."""

import can
import pytest

from backend.canbus.bus import receive, send
from backend.hal import Sound
from backend.hal.fake import FakeHal
from backend.handcart import Handcart
from shared.models import Command, State, TsacState
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
    assert rig.handcart.settings == settings


def test_every_command_beeps(rig):
    rig.handcart.request(Command.PRECHARGE)
    assert rig.hal.played == [Sound.CONFIRM]


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
