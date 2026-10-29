"""The sounds of the buzzer: which melody, and which one cuts which."""

import pytest

from backend.sounds.player import MELODIES, PRIORITY, Player
from backend.sounds.tones import BUZZ, BUZZ_HIGH, SILENT, in_loudest_key, loudness
from shared.models import Sound


def test_a_melody_plays_over_time():
    player = Player()
    player.play(Sound.CONFIRM, now=10.0)
    assert player.frequency(10.01) == BUZZ
    assert player.frequency(10.07) is None  # the rest between the two beeps
    assert player.frequency(10.12) == BUZZ
    assert player.frequency(11.0) is None  # finished


def test_a_tick_never_cuts_a_melody():
    player = Player()
    player.play(Sound.ERROR, now=10.0)
    player.play(Sound.TICK, now=10.1)
    assert player.frequency(10.25) is not None  # the alarm goes on
    player.play(Sound.TICK, now=20.0)
    assert player.frequency(20.001) == BUZZ  # alone, it ticks


def test_every_sound_has_a_melody_and_a_priority():
    assert set(MELODIES) == set(PRIORITY) == set(Sound)


def test_nothing_cuts_the_error_alarm():
    player = Player()
    player.play(Sound.ERROR, now=10.0)
    player.play(Sound.CONFIRM, now=10.1)
    player.play(Sound.DEVICE_DISCONNECTED, now=10.2)
    assert player.frequency(10.45) == BUZZ_HIGH  # still the siren: high, loud, high... at 0.2 s each


def test_a_command_cuts_the_charge_done_tune():
    player = Player()
    player.play(Sound.CHARGE_DONE, now=10.0)
    player.play(Sound.CONFIRM, now=11.0)
    assert player.frequency(11.01) == BUZZ


def test_the_operator_can_stop_the_tune_of_a_job_done():
    player = Player()
    player.play(Sound.BALANCING_DONE, now=10.0)
    player.hush()
    assert player.frequency(10.01) is None


def test_the_operator_cannot_stop_an_alarm():
    player = Player()
    player.play(Sound.ERROR, now=10.0)
    player.hush()
    assert player.frequency(10.01) == BUZZ_HIGH


def test_the_signals_play_only_the_buzzers_loud_notes():
    tunes = {Sound.CHARGE_DONE, Sound.BALANCING_DONE, Sound.STARTUP, Sound.POWER_OFF}
    for sound, melody in MELODIES.items():
        if sound not in tunes:
            assert {frequency for frequency, _ in melody} <= {BUZZ, BUZZ_HIGH, None}, sound


def test_a_tune_moves_to_the_loudest_key_as_the_same_tune():
    melody = [(1000.0, 1.0), (None, 0.05), (1200.0, 0.1)]  # held on 1000 Hz, where the buzzer is soft
    moved = in_loudest_key(melody)
    assert moved[1] == (None, 0.05)  # the rests stay
    assert moved[2][0] / moved[0][0] == pytest.approx(1.2)  # the same interval: the same tune
    assert loudness(moved[0][0]) > -1  # the note held longest on the loudest


def test_loudness_as_measured():
    assert loudness(BUZZ) == pytest.approx(0, abs=0.5)
    assert loudness(BUZZ_HIGH) == pytest.approx(-9.7, abs=0.5)
    assert loudness(300.0) == SILENT  # below what was measured


def test_a_tone_plays_for_its_time_and_any_sound_cuts_it():
    player = Player()
    player.tone(2500.0, 0.4, now=10.0)
    assert player.frequency(10.2) == 2500.0
    assert player.frequency(10.5) is None
    player.tone(2500.0, 0.4, now=20.0)
    player.play(Sound.TICK, now=20.1)
    assert player.frequency(20.101) == BUZZ
