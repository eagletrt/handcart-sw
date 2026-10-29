"""Notes and melodies for the buzzer.

A Melody is what the buzzer plays: a list of (frequency in Hz or REST, seconds). The tunes are written in
beats, as on a score, and phrase() turns them into a Melody; the short beeps are written in seconds directly.
"""

import math

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
GAP = 0.03  # s of silence after each note of a phrase, so that two equal notes are heard as two

Melody = list[tuple[float | None, float]]


def near(melody: Melody, resonance: float | None) -> Melody:
    """The melody moved by whole octaves to where the buzzer is loudest: the same tune, higher or lower.

    A piezo buzzer is loud only around its resonance, and an octave away it is barely heard. The melody
    goes as many octaves up or down as put its notes, on average, closest to the resonance. None: as written.
    """
    notes = [frequency for frequency, _ in melody if frequency is not None]
    if resonance is None or not notes:
        return melody
    middle = sum(math.log2(frequency) for frequency in notes) / len(notes)  # the average pitch, in octaves
    factor = 2 ** round(math.log2(resonance) - middle)
    return [(None if frequency is None else frequency * factor, seconds) for frequency, seconds in melody]


def phrase(bpm: float, notes: list[tuple[float | None, float]]) -> Melody:
    """(frequency or REST, length in beats) -> Melody, at bpm beats per minute."""
    beat = 60 / bpm
    melody: Melody = []
    for frequency, beats in notes:
        seconds = beats * beat
        if frequency is REST:
            melody.append((REST, seconds))
        else:
            melody += [(frequency, seconds - GAP), (REST, GAP)]
    return melody


# The tunes keep a few beats per line, to read them as on a score: the formatter would put one note per line
# fmt: off

# Schubert, "Die Forelle" (first stanza): the Samsung washing-machine tune
FORELLE = phrase(
    84,
    [
        # In einem Bächlein helle, da schoss in froher Eil'
        (FA6, 0.5), (SIb6, 0.5), (SIb6, 0.5), (RE7, 0.5),
        (RE7, 0.5), (SIb6, 1), (FA6, 0.5),
        (FA6, 0.5), (FA6, 0.75), (FA6, 0.25), (DO7, 0.25), (SIb6, 0.25),
        (LA6, 0.25), (SIb6, 0.25), (FA6, 1), (REST, 0.5),
        # die launische Forelle vorüber wie ein Pfeil
        (FA6, 0.5), (SIb6, 0.5), (SIb6, 0.5), (RE7, 0.5),
        (RE7, 0.5), (SIb6, 1), (FA6, 0.5),
        (SIb6, 0.5), (LA6, 0.5), (SOL6, 0.25), (LA6, 0.25), (SIb6, 0.5),
        (MI6, 0.5), (FA6, 1), (REST, 0.5),
        # Ich stand an dem Gestade und sah in süßer Ruh
        (FA6, 0.5), (LA6, 0.5), (LA6, 0.5), (SIb6, 0.25), (LA6, 0.25),
        (SIb6, 0.25), (LA6, 0.25), (SIb6, 1), (FA6, 0.5),
        (SIb6, 0.5), (LA6, 0.5), (LA6, 0.5), (LA6, 0.25), (DO7, 0.25),
        (DO7, 0.25), (LA6, 0.25), (SIb6, 1.5),
        # des muntern Fischleins Bade im klaren Bächlein zu
        (SIb6, 0.5), (SOL6, 0.5), (SOL6, 0.5), (SOL6, 0.5),
        (SOL6, 0.5), (SIb6, 1), (FA6, 0.5),
        (FA6, 0.5), (FA6, 0.75), (FA6, 0.25), (DO7, 0.5),
        (LA6, 0.5), (SIb6, 1.5),
        # (repeat) des muntern Fischleins Bade im klaren Bächlein zu
        (SIb6, 0.5), (SIb6, 0.25), (LA6, 0.25), (SOL6, 0.5), (SOL6, 0.25), (SIb6, 0.25),
        (LA6, 0.25), (DO7, 0.25), (SIb6, 1), (FA6, 0.5),
        (FA6, 0.5), (FA6, 0.75), (FA6, 0.25), (DO7, 0.5),
        (LA6, 0.5), (SIb6, 2),
    ],
)

# The backend started
STARTUP_SOUND = phrase(
    96,
    [
        (MIb7, 0.75), (MIb6, 0.25), (SIb6, 0.5), (LAb6, 0.5),
        (MIb6, 0.5), (MIb7, 0.5), (SIb6, 0.75),
    ],
)

# Going up: the TS is going on
PRECHARGE_SOUND = phrase(
    160,
    [
        (DO6, 0.5), (MI6, 0.5), (SOL6, 0.5), (DO7, 1),
    ],
)

# The precharge arpeggio going down: the AIRs opened, the TS goes off
DISCHARGE_SOUND = phrase(
    160,
    [
        (DO7, 0.5), (SOL6, 0.5), (MI6, 0.5), (DO6, 1),
    ],
)

# Where the precharge arpeggio ended, held: the TS is on
TS_ON_SOUND = phrase(
    160,
    [
        (SOL6, 0.5), (DO7, 2),
    ],
)

# Mozart, "Eine kleine Nachtmusik" (opening theme, one bar per line): the cells are even
EINE_KLEINE_NACHTMUSIK = phrase(
    120,
    [
        (SOL6, 1), (REST, 0.5), (RE6, 0.5), (SOL6, 1), (REST, 0.5), (RE6, 0.5),
        (SOL6, 0.5), (RE6, 0.5), (SOL6, 0.5), (SI6, 0.5), (RE7, 2),
        (DO7, 1), (REST, 0.5), (LA6, 0.5), (DO7, 1), (REST, 0.5), (LA6, 0.5),
        (DO7, 0.5), (LA6, 0.5), (SOLb6, 0.5), (LA6, 0.5), (RE6, 2),
    ],
)

# Super Mario Bros., game over: two octaves up, where the buzzer sounds best. The handcart switches off.
GAME_OVER = phrase(
    200,
    [
        (DO7, 1.5), (SOL6, 1.5), (MI6, 1),
        (LA6, 0.75), (SI6, 0.75), (LA6, 0.75),
        (LAb6, 0.75), (SIb6, 0.75), (LAb6, 0.75),
        (SOL6, 0.5), (RE6, 0.5), (MI6, 3),
    ],
)

# fmt: on

# Beeps, in seconds
CONFIRM_SOUND: Melody = [(RE7, 0.05), (REST, 0.05), (RE7, 0.05)]
REFUSED_SOUND: Melody = [(DO6, 0.15)]  # one low beep: "no"
FAILED_SOUND: Melody = [(MI6, 0.15), (REST, 0.05), (DO6, 0.35)]  # going down, low and slow
WARNING_SOUND: Melody = [(LA6, 0.1), (REST, 0.1)] * 3
ERROR_SOUND: Melody = [(RE7, 0.20), (LA6, 0.20)] * 3
TICK_SOUND: Melody = [(RE7, 0.008)]
# two short notes, going up when a device answers and down when it goes away
DEVICE_CONNECTED_SOUND: Melody = [(LA6, 0.06), (REST, 0.03), (RE7, 0.09)]
DEVICE_DISCONNECTED_SOUND: Melody = [(RE7, 0.06), (REST, 0.03), (LA6, 0.09)]
