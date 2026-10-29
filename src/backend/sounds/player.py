"""The melody of each sound, played over time without blocking: the frequency to output at each moment."""

from backend.sounds.tones import (
    CONFIRM_SOUND,
    DEVICE_CONNECTED_SOUND,
    DEVICE_DISCONNECTED_SOUND,
    DISCHARGE_SOUND,
    EINE_KLEINE_NACHTMUSIK,
    ERROR_SOUND,
    FAILED_SOUND,
    FORELLE,
    GAME_OVER,
    PRECHARGE_SOUND,
    REFUSED_SOUND,
    STARTUP_SOUND,
    TICK_SOUND,
    TS_ON_SOUND,
    WARNING_SOUND,
    Melody,
)
from shared.models import Sound

MELODIES: dict[Sound, Melody] = {
    Sound.STARTUP: STARTUP_SOUND,
    Sound.POWER_OFF: GAME_OVER,
    Sound.CONFIRM: CONFIRM_SOUND,
    Sound.REFUSED: REFUSED_SOUND,
    Sound.PRECHARGE: PRECHARGE_SOUND,
    Sound.TS_ON: TS_ON_SOUND,
    Sound.DISCHARGE: DISCHARGE_SOUND,
    Sound.CHARGE_DONE: FORELLE,
    Sound.BALANCING_DONE: EINE_KLEINE_NACHTMUSIK,
    Sound.FAILED: FAILED_SOUND,
    Sound.WARNING: WARNING_SOUND,
    Sound.ERROR: ERROR_SOUND,
    Sound.TICK: TICK_SOUND,
    Sound.DEVICE_CONNECTED: DEVICE_CONNECTED_SOUND,
    Sound.DEVICE_DISCONNECTED: DEVICE_DISCONNECTED_SOUND,
}

# A new sound cuts the one playing, unless that one is more important: an encoder tick never cuts a
# melody, nothing cuts the error alarm, and a failure is not covered by the TS going off right after it.
PRIORITY: dict[Sound, int] = {
    Sound.TICK: 0,
    Sound.CONFIRM: 1,
    Sound.REFUSED: 1,
    Sound.PRECHARGE: 1,
    Sound.TS_ON: 1,
    Sound.DISCHARGE: 1,
    Sound.CHARGE_DONE: 1,
    Sound.BALANCING_DONE: 1,
    Sound.WARNING: 1,
    Sound.DEVICE_CONNECTED: 1,
    Sound.DEVICE_DISCONNECTED: 1,
    Sound.STARTUP: 2,
    Sound.POWER_OFF: 2,
    Sound.FAILED: 2,
    Sound.ERROR: 2,
}

# The long tunes for a job done: the operator touching the handcart means they heard it, and they stop
HUSHED_BY_THE_OPERATOR = {Sound.CHARGE_DONE, Sound.BALANCING_DONE}


def length(sound: Sound) -> float:
    """How long the sound plays, in seconds."""
    return sum(duration for _, duration in MELODIES[sound])


class Player:
    def __init__(self) -> None:
        self._sound: Sound | None = None
        self._started = 0.0

    def play(self, sound: Sound, now: float) -> bool:
        """Start a sound, unless a more important one is playing. Returns whether it started."""
        playing = self._sound if self.frequency(now) is not None else None
        if playing is not None and PRIORITY[sound] < PRIORITY[playing]:
            return False
        self._sound, self._started = sound, now
        return True

    def hush(self) -> None:
        """Stop the tune playing, if it is one the operator may stop (never an alarm or a warning)."""
        if self._sound in HUSHED_BY_THE_OPERATOR:
            self._sound = None

    def frequency(self, now: float) -> float | None:
        """What to output now; None when silent."""
        if self._sound is None:
            return None
        elapsed = now - self._started
        for note, duration in MELODIES[self._sound]:
            if elapsed < duration:
                return note
            elapsed -= duration
        return None
