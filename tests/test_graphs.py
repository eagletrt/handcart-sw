"""The Graphs window: which samples make the last charge, and what each chart draws."""

import pytest

from frontend.graphs_window import (
    JUMP_STEPS,
    LIMIT,
    MIN_SPAN,
    TURN_STEPS,
    Explorer,
    at_time,
    chart,
    in_view,
    last_session,
    points,
    readout,
    session_text,
    with_view,
)
from shared.models import Sample, State


def sample(at: float, state: State = State.CHARGE, pack_voltage: float | None = 550.0) -> Sample:
    return Sample(
        time=at,
        state=state,
        pack_voltage=pack_voltage,
        current=6.0,
        cell_min=3.8,
        cell_max=3.82,
        temp_max=30.0,
        charger_voltage=551.0,
        charger_current=6.1,
    )


def test_the_last_charge_is_the_last_run_without_a_gap():
    samples = [sample(t) for t in (0, 1, 2, 100, 101, 102)]
    assert [s.time for s in last_session(samples, gap=30)] == [100, 101, 102]
    assert last_session([], gap=30) == []


def test_what_the_graphs_show_is_said_above_them():
    assert session_text([]) == "No charge recorded"
    charge = [sample(t) for t in range(0, 601, 60)]
    assert session_text(charge).startswith("Charge from ") and session_text(charge).endswith("· 10 min")
    balancing = [sample(0, State.BALANCING), sample(60, State.BALANCING)]
    assert session_text(balancing).startswith("Balancing")


def test_a_missing_reading_is_a_gap_in_the_line():
    assert points([sample(1.0), sample(2.0, pack_voltage=None)], "pack_voltage") == [
        [1000.0, 550.0],
        [2000.0, None],
    ]


def test_one_line_no_legend_two_lines_a_legend_and_their_names():
    one = chart("Pack voltage", "V", 1, [("Pack", "#fff", [])], None)
    assert "legend" not in one and not one["series"][0]["endLabel"]["show"]
    two = chart("Cell voltage", "V", 3, [("Max", "#f00", []), ("Min", "#00f", [])], None)
    assert "legend" in two and all(s["endLabel"]["show"] for s in two["series"])


def test_the_line_across_is_always_in_view():
    options = chart("Cell voltage", "V", 3, [("Max", "#f00", [])], ("Limit 4.20 V", 4.2, LIMIT))
    mark = options["series"][0]["markLine"]
    assert mark["data"] == [{"yAxis": 4.2}]
    assert "Limit 4.20 V" in options["title"]["text"]  # named in the title, not on the chart
    assert options["yAxis"][":max"].startswith("v => Math.max(") and options["yAxis"][":max"].endswith(
        ", 4.2)"
    )


def test_a_flat_line_gets_at_least_min_range_of_axis():
    options = chart("Pack voltage", "V", 1, [("Pack", "#fff", [])], None, min_range=10)
    assert "10" in options["yAxis"][":min"] and "10" in options["yAxis"][":max"]


def test_the_knob_is_ten_times_finer_than_the_arrows_even_on_a_few_samples():
    explorer = Explorer(first=0.0, last=10.0, cursor=5.0)  # a charge of ten samples: the simulator
    explorer.move(1, per_view=TURN_STEPS)
    assert explorer.cursor == pytest.approx(5.1)
    explorer.move(1, per_view=JUMP_STEPS)
    assert explorer.cursor == pytest.approx(6.1)
    explorer.move(100, per_view=JUMP_STEPS)
    assert explorer.cursor == 10.0  # stops at the end


def test_zooming_in_halves_the_view_around_the_line_down_to_min_span():
    explorer = Explorer(first=0.0, last=1000.0, cursor=900.0)
    explorer.zoom(1)
    assert explorer.view() == (500.0, 1000.0)  # around the line, not past the end
    for _ in range(20):
        explorer.zoom(1)
    assert MIN_SPAN <= explorer.span < 2 * MIN_SPAN
    explorer.zoom(-30)
    assert not explorer.zoomed and explorer.view() == (0.0, 1000.0)


def test_a_short_charge_can_be_zoomed_too():
    explorer = Explorer(first=0.0, last=11.0, cursor=5.0)
    explorer.zoom(1)
    assert explorer.zoomed and explorer.span == pytest.approx(5.5)


def test_zoomed_in_the_view_follows_the_line():
    explorer = Explorer(first=0.0, last=1000.0, cursor=100.0)
    explorer.zoom(2)  # 250 s in view
    explorer.move(1, per_view=1)  # a whole view further
    start, end = explorer.view()
    assert start <= explorer.cursor <= end and start > 0


def test_a_finger_scrolls_the_zoomed_view_and_the_line_stays_in_it():
    explorer = Explorer(first=0.0, last=1000.0, cursor=500.0)
    explorer.zoom(2)  # 250 s around 500
    explorer.pan(-100)
    start, end = explorer.view()
    assert start == pytest.approx(275.0) and start <= explorer.cursor <= end
    explorer.pan(-1000)
    assert explorer.view()[0] == 0.0  # not before the first sample
    assert explorer.cursor == pytest.approx(explorer.view()[1])  # pulled along at the edge


def test_the_line_starts_in_the_middle_of_the_view():
    explorer = Explorer(first=100.0, last=200.0)
    explorer.middle()
    assert explorer.cursor == 150.0


def test_the_readings_between_two_samples():
    samples = [sample(0.0, pack_voltage=500.0), sample(10.0, pack_voltage=600.0)]
    assert at_time(samples, 2.5).pack_voltage == pytest.approx(525.0)
    assert at_time(samples, 2.5).time == 2.5
    assert at_time(samples, -1).pack_voltage == 500.0 and at_time(samples, 99).pack_voltage == 600.0
    gap = [sample(0.0, pack_voltage=None), sample(10.0)]
    assert at_time(gap, 5.0).pack_voltage is None


def test_only_the_samples_in_view_and_one_on_each_side():
    samples = [sample(float(t)) for t in range(10)]
    assert [s.time for s in in_view(samples, 3.5, 6.5)] == [3.0, 4.0, 5.0, 6.0, 7.0]


def test_the_readings_at_the_line():
    text = readout(sample(0.0), "pack")
    assert text.endswith("· 550.0 V · 6.1 A")
    assert readout(sample(0.0), "cells").endswith("· max 3.820 V · min 3.800 V · 30.0 °C")
    assert readout(sample(0.0, pack_voltage=None), "pack").endswith("· — V · 6.1 A")


def test_the_view_and_the_line_are_always_set_even_to_nothing():
    plain = with_view(chart("Pack voltage", "V", 1, [("Pack", "#fff", [])], None), None, None)
    assert plain["xAxis"]["min"] is None and plain["series"][0]["markLine"]["data"] == []
    looked = chart("Pack voltage", "V", 1, [("Pack", "#fff", [])], ("Target 590 V", 590, LIMIT))
    looked = with_view(looked, (1000.0, 2000.0), 1500.0)
    assert looked["xAxis"]["min"] == 1000.0 and looked["xAxis"]["max"] == 2000.0
    assert [d.get("xAxis") for d in looked["series"][0]["markLine"]["data"]] == [None, 1500.0]
