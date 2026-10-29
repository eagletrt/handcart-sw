"""HTTP API of the backend, used by the frontend and by telemetry.

GET  /api/status    everything the UI shows
POST /api/command   {"command": "PRECHARGE"}: handled right away, refused with 422 and the reason
PUT  /api/settings  {"target_voltage": 590, "max_current": 6}: refused with 422 outside the limits
WS   /api/ws        {"status": ...} every STATUS_PERIOD, {"input": "UP"} as soon as a control is used,
                    and {"sound": "CONFIRM"} as soon as the buzzer starts a sound

POST /api/buzzer/hush  the operator touched the screen: the tune of a job done stops
POST /api/buzzer/play  {"sound": "CONFIRM"}: the buzzer plays it (the Debug window, to try the sounds)

GET  /api/system           version, updates on the branch, last update
POST /api/system/check     look for updates now (a few seconds)
POST /api/system/update    start ./handcart.py update: the backend restarts
POST /api/system/reboot
POST /api/system/shutdown  the last three only with the TS off and nothing running, else 422 and the reason

GET  /api/network          the handcart's addresses and the Wi-Fi networks around
POST /api/network/scan     look for Wi-Fi networks again (a few seconds)
POST /api/network/connect  {"ssid": "Eagle", "password": "..."}: 422 and the reason if it could not
POST /api/network/disconnect  leave the Wi-Fi network (it stays saved)
POST /api/network/wifi     {"on": false}: turn the Wi-Fi radio off or on
GET  /api/events           what happened, newest first: ?at_least=critical&limit=100&before_id=...
GET  /api/samples          the readings for the graphs: ?since=<s since 1970>&until=...
POST /api/network/hotspot  {"on": true}: turn the hotspot on or off (a few seconds)
PUT  /api/network/hotspot  {"ssid": "handcart", "password": "..."}: its new name and password
"""

import asyncio

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect

from backend.handcart import Handcart
from backend.network import FakeNetwork, Network
from backend.recorder import Recorder
from backend.sounds.player import length
from backend.system import System
from shared.models import (
    CommandRequest,
    HotspotDetails,
    HotspotRequest,
    NetworkInfo,
    RecordedEvent,
    Sample,
    Settings,
    Severity,
    Sound,
    SoundRequest,
    Status,
    StreamMessage,
    SystemInfo,
    WifiConnectRequest,
    WifiRadioRequest,
)

STATUS_PERIOD = 0.2  # s
INPUT_POLL_PERIOD = 0.02  # s: button presses reach the screen this fast


