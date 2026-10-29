"""Hardware of the handcart PCB: relays, shutdown feedbacks, buttons and encoder, buzzer.

Two implementations of Hal:
- BoardHal (board.py): the PCB through its peripherals. Its logic (relays.py, controls.py, feedback.py)
  only sees pin levels and bytes, so it is tested without hardware; on the Pi it gets the real drivers
  (rpi.py).
- FakeHal (fake.py): a whole board in software, to run the backend with the simulator.

The buzzer only plays a frequency here: which sound, and when, is backend/sounds.
"""

from typing import Protocol

from shared.models import InputEvent, ShutdownLoop


class Hal(Protocol):
    def poll(self, now: float) -> None:
        """Read the controls and the feedbacks. Called once per tick."""
        ...

    def set_relays(self, sd_relay_closed: bool, charger_power: bool, discharge: bool) -> None: ...

    def shutdown_loop(self) -> ShutdownLoop:
        """Feedback voltage at each point of the shutdown loop, in loop order."""
        ...

    def input_events(self) -> list[InputEvent]:
        """Buttons pressed and encoder steps since the last call, oldest first."""
        ...

    def set_buzzer(self, frequency: float | None) -> None:
        """Play a square wave at this frequency on the buzzer, or be silent with None."""
        ...
