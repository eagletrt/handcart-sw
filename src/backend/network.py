"""The Wi-Fi window's backend: the handcart's addresses, joining and leaving Wi-Fi networks, the radio.

Raspberry Pi OS manages the network with NetworkManager: this module asks it over D-Bus, with
python-networkmanager, as the handcart user. The rule that lets that user change the network is
system/polkit/50-handcart-network.rules. A scan or a connection can take seconds: the API runs these calls
in a thread, so the ticks go on.
Where there is no NetworkManager (a computer), FakeNetwork stands in, with made-up networks.
"""

import logging
import time

from shared.models import NetworkInfo, WifiNetwork

log = logging.getLogger(__name__)

SCAN_TIMEOUT = 20  # s
CONNECT_WAIT = 20  # s for the network to come up
POLL = 0.25  # s between two looks at a scan or a connection under way
PASSWORD_MIN, PASSWORD_MAX = 8, 63  # characters of a WPA password
FAKE_PASSWORD = "eagletrt"  # of every FakeNetwork network
FAKE_DELAY = (
    1.5  # s a FakeNetwork scan or connection takes: enough to see "Connecting…"
)


class Network:
    def __init__(self) -> None:
        # Imported here, not at the top: importing NetworkManager connects to the system D-Bus at once,
        # and fails where there is none (a computer). make_network() then uses FakeNetwork.
        import dbus
        import NetworkManager

        self._nm = NetworkManager
        # what a call to NetworkManager can raise: an error, or an access point/connection that went away
        self._errors = (dbus.exceptions.DBusException, NetworkManager.ObjectVanished)

    def info(self) -> NetworkInfo:
        try:
            addresses = self._addresses()
            wifi_on = bool(self._nm.NetworkManager.WirelessEnabled)
            device = self._wifi_device()
            networks = []
            if device is not None:
                networks = self._networks(device)
        except self._errors as error:
            log.warning("NetworkManager failed: %s", error)
            return NetworkInfo(
                wifi_on=False,
                addresses=[],
                networks=[],
                problem="NetworkManager is not answering",
            )
        if device is None:
            return NetworkInfo(
                wifi_on=False,
                addresses=addresses,
                networks=[],
                problem="The handcart has no Wi-Fi",
            )
        return NetworkInfo(
            wifi_on=wifi_on, addresses=addresses, networks=networks, problem=None
        )

    def scan(self) -> str | None:
        """Look for Wi-Fi networks again. Returns why it could not, or None; the result is in info()."""
        try:
            device = self._wifi_device()
            if device is None:
                return "The handcart has no Wi-Fi"
            last_scan = device.LastScan
            device.RequestScan({})
            # RequestScan only starts the scan: LastScan changes when it is over
            deadline = time.monotonic() + SCAN_TIMEOUT
            while device.LastScan == last_scan:
                if time.monotonic() > deadline:
                    return "The Wi-Fi search took too long"
                time.sleep(POLL)
        except self._errors as error:
            log.warning("Wi-Fi scan failed: %s", error)
            return "Could not search for Wi-Fi networks"
        return None

    def connect(self, ssid: str, password: str | None) -> str | None:
        """Join a network. Without a password: the saved one, or none for an open network.

        Returns why it could not, or None. The password is never logged.
        """
        if problem := password_problem(password):
            return problem

        try:
            device = self._wifi_device()
            if device is None:
                return "The handcart has no Wi-Fi"
            saved = self._saved(ssid)
            if password is None and saved:
                active = self._nm.NetworkManager.ActivateConnection(
                    saved[0], device, "/"
                )
            else:
                access_point = self._access_point(device, ssid)
                if access_point is None:
                    return f"Could not connect to {ssid}: network not found"
                # a new password replaces the saved one: else NetworkManager would keep both
                self._forget(ssid)
                settings = {
                    "connection": {"id": ssid, "type": "802-11-wireless"},
                    "802-11-wireless": {"ssid": ssid, "mode": "infrastructure"},
                }
                if password is not None:
                    settings["802-11-wireless-security"] = {
                        "key-mgmt": "wpa-psk",
                        "psk": password,
                    }
                _, active = self._nm.NetworkManager.AddAndActivateConnection(
                    settings, device, access_point
                )
        except self._errors as error:
            # the settings (password included) are not in the error, only NetworkManager's answer
            log.warning("could not connect to %s: %s", ssid, error)
            return f"Could not connect to {ssid}"

        problem = self._wait_for(active, device)
        if problem is None:
            log.info("connected to %s", ssid)
            return None
        log.warning("could not connect to %s: %s", ssid, problem)
        if problem == "did not answer":
            return f"{ssid} did not answer"
        if password is not None:
            self._forget(
                ssid
            )  # else the wrong password stays saved, and is tried again next time
        return f"Could not connect to {ssid}: {problem}"

    def disconnect(self) -> str | None:
        """Leave the Wi-Fi network the handcart is on; it stays saved. Returns why it could not, or None."""
        try:
            device = self._wifi_device()
            if device is None:
                return "The handcart has no Wi-Fi"
            device.Disconnect()
        except self._errors as error:
            log.warning("could not disconnect: %s", error)
            return "Could not disconnect from the Wi-Fi"
        log.info("disconnected from the Wi-Fi")
        return None

    def set_wifi(self, on: bool) -> str | None:
        """Turn the Wi-Fi radio on or off. Returns why it could not, or None."""
        state = "off"
        if on:
            state = "on"
        try:
            self._nm.NetworkManager.WirelessEnabled = on
        except self._errors as error:
            log.warning("could not turn the Wi-Fi %s: %s", state, error)
            return f"Could not turn the Wi-Fi {state}"
        log.info("Wi-Fi turned %s", state)
        return None

    def _wifi_device(self):
        """The Wi-Fi interface, or None if there is none.

        The handcart can have two (the Pi's wlan0 and a USB dongle): the one on a network wins, else the first.
        """
        first = None
        for device in self._nm.NetworkManager.GetDevices():
            if device.DeviceType != self._nm.NM_DEVICE_TYPE_WIFI:
                continue
            if device.ActiveAccessPoint is not None:
                return device
            if first is None:
                first = device
        return first

    def _networks(self, device) -> list[WifiNetwork]:
        """The networks the Wi-Fi interface sees, as found by its last scan."""
        active = device.ActiveAccessPoint  # None when not connected
        saved = self._saved_ssids()
        rows = []
        for access_point in device.GetAccessPoints():
            try:
                ssid = access_point.Ssid
                secured = (
                    access_point.Flags & self._nm.NM_802_11_AP_FLAGS_PRIVACY
                    or access_point.WpaFlags
                    or access_point.RsnFlags
                )
                row = WifiNetwork(
                    ssid=ssid,
                    signal=access_point.Strength,
                    secured=bool(secured),
                    connected=access_point == active,
                    saved=ssid in saved,
                )
            except self._nm.ObjectVanished:
                continue  # out of range since the list was read
            rows.append(row)
        return one_per_name(rows)

    def _access_point(self, device, ssid: str):
        """The access point of the network named ssid with the strongest signal, or None if not in range."""
        best = None
        for access_point in device.GetAccessPoints():
            try:
                if access_point.Ssid == ssid and (
                    best is None or access_point.Strength > best.Strength
                ):
                    best = access_point
            except self._nm.ObjectVanished:
                continue
        return best

    def _saved(self, ssid: str) -> list:
        """The saved connections of the network named ssid: usually one, none if never joined."""
        connections = []
        for connection in self._nm.Settings.ListConnections():
            settings = connection.GetSettings()
            if settings.get("802-11-wireless", {}).get("ssid") == ssid:
                connections.append(connection)
        return connections

    def _saved_ssids(self) -> set[str]:
        """The names of the saved Wi-Fi networks."""
        names = set()
        for connection in self._nm.Settings.ListConnections():
            settings = connection.GetSettings()
            if "ssid" in settings.get("802-11-wireless", {}):
                names.add(settings["802-11-wireless"]["ssid"])
        return names

    def _forget(self, ssid: str) -> None:
        """Delete the saved network named ssid, if there is one."""
        try:
            for connection in self._saved(ssid):
                connection.Delete()
                log.info("forgot the saved network %s", ssid)
        except self._errors as error:
            log.warning("could not forget %s: %s", ssid, error)

    def _wait_for(self, active, device) -> str | None:
        """Wait for a connection to come up. Returns why it did not, or None."""
        deadline = time.monotonic() + CONNECT_WAIT
        while time.monotonic() < deadline:
            try:
                state = active.State
            except self._errors:
                state = (
                    self._nm.NM_ACTIVE_CONNECTION_STATE_DEACTIVATED
                )  # gone: it failed
            if state == self._nm.NM_ACTIVE_CONNECTION_STATE_ACTIVATED:
                return None
            if state == self._nm.NM_ACTIVE_CONNECTION_STATE_DEACTIVATED:
                try:
                    _, reason = device.StateReason
                except self._errors:
                    reason = None
                return connect_problem(self._nm, reason)
            time.sleep(POLL)
        return "did not answer"

    def _addresses(self) -> list[str]:
        """The handcart's IPv4 addresses, on every interface but loopback."""
        addresses = []
        for device in self._nm.NetworkManager.GetDevices():
            if device.Interface == "lo":
                continue  # only the Pi itself
            config = device.Ip4Config  # None when the interface has no address
            if config is None:
                continue
            for entry in config.AddressData:
                addresses.append(entry["address"])
        return addresses