def create_app(
    handcart: Handcart,
    system: System,
    network: Network | FakeNetwork,
    recorder: Recorder | None = None,
) -> FastAPI:
    # every endpoint is async: it runs in the event loop between two ticks, never in the middle of one
    app = FastAPI(title="Handcart")

    @app.get("/api/status")
    async def status() -> Status:
        return handcart.status()

    @app.post("/api/command")
    async def command(body: CommandRequest) -> None:
        refuse_if(handcart.request(body.command))

    @app.put("/api/settings")
    async def settings(body: Settings) -> Settings:
        refuse_if(handcart.change_settings(body))
        return handcart.settings

    @app.post("/api/buzzer/hush", status_code=204)
    async def hush() -> None:
        handcart.hush()

    @app.post("/api/buzzer/play", status_code=204)
    async def play(body: SoundRequest) -> None:
        handcart.play(body.sound)

    # the record: SQLite in a thread, the SD card can be slow

    @app.get("/api/events")
    async def events(
        at_least: Severity = Severity.INFO, limit: int = 100, before_id: int | None = None
    ) -> list[RecordedEvent]:
        if recorder is None:
            return []
        return await asyncio.to_thread(recorder.events, before_id, limit, at_least)

    @app.get("/api/samples")
    async def samples(since: float, until: float | None = None) -> list[Sample]:
        if recorder is None:
            return []
        return await asyncio.to_thread(recorder.samples, since, until)

    @app.get("/api/system")
    async def system_info() -> SystemInfo:
        return system.info()

    @app.post("/api/system/check")
    async def check_updates() -> SystemInfo:
        await asyncio.to_thread(system.check)  # git fetch: in a thread, so the ticks go on meanwhile
        return system.info()

    @app.post("/api/system/update", status_code=202)
    async def update() -> None:
        refuse_if(handcart.maintenance_problem() or system.start_update())
        handcart.record("system", Severity.NOTICE, "api", "Update started", actor="api")

    @app.post("/api/system/reboot", status_code=202)
    async def reboot() -> None:
        refuse_if(handcart.maintenance_problem() or system.not_installed())
        handcart.record("system", Severity.NOTICE, "api", "Reboot", actor="api")
        await say_goodbye()
        refuse_if(system.reboot())

    @app.post("/api/system/shutdown", status_code=202)
    async def shut_down() -> None:
        refuse_if(handcart.maintenance_problem() or system.not_installed())
        handcart.record("system", Severity.NOTICE, "api", "Shut down", actor="api")
        await say_goodbye()
        refuse_if(system.shut_down())

    async def say_goodbye() -> None:
        """Play the power-off sound to the end: systemd stops the backend as soon as it is asked."""
        handcart.play(Sound.POWER_OFF)
        await asyncio.sleep(length(Sound.POWER_OFF))  # the ticks go on meanwhile, and play it

    # NetworkManager in a thread: it can take seconds, and the ticks go on meanwhile

    @app.get("/api/network")
    async def network_info() -> NetworkInfo:
        return await asyncio.to_thread(network.info)

    @app.post("/api/network/scan")
    async def scan_wifi() -> NetworkInfo:
        refuse_if(await asyncio.to_thread(network.scan))
        return await asyncio.to_thread(network.info)

    @app.post("/api/network/connect")
    async def connect_wifi(body: WifiConnectRequest) -> None:
        refuse_if(await asyncio.to_thread(network.connect, body.ssid, body.password))

    @app.post("/api/network/disconnect")
    async def disconnect_wifi() -> None:
        refuse_if(await asyncio.to_thread(network.disconnect))

    @app.post("/api/network/wifi")
    async def set_wifi(body: WifiRadioRequest) -> None:
        refuse_if(await asyncio.to_thread(network.set_wifi, body.on))

    @app.post("/api/network/hotspot")
    async def set_hotspot(body: HotspotRequest) -> None:
        refuse_if(await asyncio.to_thread(network.set_hotspot, body.on))

    @app.put("/api/network/hotspot")
    async def change_hotspot(body: HotspotDetails) -> None:
        refuse_if(await asyncio.to_thread(network.change_hotspot, body.ssid, body.password))

    @app.websocket("/api/ws")
    async def stream(socket: WebSocket) -> None:
        await socket.accept()
        last_input, next_status = handcart.inputs_since(0)[0], 0.0
        last_sound = handcart.sounds_since(0)[0]
        loop = asyncio.get_running_loop()
        try:
            while True:
                last_input, events = handcart.inputs_since(last_input)
                for event in events:
                    await socket.send_text(StreamMessage(input=event).model_dump_json())
                last_sound, sounds = handcart.sounds_since(last_sound)
                for sound in sounds:
                    await socket.send_text(StreamMessage(sound=sound).model_dump_json())
                if loop.time() >= next_status:
                    await socket.send_text(StreamMessage(status=handcart.status()).model_dump_json())
                    next_status = loop.time() + STATUS_PERIOD
                await asyncio.sleep(INPUT_POLL_PERIOD)
        except WebSocketDisconnect:
            pass

    return app


def refuse_if(problem: str | None) -> None:
    """Answer 422 with the reason, if there is one."""
    if problem:
        raise HTTPException(status_code=422, detail=problem)
