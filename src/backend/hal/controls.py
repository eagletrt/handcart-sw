"""The physical controls, from pin levels to InputEvents: four buttons and a rotary encoder.

Both are polled every tick; the encoder knob is turned by hand, so a few milliseconds are fast enough.
"""

from dataclasses import dataclass

from shared.models import InputEvent

DEBOUNCE = 0.02  # s a button must stay at a level before it counts


@dataclass
class _Button:
    event: InputEvent
    pressed: bool = False  # the state we report, after the debounce
    reading: bool = False  # the latest raw reading
    reading_since: float = 0.0  # when the raw reading last changed


class Buttons:
    """Buttons wired to ground with the internal pull-up: low while pressed."""

    def __init__(self, events_by_pin: dict[int, InputEvent]) -> None:
        self.pins = list(events_by_pin)
        self._buttons = {pin: _Button(event) for pin, event in events_by_pin.items()}

    def update(self, now: float, levels: dict[int, bool]) -> list[InputEvent]:
        """Events for the buttons that went down, once their level has been stable for DEBOUNCE."""
        events = []
        for pin, button in self._buttons.items():
            reading = not levels[pin]  # low means pressed
            if reading != button.reading:
                button.reading, button.reading_since = reading, now
                continue
            stable = now - button.reading_since >= DEBOUNCE
            if stable and reading != button.pressed:
                button.pressed = reading
                if button.pressed:
                    events.append(button.event)
        return events


class Encoder:
    """Rotary encoder with two outputs, A and B. One step per rising edge of B; A gives the direction."""

    def __init__(self) -> None:
        self._last_b: bool | None = None  # unknown until the first reading

    def update(self, a: bool, b: bool) -> list[InputEvent]:
        rising = b and self._last_b is False  # the first reading only sets the starting level
        self._last_b = b
        if not rising:
            return []
        return [InputEvent.TURN_CW if a else InputEvent.TURN_CCW]
