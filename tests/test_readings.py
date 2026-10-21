"""The frontend's reading of the status: what is open, what is over its limit, how far balancing is."""

from dataclasses import replace

import pytest

from frontend.backend import NO_BMS
from frontend.readings import (
    balancing_progress,
    cell_overvoltage,
    error_kind,
    first_open,
    overvoltage_cells,
)

MAX_CELL = 4.2
OPEN_BELOW = 2.0
CLOSED = (("supply", 12.0), ("mushroom", 12.0), ("charger", 12.0))
MUSHROOM_PRESSED = (("supply", 12.0), ("mushroom", 0.0), ("charger", 0.0))


def test_first_open_is_the_first_point_without_voltage():
    assert first_open(MUSHROOM_PRESSED, OPEN_BELOW) == "mushroom"
    assert first_open(CLOSED, OPEN_BELOW) is None


def test_a_point_not_read_yet_is_not_open():
    assert first_open((("supply", None), ("mushroom", 12.0)), OPEN_BELOW) is None


def test_overvoltage_cells_by_index():
    bms = replace(NO_BMS, cells=(4.1, 4.25, None, 4.3))
    assert overvoltage_cells(bms, MAX_CELL) == {1, 3}


def test_cell_overvoltage_read_or_reported_by_the_bms():
    assert cell_overvoltage(replace(NO_BMS, cells=(4.1, 4.25)), MAX_CELL)
    assert cell_overvoltage(replace(NO_BMS, errors=frozenset({"cellboard3CellOvervoltage"})), MAX_CELL)
    assert cell_overvoltage(replace(NO_BMS, errors=frozenset({"overvoltage"})), MAX_CELL)
    assert not cell_overvoltage(
        replace(NO_BMS, errors=frozenset({"cellboard3CellOvertemperature"})), MAX_CELL
    )


def test_error_kind():
    over = replace(NO_BMS, cells=(4.3,))
    assert (
        error_kind(over, MUSHROOM_PRESSED, MAX_CELL, OPEN_BELOW) == "mushroom"
    )  # what the operator did first
    assert error_kind(over, CLOSED, MAX_CELL, OPEN_BELOW) == "cell"
    assert error_kind(NO_BMS, CLOSED, MAX_CELL, OPEN_BELOW) == "loop"


@pytest.mark.parametrize(
    ("delta", "progress"),
    [(0.050, 0.0), (0.030, 50.0), (0.010, 100.0), (0.005, 100.0), (0.060, 0.0)],
)
def test_balancing_progress(delta, progress):
    assert balancing_progress(start_delta=0.050, delta=delta, threshold=0.010) == pytest.approx(progress)


def test_balancing_that_starts_under_the_threshold_is_done():
    assert balancing_progress(start_delta=0.008, delta=0.008, threshold=0.010) == 100.0
