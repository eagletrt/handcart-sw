"""The page on the display: top bar, the four screens, the nav with STOP, and what covers them."""

import time
from datetime import datetime

from nicegui import ui

from frontend import overlays
from frontend.backend import Backend
from frontend.readings import cell_overvoltage, error_kind, first_open, overvoltage_cells
from frontend.screens import Actions, Screen
from frontend.screens.cells import CellsScreen
from frontend.screens.charge import ChargeScreen
from frontend.screens.charger import ChargerScreen
from frontend.screens.shutdown import ShutdownScreen
from shared.config import Config
from shared.models import Command, InputEvent, Settings, State, Status

REFRESH_PERIOD = 0.25  # s
TABS = [
    ("charge", "Charge", "bolt"),
    ("cells", "Cells", "grid_view"),
    ("charger", "Charger", "ev_station"),
    ("shutdown", "Shutdown", "power"),
]
STATE_NAME = {
    State.CHECK: "Connect",
    State.IDLE: "TS off",
    State.PRECHARGE: "Precharge",
    State.READY: "TS on",
    State.CHARGE: "Charging",
    State.CHARGE_DONE: "Charged",
    State.BALANCING: "Balancing",
    State.ERROR: "Error",
}
TS_ON = {State.READY, State.CHARGE, State.CHARGE_DONE}
STOPPABLE = TS_ON | {State.PRECHARGE, State.BALANCING}  # STOP shows only when it has something to stop
TAKEOVER_STATES = {State.PRECHARGE, State.ERROR}  # entering them brings the Charge screen up
PRECHARGE_LINGER = 1.3  # s the precharge takeover stays after the TS is on, to show it worked
# the glow around the screen: red on error, yellow while energy flows, white while balancing
HALO = {State.ERROR: "halo r", State.PRECHARGE: "halo y", State.CHARGE: "halo y", State.BALANCING: "halo w"}


