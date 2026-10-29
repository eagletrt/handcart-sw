"""The Graphs window, from the chart icon in the top bar: how the last charge (or balancing) went.

Two views, the two buttons at the top: Pack (its voltage, then the charger's current) and Cells (the
lowest and the highest cell, then the hottest probe). Each measure has its own chart, one above the
other on the same time axis: never two scales on one chart. The lines that matter (the target, the
limits) are drawn across, with their name.

The data is the record's samples (backend/recorder.py): one a second while the handcart does something.
The last run of them without a gap is the last charge; while the window is open, the new ones are
added every REFRESH_PERIOD.

A look at one moment, without a mouse: a touch on a chart, or a click on a framed chart, puts a line
across both charts there, with the time and the readings above them. Then the window takes the controls
(Context.window_captures): turning moves the line a little, the left and right arrows a lot, up and down
zoom in and out around it, a click puts the controls back on the buttons. A touch moves the line too,
and a finger dragged on a chart scrolls it (zoomed in), or takes the line along (handcart.js).
The line moves in time, not from sample to sample: as fine on a charge of ten samples (the simulator)
as on one of hours; the readings above are those between the two samples around it. While the line is
there the view stays still: the samples that keep coming do not stretch the time axis under it.
"""

import bisect
import time
from dataclasses import dataclass
from datetime import datetime

from nicegui import ui

from frontend.backend import Backend
from frontend.controls import STEPS, TURNS, Target
from frontend.targets import Reachable, button, usable
from shared.config import Config
from shared.models import InputEvent, Sample, State

LOOKBACK = 6 * 3600  # s of samples read when the window opens: longer than any charge
SESSION_GAP = 30.0  # s without samples: what comes after is another charge
REFRESH_PERIOD = 5.0  # s between two reads while the window is open
TURN_STEPS = 100  # a step of the knob moves the line 1/100 of what is in view
JUMP_STEPS = 10  # an arrow: 1/10
MIN_SPAN = 5.0  # s in view at the deepest zoom
# the line under the charts: always there, so nothing moves when the line comes or goes
HINT_LOOK = "Knob or touch: move · ← →: jump · ↑ ↓: zoom · Click: done"
HINT_START = "Touch a chart, or frame it and click, to read a moment"

# colors: one measure per chart is yellow, as the energy on the other screens. Min and max cells are a
# pair checked for color blindness on black (blue and orange). Red is only for the limits.
SINGLE = "#F3FF14"
CELL_MIN = "#3987e5"
CELL_MAX = "#d95926"
LIMIT = "#FF453A"
REFERENCE = "rgba(255,255,255,.70)"  # the target: a setting, not a limit
TEXT = "#FFFFFF"
MUTE = "rgba(255,255,255,.70)"
FAINT = "rgba(255,255,255,.46)"
GRID = "rgba(255,255,255,.12)"
PANEL = "#141411"
CURSOR = "#FFFFFF"  # the line at the moment looked at


@dataclass
class Explorer:
    """The line and the zoom, in time (s since 1970): plain to test.

    The samples go from `first` to `last`; the view shows `span` s from `start`, and the line is at
    `cursor`, always in view. A step is a share of the view, whatever the number of samples.
    """

    first: float = 0.0
    last: float = 0.0
    cursor: float = 0.0
    level: int = 0  # zoom: the view shows 1 / 2**level of the samples, never less than MIN_SPAN
    start: float = 0.0

    @property
    def span(self) -> float:
        length = self.last - self.first
        return max(length / 2**self.level, min(MIN_SPAN, length))

    @property
    def zoomed(self) -> bool:
        return self.level > 0

    def view(self) -> tuple[float, float]:
        if not self.zoomed:
            return self.first, self.last
        return self.start, self.start + self.span

    def cover(self, first: float, last: float) -> None:
        """The samples go from first to last now: the line and the view stay inside them."""
        self.first, self.last = first, last
        self.cursor = max(first, min(last, self.cursor))
        self.start = max(first, min(last - self.span, self.start))

    def middle(self) -> None:
        """The line in the middle of the view: where it is seen, not on an edge."""
        start, end = self.view()
        self.cursor = (start + end) / 2

    def move(self, steps: int, per_view: int) -> None:
        """Move the line `steps` times 1/per_view of the view; the view follows it."""
        self.cursor = max(self.first, min(self.last, self.cursor + steps * self.span / per_view))
        if self.cursor < self.start:
            self.start = self.cursor
        if self.cursor > self.start + self.span:
            self.start = self.cursor - self.span

    def pan(self, seconds: float) -> None:
        """Scroll the view by `seconds` (a finger); the line stays in it."""
        self.start = max(self.first, min(self.last - self.span, self.start + seconds))
        start, end = self.view()
        self.cursor = max(start, min(end, self.cursor))

    def zoom(self, steps: int) -> None:
        """In (+1) or out (-1), around the line."""
        self.level = max(0, self.level + steps)
        while self.level > 0 and (self.last - self.first) / 2**self.level < MIN_SPAN:
            self.level -= 1  # deep enough
        self.start = max(self.first, min(self.last - self.span, self.cursor - self.span / 2))


