"""Buzzer melodies, played over time without blocking: the frequency to output at each moment."""

from backend.hal import Sound

# notes the PCB buzzer plays well: 1000-3000 Hz (from the old repo)
LA6, SI6, DO7, DO7_SHARP, RE7 = 1760.0, 1976.0, 2093.0, 2217.0, 2349.0
REST = None

Melody = list[tuple[float | None, float]]  # (frequency or REST, seconds)

MELODIES: dict[Sound, Melody] = {
    Sound.STARTUP: [
        (RE7, 0.35),
        (REST, 0.05),
        (RE7, 0.35),
        (REST, 0.05),
        (RE7, 0.35),
        (REST, 0.05),
        (DO7_SHARP, 0.60),
        (REST, 0.05),
        (SI6, 0.10),
        (REST, 0.05),
        (LA6, 1.35),
    ],
    Sound.CONFIRM: [(RE7, 0.05), (REST, 0.05), (RE7, 0.05)],
    Sound.CHARGE_DONE: [(LA6, 0.15), (REST, 0.05), (DO7, 0.15), (REST, 0.05), (RE7, 0.40)],
    Sound.ERROR: [(RE7, 0.20), (LA6, 0.20)] * 3,
    Sound.TICK: [(RE7, 0.008)],
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
