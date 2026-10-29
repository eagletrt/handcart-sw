"""The Wi-Fi window, from the icon next to the gear: the networks around, the password on the screen keyboard.

A saved or open network is joined with a touch, a new one asks for its password first. When a network with
a password does not connect (a typo, or a saved password that changed), the password is asked again.
A touch on the network the handcart is on leaves it. Leaving it and turning the Wi-Fi off are confirmed
first: an SSH session over the Wi-Fi drops.

On the right of the title, the handcart's addresses, each with what it is on (Cable, Wi-Fi, Hotspot...).
Hotspot opens a view with its switch, and its name, password and address to join it and SSH from a laptop
where there is no Wi-Fi; turning it off is confirmed first too. Change asks its new name, then its new
password, on the keyboard of the Wi-Fi passwords.
"""

from nicegui import ui
from nicegui.events import ValueChangeEventArguments

from frontend.backend import Backend
from frontend.controls import Target
from frontend.keyboard import Keyboard
from frontend.overlays import ConfirmWindow, Toast
from frontend.targets import Reachable, button, usable
from shared.models import Address, NetworkInfo, WifiNetwork

ROWS_SHOWN = 4  # the strongest networks: as many as fit on the screen
ADDRESSES_SHOWN = 4  # cable, Wi-Fi, hotspot, Tailscale: as many as fit next to the title
BARS = 4  # of the signal, as on a phone