class GraphsWindow:
    def __init__(self, cfg: Config, backend: Backend) -> None:
        self._cfg = cfg
        self._backend = backend
        self._samples: list[Sample] = []  # the last charge, oldest first
        self._view = "pack"
        self._explorer = Explorer()
        self._looking: ui.echart | None = None  # the chart the line was put on, while looking at a moment

        with ui.element("div").classes("modal") as self.root, ui.element("div").classes("sheet graphs"):
            with ui.element("div").classes("ghead"):
                with ui.element("div").classes("gtitle"):
                    ui.label("Graphs").classes("sheet-title")
                    self._session = ui.label("").classes("sheet-sub")
                self._pack_button = ui.button("Pack", on_click=lambda: self._show("pack"))
                self._pack_button.props("flat no-caps text-color=white").classes("gtab")
                self._cells_button = ui.button("Cells", on_click=lambda: self._show("cells"))
                self._cells_button.props("flat no-caps text-color=white").classes("gtab")
                self._close = ui.button("Close", on_click=lambda: self.root.set_visibility(False))
                self._close.props("flat no-caps text-color=white").classes("gclose")
            self._top = ui.echart({}).classes("gchart")
            self._bottom = ui.echart({}).classes("gchart")
            for element in (self._top, self._bottom):
                # a tap or a drag, measured in the browser on the chart's own scale (handcart.js)
                for kind in ("pointerdown", "pointermove", "pointerup", "pointercancel"):
                    element.on(
                        kind,
                        lambda event, element=element: self._on_finger(element, event.args),
                        js_handler=f"(e) => chartFinger({element.id}, e, emit)",
                    )
            self._empty = ui.label(
                "Nothing recorded yet: the graphs fill while the handcart charges or balances"
            ).classes("gempty")
            self._hint = ui.label(HINT_START).classes("ghint")
        self.root.set_visibility(False)
        ui.timer(REFRESH_PERIOD, self._read_new)

    def reachable(self) -> list[Reachable]:
        top = Reachable(Target("chart top"), self._top, press=lambda: self._look(self._top))
        bottom = Reachable(Target("chart bottom"), self._bottom, press=lambda: self._look(self._bottom))
        return usable(
            button("close", self._close, priority=1),
            button("pack", self._pack_button),
            button("cells", self._cells_button),
            top,
            bottom,
        )

    @property
    def looking(self) -> bool:
        """Whether the line is on the charts: then the controls move it (on_gesture)."""
        return self.root.visible and self._looking is not None

    async def open(self) -> None:
        self._samples = []
        self._explorer = Explorer()
        self._stop_looking()
        self.root.set_visibility(True)
        self._show(self._view)
        await self._read_new()

    def on_gesture(self, event: InputEvent) -> None:
        """A gesture of the controls while looking at a moment."""
        steps = STEPS.get(event, 0)
        if event is InputEvent.PRESS:
            self._stop_looking()
        elif event in TURNS:
            self._explorer.move(steps, TURN_STEPS)
        elif event in (InputEvent.LEFT, InputEvent.RIGHT):
            self._explorer.move(steps, JUMP_STEPS)
        elif event is InputEvent.UP:
            self._explorer.zoom(1)
        elif event is InputEvent.DOWN:
            self._explorer.zoom(-1)
        self._draw()

    def _on_finger(self, element: ui.echart, finger: object) -> None:
        """{"tap": ms}: the line goes there. {"drag": s, "at": ms}: zoomed in, the view scrolls by s with
        the finger; else the line follows the finger."""
        if not self._samples or not isinstance(finger, dict):
            return
        if "tap" in finger:
            self._look(element, finger["tap"] / 1000)
        elif "drag" in finger and self._explorer.zoomed:
            if self._looking is None:
                self._look(element)
            self._explorer.pan(finger["drag"])
            self._draw()
        elif "drag" in finger:
            self._look(element, finger["at"] / 1000)

    def _look(self, element: ui.echart, at: float | None = None) -> None:
        """Put the line on the charts, marking this chart: at `at` (a touch, s since 1970), else where it
        was, else in the middle of the view."""
        if not self._samples:
            return
        if at is not None:
            self._explorer.cursor = at
        elif self._looking is None:
            self._explorer.middle()
        self._explorer.move(0, TURN_STEPS)  # inside the samples, and the view follows the line
        for chart_element in (self._top, self._bottom):
            chart_element.classes(remove="look")
        element.classes(add="look")
        self._looking = element
        self._hint.set_text(HINT_LOOK)
        self._draw()

    def _stop_looking(self) -> None:
        """The line goes, the zoom stays; the controls are back on the buttons."""
        self._looking = None
        for chart_element in (self._top, self._bottom):
            chart_element.classes(remove="look")
        self._hint.set_text(HINT_START)
        if self._samples:
            self._explorer.cover(self._samples[0].time, self._samples[-1].time)  # the new samples, now

    def _show(self, view: str) -> None:
        self._view = view
        if view == "pack":
            self._pack_button.classes(add="sel")
            self._cells_button.classes(remove="sel")
        else:
            self._cells_button.classes(add="sel")
            self._pack_button.classes(remove="sel")
        self._draw()

    async def _read_new(self) -> None:
        """Add the samples written since the last read (all of the last LOOKBACK when there are none)."""
        if not self.root.visible:
            return
        since = time.time() - LOOKBACK
        if self._samples:
            since = self._samples[-1].time + 0.001  # after the last one already here
        new = await self._backend.read_samples(since)
        if new is None:
            return  # the backend is restarting: the next read tries again
        first = self._samples[0].time if self._samples else None
        self._samples = last_session(self._samples + new, SESSION_GAP)
        if self._samples and self._samples[0].time != first and first is not None:
            self._explorer = Explorer()  # another charge began: the line and the zoom were on the last one
            self._stop_looking()
        if self._samples and self._looking is None:
            # while looking the view stays as it is: the new samples would stretch it under the line
            self._explorer.cover(self._samples[0].time, self._samples[-1].time)
        self._draw()

    def _draw(self) -> None:
        samples = self._samples
        explorer = self._explorer
        looked_at = None
        if self._looking is not None and samples:
            looked_at = at_time(samples, explorer.cursor)
        if looked_at is not None:
            self._session.set_text(readout(looked_at, self._view))
            self._session.classes(add="readout")
        else:
            self._session.set_text(session_text(samples))
            self._session.classes(remove="readout")
        self._empty.set_visibility(not samples)
        self._top.set_visibility(bool(samples))
        self._bottom.set_visibility(bool(samples))
        if not samples:
            return
        accumulator = self._cfg.accumulator
        view = None  # the time axis: as the samples go, unless zoomed or looking (then it stays still)
        shown = samples
        if explorer.zoomed or looked_at is not None:
            view = explorer.view()
            # only what is in view: the y scale then fits it, and zooming in shows the details
            shown = in_view(samples, *view)
        settings = self._backend.status.settings if self._backend.status is not None else None
        if self._view == "pack":
            target = None
            current_limit = None
            if settings is not None:
                target = (f"Target {settings.target_voltage:g} V", settings.target_voltage, REFERENCE)
                current_limit = (f"Max {settings.max_current:g} A", settings.max_current, REFERENCE)
            top = chart(
                "Pack voltage",
                "V",
                1,
                [("Pack", SINGLE, points(shown, "pack_voltage"))],
                target,
                min_range=10,
            )
            bottom = chart(
                "Charger current",
                "A",
                1,
                [("Current", SINGLE, points(shown, "charger_current"))],
                current_limit,
                min_range=2,
            )
        else:
            cell_limit = (f"Limit {accumulator.max_cell_voltage:.2f} V", accumulator.max_cell_voltage, LIMIT)
            top = chart(
                "Cell voltage",
                "V",
                3,
                [
                    ("Max", CELL_MAX, points(shown, "cell_max")),
                    ("Min", CELL_MIN, points(shown, "cell_min")),
                ],
                cell_limit,
                min_range=0.02,
            )
            hot = (f"Limit {accumulator.max_temperature:g} °C", accumulator.max_temperature, LIMIT)
            bottom = chart(
                "Hottest probe",
                "°C",
                1,
                [("Temperature", SINGLE, points(shown, "temp_max"))],
                hot,
                min_range=2,
            )
        # the same view and line on both: they share the time axis
        view_ms = None
        if view is not None:
            view_ms = (view[0] * 1000, view[1] * 1000)
        line = looked_at.time * 1000 if looked_at is not None else None
        replace_options(self._top, with_view(top, view_ms, line))
        replace_options(self._bottom, with_view(bottom, view_ms, line))


