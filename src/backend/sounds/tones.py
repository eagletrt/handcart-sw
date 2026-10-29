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


# The handcart's buzzer, measured (a phone recording of a sweep of tones, one semitone apart from 1000 Hz):
# dB from its loudest, at 1000 Hz * 2^(i/12). A piezo loud only at about 2120 Hz and, 10 dB less, at about
# 4000 Hz; a semitone away it is already 12-17 dB softer, and the rest is down near the room's noise.
RESPONSE_FROM = 1000.0  # Hz of the first value
RESPONSE = [
    -37.1,
    -44.4,
    -38.1,
    -44.9,
    -28.6,
    -46.0,
    -48.4,
    -37.6,
    -27.1,
    -43.2,
    -37.0,
    -19.9,  # 1000-1888 Hz
    -12.5,
    0.0,
    -17.0,
    -17.7,
    -27.8,
    -28.1,
    -35.0,
    -28.8,
    -44.1,
    -49.4,
    -53.2,
    -44.7,  # 2000-3775 Hz
    -9.7,
    -12.7,
    -48.5,  # 4000-4490 Hz
]
SILENT = -50.0  # dB outside the measured range
BUZZ = 2120.0  # Hz: the buzzer's loudest
BUZZ_HIGH = 4000.0  # Hz: its other loud one, 10 dB softer; the "high" of the signals


def loudness(frequency: float) -> float:
    """dB from the loudest, between the measured points as on a straight line in semitones."""
    position = 12 * math.log2(frequency / RESPONSE_FROM)
    below = math.floor(position)
    if below < 0 or below + 1 >= len(RESPONSE):
        return SILENT
    part = position - below
    return RESPONSE[below] * (1 - part) + RESPONSE[below + 1] * part


def in_loudest_key(melody: Melody) -> Melody:
    """The melody moved, all of it, to where the buzzer plays it loudest: the same tune, in another key.

    Of the shifts up to two octaves either way, in tenths of a semitone, the one with the most sound over
    the melody's time (its notes' power, as measured, by how long each lasts). The notes held longest end up
    on the buzzer's loud ones; the others stay softer: no key makes every note of a tune loud on a piezo.
    """

    def sound(factor: float) -> float:
        return sum(
            seconds * 10 ** (loudness(frequency * factor) / 10) for frequency, seconds in melody if frequency
        )

    factors = [2 ** (tenths / 120) for tenths in range(-240, 241)]
    best = max(factors, key=sound)
    return [(None if frequency is None else frequency * best, seconds) for frequency, seconds in melody]


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
FORELLE = in_loudest_key(
    phrase(
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
)

# The backend started
STARTUP_SOUND = in_loudest_key(
    phrase(
    96,
    [
        (MIb7, 0.75), (MIb6, 0.25), (SIb6, 0.5), (LAb6, 0.5),
        (MIb6, 0.5), (MIb7, 0.5), (SIb6, 0.75),
    ],
    )
)

# Going up at the end: the TS is going on
PRECHARGE_SOUND = phrase(
    160,
    [
        (BUZZ, 0.5), (BUZZ, 0.5), (BUZZ, 0.5), (BUZZ_HIGH, 1),
    ],
)

# The precharge turned around, going down at the end: the AIRs opened, the TS goes off
DISCHARGE_SOUND = phrase(
    160,
    [
        (BUZZ_HIGH, 0.5), (BUZZ_HIGH, 0.5), (BUZZ_HIGH, 0.5), (BUZZ, 1),
    ],
)

# The loudest note, held: the TS is on
TS_ON_SOUND = phrase(
    160,
    [
        (BUZZ_HIGH, 0.5), (BUZZ, 2),
    ],
)

# Mozart, "Eine kleine Nachtmusik" (opening theme, one bar per line): the cells are even
EINE_KLEINE_NACHTMUSIK = in_loudest_key(
    phrase(
    120,
    [
        (SOL6, 1), (REST, 0.5), (RE6, 0.5), (SOL6, 1), (REST, 0.5), (RE6, 0.5),
        (SOL6, 0.5), (RE6, 0.5), (SOL6, 0.5), (SI6, 0.5), (RE7, 2),
        (DO7, 1), (REST, 0.5), (LA6, 0.5), (DO7, 1), (REST, 0.5), (LA6, 0.5),
        (DO7, 0.5), (LA6, 0.5), (SOLb6, 0.5), (LA6, 0.5), (RE6, 2),
    ],
    )
)

# Super Mario Bros., game over: two octaves up, where the buzzer sounds best. The handcart switches off.
GAME_OVER = in_loudest_key(
    phrase(
    200,
    [
        (DO7, 1.5), (SOL6, 1.5), (MI6, 1),
        (LA6, 0.75), (SI6, 0.75), (LA6, 0.75),
        (LAb6, 0.75), (SIb6, 0.75), (LAb6, 0.75),
        (SOL6, 0.5), (RE6, 0.5), (MI6, 3),
    ],
    )
)

# fmt: on

# Beeps, in seconds: on the buzzer's two loud notes only, told apart by rhythm, and by going up or down
CONFIRM_SOUND: Melody = [(BUZZ, 0.05), (REST, 0.05), (BUZZ, 0.05)]
REFUSED_SOUND: Melody = [(BUZZ, 0.35)]  # one long beep: "no"
FAILED_SOUND: Melody = [(BUZZ_HIGH, 0.15), (REST, 0.05), (BUZZ, 0.5)]  # going down, slow
WARNING_SOUND: Melody = [(BUZZ, 0.1), (REST, 0.1)] * 3
ERROR_SOUND: Melody = [(BUZZ_HIGH, 0.20), (BUZZ, 0.20)] * 3  # a siren
TICK_SOUND: Melody = [(BUZZ, 0.008)]
# two short notes, going up when a device answers and down when it goes away
DEVICE_CONNECTED_SOUND: Melody = [(BUZZ, 0.06), (REST, 0.03), (BUZZ_HIGH, 0.09)]
DEVICE_DISCONNECTED_SOUND: Melody = [(BUZZ_HIGH, 0.06), (REST, 0.03), (BUZZ, 0.09)]
