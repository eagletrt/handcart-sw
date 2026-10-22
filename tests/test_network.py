"""The network part of the System page: reading nmcli and ip, and what the Wi-Fi window says."""

from backend import network as network_module
from backend.network import (
    FAKE_PASSWORD,
    FakeNetwork,
    Network,
    connect_problem,
    parse_addresses,
    parse_networks,
    parse_saved,
    split_terse,
)
from frontend.wifi_window import ip_text, network_details, signal_bars, wifi_status
from shared.models import WifiNetwork


def test_terse_fields_keep_escaped_colons():
    assert split_terse(r"*:Eagle\:Box:82:WPA2") == ["*", "Eagle:Box", "82", "WPA2"]
    assert split_terse(r":back\\slash:40:") == ["", "back\\slash", "40", ""]


def test_saved_networks_are_only_the_wifi_ones():
    text = "Eagle:802-11-wireless\nWired connection 1:802-3-ethernet\nlo:loopback\n"
    assert parse_saved(text) == {"Eagle"}


def test_networks_one_row_per_name_connected_first():
    text = "\n".join(
        [
            ":Lab:90:WPA2",
            ":Eagle:40:WPA2",
            "*:Eagle:60:WPA2",  # the same network on another access point: the one the handcart is on
            ":Guest:70:",  # no password
            "::80:WPA2",  # hidden: no name
        ]
    )
    networks = parse_networks(text, saved={"Eagle"})
    assert [n.ssid for n in networks] == ["Eagle", "Lab", "Guest"]
    eagle = networks[0]
    assert eagle.connected and eagle.saved and eagle.secured
    assert eagle.signal == 60  # the strongest of its access points
    assert not networks[2].secured


def test_addresses_without_loopback():
    text = (
        "lo               UNKNOWN        127.0.0.1/8\n"
        "eth0             DOWN\n"
        "wlan0            UP             192.168.1.23/24\n"
    )
    assert parse_addresses(text) == ["192.168.1.23"]


def test_connect_problems_in_plain_words():
    wrong_password = "Error: Connection activation failed: Secrets were required, but not provided.\n"
    assert connect_problem(wrong_password) == "wrong password"
    assert connect_problem("Error: No network with SSID 'Lab' found.\n") == "network not found"
    assert connect_problem("Error: something else\n") == "something else"


def test_a_password_too_short_is_refused_before_nmcli():
    assert Network().connect("Eagle", "short") == "A Wi-Fi password has 8 to 63 characters"


def network(ssid="Eagle", signal=60, secured=True, connected=False, saved=False):
    return WifiNetwork(ssid=ssid, signal=signal, secured=secured, connected=connected, saved=saved)


def test_the_window_says_the_wifi_and_the_addresses():
    assert wifi_status([network("Lab"), network(connected=True)]) == "Connected to Eagle"
    assert wifi_status([network("Lab")]) == "Not connected to a Wi-Fi"
    assert ip_text(["192.168.1.23", "10.0.0.5"]) == "192.168.1.23, 10.0.0.5"
    assert ip_text([]) == "none"


def test_network_details():
    assert network_details(network(connected=True, saved=True)) == "Connected"
    assert network_details(network(saved=True, secured=False)) == "Saved · No password"
    assert network_details(network()) == ""


def test_signal_bars():
    assert [signal_bars(s) for s in (100, 75, 74, 50, 49, 25, 24, 0)] == [4, 4, 3, 3, 2, 2, 1, 1]


def test_fake_network_wants_its_password(monkeypatch):
    monkeypatch.setattr(network_module, "FAKE_DELAY", 0)
    fake = FakeNetwork()
    assert fake.connect("Lab Box: 5G", "wrong-one") == "Could not connect to Lab Box: 5G: wrong password"
    assert fake.connect("Lab Box: 5G", FAKE_PASSWORD) is None
    info = fake.info()
    assert info.networks[0].ssid == "Lab Box: 5G" and info.networks[0].connected
    assert fake.connect("E-Agle TRT", None) is None  # saved: no password needed
    assert fake.connect("Guest", None) is None  # open


def test_fake_network_disconnects_and_turns_the_wifi_off(monkeypatch):
    monkeypatch.setattr(network_module, "FAKE_DELAY", 0)
    fake = FakeNetwork()
    fake.disconnect()
    assert not any(n.connected for n in fake.info().networks)
    fake.set_wifi(False)
    info = fake.info()
    assert not info.wifi_on and info.networks == [] and info.addresses == []
    fake.set_wifi(True)
    assert fake.info().wifi_on


def test_fake_wifi_back_on_joins_its_network_again(monkeypatch):
    monkeypatch.setattr(network_module, "FAKE_DELAY", 0)
    fake = FakeNetwork()
    fake.set_wifi(False)
    fake.set_wifi(True)
    assert fake.info().networks[0].ssid == "E-Agle TRT"
    assert fake.info().networks[0].connected
