"""The frontend's connection to the backend: the latest status, the control presses, and the requests."""

import asyncio
import logging
from collections.abc import Callable

import httpx
import websockets
from pydantic import TypeAdapter

from shared.models import (
    BmsSnapshot,
    ChargerSnapshot,
    Command,
    InputEvent,
    NetworkInfo,
    Sample,
    Settings,
    Sound,
    Status,
    StreamMessage,
    SystemInfo,
)

log = logging.getLogger(__name__)

RECONNECT_DELAY = 1.0  # s
SYSTEM_PERIOD = 10.0  # s between two reads of /api/system and /api/network (updates, IP address)
WIFI_TIMEOUT = 40  # s: the backend waits up to 20 s for a scan or a connection, plus the reading after
UNREACHABLE = "The backend is not reachable"
SAMPLES_TIMEOUT = 10  # s: hours of samples from the SD card
SAMPLES = TypeAdapter(list[Sample])

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
        self.system: SystemInfo | None = None  # version and updates; None until read
        self.network: NetworkInfo | None = None  # addresses and Wi-Fi networks; None until read
        self._listeners: list[Callable[[InputEvent], None]] = []
        self._sound_listeners: list[Callable[[Sound], None]] = []

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

    async def follow_system(self) -> None:
        """Read /api/system and /api/network for ever, so the UI knows about updates and addresses."""
        while True:
            await self.read_system()
            await self.read_network()
            await asyncio.sleep(SYSTEM_PERIOD)

    async def read_system(self) -> None:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"http://{self._address}/api/system")
        except httpx.HTTPError:
            return  # keep the last one: the backend is restarting, or not there
        if response.status_code == 200:
            self.system = SystemInfo.model_validate_json(response.text)

    async def read_network(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=WIFI_TIMEOUT) as client:
                response = await client.get(f"http://{self._address}/api/network")
        except httpx.HTTPError:
            return  # keep the last one: the backend is restarting, or not there
        if response.status_code == 200:
            self.network = NetworkInfo.model_validate_json(response.text)

    async def read_samples(self, since: float) -> list[Sample] | None:
        """The record's samples from `since` (s since 1970), oldest first; None if no answer."""
        try:
            async with httpx.AsyncClient(timeout=SAMPLES_TIMEOUT) as client:
                response = await client.get(f"http://{self._address}/api/samples", params={"since": since})
        except httpx.HTTPError:
            return None
        if response.status_code != 200:
            return None
        return SAMPLES.validate_json(response.text)

    def on_input(self, listener: Callable[[InputEvent], None]) -> Callable[[], None]:
        """Call listener for every press of the physical controls. Returns a function that stops it."""
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    def on_sound(self, listener: Callable[[Sound], None]) -> Callable[[], None]:
        """Call listener for every sound the buzzer starts. Returns a function that stops it."""
        self._sound_listeners.append(listener)
        return lambda: self._sound_listeners.remove(listener)

    async def command(self, command: Command) -> str | None:
        """Returns why the backend refused the command, or None."""
        return await self._request("POST", "/api/command", {"command": command.value})

    async def change_settings(self, settings: Settings) -> str | None:
        """Returns why the backend refused the settings, or None."""
        return await self._request("PUT", "/api/settings", settings.model_dump())

    async def check_updates(self) -> str | None:
        """Look for updates now. Returns why it could not, or None; the result is in self.system."""
        problem = await self._request("POST", "/api/system/check", timeout=30)
        await self.read_system()
        return problem

    async def scan_wifi(self) -> str | None:
        """Look for Wi-Fi networks again. Returns why it could not, or None; the result is in self.network."""
        problem = await self._request("POST", "/api/network/scan", timeout=WIFI_TIMEOUT)
        await self.read_network()
        return problem

    async def connect_wifi(self, ssid: str, password: str | None) -> str | None:
        """Join a Wi-Fi network; password None for a saved or open one. Returns why it could not, or None."""
        body = {"ssid": ssid, "password": password}
        problem = await self._request("POST", "/api/network/connect", body, timeout=WIFI_TIMEOUT)
        await self.read_network()
        return problem

    async def disconnect_wifi(self) -> str | None:
        problem = await self._request("POST", "/api/network/disconnect", timeout=WIFI_TIMEOUT)
        await self.read_network()
        return problem

    async def set_wifi(self, on: bool) -> str | None:
        """Turn the Wi-Fi radio on or off. Returns why it could not, or None."""
        problem = await self._request("POST", "/api/network/wifi", {"on": on}, timeout=WIFI_TIMEOUT)
        await self.read_network()
        return problem

    async def set_hotspot(self, on: bool) -> str | None:
        """Turn the hotspot on or off. Returns why it could not, or None."""
        problem = await self._request("POST", "/api/network/hotspot", {"on": on}, timeout=WIFI_TIMEOUT)
        await self.read_network()
        return problem

    async def change_hotspot(self, ssid: str, password: str) -> str | None:
        """A new name and password for the hotspot. Returns why it could not, or None."""
        body = {"ssid": ssid, "password": password}
        problem = await self._request("PUT", "/api/network/hotspot", body, timeout=WIFI_TIMEOUT)
        await self.read_network()
        return problem

    async def hush(self) -> None:
        """The operator touched the screen: stop the tune of a job done."""
        await self._request("POST", "/api/buzzer/hush")

    async def update(self) -> str | None:
        return await self._request("POST", "/api/system/update")

    async def reboot(self) -> str | None:
        return await self._request("POST", "/api/system/reboot")

    async def shut_down(self) -> str | None:
        return await self._request("POST", "/api/system/shutdown")

    async def _request(
        self, method: str, path: str, body: dict | None = None, timeout: float = 5
    ) -> str | None:
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
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
        if message.sound is not None:
            for sound_listener in list(self._sound_listeners):
                sound_listener(message.sound)
