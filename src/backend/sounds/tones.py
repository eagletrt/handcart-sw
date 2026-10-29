"""Notes and melodies for the buzzer.

A Melody is what the buzzer plays: a list of (frequency in Hz or REST, seconds). The tunes are written in
beats, as on a score, and phrase() turns them into a Melody; the short beeps are written in seconds directly.
"""


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


# The handcart's buzzer is a piezo loud only at about 2120 Hz: a semitone away it is already 12-17 dB softer,
# and further away near the room's noise (measured with a phone recording of a sweep of tones). So the
# signals all play that one note, told apart by their rhythm; the tunes play as written, and their notes
# far from it are soft: no key makes every note of a tune loud on a piezo.
BUZZ = 2120.0  # Hz


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

# The signals, in seconds: all on the buzzer's one loud note, told apart by their rhythm alone
CONFIRM_SOUND: Melody = [(BUZZ, 0.05), (REST, 0.05), (BUZZ, 0.05)]  # two quick beeps: done
REFUSED_SOUND: Melody = [(BUZZ, 0.35)]  # one long beep: "no"
FAILED_SOUND: Melody = [(BUZZ, 0.15), (REST, 0.1), (BUZZ, 0.6)]  # short, then very long
WARNING_SOUND: Melody = [(BUZZ, 0.1), (REST, 0.1)] * 3  # three short beeps
ERROR_SOUND: Melody = [(BUZZ, 0.3), (REST, 0.1)] * 3  # three long beeps, again every so often
TICK_SOUND: Melody = [(BUZZ, 0.008)]
# beeps closer and closer, then held: the TS is going on
PRECHARGE_SOUND: Melody = [
    (BUZZ, 0.08),
    (REST, 0.2),
    (BUZZ, 0.08),
    (REST, 0.12),
    (BUZZ, 0.08),
    (REST, 0.06),
    (BUZZ, 0.4),
]
TS_ON_SOUND: Melody = [(BUZZ, 0.1), (REST, 0.08), (BUZZ, 0.7)]  # held: the TS is on
# beeps further and further apart: the AIRs opened, the TS goes off
DISCHARGE_SOUND: Melody = [
    (BUZZ, 0.08),
    (REST, 0.06),
    (BUZZ, 0.08),
    (REST, 0.12),
    (BUZZ, 0.08),
    (REST, 0.2),
    (BUZZ, 0.08),
]
# short then long when a device answers, long then short when it goes away
DEVICE_CONNECTED_SOUND: Melody = [(BUZZ, 0.05), (REST, 0.04), (BUZZ, 0.15)]
DEVICE_DISCONNECTED_SOUND: Melody = [(BUZZ, 0.15), (REST, 0.04), (BUZZ, 0.05)]