def replace_options(element: ui.echart, options: dict) -> None:
    element.options.clear()
    element.options.update(options)
    element.update()


def with_view(options: dict, view: tuple[float, float] | None, line: float | None) -> dict:
    """The chart zoomed on view (from, to in ms; None: all of it), with the line at `line` ms, or none.

    Always set, also to nothing: ECharts merges new options into the old ones, a missing key would keep
    the last zoom or line.
    """
    options["xAxis"]["min"] = view[0] if view is not None else None
    options["xAxis"]["max"] = view[1] if view is not None else None
    series = options["series"][0]
    if "markLine" not in series:
        series["markLine"] = {"silent": True, "symbol": "none", "label": {"show": False}, "data": []}
    if line is not None:
        series["markLine"]["data"].append({"xAxis": line, "lineStyle": {"color": CURSOR, "width": 2}})
    return options


def in_view(samples: list[Sample], start: float, end: float) -> list[Sample]:
    """The samples from start to end, and one more on each side: the lines reach the edges."""
    times = [s.time for s in samples]
    first = max(0, bisect.bisect_left(times, start) - 1)
    last = min(len(samples), bisect.bisect_right(times, end) + 1)
    return samples[first:last]


READINGS = (
    "pack_voltage",
    "current",
    "cell_min",
    "cell_max",
    "temp_max",
    "charger_voltage",
    "charger_current",
)


