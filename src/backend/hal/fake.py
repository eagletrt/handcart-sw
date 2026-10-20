"""Hardware stand-in for running the backend off the Pi.

It remembers the relays and the sounds, reports a closed loop, and lets a test press buttons.
"""

from backend.hal import Sound
from backend.hal.feedback import LOOP_CHANNELS
from shared.models import InputEvent, ShutdownLoop

LOOP_POINTS = tuple(LOOP_CHANNELS.values())
LOOP_VOLTAGE = 12.0  # V on a closed loop


class FakeHal:
    def __init__(self) -> None:
        self.sd_relay_closed = False
        self.charger_power = False
        self.discharge = True
        self.open_at: str | None = None  # set to one of LOOP_POINTS to simulate an open loop
        self.played: list[Sound] = []
        self._pressed: list[InputEvent] = []

    def poll(self, now: float) -> None:
        pass

    def set_relays(self, sd_relay_closed: bool, charger_power: bool, discharge: bool) -> None:
        self.sd_relay_closed = sd_relay_closed
        self.charger_power = charger_power
        self.discharge = discharge

    def shutdown_loop(self) -> ShutdownLoop:
        """12 V at every point up to an open one, 0 V after it; all 0 V with the SD relay open."""
        powered = self.sd_relay_closed
        loop = []
        for point in LOOP_POINTS:
            powered = powered and point != self.open_at
            loop.append((point, LOOP_VOLTAGE if powered else 0.0))
        return tuple(loop)

    def press(self, event: InputEvent) -> None:
        """Simulate a button press or an encoder step."""
        self._pressed.append(event)

    def input_events(self) -> list[InputEvent]:
        events, self._pressed = self._pressed, []
        return events

    def play(self, sound: Sound) -> None:
        self.played.append(sound)
