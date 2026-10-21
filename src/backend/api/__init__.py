"""HTTP API of the backend, used by the frontend and by telemetry.

GET  /api/status    everything the UI shows
POST /api/command   {"command": "PRECHARGE"}: handled right away, refused with 422 and the reason
PUT  /api/settings  {"target_voltage": 590, "max_current": 6}: refused with 422 outside the limits
WS   /api/ws        {"status": ...} every STATUS_PERIOD, and {"input": "UP"} as soon as a control is used

GET  /api/system           version, updates on the branch, last update
POST /api/system/check     look for updates now (a few seconds)
POST /api/system/update    start ./handcart.py update: the backend restarts
POST /api/system/reboot
POST /api/system/shutdown  the last three only with the TS off and nothing running, else 422 and the reason
"""

import asyncio

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect

from backend.handcart import Handcart
from backend.system import System
from shared.models import CommandRequest, Settings, Status, StreamMessage, SystemInfo

STATUS_PERIOD = 0.2  # s
INPUT_POLL_PERIOD = 0.02  # s: button presses reach the screen this fast


def create_app(handcart: Handcart, system: System) -> FastAPI:
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

    @app.post("/api/system/reboot", status_code=202)
    async def reboot() -> None:
        refuse_if(handcart.maintenance_problem() or system.reboot())

    @app.post("/api/system/shutdown", status_code=202)
    async def shut_down() -> None:
        refuse_if(handcart.maintenance_problem() or system.shut_down())

    @app.websocket("/api/ws")
    async def stream(socket: WebSocket) -> None:
        await socket.accept()
        last_input, next_status = handcart.inputs_since(0)[0], 0.0
        loop = asyncio.get_running_loop()
        try:
            while True:
                last_input, events = handcart.inputs_since(last_input)
                for event in events:
                    await socket.send_text(StreamMessage(input=event).model_dump_json())
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