class FakeNetwork:
    """The Wi-Fi off the handcart: made-up networks, to try the Wi-Fi window on a computer.

    The password of every network is FAKE_PASSWORD; any other one is wrong.
    """

    def __init__(self) -> None:
        self._wifi_on = True
        self._last_ssid: str | None = (
            None  # the network it was on when the Wi-Fi went off
        )
        self._networks = [
            WifiNetwork(
                ssid="E-Agle TRT", signal=74, secured=True, connected=True, saved=True
            ),
            WifiNetwork(
                ssid="Lab Box: 5G",
                signal=88,
                secured=True,
                connected=False,
                saved=False,
            ),
            WifiNetwork(
                ssid="Guest", signal=51, secured=False, connected=False, saved=False
            ),
            WifiNetwork(
                ssid="eduroam", signal=33, secured=True, connected=False, saved=False
            ),
            WifiNetwork(
                ssid="Far away", signal=12, secured=True, connected=False, saved=False
            ),
        ]

    def info(self) -> NetworkInfo:
        if not self._wifi_on:
            return NetworkInfo(wifi_on=False, addresses=[], networks=[], problem=None)
        addresses = []
        for network in self._networks:
            if network.connected:
                addresses.append("192.168.1.23")
        return NetworkInfo(
            wifi_on=True,
            addresses=addresses,
            networks=in_order(self._networks),
            problem=None,
        )

    def scan(self) -> str | None:
        time.sleep(FAKE_DELAY)
        return None

    def connect(self, ssid: str, password: str | None) -> str | None:
        if problem := password_problem(password):
            return problem
        time.sleep(FAKE_DELAY)
        for network in self._networks:
            if network.ssid != ssid:
                continue
            uses_saved_password = password is None and network.saved
            if (
                network.secured
                and not uses_saved_password
                and password != FAKE_PASSWORD
            ):
                return f"Could not connect to {ssid}: wrong password"
            for other in self._networks:
                other.connected = False
            network.connected = True
            network.saved = True
            return None
        return f"Could not connect to {ssid}: network not found"

    def disconnect(self) -> str | None:
        for network in self._networks:
            network.connected = False
        return None

    def set_wifi(self, on: bool) -> str | None:
        """As NetworkManager: off leaves the network, on joins it again by itself."""
        time.sleep(FAKE_DELAY)
        if not on:
            for network in self._networks:
                if network.connected:
                    self._last_ssid = network.ssid
            self.disconnect()
        elif not self._wifi_on:
            for network in self._networks:
                network.connected = network.ssid == self._last_ssid
        self._wifi_on = on
        return None


