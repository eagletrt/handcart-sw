"""Buzzer melodies, played over time without blocking: the frequency to output at each moment."""

from backend.hal import Sound

# notes the PCB buzzer plays well: 1000-3000 Hz
LA6, SI6, DO7, DO7_SHARP, RE7, DO6, RE6, SOL6 = (
    1760.0,
    1976.0,
    2093.0,
    2217.0,
    2349.0,
    1046.0,
    1175.0,
    1568.0,
)
MIb6, MI6, FA6, LAb6, SIb6, MIb7 = (
    1244.51,
    1318.51,
    1396.91,
    1661.22,
    1864.66,
    2489.02,
)
REST = None
GAP = 0.03  # silence after each note, so repeated notes are heard as separate

Melody = list[tuple[float | None, float]]  # (frequency or REST, seconds)


def _phrase(bpm: float, notes: list[tuple[float | None, float]]) -> Melody:
    """(frequency or REST, length in quarter notes) -> Melody, with a short gap after each note."""
    beat = 60 / bpm
    out: Melody = []
    for freq, beats in notes:
        d = beats * beat
        if freq is REST:
            out.append((REST, d))
        else:
            out += [(freq, d - GAP), (REST, GAP)]
    return out


# Schubert, "Die Forelle" (first stanza): the Samsung washing-machine tune
FORELLE = _phrase(
    84,
    [
        # In einem Bächlein helle, da schoss in froher Eil'
        (FA6, 0.5),
        (SIb6, 0.5),
        (SIb6, 0.5),
        (RE7, 0.5),
        (RE7, 0.5),
        (SIb6, 1),
        (FA6, 0.5),
        (FA6, 0.5),
        (FA6, 0.75),
        (FA6, 0.25),
        (DO7, 0.25),
        (SIb6, 0.25),
        (LA6, 0.25),
        (SIb6, 0.25),
        (FA6, 1),
        (REST, 0.5),
        # die launische Forelle vorüber wie ein Pfeil
        (FA6, 0.5),
        (SIb6, 0.5),
        (SIb6, 0.5),
        (RE7, 0.5),
        (RE7, 0.5),
        (SIb6, 1),
        (FA6, 0.5),
        (SIb6, 0.5),
        (LA6, 0.5),
        (SOL6, 0.25),
        (LA6, 0.25),
        (SIb6, 0.5),
        (MI6, 0.5),
        (FA6, 1),
        (REST, 0.5),
        # Ich stand an dem Gestade und sah in süßer Ruh
        (FA6, 0.5),
        (LA6, 0.5),
        (LA6, 0.5),
        (SIb6, 0.25),
        (LA6, 0.25),
        (SIb6, 0.25),
        (LA6, 0.25),
        (SIb6, 1),
        (FA6, 0.5),
        (SIb6, 0.5),
        (LA6, 0.5),
        (LA6, 0.5),
        (LA6, 0.25),
        (DO7, 0.25),
        (DO7, 0.25),
        (LA6, 0.25),
        (SIb6, 1.5),
        # des muntern Fischleins Bade im klaren Bächlein zu
        (SIb6, 0.5),
        (SOL6, 0.5),
        (SOL6, 0.5),
        (SOL6, 0.5),
        (SOL6, 0.5),
        (SIb6, 1),
        (FA6, 0.5),
        (FA6, 0.5),
        (FA6, 0.75),
        (FA6, 0.25),
        (DO7, 0.5),
        (LA6, 0.5),
        (SIb6, 1.5),
        # (repeat) des muntern Fischleins Bade im klaren Bächlein zu
        (SIb6, 0.5),
        (SIb6, 0.25),
        (LA6, 0.25),
        (SOL6, 0.5),
        (SOL6, 0.25),
        (SIb6, 0.25),
        (LA6, 0.25),
        (DO7, 0.25),
        (SIb6, 1),
        (FA6, 0.5),
        (FA6, 0.5),
        (FA6, 0.75),
        (FA6, 0.25),
        (DO7, 0.5),
        (LA6, 0.5),
        (SIb6, 2),
    ],
)

STARTUP_SOUND = _phrase(
    96,
    [
        (MIb7, 0.75),
        (MIb6, 0.25),
        (SIb6, 0.5),
        (LAb6, 0.5),
        (MIb6, 0.5),
        (MIb7, 0.5),
        (SIb6, 0.75),
    ],
)

MELODIES: dict[Sound, Melody] = {
    Sound.STARTUP: STARTUP_SOUND,
    Sound.CONFIRM: [(RE7, 0.05), (REST, 0.05), (RE7, 0.05)],
    Sound.CHARGE_DONE: FORELLE,
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
