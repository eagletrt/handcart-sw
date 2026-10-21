"""The frontend's connection to the backend: the latest status, the control presses, and the requests."""

import asyncio
import logging
from collections.abc import Callable

import httpx
import websockets

from shared.models import BmsSnapshot, ChargerSnapshot, Command, InputEvent, Settings, Status, StreamMessage

log = logging.getLogger(__name__)

RECONNECT_DELAY = 1.0  # s
UNREACHABLE = "The backend is not reachable"

# what the screen shows for a device that stopped talking: its last readings are no longer true
NO_BMS = BmsSnapshot(
    connected=False,
    state=None,
    ts_voltage=None,
    pack_voltage=None,
    cell_min=None,
    cell_max=None,
    cell_average=None,
    current=None,
    power=None,
    temp_min=None,
    temp_max=None,
    temp_average=None,
    ts_below_60v=None,
    cells=(),
    temps=(),
    balancing=(),
    errors=frozenset(),
)
NO_CHARGER = ChargerSnapshot(
    connected=False,
    state=None,
    voltage=None,
    current=None,
    grid_voltages=(None, None, None),
    max_temperature=None,
    errors=frozenset(),
    warnings=frozenset(),
)


class Backend:
    def __init__(self, address: str) -> None:
        self._address = address  # host:port
        self.status: Status | None = None  # as the screen shows it; None while the backend is not reachable
        self._listeners: list[Callable[[InputEvent], None]] = []

    async def run(self) -> None:
        """Follow /api/ws for ever, reconnecting when the backend restarts."""
        while True:
            try:
                async with websockets.connect(f"ws://{self._address}/api/ws") as socket:
                    log.info("connected to the backend")
                    async for text in socket:
                        self._receive(StreamMessage.model_validate_json(text))
            except (OSError, websockets.ConnectionClosed):
                pass
            if self.status is not None:
                log.warning("lost the backend, retrying")
            self.status = None
            await asyncio.sleep(RECONNECT_DELAY)

    def on_input(self, listener: Callable[[InputEvent], None]) -> Callable[[], None]:
        """Call listener for every press of the physical controls. Returns a function that stops it."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    async def command(self, command: Command) -> str | None:
        """Returns why the backend refused the command, or None."""
        return await self._request("POST", "/api/command", {"command": command.value})

    async def change_settings(self, settings: Settings) -> str | None:
        """Returns why the backend refused the settings, or None."""
        return await self._request("PUT", "/api/settings", settings.model_dump())

    async def _request(self, method: str, path: str, body: dict) -> str | None:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(method, f"http://{self._address}{path}", json=body)
        except httpx.HTTPError:
            return UNREACHABLE
        if response.status_code == 422:
            return response.json()["detail"]
        return None

    def _receive(self, message: StreamMessage) -> None:
        if message.status is not None:
            self.status = message.status
            if not self.status.bms.connected:
                self.status = self.status.model_copy(update={"bms": NO_BMS})
            if not self.status.charger.connected:
                self.status = self.status.model_copy(update={"charger": NO_CHARGER})
        if message.input is not None:
            for listener in list(self._listeners):
                listener(message.input)