def password_problem(password: str | None) -> str | None:
    """Why the password cannot be a WPA one, or None (None too when there is no password)."""
    if password is not None and not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
        return f"A Wi-Fi password has {PASSWORD_MIN} to {PASSWORD_MAX} characters"
    return None


def one_per_name(rows: list[WifiNetwork]) -> list[WifiNetwork]:
    """One row per network name, from one row per access point.

    A network with several access points (or radios) shows up once per access point: its row keeps the
    strongest signal, and it is connected if the handcart is on any of them. Hidden networks are left out.
    """
    networks: dict[str, WifiNetwork] = {}
    for network in rows:
        if not network.ssid:
            continue  # a hidden network: it has no name to show
        if network.ssid in networks:
            seen = networks[network.ssid]
            network.signal = max(network.signal, seen.signal)
            network.connected = network.connected or seen.connected
        networks[network.ssid] = network
    return in_order(list(networks.values()))


def in_order(networks: list[WifiNetwork]) -> list[WifiNetwork]:
    """The connected network first, then the others from the strongest."""
    strongest_first = sorted(networks, key=lambda n: n.signal, reverse=True)
    connected = [n for n in strongest_first if n.connected]
    others = [n for n in strongest_first if not n.connected]
    return connected + others


def connect_problem(nm, reason: int | None) -> str:
    """Why a connection failed, from the reason NetworkManager gives for the Wi-Fi's state."""
    if reason in (
        nm.NM_DEVICE_STATE_REASON_NO_SECRETS,
        nm.NM_DEVICE_STATE_REASON_SUPPLICANT_DISCONNECT,
    ):
        return "wrong password"
    if reason == nm.NM_DEVICE_STATE_REASON_SSID_NOT_FOUND:
        return "network not found"
    return "the network refused it"
