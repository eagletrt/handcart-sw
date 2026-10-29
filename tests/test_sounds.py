"""The sounds of the buzzer: which melody, and which one cuts which."""

from backend.sounds.player import MELODIES, PRIORITY, Player
from backend.sounds.tones import RE7, near
from shared.models import Sound


def test_a_melody_plays_over_time():
    player = Player()
    player.play(Sound.CONFIRM, now=10.0)
    assert player.frequency(10.01) == RE7
    assert player.frequency(10.07) is None  # the rest between the two beeps
    assert player.frequency(10.12) == RE7
    assert player.frequency(11.0) is None  # finished


def test_a_tick_never_cuts_a_melody():
    player = Player()
    player.play(Sound.ERROR, now=10.0)
    player.play(Sound.TICK, now=10.1)
    assert player.frequency(10.25) is not None  # the alarm goes on
    player.play(Sound.TICK, now=20.0)
    assert player.frequency(20.001) == RE7  # alone, it ticks


def test_every_sound_has_a_melody_and_a_priority():
    assert set(MELODIES) == set(PRIORITY) == set(Sound)


def test_nothing_cuts_the_error_alarm():
    player = Player()
    player.play(Sound.ERROR, now=10.0)
    player.play(Sound.CONFIRM, now=10.1)
    player.play(Sound.DEVICE_DISCONNECTED, now=10.2)
    assert player.frequency(10.45) == RE7  # still the alarm: RE7, LA6, RE7... at 0.2 s each


def test_a_command_cuts_the_charge_done_tune():
    player = Player()
    player.play(Sound.CHARGE_DONE, now=10.0)
    player.play(Sound.CONFIRM, now=11.0)
    assert player.frequency(11.01) == RE7


def test_the_operator_can_stop_the_tune_of_a_job_done():
    player = Player()
    player.play(Sound.BALANCING_DONE, now=10.0)
    player.hush()
    assert player.frequency(10.01) is None


def test_the_operator_cannot_stop_an_alarm():
    player = Player()
    player.play(Sound.ERROR, now=10.0)
    player.hush()
    assert player.frequency(10.01) == RE7


def test_a_melody_moves_by_whole_octaves_to_the_resonance():
    melody = [(1000.0, 0.1), (None, 0.05), (1200.0, 0.1)]
    assert near(melody, 4000.0) == [(4000.0, 0.1), (None, 0.05), (4800.0, 0.1)]  # two octaves up
    assert near(melody, 1100.0) == melody  # already there
    assert near(melody, None) == melody  # no resonance known: as written


def test_the_player_plays_the_melodies_around_the_resonance():
    player = Player(resonance=RE7 * 2)
    player.play(Sound.CONFIRM, now=10.0)  # written on RE7
    assert player.frequency(10.01) == RE7 * 2


def test_a_tone_plays_for_its_time_and_any_sound_cuts_it():
    player = Player()
    player.tone(2500.0, 0.4, now=10.0)
    assert player.frequency(10.2) == 2500.0
    assert player.frequency(10.5) is None
    player.tone(2500.0, 0.4, now=20.0)
    player.play(Sound.TICK, now=20.1)
    assert player.frequency(20.101) == RE7
