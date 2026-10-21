"""The handcart's physical controls: what each gesture does where the operator is.

Plain logic, no UI (tests/test_controls.py). At every gesture the page describes where the controls are
(a Context); a yellow frame marks the button they act on, a yellow cursor the cell of the map. The rules:

- left/right change screen; inside a window or the map they move instead;
- up/down (and turning, where it has nothing else to do) move the frame over the screen's buttons;
  the click presses the framed button;
- the first gesture after a pause only shows the frame, on the button with the highest priority
  (STOP while something runs, else the main action; the safe choice inside a window);
- Charge: turning drafts a new target voltage (shown on the rail, nothing changes yet);
  a click sets it, any arrow cancels it, and so does a pause;
- Cells: a click, a touch on a cell, or pressing Volts or Temps with the controls puts the cursor on the map:
  the arrows move it across the grid, turning moves it cell after cell, a click takes it away;
- in a window turning moves the frame, or changes the framed setting;
- fast turns step a value FAST_FACTOR times more;
- the frame and a draft go away after IDLE_TIME without gestures, or when the screen is touched;
  the cursor stays until a click, a switch of volts and temps, or another screen.
"""

from dataclasses import dataclass, field
from enum import StrEnum

from shared.models import InputEvent

IDLE_TIME = 10.0  # s
FAST_TURN = 0.06  # s: two encoder steps closer than this are a fast turn
FAST_FACTOR = 5

STEPS = {
    InputEvent.TURN_CW: 1,
    InputEvent.DOWN: 1,
    InputEvent.RIGHT: 1,
    InputEvent.TURN_CCW: -1,
    InputEvent.UP: -1,
    InputEvent.LEFT: -1,
}
TURNS = (InputEvent.TURN_CW, InputEvent.TURN_CCW)


class Turn(StrEnum):
    """What turning the encoder does on a screen."""

    DRAFT_TARGET = "DRAFT_TARGET"  # Charge


@dataclass(frozen=True)
class Target:
    """Something the frame can mark: a button, or a setting of a window."""

    key: str  # names it, e.g. "stop", "target_voltage"
    priority: int = 0  # where the frame starts: the highest wins
    adjusts: str | None = None  # a setting: turning changes it
    presses: str | None = None  # a click on it presses this button instead (a setting: "save")
    opens_map: bool = False  # after the click, the cursor goes on the map (Volts, Temps)


# what the page must do after a gesture, besides drawing the frame and the cursor


@dataclass(frozen=True)
class Press:
    key: str
    opens_map: bool = False  # then put the cursor on the map, at its start


@dataclass(frozen=True)
class SwitchScreen:
    step: int  # +1 the next screen, -1 the previous one


@dataclass(frozen=True)
class Adjust:
    setting: str
    steps: int  # knob steps, signed


@dataclass(frozen=True)
class DraftTarget:
    steps: int  # knob steps to add to the draft, signed


@dataclass(frozen=True)
class ConfirmTarget:
    pass


@dataclass(frozen=True)
class CancelTarget:
    pass


Effect = Press | SwitchScreen | Adjust | DraftTarget | ConfirmTarget | CancelTarget | None


@dataclass(frozen=True)
class Context:
    """Where the controls are, as the page shows it now."""

    targets: list[Target] = field(default_factory=list)  # in reading order
    window_open: bool = False
    turn: Turn | None = None
    map_name: str | None = None  # the map shown, if any: "volts" or "temps"
    map_size: tuple[int, int] = (0, 0)  # its (rows, squares per row)
    map_start: int = 0  # where the cursor starts: the highest cell, the hottest probe


