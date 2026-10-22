"""The Wi-Fi window, from the icon next to the gear: the networks around, the password on the screen keyboard.

A saved or open network is joined with a touch, a new one asks for its password first. When a network with
a password does not connect (a typo, or a saved password that changed), the password is asked again.
A touch on the network the handcart is on leaves it. Leaving it and turning the Wi-Fi off are confirmed
first: an SSH session over the Wi-Fi drops.
"""

from nicegui import ui
from nicegui.events import ValueChangeEventArguments

from frontend.backend import Backend
from frontend.controls import Target
from frontend.keyboard import Keyboard
from frontend.overlays import ConfirmWindow, Toast
from frontend.targets import Reachable, button, usable
from shared.models import WifiNetwork

ROWS_SHOWN = 4  # the strongest networks: as many as fit on the screen
BARS = 4  # of the signal, as on a phone


class WifiWindow:
    def __init__(self, backend: Backend, toast: Toast, confirm: ConfirmWindow) -> None:
        self._backend = backend
        self._toast = toast
        self._confirm = confirm
        self._shown: list[WifiNetwork] = []  # the networks in the rows, in order
        self._asking: WifiNetwork | None = None  # the network the keyboard is asking the password of
        self._doing: str | None = None  # "Searching…" while waiting for the backend, else None

        with ui.element("div").classes("modal") as self.root, ui.element("div").classes("sheet wifi"):
            with ui.element("div") as self._list_view:
                with ui.element("div").classes("whead"):
                    with ui.element("div"):
                        with ui.element("div").classes("wtitle"):
                            ui.label("Wi-Fi").classes("sheet-title")
                            # shows whether the Wi-Fi is on; turning it off asks first
                            self._switch = ui.switch(value=True, on_change=self._on_switch)
                            self._switch.props("color=primary").classes("wswitch")
                        self._status = ui.label("").classes("sheet-sub")
                    with ui.element("div").classes("wip"):
                        ui.label("IP address").classes("lbl")
                        self._ip = ui.label("").classes("num")  # big: to type it in ssh
                # button, name, details, signal bars
                self._rows: list[tuple[ui.button, ui.label, ui.label, ui.element]] = []
                with ui.element("div").classes("wrows"):
                    for i in range(ROWS_SHOWN):
                        with ui.button(on_click=lambda i=i: self._on_network(i)) as row:
                            row.props("flat no-caps text-color=white").classes("wrow")
                            with ui.element("div").classes("wleft"):
                                ui.icon("check_circle").classes("wcheck")  # shown on the connected one (CSS)
                                name = ui.label("").classes("wname")
                            with ui.element("div").classes("wright"):
                                details = ui.label("").classes("wdet")
                                with ui.element("div").classes("bars") as bars:
                                    for _ in range(BARS):
                                        ui.element("span")
                        self._rows.append((row, name, details, bars))
                with ui.element("div").classes("sheet-actions"):
                    self._close = ui.button("Close", on_click=lambda: self.root.set_visibility(False))
                    self._close.props("flat no-caps text-color=white").classes("cancel")
                    self._scan = ui.button("Search again", icon="refresh", on_click=self._on_scan)
                    self._scan.props("unelevated no-caps text-color=black")

            with ui.element("div") as self._password_view:
                self._keyboard = Keyboard()
                with ui.element("div").classes("sheet-actions"):
                    self._cancel = ui.button("Cancel", on_click=self._show_list)
                    self._cancel.props("flat no-caps text-color=white").classes("cancel")
                    self._connect = ui.button("Connect", on_click=self._on_connect)
                    self._connect.props("unelevated no-caps text-color=black")
        self.root.set_visibility(False)
        self._password_view.set_visibility(False)

    def reachable(self) -> list[Reachable]:
        if self._password_view.visible:
            actions = usable(button("cancel", self._cancel), button("connect", self._connect))
            return [*self._keyboard.reachable(), *actions]
        switch = Reachable(Target("wifi switch"), self._switch, press=self._flip_switch)
        rows = [button(f"network {i}", row) for i, (row, _, _, _) in enumerate(self._rows)]
        actions = usable(button("close", self._close, priority=1), button("search", self._scan))
        return [switch, *usable(*rows), *actions]

    async def open(self) -> None:
        self._show_list()
        self.root.set_visibility(True)
        await self._on_scan()  # what the Wi-Fi saw last may be old: look again

    def update(self) -> None:
        """Draw what the backend last said about the network (the keyboard is left alone)."""
        if self._password_view.visible:
            return
        info = self._backend.network
        if info is not None and self._doing is None:  # while turning it on or off, the switch shows the wish
            self._switch.set_value(info.wifi_on)
        self._scan.set_visibility(info is not None and info.wifi_on)  # searching needs the Wi-Fi on
        if info is None:
            status = "Reading the network…"
            self._shown = []
            self._ip.set_text("–")
        elif not info.wifi_on:
            status = "Wi-Fi is off"
            self._shown = []
            self._ip.set_text(ip_text(info.addresses))  # a cable may still give one
        elif info.problem:
            status = info.problem
            self._shown = []
            self._ip.set_text(ip_text(info.addresses))
        else:
            status = wifi_status(info.networks)
            self._shown = info.networks[:ROWS_SHOWN]
            self._ip.set_text(ip_text(info.addresses))
        if self._doing is not None:
            status = self._doing  # until the backend answers
        self._status.set_text(status)

        for i, (row, name, details, bars) in enumerate(self._rows):
            if i < len(self._shown):
                network = self._shown[i]
                name.set_text(network.ssid)
                details.set_text(network_details(network))
                bars.classes(replace=f"bars b{signal_bars(network.signal)}")
                if network.connected:
                    row.classes(add="on")
                else:
                    row.classes(remove="on")
                row.set_visibility(True)
            else:
                row.set_visibility(False)

    def _wifi_on(self) -> bool:
        info = self._backend.network
        return info is not None and info.wifi_on

    # buttons

    async def _on_scan(self) -> None:
        if not self._wifi_on():
            return  # nothing to search with
        self._doing = "Searching…"
        self.update()
        problem = await self._backend.scan_wifi()
        self._doing = None
        if problem:
            self._toast.show(problem, ok=False)
        self.update()

    async def _on_network(self, i: int) -> None:
        network = self._shown[i]
        if network.connected:
            self._confirm.ask(
                f"Disconnect from {network.ssid}?",
                "It stays saved: a touch connects again. An SSH session over this Wi-Fi drops.",
                "Disconnect",
                self._disconnect,
            )
        elif network.saved or not network.secured:
            await self._join(network, None)
        else:
            self._ask_password(network)

    async def _on_connect(self) -> None:
        if self._asking is not None:
            await self._join(self._asking, self._keyboard.text)

    async def _join(self, network: WifiNetwork, password: str | None) -> None:
        self._doing = f"Connecting to {network.ssid}…"
        self._show_list()
        problem = await self._backend.connect_wifi(network.ssid, password)
        self._doing = None
        if problem is None:
            self._toast.show(f"Connected to {network.ssid}", ok=True)
            self.update()
        elif network.secured:
            self._toast.show(problem, ok=False)
            self._ask_password(network)
        else:
            self._toast.show(problem, ok=False)
            self.update()

    async def _disconnect(self) -> None:
        problem = await self._backend.disconnect_wifi()
        if problem:
            self._toast.show(problem, ok=False)
        self.update()

    async def _on_switch(self, event: ValueChangeEventArguments) -> None:
        """The switch moved: by the operator, or by update() showing what the backend said."""
        wanted = event.value
        if wanted == self._wifi_on():
            return  # it shows how things are: nothing to do
        if wanted:
            await self._set_wifi(True)
            return
        self._switch.set_value(True)  # it stays on until the operator confirms
        self._confirm.ask(
            "Turn the Wi-Fi off?",
            "The handcart leaves its network. An SSH session over this Wi-Fi drops. "
            "It comes back on by itself when the handcart restarts.",
            "Turn off",
            lambda: self._set_wifi(False),
        )

    def _flip_switch(self) -> None:
        """The physical controls pressed the switch."""
        self._switch.set_value(not self._switch.value)

    async def _set_wifi(self, on: bool) -> None:
        if on:
            self._doing = "Turning the Wi-Fi on…"
        else:
            self._doing = "Turning the Wi-Fi off…"
        self.update()
        problem = await self._backend.set_wifi(on)
        self._doing = None
        if problem:
            self._toast.show(problem, ok=False)
        self.update()

    def _ask_password(self, network: WifiNetwork) -> None:
        self._asking = network
        self._keyboard.clear(f"Password of {network.ssid}")
        self._list_view.set_visibility(False)
        self._password_view.set_visibility(True)

    def _show_list(self) -> None:
        self._asking = None
        self._password_view.set_visibility(False)
        self._list_view.set_visibility(True)
        self.update()


def wifi_status(networks: list[WifiNetwork]) -> str:
    """ "Connected to Eagle": the Wi-Fi the handcart is on."""
    for network in networks:
        if network.connected:
            return f"Connected to {network.ssid}"
    return "Not connected to a Wi-Fi"


def ip_text(addresses: list[str]) -> str:
    """The addresses to reach the handcart at, e.g. over SSH."""
    if addresses:
        return ", ".join(addresses)
    return "none"


def network_details(network: WifiNetwork) -> str:
    """ "Connected", "Saved · No password": what the row says besides the name and the signal."""
    parts = []
    if network.connected:
        parts.append("Connected")
    elif network.saved:
        parts.append("Saved")
    if not network.secured:
        parts.append("No password")
    return " · ".join(parts)


def signal_bars(signal: int) -> int:
    """How many of the BARS are lit for a signal in %: at least one, the network is there."""
    if signal >= 75:
        return 4
    if signal >= 50:
        return 3
    if signal >= 25:
        return 2
    return 1
