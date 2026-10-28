"""Notes and melodies for the buzzer: a Melody is a list of (frequency or REST, seconds)."""

# Note frequencies in Hz (equal temperament, LA4 = 440 Hz).
# Black keys use the flat name: REb = DO#, MIb = RE#, SOLb = FA#, LAb = SOL#, SIb = LA#.

# Octave 5
DO5 = 523.25
REb5 = 554.37
RE5 = 587.33
MIb5 = 622.25
MI5 = 659.26
FA5 = 698.46
SOLb5 = 739.99
SOL5 = 783.99
LAb5 = 830.61
LA5 = 880.00
SIb5 = 932.33
SI5 = 987.77

# Octave 6
DO6 = 1046.50
REb6 = 1108.73
RE6 = 1174.66
MIb6 = 1244.51
MI6 = 1318.51
FA6 = 1396.91
SOLb6 = 1479.98
SOL6 = 1567.98
LAb6 = 1661.22
LA6 = 1760.00
SIb6 = 1864.66
SI6 = 1975.53

# Octave 7
DO7 = 2093.00
REb7 = 2217.46
RE7 = 2349.32
MIb7 = 2489.02
MI7 = 2637.02
FA7 = 2793.83
SOLb7 = 2959.96
SOL7 = 3135.96
LAb7 = 3322.44
LA7 = 3520.00
SIb7 = 3729.31
SI7 = 3951.07

REST = None
GAP = 0.03

Melody = list[tuple[float | None, float]]


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

SHUTDOWN_SOUND = _phrase(
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

CONFIRM_SOUND: Melody = [(RE7, 0.05), (REST, 0.05), (RE7, 0.05)]
ERROR_SOUND: Melody = [(RE7, 0.20), (LA6, 0.20)] * 3
TICK_SOUND: Melody = [(RE7, 0.008)]

# PLUG_IN_SOUND: _phrase()