class Controls:
    def __init__(self) -> None:
        self.framed: str | None = None  # the key of the framed target
        self.cursor: int | None = None  # the square of the map under the cursor
        self.drafting = False  # a new target voltage is being drafted on Charge
        self._cursor_map: str | None = None  # the map the cursor is on
        self._last_gesture = float("-inf")
        self._last_turn = float("-inf")

    def handle(self, event: InputEvent, context: Context, now: float) -> Effect:
        """One gesture of the controls."""
        self.expire(now)
        self._last_gesture = now
        steps = STEPS.get(event, 0)
        if event in TURNS:
            if now - self._last_turn < FAST_TURN:
                steps *= FAST_FACTOR
            self._last_turn = now

        if self.drafting:
            return self._drafting(event, steps)
        if self._on_map(context):
            self._in_map(event, context.map_size)
            return None
        if context.window_open:
            return self._in_window(event, context.targets, steps)
        return self._on_screen(event, context, steps)

    def touch_map(self, square: int, context: Context) -> None:
        """A touch on a square of the map: the cursor goes there, ready to be moved."""
        self.framed = None
        self.cursor = square
        self._cursor_map = context.map_name

    def follow(self, context: Context, now: float) -> None:
        """Called at every refresh: what the frame or the cursor marked may be gone."""
        self.expire(now)
        if self.framed not in [target.key for target in context.targets]:
            self.framed = None
        if self.cursor is not None and not self._on_map(context):
            self.cursor = None  # another screen, a window, or volts switched to temps

    def expire(self, now: float) -> None:
        """After a pause: no frame, no draft (the cursor stays)."""
        if now - self._last_gesture > IDLE_TIME:
            self.clear()

    def clear(self) -> None:
        """No frame, no draft: after a pause, or a touch outside the map."""
        self.framed = None
        self.drafting = False

    # where the controls are

    def _on_map(self, context: Context) -> bool:
        return (
            self.cursor is not None
            and not context.window_open
            and context.map_name is not None
            and context.map_name == self._cursor_map
        )

    def _on_screen(self, event: InputEvent, context: Context, steps: int) -> Effect:
        framed = self._framed(context.targets)
        if event in (InputEvent.LEFT, InputEvent.RIGHT):
            self.clear()
            return SwitchScreen(steps)
        if event in TURNS and context.turn is Turn.DRAFT_TARGET:
            self.framed = None
            self.drafting = True
            return DraftTarget(steps)
        if event is InputEvent.PRESS and framed is not None:
            return Press(framed.key, framed.opens_map)
        if event is InputEvent.PRESS and context.map_name is not None:
            self.touch_map(context.map_start, context)  # onto the map
            return None
        if framed is None:
            self._start(context.targets)  # the first gesture only shows where the controls are
            return None
        direction = 1 if steps > 0 else -1  # up, down, or a turn: one button at a time
        self._move(context.targets, framed, direction)
        return None

    def _drafting(self, event: InputEvent, steps: int) -> Effect:
        if event in TURNS:
            return DraftTarget(steps)
        self.drafting = False
        if event is InputEvent.PRESS:
            return ConfirmTarget()
        return CancelTarget()  # any arrow

    def _in_window(self, event: InputEvent, targets: list[Target], steps: int) -> Effect:
        framed = self._framed(targets)
        if framed is None:
            self._start(targets)
            return None
        if event is InputEvent.PRESS:
            return Press(framed.presses or framed.key)
        if event in TURNS and framed.adjusts is not None:
            return Adjust(framed.adjusts, steps)
        direction = 1 if steps > 0 else -1  # a fast turn still moves the frame one button
        self._move(targets, framed, direction)
        return None

    def _in_map(self, event: InputEvent, size: tuple[int, int]) -> None:
        """The cursor stops at the edges: in a grid that is what one expects."""
        assert self.cursor is not None
        rows, per_row = size
        row, column = divmod(self.cursor, per_row)
        step = STEPS.get(event, 0)
        if event is InputEvent.PRESS:
            self.cursor = None  # off the map
        elif event in TURNS:
            self.cursor = max(0, min(rows * per_row - 1, self.cursor + step))
        elif event in (InputEvent.LEFT, InputEvent.RIGHT):
            self.cursor = row * per_row + max(0, min(per_row - 1, column + step))
        else:
            self.cursor = max(0, min(rows - 1, row + step)) * per_row + column

    # the frame

    def _framed(self, targets: list[Target]) -> Target | None:
        for target in targets:
            if target.key == self.framed:
                return target
        return None

    def _start(self, targets: list[Target]) -> None:
        best = None
        for target in targets:
            if best is None or target.priority > best.priority:
                best = target
        self.framed = best.key if best is not None else None

    def _move(self, targets: list[Target], framed: Target, step: int) -> None:
        position = (targets.index(framed) + step) % len(targets)
        self.framed = targets[position].key