def at_time(samples: list[Sample], at: float) -> Sample:
    """The readings at `at`, between the two samples around it (a straight line, as drawn)."""
    times = [s.time for s in samples]
    i = bisect.bisect_left(times, at)
    if i == 0:
        return samples[0].model_copy(update={"time": at})
    if i == len(samples):
        return samples[-1].model_copy(update={"time": at})
    before, after = samples[i - 1], samples[i]
    if after.time == before.time:
        return after.model_copy(update={"time": at})
    share = (at - before.time) / (after.time - before.time)
    readings: dict[str, object] = {"time": at}
    for name in READINGS:
        a, b = getattr(before, name), getattr(after, name)
        readings[name] = None if a is None or b is None else a + (b - a) * share
    return before.model_copy(update=readings)


def readout(sample: Sample, view: str) -> str:
    """ "10:02:13 · 588.4 V · 5.9 A": the moment the line is on, with the readings of the view."""
    at = datetime.fromtimestamp(sample.time).strftime("%H:%M:%S")
    if view == "pack":
        return f"{at} · {value(sample.pack_voltage, 1, 'V')} · {value(sample.charger_current, 1, 'A')}"
    return (
        f"{at} · max {value(sample.cell_max, 3, 'V')} · min {value(sample.cell_min, 3, 'V')}"
        f" · {value(sample.temp_max, 1, '°C')}"
    )


def value(number: float | None, decimals: int, unit: str) -> str:
    if number is None:
        return f"— {unit}"
    return f"{number:.{decimals}f} {unit}"


def last_session(samples: list[Sample], gap: float) -> list[Sample]:
    """The last run of samples with no more than `gap` s between two: the last charge or balancing."""
    start = 0
    for i in range(1, len(samples)):
        if samples[i].time - samples[i - 1].time > gap:
            start = i
    return samples[start:]


def session_text(samples: list[Sample]) -> str:
    """ "Charge from 14:02 · 42 min": what the graphs show."""
    if not samples:
        return "No charge recorded"
    kind = "Charge"
    if any(s.state is State.BALANCING for s in samples):
        kind = "Balancing"
    start = datetime.fromtimestamp(samples[0].time).strftime("%H:%M")
    minutes = (samples[-1].time - samples[0].time) / 60
    return f"{kind} from {start} · {minutes:.0f} min"


