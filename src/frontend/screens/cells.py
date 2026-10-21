"""Cells screen: a map of every cell (or temperature probe), min/max/delta, and balancing."""

import time
from collections import deque
from dataclasses import dataclass

from nicegui import ui

from frontend import colors
from frontend.readings import balancing_progress, overvoltage_cells
from frontend.screens import Actions
from frontend.targets import Reachable, button, usable
from shared.config import Config
from shared.models import BmsSnapshot, Command, State, Status

MAP_WINDOW = 0.030  # V: full violet 30 mV under the pack average, full orange 30 mV over it
HINT = "Tap a cell, or click the knob, to read it"


@dataclass(frozen=True)
class Square:
    """One cell or probe on the map."""

    classes: str  # CSS: "c", plus hi (highest), lo (lowest), bal (balancing), flt (blinking red)
    color: str
    text: str  # shown under the map when the cursor is on it
    alarm: bool = False  # that text in red


TREND_PERIOD = 5.0  # s between two points of the balancing trend
TREND_POINTS = 120  # points kept: the last 10 minutes


class CellsScreen:
    def __init__(self, cfg: Config, actions: Actions) -> None:
        self._cfg = cfg.accumulator
        self._volts = True  # False: temperatures
        self._trend: deque[float] = deque(maxlen=TREND_POINTS)  # cell delta while balancing, V
        self._next_trend_point = 0.0  # s, monotonic
        self._start_delta: float | None = None  # V, when balancing began: 0 % on the progress bar
        self.cursor: int | None = None  # the square under the cursor (set by the page, from controls.py)
        self._squares: list[Square] = []  # as last drawn

        with ui.element("div").classes("tab cells") as self.root:
            with ui.element("div").classes("cells-head"):
                with ui.element("div").classes("seg"):
                    self._volts_button = ui.button("Volts", on_click=lambda: self._set_mode(True))
                    self._temps_button = ui.button("Temps", on_click=lambda: self._set_mode(False))
                    for button in (self._volts_button, self._temps_button):
                        button.props("flat no-caps text-color=white")
                with ui.element("div").classes("cstats"):
                    self._min = self._cstat("Min")
                    self._max = self._cstat("Max")
                    with ui.element("div"):
                        ui.label("Delta").classes("lbl")
                        with ui.element("div").classes("vrow"):
                            self._delta = ui.label("—").classes("v num")
                            self._trend_chart = ui.html("").classes("trend")
            self._map = ui.html("")
            with ui.element("div").classes("cfoot"):
                with ui.element("div").classes("cleft"):
                    self._legend = ui.html("").classes("cleg num")
                    self._detail = ui.label(HINT).classes("detail hint num")
                # the balancing threshold, in the settings window
                self._threshold = ui.button(icon="tune", on_click=actions.open_balancing_settings)
                self._threshold.props("flat text-color=white").classes("thrbtn")
                with (
                    ui.button(on_click=lambda: actions.send(Command.BALANCE))
                    .props("unelevated no-caps")
                    .classes("balbtn") as self._balance,
                    ui.element("div").classes("btxt"),  # the note under the label: it can be long
                ):
                    self._balance_label = ui.label("Balance")
                    self._balance_note = ui.label("").classes("bs num")
        self._set_mode(True)

    def record(self, status: Status) -> None:
        """Follow the balancing, also while another screen is shown. Called at every refresh."""
        delta = status.bms.cell_delta
        if status.state is not State.BALANCING:
            self._trend.clear()
            self._start_delta = None
            return
        if delta is None:
            return
        if self._start_delta is None:
            self._start_delta = delta
        now = time.monotonic()
        if now >= self._next_trend_point:
            self._trend.append(delta)
            self._next_trend_point = now + TREND_PERIOD

    def update(self, status: Status) -> None:
        if self._volts:
            self._show_volts(status.bms)
            self._trend_chart.set_content(self._trend_svg(status.settings.balancing_threshold))
        else:
            self._show_temps(status.bms)
            self._trend_chart.set_content("")
        self._update_detail()
        self._update_balance(status.bms, status.state, status.settings.balancing_threshold)

    def reachable(self) -> list[Reachable]:
        # the frame starts on the mode shown: one turn to the other one, a click to the map (controls.py)
        if self._volts:
            volts_priority, temps_priority = 1, 0
        else:
            volts_priority, temps_priority = 0, 1
        return usable(
            button("volts", self._volts_button, priority=volts_priority, opens_map=True),
            button("temps", self._temps_button, priority=temps_priority, opens_map=True),
            button("threshold", self._threshold),
            button("balance", self._balance),
        )

    # for the physical controls (controls.py)

    def map_name(self) -> str:
        if self._volts:
            return "volts"
        return "temps"

    def map_size(self) -> tuple[int, int]:
        """(cellboards, squares per cellboard) of the map shown."""
        if self._volts:
            return self._cfg.cellboards, self._cfg.cells_per_cellboard
        return self._cfg.cellboards, self._cfg.temps_per_cellboard

    def map_start(self, bms: BmsSnapshot) -> int:
        """Where the cursor starts: a faulty cell, else the highest cell; in temps, the hottest probe."""
        if self._volts:
            faulty = overvoltage_cells(bms, self._cfg.max_cell_voltage)
            if faulty:
                return min(faulty)
            values = bms.cells
        else:
            values = bms.temps
        readings = [(value, i) for i, value in enumerate(values) if value is not None]
        if not readings:
            return 0
        return max(readings)[1]

    def show_volts(self) -> None:
        self._set_mode(True)

    def show_temps(self) -> None:
        self._set_mode(False)

    # volts and temperatures

    def _show_volts(self, bms: BmsSnapshot) -> None:
        cells = bms.cells
        faulty = overvoltage_cells(bms, self._cfg.max_cell_voltage)  # left out of the scale and the stats
        healthy = [v for i, v in enumerate(cells) if v is not None and i not in faulty]
        if not healthy:
            self._empty()
            return
        average = sum(healthy) / len(healthy)
        highest, lowest = cells.index(max(healthy)), cells.index(min(healthy))

        squares = []
        for i, v in enumerate(cells):
            classes = "c"
            if i in faulty:
                classes += " flt"
            elif i == highest:
                classes += " hi"
            if i == lowest:
                classes += " lo"
            if i < len(bms.balancing) and bms.balancing[i]:
                classes += " bal"
            board, cell = divmod(i, self._cfg.cells_per_cellboard)
            if v is None:
                color, reading = colors.NO_READING, "—"
            elif i in faulty:
                color, reading = colors.NEUTRAL, f"{v:.3f} V · overvoltage"  # the CSS paints it red
            else:
                position = (v - average) / MAP_WINDOW
                color, reading = colors.diverging(position, colors.VOLTS_LOW, colors.VOLTS_HIGH), f"{v:.3f} V"
            squares.append(
                Square(classes, color, f"CB{board + 1} · cell {cell + 1} · {reading}", i in faulty)
            )
        self._draw(squares, self._cfg.cells_per_cellboard, column_gap=3)

        self._min.set_text(f"{min(healthy):.3f} V")
        self._max.set_text(f"{max(healthy):.3f} V")
        self._delta.set_text(f"{(max(healthy) - min(healthy)) * 1000:.0f} mV")
        low, high = average - MAP_WINDOW, average + MAP_WINDOW
        scale = colors.gradient(colors.VOLTS_LOW, colors.VOLTS_HIGH)
        legend = (
            f'<span class="li"><i class="grad" style="background:{scale}"></i>{low:.3f}–{high:.3f}</span>'
            '<span class="li"><i class="sw hi"></i>Highest</span>'
            '<span class="li"><i class="sw lo"></i>Lowest</span>'
        )
        if any(bms.balancing):  # only then: with Fault too the legend would not fit
            legend += '<span class="li"><i class="sw bal"></i>Balancing</span>'
        if faulty:
            legend += '<span class="li"><i class="sw flt"></i>Fault</span>'
        self._legend.set_content(legend)

    def _show_temps(self, bms: BmsSnapshot) -> None:
        temps = [t for t in bms.temps if t is not None]
        if not temps:
            self._empty()
            return
        hottest = bms.temps.index(max(temps))

        pack = self._cfg
        squares = []
        for i, t in enumerate(bms.temps):
            classes = "c"
            if i == hottest:
                classes += " hi"
            alarm = False
            if t is None:
                color, reading = colors.NO_READING, "—"
            elif t > pack.max_temperature:
                color, reading, alarm = colors.NEUTRAL, f"{t:.1f} °C · too hot", True
                classes += " flt"  # blinking red, from the CSS
            elif t > pack.warm_temperature:
                color, reading = self._temperature_color(t), f"{t:.1f} °C · warm"
            elif t < pack.cold_temperature:
                color, reading = self._temperature_color(t), f"{t:.1f} °C · cold"
            else:
                color, reading = self._temperature_color(t), f"{t:.1f} °C"
            board, probe = divmod(i, pack.temps_per_cellboard)
            squares.append(Square(classes, color, f"CB{board + 1} · probe {probe + 1} · {reading}", alarm))
        # narrower columns (48 probes), same rows: the map keeps its height, nothing below it moves
        self._draw(squares, pack.temps_per_cellboard, column_gap=2)

        self._min.set_text(f"{min(temps):.1f} °C")
        self._max.set_text(f"{max(temps):.1f} °C")
        self._delta.set_text(f"{max(temps) - min(temps):.1f} °C")
        cold, warm, limit = pack.cold_temperature, pack.warm_temperature, pack.max_temperature
        blue = f"background:{colors.TEMPS_COLD}"
        scale = f"background:{colors.temperature_gradient(cold, warm, limit)}"
        self._legend.set_content(
            f'<span class="li"><i class="sw" style="{blue}"></i>&lt; {cold:g}</span>'
            f'<span class="li"><i class="grad" style="{scale}"></i>{cold:g} · {warm:g} · {limit:g}</span>'
            f'<span class="li"><i class="sw flt"></i>&gt; {limit:g} °C</span>'
            '<span class="li"><i class="sw hi"></i>Hottest</span>'
        )

    def _temperature_color(self, temp: float) -> str:
        pack = self._cfg
        return colors.temperature(temp, pack.cold_temperature, pack.warm_temperature, pack.max_temperature)

    def _empty(self) -> None:
        self._squares = []
        self._map.set_content("")
        for label in (self._min, self._max, self._delta):
            label.set_text("—")
        self._legend.set_content("")

    def _draw(self, squares: list[Square], per_board: int, column_gap: int) -> None:
        """One row per cellboard: its name, then its squares; "cur" marks the cursor.

        data-i tells handcart.js which square was touched.
        """
        self._squares = squares
        columns = f"38px repeat({per_board}, minmax(0,1fr))"
        rows = [f'<div class="cmap" style="grid-template-columns: {columns}; column-gap: {column_gap}px">']
        for i, square in enumerate(squares):
            if i % per_board == 0:
                rows.append(f'<div class="rl">CB{i // per_board + 1}</div>')
            classes = square.classes
            if i == self.cursor:
                classes += " cur"
            rows.append(f'<div class="{classes}" style="background:{square.color}" data-i="{i}"></div>')
        rows.append("</div>")
        self._map.set_content("".join(rows))

    def _update_detail(self) -> None:
        """Under the map: the square under the cursor, or how to get one."""
        if self.cursor is None or self.cursor >= len(self._squares):
            self._detail.set_text(HINT)
            self._detail.classes(replace="detail hint num")
            return
        square = self._squares[self.cursor]
        self._detail.set_text(square.text)
        if square.alarm:
            self._detail.classes(replace="detail alarm num")
        else:
            self._detail.classes(replace="detail num")

    def _trend_svg(self, threshold: float) -> str:
        """Delta over the last minutes of balancing, with the threshold (V) as a dashed line."""
        if len(self._trend) < 2:
            return ""
        width, height = 120, 34
        top = max(max(self._trend), threshold * 1.5)

        def y(delta: float) -> float:
            return height - 2 - delta / top * (height - 4)

        xs = [i / (len(self._trend) - 1) * width for i in range(len(self._trend))]
        points = " ".join(f"{x:.1f},{y(d):.1f}" for x, d in zip(xs, self._trend, strict=True))
        return (
            f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}">'
            f'<line x1="0" y1="{y(threshold):.1f}" x2="{width}" y2="{y(threshold):.1f}" '
            'stroke="rgba(255,255,255,.35)" stroke-dasharray="3 3"/>'
            f'<polyline points="{points}" fill="none" stroke="#F3FF14" stroke-width="2"/>'
            f'<circle cx="{xs[-1]:.1f}" cy="{y(self._trend[-1]):.1f}" r="3" fill="#F3FF14"/></svg>'
        )

    # balancing

    def _update_balance(self, bms: BmsSnapshot, s: State, threshold: float) -> None:
        threshold_mv = threshold * 1000
        if s is State.BALANCING:
            start, delta = self._start_delta, bms.cell_delta
            progress = 0.0
            if start is not None and delta is not None:
                progress = balancing_progress(start, delta, threshold)
            self._balance_label.set_text("Balancing")
            delta_mv = "—" if delta is None else f"{delta * 1000:.0f}"
            self._balance_note.set_text(f"{sum(bms.balancing)} cells · {delta_mv}→{threshold_mv:.0f} mV")
            self._balance.props("icon=hourglass_top text-color=white")
            self._balance.classes(replace="balbtn run")
            self._balance.style(f"--p:{progress:.0f}%")
            self._balance.set_enabled(False)  # stopping is the red STOP's job
        else:
            why_not = {
                State.IDLE: f"until {threshold_mv:.0f} mV",
                State.ERROR: "clear the error first",
                State.CHECK: "connect first",
            }
            self._balance_label.set_text("Balance")
            self._balance_note.set_text(why_not.get(s, "TS must be off"))
            self._balance.props("icon=balance text-color=black")
            self._balance.classes(replace="balbtn")
            self._balance.set_enabled(s is State.IDLE)

    def _set_mode(self, volts: bool) -> None:
        self._volts = volts
        if volts:
            self._volts_button.classes(add="sel")
            self._temps_button.classes(remove="sel")
        else:
            self._volts_button.classes(remove="sel")
            self._temps_button.classes(add="sel")

    def _cstat(self, title: str) -> ui.label:
        with ui.element("div"):
            ui.label(title).classes("lbl")
            with ui.element("div").classes("vrow"):
                return ui.label("—").classes("v num")
