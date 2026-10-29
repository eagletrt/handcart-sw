"""The network part of the System page: the Wi-Fi networks, and what the Wi-Fi window says."""

from backend import network as network_module
from backend.network import (
    DEVICE_TYPE_BRIDGE,
    DEVICE_TYPE_ETHERNET,
    DEVICE_TYPE_WIFI,
    FAKE_PASSWORD,
    FakeNetwork,
    address_name,
    connect_problem,
    hotspot_problem,
    in_address_order,
    load_hotspot,
    one_per_name,
    password_problem,
    ssid_text,
)
from frontend.wifi_window import address_lines, network_details, signal_bars, wifi_status
from shared.models import Address, WifiNetwork

DEVICE_TYPE_TUN = 16  # tailscale0


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
    addresses = [Address(name="Wi-Fi", address="192.168.1.23"), Address(name="Cable", address="10.0.0.5")]
    assert address_lines(addresses) == [("Wi-Fi", "192.168.1.23"), ("Cable", "10.0.0.5")]
    assert address_lines([]) == [("IP address", "none")]


def test_each_address_says_what_it_is_on():
    assert address_name("eth0", DEVICE_TYPE_ETHERNET, hotspot=False) == "Cable"
    assert address_name("wlan1", DEVICE_TYPE_WIFI, hotspot=False) == "Wi-Fi"
    assert address_name("wlan0", DEVICE_TYPE_WIFI, hotspot=True) == "Hotspot"
    assert address_name("tailscale0", DEVICE_TYPE_TUN, hotspot=False) == "Tailscale"
    assert address_name("usb0", 99, hotspot=False) == "usb0"
    assert address_name("docker0", DEVICE_TYPE_BRIDGE, hotspot=False) is None
    assert address_name("lo", 32, hotspot=False) is None


def test_addresses_cable_first():
    addresses = [
        Address(name="Tailscale", address="100.64.0.14"),
        Address(name="usb0", address="10.0.0.2"),
        Address(name="Wi-Fi", address="192.168.1.251"),
        Address(name="Cable", address="192.168.2.10"),
    ]
    assert [a.name for a in in_address_order(addresses)] == ["Cable", "Wi-Fi", "Tailscale", "usb0"]


def test_network_details():
    assert network_details(network(connected=True, saved=True)) == "Connected"
    assert network_details(network(saved=True, secured=False)) == "Saved · No password"
    assert network_details(network()) == ""


def test_signal_bars():
    assert [signal_bars(s) for s in (100, 75, 74, 50, 49, 25, 24, 0)] == [4, 4, 3, 3, 2, 2, 1, 1]


def test_fake_network_wants_its_password(monkeypatch, cfg):
    monkeypatch.setattr(network_module, "FAKE_DELAY", 0)
    fake = FakeNetwork(cfg.hotspot)
    assert fake.connect("Lab Box: 5G", "wrong-one") == "Could not connect to Lab Box: 5G: wrong password"
    assert fake.connect("Lab Box: 5G", FAKE_PASSWORD) is None
    info = fake.info()
    assert info.networks[0].ssid == "Lab Box: 5G" and info.networks[0].connected
    assert fake.connect("E-Agle TRT", None) is None  # saved: no password needed
    assert fake.connect("Guest", None) is None  # open


def test_fake_network_disconnects_and_turns_the_wifi_off(monkeypatch, cfg):
    monkeypatch.setattr(network_module, "FAKE_DELAY", 0)
    fake = FakeNetwork(cfg.hotspot)
    fake.disconnect()
    assert not any(n.connected for n in fake.info().networks)
    fake.set_wifi(False)
    info = fake.info()
    assert not info.wifi_on and info.networks == [] and info.addresses == []
    fake.set_wifi(True)
    assert fake.info().wifi_on


def test_fake_wifi_back_on_joins_its_network_again(monkeypatch, cfg):
    monkeypatch.setattr(network_module, "FAKE_DELAY", 0)
    fake = FakeNetwork(cfg.hotspot)
    fake.set_wifi(False)
    fake.set_wifi(True)
    assert fake.info().networks[0].ssid == "E-Agle TRT"
    assert fake.info().networks[0].connected


def test_fake_hotspot_goes_off_with_the_wifi_and_back_with_it(monkeypatch, cfg):
    monkeypatch.setattr(network_module, "FAKE_DELAY", 0)
    fake = FakeNetwork(cfg.hotspot)
    assert fake.set_hotspot(True) is None
    info = fake.info()
    assert info.hotspot.on and info.hotspot.ssid == cfg.hotspot.ssid
    assert Address(name="Hotspot", address="10.42.0.1") in info.addresses
    fake.set_wifi(False)
    assert not fake.info().hotspot.on
    assert fake.set_hotspot(True) == "Turn the Wi-Fi on first"
    fake.set_wifi(True)
    assert fake.info().hotspot.on  # still saved: back on by itself


def test_a_hotspot_name_or_password_it_cannot_have_is_refused():
    assert hotspot_problem("", "eagletrt") == "A Wi-Fi name has 1 to 32 characters"
    assert hotspot_problem("x" * 33, "eagletrt") == "A Wi-Fi name has 1 to 32 characters"
    assert hotspot_problem("handcart", "short") == "A Wi-Fi password has 8 to 63 characters"
    assert hotspot_problem("handcart", "eagletrt") is None


def test_the_hotspot_changed_on_the_screen_is_kept_across_restarts(monkeypatch, cfg, tmp_path):
    monkeypatch.setattr(network_module, "FAKE_DELAY", 0)
    file = tmp_path / "var" / "hotspot.json"
    fake = FakeNetwork(cfg.hotspot, file)
    assert fake.info().hotspot.ssid == cfg.hotspot.ssid  # config.toml's, until changed
    assert fake.change_hotspot("handcart-2", "short") == "A Wi-Fi password has 8 to 63 characters"
    assert not file.exists()
    assert fake.change_hotspot("handcart-2", "new-password") is None
    again = FakeNetwork(cfg.hotspot, file)  # the backend restarted
    assert again.info().hotspot.ssid == "handcart-2"
    assert again.info().hotspot.password == "new-password"


def test_an_unreadable_hotspot_file_falls_back_to_the_config(cfg, tmp_path):
    file = tmp_path / "hotspot.json"
    file.write_text("not json")
    assert load_hotspot(cfg.hotspot, file).ssid == cfg.hotspot.ssid
    file.write_text('{"ssid": "handcart", "password": "short"}')
    assert load_hotspot(cfg.hotspot, file).password == cfg.hotspot.password
