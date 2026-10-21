"""The colour scales of the cell maps."""

from frontend.colors import NEUTRAL, VOLTS_HIGH, VOLTS_LOW, diverging, mix


def test_gray_in_the_middle_and_the_end_colours_at_the_ends():
    assert diverging(0, VOLTS_LOW, VOLTS_HIGH) == NEUTRAL
    assert diverging(-1, VOLTS_LOW, VOLTS_HIGH) == VOLTS_LOW
    assert diverging(1, VOLTS_LOW, VOLTS_HIGH) == VOLTS_HIGH


def test_beyond_the_ends_the_colour_stays_at_the_end():
    assert diverging(5, VOLTS_LOW, VOLTS_HIGH) == VOLTS_HIGH
    assert diverging(-5, VOLTS_LOW, VOLTS_HIGH) == VOLTS_LOW


def test_mix():
    assert mix("#000000", "#ffffff", 0.5) == "#808080"
