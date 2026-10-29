"""The physical controls, from pin levels to InputEvents: four buttons and a rotary encoder.

The buttons are polled every tick: a press lasts far longer. The encoder works on each change of its two
outputs, timed by pigpiod as it happens (hal/rpi.py): a fast turn changes them faster than the ticks come.
"""

from dataclasses import dataclass

from shared.models import InputEvent

DEBOUNCE = 0.02  # s a button must stay at a level before it counts
# the levels of the encoder's (A, B) through one click of the knob clockwise: A goes up first
CLOCKWISE = [(False, False), (True, False), (True, True), (False, True)]


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
    """Rotary encoder with two outputs, A and B: each click of the knob takes them once round CLOCKWISE.

    The step counts when the knob is back at rest (the levels it had at the start), after most of the cycle
    in one direction: a bouncing contact goes forth and back and counts nothing.
    """

    def __init__(self, a: bool, b: bool) -> None:
        self._rest = (a, b)
        self._levels = (a, b)
        self._moved = 0  # quarters of a cycle since the rest, clockwise positive

    def change(self, is_a: bool, high: bool) -> list[InputEvent]:
        """A or B changed level: the step, if this ends one."""
        a, b = self._levels
        levels = (high, b) if is_a else (a, high)
        if levels == self._levels:
            return []  # the same level again: nothing moved
        if CLOCKWISE.index(levels) == (CLOCKWISE.index(self._levels) + 1) % len(CLOCKWISE):
            self._moved += 1
        else:
            self._moved -= 1  # one output changes at a time: if not forward, back
        self._levels = levels
        if levels != self._rest:
            return []
        moved, self._moved = self._moved, 0
        if moved >= 3:  # 4 in a clean click; 3 if an edge went missing
            return [InputEvent.TURN_CW]
        if moved <= -3:
            return [InputEvent.TURN_CCW]
        return []
