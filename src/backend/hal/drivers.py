"""The three peripherals the handcart PCB needs, as small interfaces.

On the Pi they are implemented in hal/rpi.py; in the tests by simple fakes. Everything else in hal/
works on these, so it runs and is tested without the hardware.
"""

from typing import Protocol


class Gpio(Protocol):
    def write(self, pin: int, high: bool) -> None: ...

    def read(self, pin: int) -> bool:
        """True if the pin is high."""
        ...


class Pwm(Protocol):
    def tone(self, frequency: float | None) -> None:
        """Play a square wave at this frequency, or be silent with None."""
        ...


class Spi(Protocol):
    def transfer(self, data: bytes) -> bytes:
        """Send data and return what came back, byte for byte."""
        ...
