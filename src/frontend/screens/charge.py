"""Charge screen: the pack voltage on the left, the one action that makes sense now on the right."""

import math
from dataclasses import dataclass

from nicegui import ui

from frontend.screens import Actions, number
from frontend.targets import Reachable, button, usable
from shared.config import Config
from shared.models import Command, State, Status


@dataclass(frozen=True)
class Action:
    """A button: it sends a command, or opens a screen, or (neither) shows the state disabled."""

    label: str
    icon: str
    command: Command | None = None
    opens: str | None = None  # a screen: "cells", ...


# the big button, per state
PRIMARY = {
    State.CHECK: Action("Connect accumulator", "cable"),
    State.IDLE: Action("Precharge", "bolt", command=Command.PRECHARGE),
    State.PRECHARGE: Action("Precharging", "bolt"),
    State.READY: Action("Start charging", "play_arrow", command=Command.START_CHARGE),
    State.CHARGE: Action("Pause", "pause", command=Command.PAUSE_CHARGE),
    State.CHARGE_DONE: Action("Charged", "check_circle"),
    State.BALANCING: Action("View cells", "grid_view", opens="cells"),
    State.ERROR: Action("Reset errors", "restart_alt", command=Command.RESET),
}
# the button under it, only in some states
SECONDARY = {
    State.IDLE: Action("Balance cells", "tune", opens="cells"),
    State.CHARGE_DONE: Action("Charge again", "replay", command=Command.START_CHARGE),
}
OUTLINED = {State.CHARGE, State.CHARGE_DONE, State.BALANCING}  # the action is not the next step forward

# the voltage rail under the big number
RAIL_BELOW_TARGET_MIN = 14  # V shown left of the lowest target
RAIL_ABOVE_PACK_LIMIT = 6  # V shown right of the pack limit
RAIL_TICK_STEP = 20  # V between the numbers under the rail
TARGET_LABEL_MIN_POSITION = 12  # %: the target label sits left of its mark; keep it on the rail
LIMIT_LABEL_WIDTH = 17  # % of the rail taken by "max 605 V": a target label further right would cover it


