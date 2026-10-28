"""Buzzer melodies, played over time without blocking: the frequency to output at each moment."""

from backend.hal import Sound
from backend.hal.tones import (
    CONFIRM_SOUND,
    ERROR_SOUND,
    FORELLE,
    STARTUP_SOUND,
    TICK_SOUND,
    SHUTDOWN_SOUND,
    Melody,
)

MELODIES: dict[Sound, Melody] = {
    Sound.STARTUP: SHUTDOWN_SOUND,
    Sound.CONFIRM: CONFIRM_SOUND,
    Sound.CHARGE_DONE: FORELLE,
    Sound.ERROR: ERROR_SOUND,
    Sound.TICK: TICK_SOUND,
}


class Player:
    def __init__(self) -> None:
        self._melody: Melody = []
        self._started = 0.0

    def play(self, sound: Sound, now: float) -> None:
        """Start a melody, replacing the one playing; a tick never cuts one (an error alarm, say)."""
        if sound is Sound.TICK and self.frequency(now) is not None:
            return
        self._melody, self._started = MELODIES[sound], now

    def frequency(self, now: float) -> float | None:
        """What to output now; None when silent."""
        elapsed = now - self._started
        for note, duration in self._melody:
            if elapsed < duration:
                return note
            elapsed -= duration
        return None
