"""The network part of the System page: the Wi-Fi networks, and what the Wi-Fi window says."""

from backend import network as network_module
from backend.network import (
    FAKE_PASSWORD,
    FakeNetwork,
    connect_problem,
    one_per_name,
    password_problem,
    ssid_text,
)
from frontend.wifi_window import ip_text, network_details, signal_bars, wifi_status
from shared.models import WifiNetwork


def test_networks_one_row_per_name_connected_first():
    rows = [
        network("Lab", signal=90),
        network("Eagle", signal=40, saved=True),
        network("Eagle", signal=60, connected=True, saved=True),  # another access point: the one it is on
        network("Guest", signal=70, secured=False),
        network("", signal=80),  # hidden: no name
    ]
    networks = one_per_name(rows)
    assert [n.ssid for n in networks] == ["Eagle", "Lab", "Guest"]
    eagle = networks[0]
    assert eagle.connected and eagle.saved and eagle.secured
    assert eagle.signal == 60  # the strongest of its access points
    assert not networks[2].secured


def test_connect_problems_in_plain_words():
    assert connect_problem(7) == "wrong password"
    assert connect_problem(8) == "wrong password"
    assert connect_problem(53) == "network not found"
    assert connect_problem(None) == "the network refused it"


def test_network_names_from_dbus_bytes():
    assert ssid_text([101, 97, 103, 108, 101, 116, 114, 116]) == "eagletrt"
    assert ssid_text("Café".encode()) == "Café"


def test_a_password_too_short_is_refused():
    assert password_problem("short") == "A Wi-Fi password has 8 to 63 characters"
    assert password_problem(None) is None


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