def points(samples: list[Sample], field: str) -> list[list[float | None]]:
    """[time in ms, value] for ECharts; a missing reading is a gap in the line."""
    return [[s.time * 1000, getattr(s, field)] for s in samples]


def chart(
    title: str,
    unit: str,
    decimals: int,
    series: list[tuple[str, str, list[list[float | None]]]],
    line_across: tuple[str, float, str] | None,
    min_range: float = 0.0,
) -> dict:
    """The ECharts options of one chart: one y scale, the series as (name, color, points), and a line
    across (label, value, color) such as the target, or None. The y axis covers at least min_range
    (its unit), around the readings: a flat line is drawn in the middle, not squashed against an edge.

    Keys starting with ":" are JavaScript, for NiceGUI: the tooltip's numbers, and an axis that always
    reaches the line across.
    """
    several = len(series) > 1
    axis_decimals = max(decimals - 1, 0)  # one less than the tooltip: "4.10 V", "590 V" on the axis
    rounding = 10**axis_decimals  # the ends of the axis, rounded as its labels
    pad = f"Math.max(0, {min_range} - (v.max - v.min)) / 2"
    lowest = f"Math.floor((v.min - {pad}) * {rounding}) / {rounding}"
    highest = f"Math.ceil((v.max + {pad}) * {rounding}) / {rounding}"
    options: dict = {
        "animation": False,
        "backgroundColor": "transparent",
        "textStyle": {"fontFamily": "Helvetica Neue, Helvetica, Arial, sans-serif"},
        "title": {"text": title, "left": 0, "top": 0, "textStyle": {"color": TEXT, "fontSize": 16}},
        "grid": {"left": 52, "right": 56, "top": 32, "bottom": 26},
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {"type": "line", "lineStyle": {"color": FAINT}},
            "backgroundColor": PANEL,
            "borderColor": GRID,
            "textStyle": {"color": TEXT, "fontSize": 15},
            ":valueFormatter": f"v => v == null ? '—' : v.toFixed({decimals}) + ' {unit}'",
        },
        "xAxis": {
            "type": "time",
            "axisLine": {"lineStyle": {"color": GRID}},
            "axisTick": {"show": False},
            "axisLabel": {"color": FAINT, "fontSize": 13, "hideOverlap": True},
            "splitLine": {"show": False},
        },
        "yAxis": {
            "type": "value",
            "scale": True,
            "axisLabel": {
                "color": FAINT,
                "fontSize": 13,
                ":formatter": f"v => v.toFixed({axis_decimals}) + ' {unit}'",
            },
            "splitLine": {"lineStyle": {"color": GRID, "width": 1}},
            ":min": f"v => {lowest}",
            ":max": f"v => {highest}",
        },
        "series": [],
    }
    if several:
        options["legend"] = {
            "top": 0,
            "right": 0,
            "icon": "roundRect",
            "itemWidth": 14,
            "itemHeight": 4,
            "textStyle": {"color": MUTE, "fontSize": 14},
        }
    for name, color, data in series:
        options["series"].append(
            {
                "type": "line",
                "name": name,
                "data": data,
                "showSymbol": False,
                "sampling": "lttb",  # hours of samples: drawn with as many points as fit
                "lineStyle": {"width": 2, "color": color},
                "itemStyle": {"color": color},
                # several lines: each says its name at its end, not by color alone
                "endLabel": {"show": several, "formatter": name, "color": MUTE, "fontSize": 13},
                "labelLayout": {"moveOverlap": "shiftY"},  # two close lines: their names do not overlap
            }
        )
    if line_across is not None and options["series"]:
        label, value, color = line_across
        options["series"][0]["markLine"] = {
            "silent": True,
            "symbol": "none",
            "lineStyle": {"color": color, "type": "solid", "width": 1},
            "label": {"show": False},  # named in the title: on the chart it would cover the lines
            "data": [{"yAxis": value}],
        }
        # "Pack voltage  ━ Target 590 V", the dash in the color of the line
        options["title"]["text"] = f"{{t|{title}}}   {{line|━}} {{name|{label}}}"
        options["title"]["textStyle"]["rich"] = {
            "t": {"color": TEXT, "fontSize": 16, "fontWeight": "bold"},
            "line": {"color": color, "fontSize": 14},
            "name": {"color": MUTE, "fontSize": 14},
        }
        # the axis stretches to the line across: a target above the readings is still seen
        options["yAxis"][":max"] = f"v => Math.max({highest}, {value})"
    return options
