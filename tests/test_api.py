"""The HTTP API: what the frontend and telemetry can read and ask."""

import can
import pytest
from fastapi.testclient import TestClient

from backend import network as network_module
from backend.api import create_app
from backend.hal.fake import FakeHal
from backend.handcart import Handcart
from backend.network import FakeNetwork
from backend.recorder import Recorder
from backend.system import System
from shared.models import InputEvent, NetworkInfo, RecordedEvent, Sound, Status, StreamMessage


@pytest.fixture
def client(cfg):
    bus = can.Bus(interface="virtual", channel="api", receive_own_messages=False)
    hal = FakeHal()
    handcart = Handcart(cfg, hal, bus, bus)
    with TestClient(create_app(handcart, System(cfg.update), FakeNetwork(cfg.hotspot))) as client:
        client.handcart = handcart  # type: ignore[attr-defined]
        client.hal = hal  # type: ignore[attr-defined]
        yield client
    bus.shutdown()


def test_status(client):
    response = client.get("/api/status")
    assert response.status_code == 200
    status = Status.model_validate(response.json())  # what the frontend will do
    assert status.state == "CHECK"
    assert not status.bms.connected


def test_a_refused_command_answers_with_the_reason(client):
    response = client.post("/api/command", json={"command": "PRECHARGE"})  # no BMS yet
    assert response.status_code == 422
    assert "not possible" in response.json()["detail"]


def test_unknown_command_is_rejected(client):
    assert client.post("/api/command", json={"command": "LAUNCH"}).status_code == 422


def test_settings(client, cfg):
    ok = {"target_voltage": cfg.charge.target_voltage_min, "max_current": 5.0, "balancing_threshold": 0.02}
    assert client.put("/api/settings", json=ok).json() == ok

    too_high = {**ok, "target_voltage": cfg.charge.target_voltage_max + 1}
    response = client.put("/api/settings", json=too_high)
    assert response.status_code == 422
    assert "outside" in response.json()["detail"]


def test_status_stream(client):
    with client.websocket_connect("/api/ws") as socket:
        message = StreamMessage.model_validate_json(socket.receive_text())
        assert message.status is not None
        assert message.status.state == "CHECK"


def test_control_presses_reach_the_stream(client):
    with client.websocket_connect("/api/ws") as socket:
        client.hal.press(InputEvent.UP)
        client.handcart.tick()
        for _ in range(20):  # status messages may come first
            message = StreamMessage.model_validate_json(socket.receive_text())
            if message.input is not None:
                break
        assert message.input is InputEvent.UP


def test_system_info(client, cfg):
    info = client.get("/api/system").json()
    assert info["branch"] == cfg.update.branch
    assert info["version"]


def test_reboot_is_refused_off_the_handcart(client):
    response = client.post("/api/system/reboot")
    assert response.status_code == 422
    assert "Only on the handcart" in response.json()["detail"]


def test_network(client):
    response = client.get("/api/network")
    assert response.status_code == 200
    assert NetworkInfo.model_validate(response.json()).networks  # the made-up ones


def test_the_hotspot_goes_on_and_off(client, monkeypatch):
    monkeypatch.setattr(network_module, "FAKE_DELAY", 0)
    assert client.post("/api/network/hotspot", json={"on": True}).status_code == 200
    hotspot = NetworkInfo.model_validate(client.get("/api/network").json()).hotspot
    assert hotspot.on and hotspot.address == "10.42.0.1"
    assert client.post("/api/network/hotspot", json={"on": False}).status_code == 200
    assert not NetworkInfo.model_validate(client.get("/api/network").json()).hotspot.on


def test_a_refused_hotspot_name_answers_with_the_reason(client):
    response = client.put("/api/network/hotspot", json={"ssid": "", "password": "eagletrt"})
    assert response.status_code == 422
    assert "1 to 32" in response.json()["detail"]


def test_a_refused_wifi_connection_answers_with_the_reason(client):
    response = client.post("/api/network/connect", json={"ssid": "Eagle", "password": "short"})
    assert response.status_code == 422
    assert "8 to 63" in response.json()["detail"]


def test_the_sounds_of_the_buzzer_reach_the_stream(client):
    with client.websocket_connect("/api/ws") as socket:
        client.handcart.play(Sound.CONFIRM)
        for _ in range(20):  # status messages may come first
            message = StreamMessage.model_validate_json(socket.receive_text())
            if message.sound is not None:
                break
        assert message.sound is Sound.CONFIRM


def test_a_touch_stops_the_tune_of_a_job_done(client):
    client.handcart.play(Sound.BALANCING_DONE)
    client.handcart.tick()
    assert client.hal.buzzer is not None
    assert client.post("/api/buzzer/hush").status_code == 204
    client.handcart.tick()
    assert client.hal.buzzer is None


def test_the_debug_window_plays_a_sound_on_the_buzzer(client):
    assert client.post("/api/buzzer/play", json={"sound": "CHARGE_DONE"}).status_code == 204
    client.handcart.tick()
    assert client.hal.buzzer is not None
    assert client.post("/api/buzzer/play", json={"sound": "SIREN"}).status_code == 422


def test_events_and_samples_from_the_record(cfg, tmp_path):
    bus = can.Bus(interface="virtual", channel="api-record", receive_own_messages=False)
    recorder = Recorder(tmp_path / "record.db")
    handcart = Handcart(cfg, FakeHal(), bus, bus, recorder=recorder)
    app = create_app(handcart, System(cfg.update), FakeNetwork(cfg.hotspot), recorder)
    with TestClient(app) as client:
        client.post("/api/command", json={"command": "PRECHARGE"})  # refused: no BMS
        events = [RecordedEvent.model_validate(e) for e in client.get("/api/events").json()]
        assert [e.kind for e in events] == ["refusal", "command"]
        notices = client.get("/api/events", params={"at_least": "notice"}).json()
        assert [e["kind"] for e in notices] == ["refusal"]
        assert client.get("/api/samples", params={"since": 0}).json() == []
    bus.shutdown()


def test_a_tone_to_find_the_resonance(client):
    assert client.post("/api/buzzer/tone", json={"frequency": 2500}).status_code == 204
    client.handcart.tick()
    assert client.hal.buzzer == 2500
    assert client.post("/api/buzzer/tone", json={"frequency": 50}).status_code == 422  # not a buzzer's


def test_the_resonance_found_is_kept_across_restarts(cfg, tmp_path):
    bus = can.Bus(interface="virtual", channel="api-buzzer", receive_own_messages=False)
    buzzer_file = tmp_path / "buzzer.json"

    def start() -> Handcart:
        return Handcart(cfg, FakeHal(), bus, bus, buzzer_file=buzzer_file)

    handcart = start()
    with TestClient(create_app(handcart, System(cfg.update), FakeNetwork(cfg.hotspot))) as client:
        assert client.get("/api/buzzer").json() == {"resonance": None}  # none saved yet: as written
        assert client.put("/api/buzzer/resonance", json={"frequency": 2700}).status_code == 204
    assert start().resonance == 2700
    bus.shutdown()
