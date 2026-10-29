"""The sounds of the buzzer: which melody, and which one cuts which."""

from backend.sounds.player import MELODIES, PRIORITY, Player
from backend.sounds.tones import RE7
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
