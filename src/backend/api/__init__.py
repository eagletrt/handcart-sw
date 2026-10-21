"""HTTP API of the backend, used by the frontend and by telemetry.

GET  /api/status    everything the UI shows
POST /api/command   {"command": "PRECHARGE"}: handled right away, refused with 422 and the reason
PUT  /api/settings  {"target_voltage": 590, "max_current": 6}: refused with 422 outside the limits
WS   /api/ws        {"status": ...} every STATUS_PERIOD, and {"input": "UP"} as soon as a control is used
"""

import asyncio

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect

from backend.handcart import Handcart
from shared.models import CommandRequest, Settings, Status, StreamMessage

STATUS_PERIOD = 0.2  # s
INPUT_POLL_PERIOD = 0.02  # s: button presses reach the screen this fast


def create_app(handcart: Handcart) -> FastAPI:
    # every endpoint is async: it runs in the event loop between two ticks, never in the middle of one
    app = FastAPI(title="Handcart")

    @app.get("/api/status")
    async def status() -> Status:
        return handcart.status()

    @app.post("/api/command")
    async def command(body: CommandRequest) -> None:
        refusal = handcart.request(body.command)
        if refusal:
            raise HTTPException(status_code=422, detail=refusal)

    @app.put("/api/settings")
    async def settings(body: Settings) -> Settings:
        problem = handcart.change_settings(body)
        if problem:
            raise HTTPException(status_code=422, detail=problem)
        return handcart.settings

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