class Page:
    def __init__(self, cfg: Config, backend: Backend) -> None:
        self._cfg = cfg
        self._backend = backend
        self._tab = "charge"
        self._state: State | None = None
        self._entered = 0.0  # when the current state began

        actions = Actions(send=self._send, show=self._show, open_settings=self._open_settings)
        with ui.element("div").classes("screen"):
            self._halo = ui.element("div").classes("halo")
            with ui.element("div").classes("top"):
                ui.element("div").classes("eagle")
                self._pill = ui.label("").classes("pill").on("click", lambda: self._show("charge"))
                ui.button(icon="info_outline", on_click=self._open_info).props(
                    "flat round dense text-color=white"
                ).classes("info")
                ui.element("div").classes("spacer")
                self._hv = ui.label("").classes("ts num")
                self._clock = ui.label("").classes("clock num")

            with ui.element("div").classes("content"):
                self._charge = ChargeScreen(cfg, actions)
                self._cells = CellsScreen(cfg, actions)
                self._charger = ChargerScreen()
                self._shutdown = ShutdownScreen(cfg)
                self._precharge = overlays.Precharge()
                self._error = overlays.Error(
                    on_reset=lambda: self._send(Command.RESET), on_details=self._on_details
                )

            with ui.element("div").classes("nav") as self._nav:
                self._tabs = {}
                for key, title, icon in TABS:
                    with ui.element("div").classes("nt").on("click", lambda key=key: self._show(key)) as tab:
                        ui.icon(icon)
                        ui.label(title)
                        self._tabs[key] = (tab, ui.element("div").classes("badge"))
                with (
                    ui.button(on_click=lambda: self._send(Command.STOP))
                    .props("unelevated no-caps color=negative")
                    .classes("stop") as self._stop
                ):
                    ui.label("STOP").classes("s1")
                    self._stop_note = ui.label("").classes("s2")

            self._settings = overlays.SettingsWindow(cfg, self._save_settings)
            self._info = overlays.InfoWindow()
            self._toast = overlays.Toast()
            with ui.element("div").classes("offline") as self._offline:
                ui.element("div").classes("eagle")
                ui.label("Waiting for the backend")

        self._screens: dict[str, Screen] = {
            "charge": self._charge,
            "cells": self._cells,
            "charger": self._charger,
            "shutdown": self._shutdown,
        }
        self._select("charge")
        self._client = ui.context.client
        self._client.on_disconnect(backend.on_input(self._on_input))
        ui.timer(REFRESH_PERIOD, self._refresh)
        # size the screen to the display once the browser has drawn the page (handcart.js)
        ui.timer(0.1, lambda: ui.run_javascript("fitScreen()"), once=True)

    def _refresh(self) -> None:
        status = self._backend.status
        self._offline.set_visibility(status is None)
        self._clock.set_text(datetime.now().strftime("%H:%M"))
        self._toast.update()
        if status is None:
            return

        s = status.state
        if s is not self._state:
            self._state = s
            self._entered = time.monotonic()
            if s in TAKEOVER_STATES:
                self._select("charge")

        self._cells.record(status)
        self._update_top(status)
        self._update_nav(status)
        self._screens[self._tab].update(status)

        on_charge = self._tab == "charge"
        lingering = s is State.READY and time.monotonic() - self._entered < PRECHARGE_LINGER
        self._precharge.root.set_visibility(on_charge and (s is State.PRECHARGE or lingering))
        if s is State.PRECHARGE or lingering:
            self._precharge.update(status)
        self._error.root.set_visibility(on_charge and s is State.ERROR)
        if s is State.ERROR:
            self._error.update(status, self._error_kind(status))

    def _update_top(self, status: Status) -> None:
        s, bms = status.state, status.bms
        self._halo.classes(replace=HALO.get(s, "halo"))
        self._pill.set_text(STATE_NAME[s])
        if s is State.ERROR:
            self._pill.classes(replace="pill err")
        elif s in TS_ON or s is State.PRECHARGE:
            self._pill.classes(replace="pill hv")
        else:
            self._pill.classes(replace="pill")

        if bms.ts_below_60v is None:
            self._hv.set_text("HV ?")  # unknown is not safe
            self._hv.classes(replace="ts num")
        elif bms.ts_below_60v:
            self._hv.set_text("HV < 60 V")
            self._hv.classes(replace="ts num")
        else:
            self._hv.set_text(f"HV {bms.ts_voltage or 0:.0f} V")
            self._hv.classes(replace="ts num live")

    def _update_nav(self, status: Status) -> None:
        s = status.state
        if s in STOPPABLE:
            self._nav.classes(replace="nav armed")  # makes room for STOP
            self._stop.set_visibility(True)
        else:
            self._nav.classes(replace="nav")
            self._stop.set_visibility(False)
        if s is State.BALANCING:
            self._stop_note.set_text("Stop balancing")
        else:
            self._stop_note.set_text("TS off")

        cell_fault = cell_overvoltage(status.bms, self._cfg.accumulator.max_cell_voltage)
        badges = {
            "charge": s is State.ERROR and self._tab != "charge",
            "cells": cell_fault or (s is State.BALANCING and self._tab != "cells"),
            "charger": not status.charger.connected,
            "shutdown": first_open(status.shutdown, self._cfg.shutdown.open_below) is not None,
        }
        for key, visible in badges.items():
            self._tabs[key][1].set_visibility(visible)
        cells_badge = self._tabs["cells"][1]
        if cell_fault:
            cells_badge.classes(remove="y")  # red: a fault
        else:
            cells_badge.classes(add="y")  # white: balancing

    def _error_kind(self, status: Status) -> str:
        return error_kind(
            status.bms, status.shutdown, self._cfg.accumulator.max_cell_voltage, self._cfg.shutdown.open_below
        )

    # actions

    def _show(self, key: str) -> None:
        """Go to a screen and draw it now, without waiting for the next refresh."""
        self._select(key)
        self._refresh()

    def _select(self, key: str) -> None:
        """Make a screen the visible one and highlight its tab."""
        self._tab = key
        for name, screen in self._screens.items():
            screen.root.set_visibility(name == key)
        for name, (tab, _) in self._tabs.items():
            if name == key:
                tab.classes(add="sel")
            else:
                tab.classes(remove="sel")

    async def _send(self, command: Command) -> None:
        problem = await self._backend.command(command)
        if problem:
            self._toast.show(problem, ok=False)

    async def _save_settings(self, settings: Settings) -> bool:
        problem = await self._backend.change_settings(settings)
        if problem:
            self._toast.show(problem, ok=False)
            return False
        self._toast.show("Settings saved", ok=True)
        return True

    def _open_settings(self) -> None:
        if self._backend.status is not None:
            self._settings.open(self._backend.status.settings)

    def _open_info(self) -> None:
        if self._backend.status is not None:
            self._info.open(self._backend.status.state)

    def _on_details(self) -> None:
        status = self._backend.status
        if status is None:
            return
        if self._error_kind(status) != "cell":
            self._show("shutdown")
            return
        self._show("cells")
        cells = overvoltage_cells(status.bms, self._cfg.accumulator.max_cell_voltage)
        if cells:  # empty when only the BMS reported it: the map shows the cells anyway
            self._cells.show_cell(min(cells), status.bms)

    def _on_input(self, event: InputEvent) -> None:
        """The physical controls: left and right change screen, the rest moves and presses the focus.

        Called by the backend connection, outside this page's context: hence self._client.
        """
        keys = [key for key, _, _ in TABS]
        modal_open = self._settings.root.visible or self._info.root.visible
        if event in (InputEvent.LEFT, InputEvent.RIGHT) and not modal_open:
            step = 1 if event is InputEvent.RIGHT else -1
            self._show(keys[(keys.index(self._tab) + step) % len(keys)])
        elif event in (InputEvent.UP, InputEvent.TURN_CCW):
            self._client.run_javascript("moveFocus(-1)")
        elif event in (InputEvent.DOWN, InputEvent.TURN_CW):
            self._client.run_javascript("moveFocus(1)")
        elif event is InputEvent.PRESS:
            self._client.run_javascript("pressFocused()")