class ChargeScreen:
    def __init__(self, cfg: Config, actions: Actions) -> None:
        self._actions = actions
        self._state = State.CHECK
        self._rail_low = cfg.charge.target_voltage_min - RAIL_BELOW_TARGET_MIN  # V at the left end
        self._rail_high = cfg.accumulator.max_pack_voltage + RAIL_ABOVE_PACK_LIMIT  # V at the right end
        self.draft: float | None = None  # V: a target being drafted with the encoder, not set yet

        with ui.element("div").classes("tab charge") as self.root:
            with ui.element("div").classes("left"):
                ui.label("Pack").classes("lbl")
                with ui.element("div").classes("big num"):
                    self._voltage = ui.label("—").style("display:inline")
                    ui.label("V").classes("big-unit").style("display:inline")
                self._build_rail(cfg.accumulator.max_pack_voltage)
                with ui.element("div").classes("stats"):
                    self._current = self._stat("Current")
                    self._power = self._stat("Power")
                    self._cell_max = self._stat("Max cell")
            with ui.element("div").classes("right"):
                self._main = (
                    ui.button("—", on_click=self._on_main).props("unelevated no-caps").classes("main")
                )
                self._alt = (
                    ui.button("", on_click=self._on_alt).props("flat no-caps text-color=white").classes("alt")
                )
                self._checks = ui.html("").classes("checks")
                with (
                    ui.button(on_click=actions.open_settings)
                    .props("flat no-caps text-color=white")
                    .classes("setp") as self._setpoints_button
                ):
                    self._setpoints = ui.html("").classes("sv num")
                    ui.icon("tune")

    def update(self, status: Status) -> None:
        s, bms, charger = status.state, status.bms, status.charger
        self._state = s
        self._voltage.set_text(number(bms.pack_voltage))
        target = status.settings.target_voltage if self.draft is None else self.draft
        self._update_rail(bms.pack_voltage, target, s is State.CHARGE)
        self._current.set_content(f"{number(charger.current)}<small>A</small>")
        self._power.set_content(f"{number(bms.power, 2)}<small>kW</small>")
        self._cell_max.set_content(f"{number(bms.cell_max, 3)}<small>V</small>")

        main = PRIMARY[s]
        label = main.label
        if s is State.PRECHARGE and bms.ts_voltage and bms.pack_voltage:
            label = f"Precharging {min(99.0, bms.ts_voltage / bms.pack_voltage * 100):.0f}%"
        self._main.set_text(label)
        if s is State.CHARGE_DONE:
            self._main.props(f"icon={main.icon} text-color=white").classes(replace="main ghost done")
        elif s in OUTLINED:
            self._main.props(f"icon={main.icon} text-color=white").classes(replace="main ghost")
        else:
            self._main.props(f"icon={main.icon} text-color=black").classes(replace="main")
        self._main.set_enabled(main.command is not None or main.opens is not None)

        secondary = SECONDARY.get(s)
        self._alt.set_visibility(secondary is not None)
        if secondary is not None:
            self._alt.set_text(secondary.label)
            self._alt.props(f"icon={secondary.icon}")

        self._setpoints_button.set_visibility(s not in (State.CHECK, State.BALANCING, State.ERROR))
        self._checks.set_visibility(s is State.CHECK)
        self._checks.set_content(
            self._check("BMS", bms.connected) + self._check("Charger", charger.connected)
        )
        if self.draft is None:
            target_html = f"<b>{status.settings.target_voltage:g} V</b>"
        else:
            target_html = f'<b class="draft">{self.draft:g} V</b>'  # yellow: not set yet
        self._setpoints.set_content(
            f"<div><span>Target</span>{target_html}</div>"
            f"<div><span>Max current</span><b>{status.settings.max_current:g} A</b></div>"
        )

    def settings_shown(self) -> bool:
        """The target can be changed only when its box is shown (not while checking, balancing, in error)."""
        return self._setpoints_button.visible

    def reachable(self) -> list[Reachable]:
        return usable(
            button("main", self._main, priority=1),
            button("alt", self._alt),
            button("setpoints", self._setpoints_button),
        )

    # building blocks

    def _check(self, name: str, connected: bool) -> str:
        """A device box, white once the device answers."""
        if connected:
            return f'<span class="ok">{name}</span>'
        return f"<span>{name}</span>"

    def _stat(self, title: str) -> ui.html:
        with ui.element("div").classes("stat"):
            ui.label(title).classes("lbl")
            return ui.html("—").classes("v num")

    def _build_rail(self, limit: float) -> None:
        with ui.element("div").classes("rail"):
            ui.element("div").classes("rail-track")
            self._fill = ui.element("div").classes("rail-fill")
            self._target_mark = ui.element("div").classes("mark target")
            self._target_label = ui.label("").classes("rlbl target num")
            ui.element("div").classes("mark limit").style(f"left:{self._position(limit):.2f}%")
            self._limit_label = ui.label(f"max {limit:.0f} V").classes("rlbl limit num")
            first_tick = math.ceil(self._rail_low / RAIL_TICK_STEP) * RAIL_TICK_STEP
            for volts in range(first_tick, int(self._rail_high) + 1, RAIL_TICK_STEP):
                ui.label(str(volts)).classes("tick num").style(f"left:{self._position(volts):.2f}%")

    def _update_rail(self, pack: float | None, target: float, charging: bool) -> None:
        self._fill.style(f"width:{self._position(pack or self._rail_low):.2f}%")
        if charging:
            self._fill.classes(replace="rail-fill flow")  # moving stripes
        else:
            self._fill.classes(replace="rail-fill")
        self._target_mark.style(f"left:{self._position(target):.2f}%")
        label_position = max(self._position(target), TARGET_LABEL_MIN_POSITION)
        self._target_label.style(f"left:{label_position:.2f}%")
        self._target_label.set_text(f"{target:g} V")
        # close to the limit the two labels would overlap: the dashed red mark still shows the limit
        self._limit_label.set_visibility(self._position(target) < 100 - LIMIT_LABEL_WIDTH)
        if self.draft is None:
            self._target_mark.classes(remove="draft")
        else:
            self._target_mark.classes(add="draft")

    def _position(self, volts: float) -> float:
        """Where a voltage sits on the rail, in percent."""
        return max(0.0, min(100.0, (volts - self._rail_low) / (self._rail_high - self._rail_low) * 100))

    # buttons

    async def _on_main(self) -> None:
        await self._do(PRIMARY[self._state])

    async def _on_alt(self) -> None:
        secondary = SECONDARY.get(self._state)
        if secondary is not None:
            await self._do(secondary)

    async def _do(self, action: Action) -> None:
        if action.command is not None:
            await self._actions.send(action.command)
        if action.opens is not None:
            self._actions.show(action.opens)
