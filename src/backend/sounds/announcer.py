"""When the buzzer speaks: from what happened in one tick, the sounds to play.

The sounds for the operator's commands (confirm, refused) are decided by Handcart.request, which knows
whether the command was accepted. Everything else is here.
"""

from backend.core import Event, Inputs, Transition
from backend.core.checks import BMS_HV_STATES
from backend.core.events import NOT_DELIVERING
from backend.core.model import Trigger
from shared.config import Accumulator
from shared.models import Sound, State

ALARM_REPEAT = 30.0  # s: while in ERROR, the alarm sounds again this often, for who was not there
WARM_HYSTERESIS = 1.0  # °C: a warm cell must cool this much below the limit before it can warn again

# By what moved the machine, before looking at where it went
SOUND_ON_TRIGGER: dict[Trigger, Sound] = {
    Event.TS_ON: Sound.TS_ON,
    Event.BALANCING_DONE: Sound.BALANCING_DONE,
    Event.TS_NOT_REACHED: Sound.FAILED,
    Event.PRECHARGE_TIMEOUT: Sound.FAILED,
    Event.BALANCING_NOT_STARTED: Sound.FAILED,
}
SOUND_ON_ENTERING = {
    State.PRECHARGE: Sound.PRECHARGE,
    State.CHARGE_DONE: Sound.CHARGE_DONE,
    State.ERROR: Sound.ERROR,
}


class Announcer:
    def __init__(self, pack: Accumulator) -> None:
        self._pack = pack
        # what the last tick saw, to sound only when it changes
        self._connected = (False, False)  # BMS, charger
        self._airs_closed = False
        self._not_delivering = False
        self._warm = False
        self._alarm_at = 0.0  # when the error alarm last sounded

    def sounds(
        self, now: float, inputs: Inputs, state: State, transition: Transition | None, message: str
    ) -> list[Sound]:
        """The sounds for this tick, in order: when two start together, the Player keeps the right one."""
        sounds = self._devices(inputs)
        if transition is not None:
            sound = SOUND_ON_TRIGGER.get(transition.trigger) or SOUND_ON_ENTERING.get(transition.target)
            if sound is not None:
                sounds.append(sound)
            if transition.target is State.ERROR:
                self._alarm_at = now
        elif state is State.ERROR and now - self._alarm_at >= ALARM_REPEAT:
            sounds.append(Sound.ERROR)
            self._alarm_at = now

        airs_closed = inputs.bms.state in BMS_HV_STATES
        if self._airs_closed and not airs_closed:
            sounds.append(Sound.DISCHARGE)  # the TS goes off, whatever the reason
        self._airs_closed = airs_closed

        not_delivering = message == NOT_DELIVERING
        if not_delivering and not self._not_delivering:
            sounds.append(Sound.WARNING)
        self._not_delivering = not_delivering

        if self._warm_cell_now(inputs):
            sounds.append(Sound.WARNING)
        return sounds

    def _devices(self, inputs: Inputs) -> list[Sound]:
        sounds = []
        connected = (inputs.bms.connected, inputs.charger.connected)
        for was, now in zip(self._connected, connected, strict=True):
            if now and not was:
                sounds.append(Sound.DEVICE_CONNECTED)
            elif was and not now:
                sounds.append(Sound.DEVICE_DISCONNECTED)
        self._connected = connected
        return sounds

    def _warm_cell_now(self, inputs: Inputs) -> bool:
        """Whether a cell has just gone above the warm temperature: below the error limit, worth a look."""
        temp = inputs.bms.temp_max
        if temp is None:
            return False
        if not self._warm and temp > self._pack.warm_temperature:
            self._warm = True
            return True
        if self._warm and temp < self._pack.warm_temperature - WARM_HYSTERESIS:
            self._warm = False
        return False
