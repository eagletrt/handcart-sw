"""Hardware of the handcart PCB: relays, shutdown feedbacks, buttons and encoder, buzzer.

Two implementations: the real one on the Pi (GPIO and ADC), and FakeHal everywhere else.
"""

from enum import StrEnum
from typing import Protocol

from shared.models import InputEvent, ShutdownLoop


class Sound(StrEnum):
    STARTUP = "STARTUP"
    CONFIRM = "CONFIRM"  # a command reached the backend
    CHARGE_DONE = "CHARGE_DONE"
    ERROR = "ERROR"


class Hal(Protocol):
    def set_relays(self, sd_relay_closed: bool, charger_power: bool, discharge: bool) -> None: ...

    def shutdown_loop(self) -> ShutdownLoop:
        """Feedback voltage at each point of the shutdown loop, in loop order."""
        ...

    def input_events(self) -> list[InputEvent]:
        """Buttons pressed and encoder steps since the last call, oldest first."""
        ...

    def play(self, sound: Sound) -> None:
        """Start a sound on the buzzer, without waiting for it to end."""
        ...