class WifiWindow:
    def __init__(self, backend: Backend, toast: Toast, confirm: ConfirmWindow) -> None:
        self._backend = backend
        self._toast = toast
        self._confirm = confirm
        self._shown: list[WifiNetwork] = []  # the networks in the rows, in order
        self._asking: WifiNetwork | None = None  # the network the keyboard is asking the password of
        self._doing: str | None = None  # "Searching…" while waiting for the backend, else None
        self._hotspot_doing: str | None = None  # "Turning the hotspot on…", as _doing
        # "name" or "password" while the keyboard asks the hotspot's new ones, else None
        self._editing: str | None = None
        self._new_ssid = ""  # what was typed: kept to fix it if the backend refuses it
        self._new_password = ""

        # built when it opens and emptied when it closes: the browser redraws every element of the page at
        # each change, hidden ones too. Built once here, so that every attribute exists before it opens.
        self.root = ui.element("div").classes("modal")
        with self.root:
            self._build()
        self.close()

    def _build(self) -> None:
        with ui.element("div").classes("sheet wifi"):
            with ui.element("div") as self._list_view:
                with ui.element("div").classes("whead"):
                    with ui.element("div"):
                        with ui.element("div").classes("wtitle"):
                            ui.label("Wi-Fi").classes("sheet-title")
                            # shows whether the Wi-Fi is on; turning it off asks first
                            self._switch = ui.switch(value=True, on_change=self._on_switch)
                            self._switch.props("color=primary").classes("wswitch")
                        self._status = ui.label("").classes("sheet-sub")
                    # what each address is on, and the address: big, to type it in ssh
                    self._addresses: list[tuple[ui.label, ui.label]] = []
                    with ui.element("div").classes("wip"):
                        for _ in range(ADDRESSES_SHOWN):
                            self._addresses.append((ui.label("").classes("lbl"), ui.label("").classes("num")))
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
                with ui.element("div").classes("sheet-actions wacts"):
                    self._close = ui.button("Close", on_click=self.close)
                    self._close.props("flat no-caps text-color=white").classes("cancel")
                    self._open_hotspot = ui.button(
                        "Hotspot", icon="wifi_tethering", on_click=self._show_hotspot
                    )
                    self._open_hotspot.props("flat no-caps text-color=white").classes("cancel")
                    self._scan = ui.button("Search again", icon="refresh", on_click=self._on_scan)
                    self._scan.props("unelevated no-caps text-color=black")

            with ui.element("div") as self._hotspot_view:
                with ui.element("div").classes("wtitle"):
                    ui.label("Hotspot").classes("sheet-title")
                    self._hotspot_switch = ui.switch(value=False, on_change=self._on_hotspot_switch)
                    self._hotspot_switch.props("color=primary").classes("wswitch")
                self._hotspot_status = ui.label("").classes("sheet-sub")
                with ui.element("div").classes("hbox"):
                    ui.label("Name").classes("lbl")
                    self._hotspot_ssid = ui.label("").classes("num")
                    ui.label("Password").classes("lbl")
                    self._hotspot_password = ui.label("").classes("num")
                    ui.label("SSH to").classes("lbl")
                    self._hotspot_address = ui.label("").classes("num")
                ui.label(
                    "Join it from the laptop, then SSH to its address. It uses the Wi-Fi that is not on "
                    "a network: the handcart stays on its network. It stays on after a restart; "
                    "a laptop on it drops when the name or the password changes."
                ).classes("hnote")
                with ui.element("div").classes("sheet-actions hacts"):
                    self._back = ui.button("Back", on_click=self._show_list)
                    self._back.props("flat no-caps text-color=white").classes("cancel")
                    self._change = ui.button(
                        "Change name and password", icon="edit", on_click=self._on_change
                    )
                    self._change.props("unelevated no-caps text-color=black")

            with ui.element("div") as self._password_view:
                self._keyboard = Keyboard()
                with ui.element("div").classes("sheet-actions"):
                    self._cancel = ui.button("Cancel", on_click=self._on_cancel)
                    self._cancel.props("flat no-caps text-color=white").classes("cancel")
                    self._connect = ui.button("Connect", on_click=self._on_connect)
                    self._connect.props("unelevated no-caps text-color=black")
        self._password_view.set_visibility(False)
        self._hotspot_view.set_visibility(False)

    def close(self) -> None:
        self.root.set_visibility(False)
        self.root.clear()

    def reachable(self) -> list[Reachable]:
        if self._password_view.visible:
            actions = usable(button("cancel", self._cancel), button("connect", self._connect))
            return [*self._keyboard.reachable(), *actions]
        if self._hotspot_view.visible:
            switch = Reachable(
                Target("hotspot switch"), self._hotspot_switch, press=self._flip_hotspot_switch
            )
            return [switch, *usable(button("back", self._back, priority=1), button("change", self._change))]
        switch = Reachable(Target("wifi switch"), self._switch, press=self._flip_switch)
        rows = [button(f"network {i}", row) for i, (row, _, _, _) in enumerate(self._rows)]
        actions = usable(
            button("close", self._close, priority=1),
            button("hotspot", self._open_hotspot),
            button("search", self._scan),
        )
        return [switch, *usable(*rows), *actions]

    async def open(self) -> None:
        self.root.clear()
        with self.root:
            self._build()
        self.root.set_visibility(True)  # first: update skips a closed window
        self._show_list()
        await self._on_scan()  # what the Wi-Fi saw last may be old: look again

    def update(self) -> None:
        """Draw what the backend last said about the network (the keyboard is left alone)."""
        if not self.root.visible or self._password_view.visible:
            return  # closed, its switch must not change: that would ask to turn the Wi-Fi off
        info = self._backend.network
        self._update_hotspot(info)
        if info is not None and self._doing is None:  # while turning it on or off, the switch shows the wish
            self._switch.set_value(info.wifi_on)
        self._scan.set_visibility(info is not None and info.wifi_on)  # searching needs the Wi-Fi on
        if info is not None and info.hotspot.on:
            self._open_hotspot.classes(add="on")
        else:
            self._open_hotspot.classes(remove="on")
        if info is None:
            status = "Reading the network…"
            self._shown = []
            lines = [("IP address", "–")]
        elif not info.wifi_on:
            status = "Wi-Fi is off"
            self._shown = []
            lines = address_lines(info.addresses)  # a cable may still give one
        elif info.problem:
            status = info.problem
            self._shown = []
            lines = address_lines(info.addresses)
        else:
            status = wifi_status(info.networks)
            self._shown = info.networks[:ROWS_SHOWN]
            lines = address_lines(info.addresses)
        for i, (name, address) in enumerate(self._addresses):
            if i < len(lines):
                name.set_text(lines[i][0])
                address.set_text(lines[i][1])
                name.set_visibility(True)
                address.set_visibility(True)
            else:
                name.set_visibility(False)
                address.set_visibility(False)
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

    def _update_hotspot(self, info: NetworkInfo | None) -> None:
        if info is None:
            self._hotspot_status.set_text("Reading the network…")
            return
        hotspot = info.hotspot
        if self._hotspot_doing is None:  # while turning it on or off, the switch shows the wish
            self._hotspot_switch.set_value(hotspot.on)
        self._hotspot_ssid.set_text(hotspot.ssid)
        self._hotspot_password.set_text(hotspot.password)
        self._hotspot_address.set_text(hotspot.address or "–")
        if self._hotspot_doing is not None:
            status = self._hotspot_doing
        elif hotspot.on:
            status = f"On: join {hotspot.ssid} from the laptop"
        elif not info.wifi_on:
            status = "Off: the Wi-Fi is off"
        else:
            status = "Off"
        self._hotspot_status.set_text(status)

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

    def typing(self) -> bool:
        """Whether the password keyboard is open: a USB keyboard types into it (on_key)."""
        return self.root.visible and self._password_view.visible

    async def on_key(self, key: str) -> None:
        """A key of a USB keyboard while typing: Enter connects, Escape goes back, the rest types."""
        if key == "Enter":
            await self._on_connect()
        elif key == "Escape":
            self._on_cancel()
        else:
            self._keyboard.press_key(key)

    async def _on_connect(self) -> None:
        """Connect, or, for the hotspot, Next after its name and Save after its password."""
        if self._editing == "name":
            self._new_ssid = self._keyboard.text
            self._edit_hotspot("password")
        elif self._editing == "password":
            self._new_password = self._keyboard.text
            await self._save_hotspot()
        elif self._asking is not None:
            await self._join(self._asking, self._keyboard.text)

    def _on_cancel(self) -> None:
        if self._editing is not None:
            self._show_hotspot()
        else:
            self._show_list()

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
            "The handcart leaves its network, and the hotspot goes off. An SSH session over the Wi-Fi drops. "
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

    async def _on_hotspot_switch(self, event: ValueChangeEventArguments) -> None:
        """The hotspot switch moved: by the operator, or by update() showing what the backend said."""
        info = self._backend.network
        wanted = event.value
        if info is None or wanted == info.hotspot.on:
            return  # it shows how things are: nothing to do
        if wanted:
            await self._set_hotspot(True)
            return
        self._hotspot_switch.set_value(True)  # it stays on until the operator confirms
        self._confirm.ask(
            "Turn the hotspot off?",
            "An SSH session over the hotspot drops. It stays off after a restart.",
            "Turn off",
            lambda: self._set_hotspot(False),
        )

    def _flip_hotspot_switch(self) -> None:
        """The physical controls pressed the hotspot switch."""
        self._hotspot_switch.set_value(not self._hotspot_switch.value)

    async def _set_hotspot(self, on: bool) -> None:
        if on:
            self._hotspot_doing = "Turning the hotspot on…"
        else:
            self._hotspot_doing = "Turning the hotspot off…"
        self.update()
        problem = await self._backend.set_hotspot(on)
        self._hotspot_doing = None
        if problem:
            self._toast.show(problem, ok=False)
        self.update()

    def _on_change(self) -> None:
        """Change: the keyboard, with the hotspot's name and password already typed, to edit them."""
        info = self._backend.network
        if info is None:
            return
        self._new_ssid = info.hotspot.ssid
        self._new_password = info.hotspot.password
        self._edit_hotspot("name")

    def _edit_hotspot(self, step: str) -> None:
        """The keyboard asks the hotspot's new name (step "name") or new password ("password")."""
        self._editing = step
        self._asking = None
        # shown, not dots: they are on the screen anyway, to type them on the laptop
        if step == "name":
            self._keyboard.clear("Hotspot name", self._new_ssid, shown=True)
            self._connect.set_text("Next")
        else:
            self._keyboard.clear("Hotspot password", self._new_password, shown=True)
            self._connect.set_text("Save")
        self._list_view.set_visibility(False)
        self._hotspot_view.set_visibility(False)
        self._password_view.set_visibility(True)

    async def _save_hotspot(self) -> None:
        self._hotspot_doing = "Changing the hotspot…"
        self._show_hotspot()
        problem = await self._backend.change_hotspot(self._new_ssid, self._new_password)
        self._hotspot_doing = None
        if problem:
            self._toast.show(problem, ok=False)
            self._edit_hotspot("name")  # what was typed is still there, to fix it
        else:
            self._toast.show(f"The hotspot is now {self._new_ssid}", ok=True)
            self.update()

    def _ask_password(self, network: WifiNetwork) -> None:
        self._asking = network
        self._editing = None
        self._keyboard.clear(f"Password of {network.ssid}")
        self._connect.set_text("Connect")
        self._list_view.set_visibility(False)
        self._password_view.set_visibility(True)

    def _show_list(self) -> None:
        self._asking = None
        self._editing = None
        self._password_view.set_visibility(False)
        self._hotspot_view.set_visibility(False)
        self._list_view.set_visibility(True)
        self.update()

    def _show_hotspot(self) -> None:
        self._asking = None
        self._editing = None
        self._password_view.set_visibility(False)
        self._list_view.set_visibility(False)
        self._hotspot_view.set_visibility(True)
        self.update()


def wifi_status(networks: list[WifiNetwork]) -> str:
    """ "Connected to Eagle": the Wi-Fi the handcart is on."""
    for network in networks:
        if network.connected:
            return f"Connected to {network.ssid}"
    return "Not connected to a Wi-Fi"


def address_lines(addresses: list[Address]) -> list[tuple[str, str]]:
    """The lines next to the title: what each address is on, and the address, to reach it over SSH."""
    if not addresses:
        return [("IP address", "none")]
    lines = []
    for address in addresses[:ADDRESSES_SHOWN]:
        lines.append((address.name, address.address))
    return lines


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
