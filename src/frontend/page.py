"""The page on the display: top bar, the four screens, the nav with STOP, and what covers them."""

import time
from datetime import datetime
from functools import partial

from nicegui import background_tasks, ui

from frontend import local_files, overlays
from frontend.backend import Backend
from frontend.controls import Adjust, Context, Controls, Press, SwitchScreen, Target
from frontend.readings import (
    cell_overvoltage,
    details_screen,
    error_kind,
    first_open,
    hot_probes,
    overvoltage_cells,
    ts_discharging,
)
from frontend.screens import Actions, Screen
from frontend.screens.cells import CellsScreen
from frontend.screens.charge import ChargeScreen
from frontend.screens.charger import ChargerScreen
from frontend.screens.shutdown import ShutdownScreen
from frontend.system_window import SystemWindow
from frontend.targets import Reachable, button, usable
from frontend.updating import Updating
from frontend.wifi_window import WifiWindow
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
        self._stopped_with_ts_on = False  # the state before the last ERROR had the TS on
        self._entered = 0.0  # when the current state began
        self._told_updates = False  # the toast about updates shows once
        self._controls = Controls()
        self._framed_element: ui.element | None = None  # the element the frame is drawn on

        actions = Actions(
            send=self._send,
            show=self._show,
            open_settings=self._open_settings,
            open_balancing_settings=self._open_balancing_settings,
        )
        with ui.element("div").classes("screen"):
            self._halo = ui.element("div").classes("halo")
            with ui.element("div").classes("top"):
                ui.element("div").classes("eagle")
                self._pill = ui.label("").classes("pill").on("click", lambda: self._show("charge"))
                self._info_button = ui.button(icon="info_outline", on_click=self._open_info)
                self._info_button.props("flat round dense text-color=white").classes("info")
                ui.element("div").classes("spacer")
                self._wifi_button = ui.button(icon="wifi_off", on_click=self._open_wifi)
                self._wifi_button.props("flat round dense text-color=white").classes("info wifi-off")
                with (
                    ui.button(icon="settings", on_click=self._open_system)
                    .props("flat round dense text-color=white")
                    .classes("info gear") as self._gear
                ):
                    self._gear_badge = ui.element("div").classes("badge")
                self._hv = ui.label("").classes("ts num")
                self._clock = ui.label("").classes("clock num")

            with ui.element("div").classes("content"):
                self._charge = ChargeScreen(cfg, actions)
                self._cells = CellsScreen(cfg, actions)
                self._charger = ChargerScreen()
                self._shutdown = ShutdownScreen(cfg)
                self._precharge = overlays.Precharge()
                self._balancing = overlays.Balancing(on_view_cells=lambda: self._show("cells"))
                self._done = overlays.Done()
                self._discharge = overlays.Discharge()  # above the error takeover (CSS)
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
            self._confirm = overlays.ConfirmWindow()
            self._wifi = WifiWindow(backend, self._toast, self._confirm)
            self._system = SystemWindow(
                backend, self._confirm, lambda problem: self._toast.show(problem, ok=False)
            )
            self._updating = Updating(self._toast)
            # the windows that cover the screens, the topmost first
            self._windows = (self._confirm, self._wifi, self._system, self._settings, self._info)
            with ui.element("div").classes("offline") as self._offline:
                ui.element("div").classes("eagle")
                ui.label("Waiting for the backend")
                self._backend_error = ui.label("").classes("why")  # why it stopped, if it said so

        self._screens: dict[str, Screen] = {
            "charge": self._charge,
            "cells": self._cells,
            "charger": self._charger,
            "shutdown": self._shutdown,
        }
        self._select("charge")
        self._client = ui.context.client
        self._client.on_disconnect(backend.on_input(self._on_input))
        # on a computer, handcart.js turns keys and the mouse wheel into the same controls
        ui.on("handcart_control", lambda event: self._on_input(InputEvent(event.args)))
        ui.on("handcart_touch", self._on_touch)
        ui.on("handcart_cell", lambda event: self._on_cell_touched(int(event.args)))
        ui.timer(REFRESH_PERIOD, self._refresh)
        # size the screen to the display once the browser has drawn the page (handcart.js)
        ui.timer(0.1, lambda: ui.run_javascript("fitScreen()"), once=True)

    def _refresh(self) -> None:
        status = self._backend.status
        self._offline.set_visibility(status is None)
        self._updating.refresh()
        if status is None:
            self._backend_error.set_text(local_files.backend_error())
        self._clock.set_text(datetime.now().strftime("%H:%M"))
        self._toast.update()
        self._update_system()
        if status is None:
            return

        s = status.state
        if s is not self._state:
            if s is State.ERROR:  # "Charging stopped" only if the TS was on
                self._stopped_with_ts_on = self._state in TS_ON or self._state is State.PRECHARGE
            self._state = s
            self._entered = time.monotonic()
            self._done.dismissed = False
            if s in TAKEOVER_STATES:
                self._close_windows()  # nothing may hide an error, or the precharge
                self._select("charge")
            elif s is State.CHARGE_DONE or status.balancing_done:
                self._select("charge")  # a job done: on the screen that says so

        self._cells.record(status)
        self._update_top(status)
        self._update_nav(status)
        self._screens[self._tab].update(status)

        on_charge = self._tab == "charge"
        lingering = s is State.READY and time.monotonic() - self._entered < PRECHARGE_LINGER
        self._precharge.root.set_visibility(on_charge and (s is State.PRECHARGE or lingering))
        if s is State.PRECHARGE or lingering:
            self._precharge.update(status)
        self._balancing.root.set_visibility(on_charge and s is State.BALANCING)
        if s is State.BALANCING:
            self._balancing.update(status)
        else:
            self._balancing.done()
        job_done = s is State.CHARGE_DONE or status.balancing_done
        self._done.root.set_visibility(on_charge and job_done and not self._done.dismissed)
        if job_done:
            self._done.update(status)
        self._error.root.set_visibility(on_charge and s is State.ERROR)
        if s is State.ERROR:
            self._error.update(status, self._error_kind(status), self._stopped_with_ts_on)
        if ts_discharging(s, status.bms):
            self._discharge.root.set_visibility(not self._discharge.dismissed)
            self._discharge.update(status)
        else:
            self._discharge.root.set_visibility(False)
            self._discharge.done()
        self._follow_controls()

    def _update_system(self) -> None:
        """The gear's badge and, once, a toast when the branch has updates."""
        info = self._backend.system
        has_updates = info is not None and len(info.updates) > 0
        self._gear_badge.set_visibility(has_updates)
        if has_updates and not self._told_updates:
            self._told_updates = True
            self._toast.show("Update available: open the gear", ok=True)
        if self._system.root.visible:
            self._system.update()
        self._update_wifi_button()
        if self._wifi.root.visible:
            self._wifi.update()

    def _update_wifi_button(self) -> None:
        """Next to the gear: the Wi-Fi icon. White when on a network, grey when on but not on a network,
        crossed out when the Wi-Fi is off."""
        network = self._backend.network
        wifi_on = network is not None and network.wifi_on
        connected = network is not None and any(n.connected for n in network.networks)
        if connected:
            self._wifi_button.props("icon=wifi")
            self._wifi_button.classes(remove="wifi-off")
        elif wifi_on:
            self._wifi_button.props("icon=wifi")
            self._wifi_button.classes(add="wifi-off")
        else:
            self._wifi_button.props("icon=wifi_off")
            self._wifi_button.classes(add="wifi-off")

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

        pack = self._cfg.accumulator
        cell_fault = cell_overvoltage(status.bms, pack.max_cell_voltage) or bool(
            hot_probes(status.bms, pack.max_temperature)
        )
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

    def _close_windows(self) -> None:
        for window in self._windows:
            window.root.set_visibility(False)

    def _error_kind(self, status: Status) -> str:
        return error_kind(status.fault, status.bms, self._cfg.accumulator)

    # actions

    def _show(self, key: str) -> None:
        """Go to a screen and draw it now, without waiting for the next refresh."""
        self._hush()
        self._select(key)
        self._refresh()

    def _hush(self) -> None:
        """The operator is there: stop the tune of a job done (charge, balancing)."""
        background_tasks.create(self._backend.hush())

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
            settings = self._backend.status.settings
            self._settings.open(settings, "Charge settings", ("target_voltage", "max_current"))

    def _open_balancing_settings(self) -> None:
        if self._backend.status is not None:
            settings = self._backend.status.settings
            self._settings.open(settings, "Balancing settings", ("balancing_threshold",))

    async def _open_wifi(self) -> None:
        await self._wifi.open()

    def _open_system(self) -> None:
        self._system.open()

    def _open_info(self) -> None:
        if self._backend.status is not None:
            self._info.open(self._backend.status.state)

    def _on_details(self) -> None:
        status = self._backend.status
        if status is None:
            return
        kind = self._error_kind(status)
        screen = details_screen(status.fault)
        if screen != "cells":
            self._show(screen)
            return
        if kind == "hot":
            self._show("cells")
            self._cells.show_temps()
            return
        self._cells.show_volts()
        self._show("cells")
        cells = overvoltage_cells(status.bms, self._cfg.accumulator.max_cell_voltage)
        if cells:  # empty when only the BMS reported it: the map shows the cells anyway
            self._on_cell_touched(min(cells))

    # physical controls (rules in controls.py)

    def _on_input(self, event: InputEvent) -> None:
        """A press of the handcart's controls, or of the computer's keys.

        From the backend connection it arrives outside this page's context: elements still update.
        """
        reachable, context = self._context()
        effect = self._controls.handle(event, context, time.monotonic())
        if isinstance(effect, Press):
            for item in reachable:
                if item.target.key == effect.key:
                    item.press()
            if effect.opens_map:
                self._cursor_on_map_start(effect.key)
        elif isinstance(effect, SwitchScreen):
            keys = [key for key, _, _ in TABS]
            self._show(keys[(keys.index(self._tab) + effect.step) % len(keys)])
        elif isinstance(effect, Adjust):
            self._settings.turn(effect.setting, effect.steps)
        self._follow_controls()

    def _cursor_on_map_start(self, pressed: str) -> None:
        """Volts or Temps pressed with the controls: the cursor goes on that map, on its highest square.

        The button's click reaches the browser and comes back a moment later: the mode is set here too.
        """
        if pressed == "temps":
            self._cells.show_temps()
        else:
            self._cells.show_volts()
        _, context = self._context()
        self._controls.touch_map(context.map_start, context)

    def _on_touch(self) -> None:
        """The operator touched the screen outside the map: the frame goes."""
        self._hush()
        self._controls.clear()
        self._follow_controls()

    def _on_cell_touched(self, square: int) -> None:
        """A touch on the map: the cursor goes there, to be corrected with the controls if it missed."""
        self._hush()
        _, context = self._context()
        self._controls.touch_map(square, context)
        self._follow_controls()

    def _follow_controls(self) -> None:
        """Draw the frame and the cursor where controls.py says (after a gesture, and at every refresh)."""
        reachable, context = self._context()
        self._controls.follow(context, time.monotonic())
        self._draw_frame(reachable)
        if self._cells.cursor != self._controls.cursor:
            self._cells.cursor = self._controls.cursor
            if self._tab == "cells" and self._backend.status is not None:
                self._cells.update(self._backend.status)  # move the cursor now, not at the next refresh

    def _context(self) -> tuple[list[Reachable], Context]:
        """What the controls can reach now (in reading order), and where they are."""
        if self._updating.root.visible:
            return [], Context(window_open=True)  # updating: nothing to press until it is over
        for window in self._windows:  # the topmost first
            if window.root.visible:
                reachable = window.reachable()
                return reachable, Context(targets=[item.target for item in reachable], window_open=True)

        map_name, map_size, map_start = None, (0, 0), 0
        if self._precharge.root.visible:
            content: list[Reachable] = []  # it covers the screen, nothing to press there
        elif self._discharge.root.visible:
            content = self._discharge.reachable()
        elif self._balancing.root.visible:
            content = self._balancing.reachable()
        elif self._done.root.visible:
            content = self._done.reachable()
        elif self._error.root.visible:
            content = self._error.reachable()
        else:
            content = self._screens[self._tab].reachable()
            if self._tab == "cells" and self._backend.status is not None:
                map_name, map_size = self._cells.map_name(), self._cells.map_size()
                map_start = self._cells.map_start(self._backend.status.bms)
        top = usable(
            button("info", self._info_button), button("wifi", self._wifi_button), button("system", self._gear)
        )
        tabs = [Reachable(Target(key), tab, partial(self._show, key)) for key, (tab, _) in self._tabs.items()]
        stop = usable(button("stop", self._stop, priority=2))  # while something runs, the frame starts here
        reachable = [*top, *content, *tabs, *stop]
        context = Context(
            targets=[item.target for item in reachable],
            map_name=map_name,
            map_size=map_size,
            map_start=map_start,
        )
        return reachable, context

    def _draw_frame(self, reachable: list[Reachable]) -> None:
        """The yellow frame on the framed target.

        Checked at every refresh: a screen's update may replace the classes of its buttons, frame included.
        """
        element = None
        for item in reachable:
            if item.target.key == self._controls.framed:
                element = item.element
        if self._framed_element is not None and self._framed_element is not element:
            self._framed_element.classes(remove="kframe")
        if element is not None and "kframe" not in element.classes:
            element.classes(add="kframe")
        self._framed_element = element
