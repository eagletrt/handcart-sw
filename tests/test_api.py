"""The HTTP API: what the frontend and telemetry can read and ask."""

import can
import pytest
from fastapi.testclient import TestClient

from backend.api import create_app
from backend.hal.fake import FakeHal
from backend.handcart import Handcart
from backend.system import System
from shared.models import InputEvent, Status, StreamMessage


@pytest.fixture
def client(cfg):
    bus = can.Bus(interface="virtual", channel="api", receive_own_messages=False)
    hal = FakeHal()
    handcart = Handcart(cfg, hal, bus, bus)
    with TestClient(create_app(handcart, System(cfg.update))) as client:
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
    ok = {"target_voltage": cfg.charge.target_voltage_min, "max_current": 5.0}
    assert client.put("/api/settings", json=ok).json() == ok

    too_high = {"target_voltage": cfg.charge.target_voltage_max + 1, "max_current": 5.0}
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
