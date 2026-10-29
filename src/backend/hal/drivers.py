"""The peripherals the handcart PCB needs, as small interfaces.

On the Pi they are implemented in hal/rpi.py; in the tests by simple fakes. Everything else in hal/
works on these, so it runs and is tested without the hardware.
"""

from typing import Protocol


class Gpio(Protocol):
    def write(self, pin: int, high: bool) -> None: ...

    def read(self, pin: int) -> bool:
        """True if the pin is high."""


class Pwm(Protocol):
    def tone(self, frequency: float | None) -> None:
        """Play a square wave at this frequency, or be silent with None."""


class SilentPwm:
    """A buzzer that plays nothing: on the Pi when pigpiod is not running."""

    def tone(self, frequency: float | None) -> None:
        pass


class EncoderPins(Protocol):
    """The encoder's two outputs, A and B."""

    def levels(self) -> tuple[bool, bool]:
        """A and B now, high or not."""

    def changes(self) -> list[tuple[bool, bool]]:
        """Each change of A or B since the last call, oldest first: (it is A, high now)."""


class PolledEncoderPins:
    """A and B read at each tick: on the Pi when pigpiod is not running, and in the tests.

    A fast turn can change them faster than the ticks come: then steps are lost or go the wrong way.
    """

    def __init__(self, gpio: Gpio, a: int, b: int) -> None:
        self._gpio = gpio
        self._a, self._b = a, b
        self._last = self.levels()

    def levels(self) -> tuple[bool, bool]:
        return self._gpio.read(self._a), self._gpio.read(self._b)

    def changes(self) -> list[tuple[bool, bool]]:
        a, b = self.levels()
        last_a, last_b = self._last
        self._last = (a, b)
        changes = []
        if a != last_a:
            changes.append((True, a))
        if b != last_b:
            changes.append((False, b))
        return changes


class Spi(Protocol):
    def transfer(self, data: bytes) -> bytes:
        """Send data and return what came back, byte for byte."""
