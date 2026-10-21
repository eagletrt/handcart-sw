"""The frontend's reading of the status: what is open, what is over its limit, how far balancing is."""

from dataclasses import replace

import pytest

from frontend.backend import NO_BMS, NO_CHARGER
from frontend.readings import (
    balancing_progress,
    cell_overvoltage,
    details_screen,
    error_kind,
    first_open,
    hot_probes,
    overvoltage_cells,
    ts_discharging,
    waiting_for,
)
from shared.models import Settings, State, Status

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


def test_error_kind(cfg):
    pack = cfg.accumulator
    over = replace(NO_BMS, cells=(pack.max_cell_voltage + 0.1,))
    hot = replace(NO_BMS, temp_max=pack.max_temperature + 1)
    # the mushroom first: it is what the operator did
    assert error_kind("shutdown loop open at mushroom", over, pack) == "mushroom"
    assert error_kind("BMS: overvoltage", over, pack) == "cell"
    assert error_kind("Cell temperature 60.0 °C, above 55 °C", hot, pack) == "hot"
    assert error_kind("BMS: connectorDisconnected", NO_BMS, pack) == "bms"
    assert error_kind("BMS in error", NO_BMS, pack) == "bms"
    assert error_kind("Charger: Error_Overtemperature", NO_BMS, pack) == "charger"
    assert error_kind("The BMS stopped responding", hot, pack) == "offline"  # its readings are old
    assert error_kind("The charger stopped responding", NO_BMS, pack) == "offline"
    assert error_kind("shutdown loop open at TSMS", NO_BMS, pack) == "loop"
    # in ERROR the SD relay is open, so the loop reads open: not a reason to show the mushroom
    assert error_kind("BMS: connectorDisconnected", NO_BMS, pack) != "mushroom"


def test_details_open_the_screen_about_the_error():
    assert details_screen("hot", "") == "cells"
    assert details_screen("bms", "BMS in error") == "cells"
    assert details_screen("charger", "Charger: in error") == "charger"
    assert details_screen("offline", "The charger stopped responding") == "charger"
    assert details_screen("offline", "The BMS stopped responding") == "cells"
    assert details_screen("mushroom", "shutdown loop open at mushroom") == "shutdown"
    assert details_screen("loop", "shutdown loop open at TSMS") == "shutdown"


def test_hot_probes_by_index():
    bms = replace(NO_BMS, temps=(30.0, 56.0, None, 60.0))
    assert hot_probes(bms, 55.0) == {1, 3}


@pytest.mark.parametrize(
    ("delta", "progress"),
    [(0.050, 0.0), (0.030, 50.0), (0.010, 100.0), (0.005, 100.0), (0.060, 0.0)],
)
def test_balancing_progress(delta, progress):
    assert balancing_progress(start_delta=0.050, delta=delta, threshold=0.010) == pytest.approx(progress)


def test_balancing_that_starts_under_the_threshold_is_done():
    assert balancing_progress(start_delta=0.008, delta=0.008, threshold=0.010) == 100.0


def test_the_discharge_warning_shows_after_ts_off_until_below_60_volts():
    live = replace(NO_BMS, connected=True, ts_below_60v=False, ts_voltage=420.0)
    safe = replace(live, ts_below_60v=True, ts_voltage=30.0)
    unknown = replace(live, ts_below_60v=None)
    assert ts_discharging(State.IDLE, live)
    assert ts_discharging(State.ERROR, live)
    assert not ts_discharging(State.IDLE, safe)
    assert not ts_discharging(State.CHARGE, live)  # asked on: it is supposed to be live
    assert not ts_discharging(State.PRECHARGE, live)
    assert not ts_discharging(State.IDLE, unknown)  # "HV ?" in the top bar instead


def test_the_check_button_says_what_is_missing():
    bms = replace(NO_BMS, connected=True)
    charger = replace(NO_CHARGER, connected=True)

    def status(bms, charger):
        return Status(
            state=State.CHECK,
            message="",
            settings=Settings(target_voltage=590, max_current=6, balancing_threshold=0.01),
            bms=bms,
            charger=charger,
            shutdown=(),
        )

    assert waiting_for(status(NO_BMS, NO_CHARGER))[0] == "Connect accumulator and charger"
    assert waiting_for(status(NO_BMS, charger))[0] == "Connect accumulator"
    assert waiting_for(status(bms, NO_CHARGER))[0] == "Connect charger"
    assert waiting_for(status(bms, charger))[0] == "Resetting charger"
