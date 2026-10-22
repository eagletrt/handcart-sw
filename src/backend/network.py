"""The Wi-Fi window's backend: the handcart's addresses, joining and leaving Wi-Fi networks, the radio.

Raspberry Pi OS manages the network with NetworkManager: this module asks it through nmcli, as the
handcart user. The rule that lets that user change the network is system/polkit/50-handcart-network.rules.
nmcli can take seconds (a scan, a connection): the API runs these calls in a thread, so the ticks go on.
Where there is no nmcli (a computer), FakeNetwork stands in, with made-up networks.
"""

import logging
import subprocess
import time

from shared.models import NetworkInfo, WifiNetwork

log = logging.getLogger(__name__)

NMCLI_TIMEOUT = 10  # s, for reading what NetworkManager already knows
SCAN_TIMEOUT = 20  # s
CONNECT_WAIT = 20  # s for the network to come up; nmcli gives up after this
WIFI_PROFILE = "802-11-wireless"  # the type of a saved Wi-Fi network, in nmcli
WIFI_DEVICE = "wifi"  # the type of a Wi-Fi interface (wlan0), in nmcli
PASSWORD_MIN, PASSWORD_MAX = 8, 63  # characters of a WPA password
FAKE_PASSWORD = "eagletrt"  # of every FakeNetwork network
FAKE_DELAY = 1.5  # s a FakeNetwork scan or connection takes: enough to see "Connecting…"


