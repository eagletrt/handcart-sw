"""The sounds of the buzzer: which melody, and which one cuts which."""

from backend.sounds.player import MELODIES, PRIORITY, Player
from backend.sounds.tones import BUZZ
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
    assert player.frequency(10.45) == BUZZ  # still the alarm: its second beep


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
    assert player.frequency(10.01) == BUZZ


def test_the_signals_play_only_the_buzzers_loud_note():
    tunes = {Sound.CHARGE_DONE, Sound.BALANCING_DONE, Sound.STARTUP, Sound.POWER_OFF}
    for sound, melody in MELODIES.items():
        if sound not in tunes:
            assert {frequency for frequency, _ in melody} <= {BUZZ, None}, sound


def test_a_tone_plays_for_its_time_and_any_sound_cuts_it():
    player = Player()
    player.tone(2500.0, 0.4, now=10.0)
    assert player.frequency(10.2) == 2500.0
    assert player.frequency(10.5) is None
    player.tone(2500.0, 0.4, now=20.0)
    player.play(Sound.TICK, now=20.1)
    assert player.frequency(20.101) == BUZZ
