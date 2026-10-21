"""Cells screen: a map of every cell (or temperature probe), min/max/delta, and balancing."""

import json
import time
from collections import deque

from nicegui import ui

from frontend import colors
from frontend.readings import balancing_progress, overvoltage_cells
from frontend.screens import Actions
from shared.config import Config
from shared.models import BmsSnapshot, Command, State, Status

MAP_WINDOW = 0.030  # V: full violet 30 mV under the pack average, full orange 30 mV over it
TREND_PERIOD = 5.0  # s between two points of the balancing trend
TREND_POINTS = 120  # points kept: the last 10 minutes


class CellsScreen:
    def __init__(self, cfg: Config, actions: Actions) -> None:
        self._cfg = cfg.accumulator
        self._volts = True  # False: temperatures
        self._trend: deque[float] = deque(maxlen=TREND_POINTS)  # cell delta while balancing, V
        self._next_trend_point = 0.0  # s, monotonic
        self._start_delta: float | None = None  # V, when balancing began: 0 % on the progress bar

        with ui.element("div").classes("tab") as self.root:
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
                    ui.html('<div id="cell-detail" class="hint num">Tap a cell to read it</div>')
                with (
                    ui.button(on_click=lambda: actions.send(Command.BALANCE))
                    .props("unelevated no-caps")
                    .classes("balbtn") as self._balance
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
            self._trend_chart.set_content(self._trend_svg())
        else:
            self._show_temps(status.bms)
            self._trend_chart.set_content("")
        self._update_balance(status.bms, status.state)

    def show_cell(self, index: int, bms: BmsSnapshot) -> None:
        """Volts mode, with one cell already read out under the map (from the error's Details)."""
        self._set_mode(True)
        board, cell = divmod(index, self._cfg.cells_per_cellboard)
        text = f"CB{board + 1} · cell {cell + 1} · {bms.cells[index]:.3f} V · overvoltage"
        ui.run_javascript(f"showCellDetail({json.dumps(text)}, true)")

    def show_temps(self) -> None:
        """Temps mode (from the error's Details, for a cell too hot)."""
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
            squares.append((classes, color, f"CB{board + 1} · cell {cell + 1} · {reading}"))
        self._map.set_content(self._grid(squares, self._cfg.cells_per_cellboard, gap=3))

        self._min.set_text(f"{min(healthy):.3f} V")
        self._max.set_text(f"{max(healthy):.3f} V")
        self._delta.set_text(f"{(max(healthy) - min(healthy)) * 1000:.0f} mV")
        low, high = average - MAP_WINDOW, average + MAP_WINDOW
        scale = colors.gradient(colors.VOLTS_LOW, colors.VOLTS_HIGH)
        legend = (
            f'<span class="li"><i class="grad" style="background:{scale}"></i>{low:.3f}–{high:.3f}</span>'
            '<span class="li"><i class="sw hi"></i>Highest</span>'
            '<span class="li"><i class="sw lo"></i>Lowest</span>'
            '<span class="li"><i class="sw bal"></i>Balancing</span>'
        )
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
            if t is None:
                color, reading = colors.NO_READING, "—"
            elif t < pack.cold_temperature:
                color, reading = colors.TEMPS_COLD, f"{t:.1f} °C · cold"
            elif t <= pack.warm_temperature:
                color, reading = self._temperature_color(t), f"{t:.1f} °C"
            elif t <= pack.max_temperature:
                color, reading = self._temperature_color(t), f"{t:.1f} °C · warm"
            else:
                color, reading = colors.NEUTRAL, f"{t:.1f} °C · too hot"
                classes += " flt"  # blinking red, from the CSS
            board, probe = divmod(i, pack.temps_per_cellboard)
            squares.append((classes, color, f"CB{board + 1} · probe {probe + 1} · {reading}"))
        self._map.set_content(self._grid(squares, self._cfg.temps_per_cellboard, gap=2))

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
        self._map.set_content("")
        for label in (self._min, self._max, self._delta):
            label.set_text("—")
        self._legend.set_content("")

    def _grid(self, squares: list[tuple[str, str, str]], per_board: int, gap: int) -> str:
        """One row per cellboard: its name, then a square per cell (classes, background, text on tap)."""
        columns = f"38px repeat({per_board}, minmax(0,1fr))"
        rows = [f'<div class="cmap" style="grid-template-columns: {columns}; gap: {gap}px">']
        for i, (classes, color, text) in enumerate(squares):
            if i % per_board == 0:
                rows.append(f'<div class="rl">CB{i // per_board + 1}</div>')
            rows.append(f'<div class="{classes}" style="background:{color}" data-l="{text}"></div>')
        rows.append("</div>")
        return "".join(rows)

    def _trend_svg(self) -> str:
        """Delta over the last minutes of balancing, with the threshold as a dashed line."""
        if len(self._trend) < 2:
            return ""
        width, height = 120, 34
        threshold = self._cfg.balancing_threshold
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

    def _update_balance(self, bms: BmsSnapshot, s: State) -> None:
        threshold_mv = self._cfg.balancing_threshold * 1000
        if s is State.BALANCING:
            start, delta, threshold = self._start_delta, bms.cell_delta, self._cfg.balancing_threshold
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
            self._balance.props("icon=tune text-color=black")
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
        ui.run_javascript("showCellDetail(null)")

    def _cstat(self, title: str) -> ui.label:
        with ui.element("div"):
            ui.label(title).classes("lbl")
            with ui.element("div").classes("vrow"):
                return ui.label("—").classes("v num")
