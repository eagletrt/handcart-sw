"""The safe in front of the Debug window: five taps on the eagle bring it up.

Its dial turns with the encoder of the handcart, or with a finger on it (handcart.js); the combination
is in safe.py. With the right one the handle turns, the bolts go in and the door swings open on the
Debug window; with a wrong one the door shakes and the dial starts over.
"""

import asyncio
from collections.abc import Callable

from nicegui import background_tasks, ui

from frontend.backend import Backend
from frontend.controls import Target
from frontend.safe import NUMBERS, RIGHT, Dial
from frontend.targets import Reachable, button, usable
from shared.models import Sound

DIAL = "safe dial"  # the setting the encoder turns when the frame is on the dial
OPEN_TIME = 1.9  # s: the handle, the bolts and the door (handcart.css), then the Debug window
HINT = "Right to the first number, left to the second, right to the third. Then pull the handle."


def dial_face() -> str:
    """The dial: a tick for each number, a longer one with the number every five."""
    parts = [
        '<svg viewBox="-100 -100 200 200" class="dial-face">',
        '<circle r="97" class="rim"/>',
        '<circle r="90" class="disc"/>',
    ]
    for n in range(NUMBERS):
        angle = -n * 360 / NUMBERS  # counterclockwise: turning right brings the next number under the mark
        if n % 5 == 0:
            parts.append(f'<line y1="-88" y2="-76" transform="rotate({angle})" class="tk long"/>')
            parts.append(f'<text y="-58" transform="rotate({angle})" class="nb">{n}</text>')
        else:
            parts.append(f'<line y1="-88" y2="-81" transform="rotate({angle})" class="tk"/>')
    parts.append('<circle r="34" class="knob"/><circle r="26" class="knob-top"/></svg>')
    return "".join(parts)


class SafeWindow:
    def __init__(self, backend: Backend, on_open: Callable[[], None]) -> None:
        self._backend = backend
        self._on_open = on_open  # the right combination: what is behind the door
        self._client = ui.context.client
        self._dial = Dial()
        self._opening = False  # the door is opening: the dial and the handle wait

        with ui.element("div").classes("modal") as self.root, ui.element("div").classes("sheet safe"):
            with ui.element("div").classes("vault") as self._vault:
                with ui.element("div").classes("inside"):
                    ui.element("div").classes("eagle")
                    ui.label("Debug")
                with ui.element("div").classes("door") as self._door:
                    for row in ("b1", "b2", "b3"):
                        ui.element("div").classes(f"bolt {row}")
                    with ui.element("div").classes("dialwrap") as self._dial_area:
                        self._face = ui.html(dial_face()).classes("dial")
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
                    self._close = ui.button("Close", on_click=lambda: self.root.set_visibility(False))
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
        self.root.set_visibility(False)

    def reachable(self) -> list[Reachable]:
        # on the dial the encoder turns it, and a click pulls the handle
        target = Target("dial", priority=1, adjusts=DIAL, presses="pull")
        dial = Reachable(target, self._dial_area, lambda: None)
        return [dial, *usable(button("close", self._close), button("pull", self._pull))]

    def open(self) -> None:
        """Locked, the dial at 0."""
        self._dial = Dial()
        self._opening = False
        self._vault.classes(remove="open")
        self._draw()
        self.root.set_visibility(True)

    def turn(self, steps: int) -> None:
        """The encoder on the dial (the buzzer ticks by itself at each step)."""
        if not self._opening:
            self._dial.turn(steps)
            self._draw()

    def _on_finger(self, steps: int) -> None:
        """A finger turned the dial: the buzzer ticks as for the encoder."""
        if steps != 0 and not self._opening:
            self.turn(steps)
            background_tasks.create(self._backend.play(Sound.TICK))

    async def _on_pull(self) -> None:
        if self._opening:
            return
        if not self._dial.pull():
            self._draw()
            self._client.run_javascript(f"replay({self._door.id}, 'shake')")
            await self._backend.play(Sound.REFUSED)
            return
        self._opening = True
        self._vault.classes(add="open")
        await self._backend.play(Sound.CONFIRM)
        await asyncio.sleep(OPEN_TIME)
        if self.root.visible:  # not closed meanwhile
            self.root.set_visibility(False)
            self._on_open()

    def _draw(self) -> None:
        # the whole turns, not the number: past 19 the dial goes on to 0 instead of spinning back
        self._face.style(f"transform: rotate({self._dial.position * 360 / NUMBERS}deg)")
        self._number.set_text(str(self._dial.number))
        for i, slot in enumerate(self._slots):
            if i < len(self._dial.turns):
                direction, number = self._dial.turns[i]
                arrow = "↻" if direction == RIGHT else "↺"
                slot.set_text(f"{arrow} {number}")
                slot.classes(add="set")
            else:
                slot.set_text("–")
                slot.classes(remove="set")