class Network:
    def info(self) -> NetworkInfo:
        addresses = self._addresses()
        try:
            wifi_on = self._nmcli("radio", "wifi").strip() == "enabled"
            saved = parse_saved(self._nmcli("-t", "-f", "NAME,TYPE", "connection", "show"))
            listing = self._nmcli(
                "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list", "--rescan", "no"
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            log.warning("nmcli failed: %s", error)
            return NetworkInfo(
                wifi_on=False, addresses=addresses, networks=[], problem="NetworkManager is not answering"
            )
        networks = parse_networks(listing, saved)
        return NetworkInfo(wifi_on=wifi_on, addresses=addresses, networks=networks, problem=None)

    def scan(self) -> str | None:
        """Look for Wi-Fi networks again. Returns why it could not, or None; the result is in info()."""
        try:
            self._nmcli("device", "wifi", "list", "--rescan", "yes", timeout=SCAN_TIMEOUT)
        except subprocess.TimeoutExpired:
            return "The Wi-Fi search took too long"
        except subprocess.CalledProcessError as error:
            log.warning("Wi-Fi scan failed: %s", error.stderr.strip())
            return "Could not search for Wi-Fi networks"
        return None

    def connect(self, ssid: str, password: str | None) -> str | None:
        """Join a network. Without a password: the saved one, or none for an open network.

        Returns why it could not, or None. The password is never logged.
        """
        if problem := password_problem(password):
            return problem

        command = ["--wait", str(CONNECT_WAIT), "device", "wifi", "connect", ssid]
        if password is not None:
            # a new password replaces the saved one: else nmcli would make a second profile for it
            self._forget(ssid)
            command += ["password", password]
        try:
            self._nmcli(*command, timeout=CONNECT_WAIT + 5)
        except subprocess.TimeoutExpired:
            return f"{ssid} did not answer"
        except subprocess.CalledProcessError as error:
            # stderr only: error itself holds the command, password included
            log.warning("could not connect to %s: %s", ssid, error.stderr.strip())
            if password is not None:
                self._forget(ssid)  # else the wrong password stays saved, and is tried again next time
            return f"Could not connect to {ssid}: {connect_problem(error.stderr)}"
        log.info("connected to %s", ssid)
        return None

    def disconnect(self) -> str | None:
        """Leave the Wi-Fi network the handcart is on; it stays saved. Returns why it could not, or None."""
        try:
            device = self._wifi_device()
            self._nmcli("device", "disconnect", device)
        except subprocess.CalledProcessError as error:
            log.warning("could not disconnect: %s", error.stderr.strip())
            return "Could not disconnect from the Wi-Fi"
        except subprocess.TimeoutExpired:
            return "NetworkManager is not answering"
        log.info("disconnected from the Wi-Fi")
        return None

    def set_wifi(self, on: bool) -> str | None:
        """Turn the Wi-Fi radio on or off. Returns why it could not, or None."""
        state = "off"
        if on:
            state = "on"
        try:
            self._nmcli("radio", "wifi", state)
        except subprocess.CalledProcessError as error:
            log.warning("could not turn the Wi-Fi %s: %s", state, error.stderr.strip())
            return f"Could not turn the Wi-Fi {state}"
        except subprocess.TimeoutExpired:
            return "NetworkManager is not answering"
        log.info("Wi-Fi turned %s", state)
        return None

    def _wifi_device(self) -> str:
        """The name of the Wi-Fi interface: wlan0 on the Pi."""
        for line in self._nmcli("-t", "-f", "DEVICE,TYPE", "device").splitlines():
            device, kind = split_terse(line)
            if kind == WIFI_DEVICE:
                return device
        return "wlan0"

    def _forget(self, ssid: str) -> None:
        """Delete the saved network named ssid, if there is one."""
        result = subprocess.run(
            ["nmcli", "connection", "delete", "id", ssid],
            capture_output=True,
            text=True,
            timeout=NMCLI_TIMEOUT,
        )
        if result.returncode == 0:
            log.info("forgot the saved network %s", ssid)

    def _addresses(self) -> list[str]:
        """The handcart's IPv4 addresses, from ip; none where ip is missing (on a Mac)."""
        try:
            result = subprocess.run(
                ["ip", "-brief", "-4", "address", "show"],
                capture_output=True,
                text=True,
                timeout=NMCLI_TIMEOUT,
                check=True,
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return []
        return parse_addresses(result.stdout)

    def _nmcli(self, *args: str, timeout: float = NMCLI_TIMEOUT) -> str:
        """Run nmcli and return what it printed."""
        result = subprocess.run(["nmcli", *args], capture_output=True, text=True, timeout=timeout, check=True)
        return result.stdout


class FakeNetwork:
    """The Wi-Fi off the handcart: made-up networks, to try the Wi-Fi window on a computer.

    The password of every network is FAKE_PASSWORD; any other one is wrong.
    """

    def __init__(self) -> None:
        self._wifi_on = True
        self._last_ssid: str | None = None  # the network it was on when the Wi-Fi went off
        self._networks = [
            WifiNetwork(ssid="E-Agle TRT", signal=74, secured=True, connected=True, saved=True),
            WifiNetwork(ssid="Lab Box: 5G", signal=88, secured=True, connected=False, saved=False),
            WifiNetwork(ssid="Guest", signal=51, secured=False, connected=False, saved=False),
            WifiNetwork(ssid="eduroam", signal=33, secured=True, connected=False, saved=False),
            WifiNetwork(ssid="Far away", signal=12, secured=True, connected=False, saved=False),
        ]

    def info(self) -> NetworkInfo:
        if not self._wifi_on:
            return NetworkInfo(wifi_on=False, addresses=[], networks=[], problem=None)
        addresses = []
        for network in self._networks:
            if network.connected:
                addresses.append("192.168.1.23")
        return NetworkInfo(wifi_on=True, addresses=addresses, networks=in_order(self._networks), problem=None)

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
            if network.secured and not uses_saved_password and password != FAKE_PASSWORD:
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


# reading what nmcli and ip print


def split_terse(line: str) -> list[str]:
    """The fields of a line of nmcli -t: split at ':', where '\\:' is a colon inside a field."""
    fields = []
    field = ""
    escaped = False
    for char in line:
        if escaped:
            field += char
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == ":":
            fields.append(field)
            field = ""
        else:
            field += char
    fields.append(field)
    return fields


def parse_saved(text: str) -> set[str]:
    """The names of the saved Wi-Fi networks, from nmcli -t -f NAME,TYPE connection show."""
    names = set()
    for line in text.splitlines():
        name, kind = split_terse(line)
        if kind == WIFI_PROFILE:
            names.add(name)
    return names


def parse_networks(text: str, saved: set[str]) -> list[WifiNetwork]:
    """The networks in nmcli -t -f IN-USE,SSID,SIGNAL,SECURITY device wifi list: one per name.

    A network with several access points (or radios) shows up once per access point: its row keeps the
    strongest signal, and it is connected if the handcart is on any of them. Hidden networks are left out.
    """
    networks: dict[str, WifiNetwork] = {}
    for line in text.splitlines():
        in_use, ssid, signal, security = split_terse(line)
        if not ssid:
            continue  # a hidden network: it has no name to show
        network = WifiNetwork(
            ssid=ssid,
            signal=int(signal),
            secured=security not in ("", "--"),
            connected=in_use == "*",
            saved=ssid in saved,
        )
        if ssid in networks:
            seen = networks[ssid]
            network.signal = max(network.signal, seen.signal)
            network.connected = network.connected or seen.connected
        networks[ssid] = network

    return in_order(list(networks.values()))


def in_order(networks: list[WifiNetwork]) -> list[WifiNetwork]:
    """The connected network first, then the others from the strongest."""
    strongest_first = sorted(networks, key=lambda n: n.signal, reverse=True)
    connected = [n for n in strongest_first if n.connected]
    others = [n for n in strongest_first if not n.connected]
    return connected + others


def parse_addresses(text: str) -> list[str]:
    """ "wlan0  UP  192.168.1.23/24" (ip -brief -4 address) -> "192.168.1.23". Not loopback."""
    addresses = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) < 3 or fields[0] == "lo":
            continue  # no address, or only the Pi itself
        for address in fields[2:]:
            addresses.append(address.split("/")[0])  # without the /24
    return addresses


def connect_problem(stderr: str) -> str:
    """Why nmcli could not connect, in the operator's words when we know them."""
    if "Secrets were required" in stderr:
        return "wrong password"
    if "No network with SSID" in stderr:
        return "network not found"
    return stderr.strip().removeprefix("Error: ")
