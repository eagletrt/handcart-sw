"""The safe in front of the Debug window: five taps on the eagle bring it up.

Its dial turns with the encoder of the handcart, or with a finger on it (handcart.js); the combination
is in safe.py. While the safe is up it takes every gesture of the controls: turning turns the dial, the
click pulls the handle, left closes it. With the right combination the handle turns, the bolts go in,
the door swings open and the Debug window comes out of the safe; with a wrong one the door shakes
and the dial starts over.
"""

import asyncio
from collections.abc import Callable

from nicegui import background_tasks, ui

from frontend.backend import Backend
from frontend.safe import NUMBERS, RIGHT, Dial
from frontend.targets import Reachable
from shared.models import InputEvent, Sound

OPEN_TIME = 2.2  # s: the handle, the bolts, the door and the fade (handcart.css), then the Debug window
HINT = "Turn right to the first number, left to the second, right to the third, then pull the handle."
GRIPS = 36  # ridges around the knob


def dial_face() -> str:
    """The dial: a tick and a number for each step, longer and brighter every five."""
    parts = [
        # a size of its own: without the CSS (an old copy in the browser) it would fill the screen
        '<svg viewBox="-100 -100 200 200" width="214" height="214" class="dial-face">',
        '<circle r="98" class="rim"/>',
        '<circle r="91" class="disc"/>',
    ]
    for n in range(NUMBERS):
        angle = -n * 360 / NUMBERS  # counterclockwise: turning right brings the next number under the mark
        if n % 5 == 0:
            parts.append(f'<line y1="-89" y2="-75" transform="rotate({angle})" class="tk long"/>')
            parts.append(f'<text y="-60" transform="rotate({angle})" class="nb long">{n}</text>')
        else:
            parts.append(f'<line y1="-89" y2="-80" transform="rotate({angle})" class="tk"/>')
            parts.append(f'<text y="-62" transform="rotate({angle})" class="nb">{n}</text>')
    parts.append('<circle r="40" class="knob"/>')
    for i in range(GRIPS):
        parts.append(f'<line y1="-40" y2="-34" transform="rotate({i * 360 / GRIPS})" class="grip"/>')
    parts.append('<circle r="30" class="knob-top"/><line y1="-28" y2="-16" class="knob-mark"/></svg>')
    return "".join(parts)


class SafeWindow:
    def __init__(self, backend: Backend, on_open: Callable[[], None]) -> None:
        self._backend = backend
        self._on_open = on_open  # the right combination: what is behind the door
        self._client = ui.context.client
        self._dial = Dial()
        self._opening = False  # the door is opening: the dial and the handle wait

        # built when it opens and emptied when it closes: the browser redraws every element of the page at
        # each change, hidden ones too. Built once here, so that every attribute exists before it opens.
        self.root = ui.element("div").classes("modal")
        with self.root:
            self._build()
        self.close()

    def _build(self) -> None:
        with ui.element("div").classes("sheet safe") as self._sheet:
            with ui.element("div").classes("vault"):
                with ui.element("div").classes("inside"):
                    ui.element("div").classes("eagle")
                    ui.label("Debug")
                with ui.element("div").classes("door") as self._door:
                    for row in ("b1", "b2", "b3"):
                        ui.element("div").classes(f"bolt {row}")
                    with ui.element("div").classes("dialwrap") as self._dial_area:
                        # the face is sent once; each step only turns the div around it (a few bytes, and
                        # the Pi's browser does not rebuild the face)
                        with ui.element("div").classes("dial") as self._face:
                            ui.html(dial_face())
                        ui.element("div").classes("dmark")
                    with ui.element("div").classes("handle"):
                        ui.element("div").classes("hbar")
                        ui.element("div").classes("hhub")
            with ui.element("div").classes("sright"):
                ui.label("Debug").classes("sheet-title")
                ui.label(HINT).classes("sheet-sub")
                self._number = ui.label("0").classes("snum num")
                with ui.element("div").classes("slots"):
                    self._slots = [ui.label("").classes("slot num") for _ in range(3)]
                with ui.element("div").classes("sheet-actions"):
                    self._close = ui.button("Close", on_click=self.close)
                    self._close.props("flat no-caps text-color=white").classes("cancel")
                    self._pull = ui.button("Pull the handle", icon="lock_open", on_click=self._on_pull)
                    self._pull.props("unelevated no-caps text-color=black")
        # a finger on the dial turns it, measured in the browser (handcart.js)
        for kind in ("pointerdown", "pointermove", "pointerup", "pointercancel"):
            self._dial_area.on(
                kind,
                lambda event: self._on_finger(int(event.args)),
                js_handler="(e) => dialFinger(e, emit)",
            )

    def close(self) -> None:
        self.root.set_visibility(False)
        self.root.clear()

    def reachable(self) -> list[Reachable]:
        return []  # no frame: the safe takes every gesture itself (on_gesture)

    def open(self) -> None:
        """Locked, the dial at 0: a new door, closed."""
        self.root.clear()
        with self.root:
            self._build()
        self._dial = Dial()
        self._opening = False
        self._draw()
        self.root.set_visibility(True)

    def on_gesture(self, event: InputEvent) -> None:
        """The controls, while the safe is up: the buzzer ticks by itself at each step of the encoder."""
        if event is InputEvent.TURN_CW:
            self._turn(1)
        elif event is InputEvent.TURN_CCW:
            self._turn(-1)
        elif event is InputEvent.PRESS:
            background_tasks.create(self._on_pull())
        elif event is InputEvent.LEFT and not self._opening:
            self.close()

    def _on_finger(self, steps: int) -> None:
        """A finger turned the dial: the buzzer ticks as for the encoder."""
        if steps != 0 and not self._opening:
            self._turn(steps)
            background_tasks.create(self._backend.play(Sound.TICK))

    def _turn(self, steps: int) -> None:
        if not self._opening:
            self._dial.turn(steps)
            self._draw()

    async def _on_pull(self) -> None:
        if self._opening:
            return
        if not self._dial.pull():
            self._draw()
            self._client.run_javascript(f"replay({self._door.id}, 'shake')")
            await self._backend.play(Sound.REFUSED)
            return
        self._opening = True
        self._sheet.classes(add="open")
        await self._backend.play(Sound.CONFIRM)
        await asyncio.sleep(OPEN_TIME)
        if self.root.visible:  # not closed meanwhile
            self.close()
            self._on_open()

    def _draw(self) -> None:
        # the whole turns, not the number: past 19 the dial goes on to 0 instead of spinning back
        self._face.style(f"transform: rotate({self._dial.position * 360 / NUMBERS}deg)")
        self._number.set_text(str(self._dial.number))
        for i, slot in enumerate(self._slots):
            if i < len(self._dial.turns):
                direction, number = self._dial.turns[i]
                side = "Right" if direction == RIGHT else "Left"
                slot.set_text(f"{side} {number}")
                slot.classes(add="filled")
            else:
                slot.set_text("–")
                slot.classes(remove="filled")
