"""The colour scales of the cell maps."""

from frontend.colors import (
    NEUTRAL,
    TEMPS_COLD,
    TEMPS_HOT,
    TEMPS_WARM,
    VOLTS_HIGH,
    VOLTS_LOW,
    diverging,
    mix,
    temperature,
)


def test_gray_in_the_middle_and_the_end_colours_at_the_ends():
    assert diverging(0, VOLTS_LOW, VOLTS_HIGH) == NEUTRAL
    assert diverging(-1, VOLTS_LOW, VOLTS_HIGH) == VOLTS_LOW
    assert diverging(1, VOLTS_LOW, VOLTS_HIGH) == VOLTS_HIGH


def test_beyond_the_ends_the_colour_stays_at_the_end():
    assert diverging(5, VOLTS_LOW, VOLTS_HIGH) == VOLTS_HIGH
    assert diverging(-5, VOLTS_LOW, VOLTS_HIGH) == VOLTS_LOW


def test_mix():
    assert mix("#000000", "#ffffff", 0.5) == "#808080"


def test_temperature_is_pinned_to_the_thresholds():
    assert temperature(10, cold=15, warm=45, limit=55) == TEMPS_COLD
    assert temperature(15, cold=15, warm=45, limit=55) == NEUTRAL
    assert temperature(45, cold=15, warm=45, limit=55) == TEMPS_WARM
    assert temperature(55, cold=15, warm=45, limit=55) == TEMPS_HOT


def test_temperature_warms_up_before_the_warm_threshold():
    assert temperature(40, cold=15, warm=45, limit=55) == mix(NEUTRAL, TEMPS_WARM, 25 / 30)
