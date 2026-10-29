"""The Debug window, behind the safe (safe_window.py): to try the handcart's parts by hand.

The buzzer plays each sound on demand; the controls light up as they arrive, with how many of each,
to see that no press or step of the encoder is lost; a line says what the handcart sees, another how fast
the screen answers (measured by its own browser); the terminal is here, on the Pi itself. Closing it
locks it again behind the safe.
"""

import time
from collections.abc import Callable

from nicegui import ui

from frontend.backend import Backend
from frontend.targets import Reachable, button, usable
from shared.models import InputEvent, Sound

FLASH_TIME = 0.4  # s a control stays lit after it arrives
SPEED_PERIOD = 1.0  # s between two readings of how fast the screen answers
CONTROL_NAMES = {
    InputEvent.UP: "Up",
    InputEvent.DOWN: "Down",
    InputEvent.LEFT: "Left",
    InputEvent.RIGHT: "Right",
    InputEvent.PRESS: "Click",
    InputEvent.TURN_CCW: "Turn left",
    InputEvent.TURN_CW: "Turn right",
}


class DebugWindow:
    def __init__(
        self,
        backend: Backend,
        report: Callable[[str], None],
        open_terminal: Callable[[], None] | None,  # None: no terminal (the page is not on the Pi itself)
    ) -> None:
        self._backend = backend
        self._report = report  # shows why something was refused
        self._open_terminal = open_terminal
        self._counts = dict.fromkeys(InputEvent, 0)
        self._lit_at = dict.fromkeys(InputEvent, float("-inf"))
        self._client = ui.context.client

        # built when it opens and emptied when it closes: the browser redraws every element of the page at
        # each change, hidden ones too. Built once here, so that every attribute exists before it opens.
        self.root = ui.element("div").classes("modal")
        with self.root:
            self._build()
        self.close()
        ui.timer(SPEED_PERIOD, self._measure_speed)

    def _build(self) -> None:
        with ui.element("div").classes("sheet dbg"):
            with ui.element("div").classes("thead"):
                ui.label("Debug").classes("sheet-title")
                self._version = ui.label("").classes("sheet-sub num")
            ui.label("Buzzer").classes("lbl dlbl")
            with ui.element("div").classes("dsounds"):
                self._sounds = []
                for sound in Sound:
                    label = sound.replace("_", " ").capitalize()
                    chip = ui.button(label, on_click=lambda sound=sound: self._play(sound))
                    chip.props("flat no-caps text-color=white").classes("tchip")
                    self._sounds.append(chip)
            ui.label("Controls").classes("lbl dlbl")
            with ui.element("div").classes("dctrls"):
                self._controls = {event: ui.label("").classes("dctrl num") for event in CONTROL_NAMES}
            self._handcart = ui.label("").classes("sheet-sub dline num")
            self._speed = ui.label("Touch the screen a few times to measure it").classes(
                "sheet-sub dspeed num"
            )
            with ui.element("div").classes("sheet-actions tacts"):
                self._close = ui.button("Lock", icon="lock", on_click=self.close)
                self._close.props("flat no-caps text-color=white").classes("cancel")
                self._terminal = ui.button("Terminal", icon="terminal", on_click=self._open_terminal)
                self._terminal.props("unelevated no-caps text-color=black")
                self._terminal.set_visibility(self._open_terminal is not None)

    def close(self) -> None:
        self.root.set_visibility(False)
        self.root.clear()

    def reachable(self) -> list[Reachable]:
        sounds = usable(*[button(f"sound {i}", chip) for i, chip in enumerate(self._sounds)])
        actions = usable(button("lock", self._close, priority=1), button("terminal", self._terminal))
        return [*sounds, *actions]

    def open(self) -> None:
        self._counts = dict.fromkeys(InputEvent, 0)
        self.root.clear()
        with self.root:
            self._build()
        self.root.set_visibility(True)  # first: update skips a closed window
        self.update()

    def on_input(self, event: InputEvent) -> None:
        """A press of the handcart's controls: its chip lights up and counts it."""
        self._counts[event] += 1
        self._lit_at[event] = time.monotonic()
        self.update()

    def update(self) -> None:
        """At every refresh of the page, while open."""
        if not self.root.visible:
            return
        info = self._backend.system
        if info is not None:
            self._version.set_text(f"Version {info.version} · branch {info.branch}")
        now = time.monotonic()
        for event, chip in self._controls.items():
            chip.set_text(f"{CONTROL_NAMES[event]} {self._counts[event]}")
            if now - self._lit_at[event] < FLASH_TIME:
                chip.classes(add="on")
            else:
                chip.classes(remove="on")
        self._handcart.set_text(self._handcart_line())

    def _handcart_line(self) -> str:
        status = self._backend.status
        if status is None:
            return "Backend not reachable"
        parts = [
            f"State {status.state}",
            "BMS on CAN" if status.bms.connected else "No BMS",
            "Charger on CAN" if status.charger.connected else "No charger",
        ]
        network = self._backend.network
        if network is not None:
            parts += [f"{address.name} {address.address}" for address in network.addresses]
        return " · ".join(parts)

    async def _measure_speed(self) -> None:
        """While open: the touches the browser timed, anywhere on the screen (handcart.js), and a round trip
        to the browser and back."""
        if not self.root.visible:
            return
        asked = time.monotonic()
        try:
            touches = await self._client.run_javascript("touchLatency()", timeout=5)
        except TimeoutError:
            self._speed.set_text("The browser did not answer within 5 s")
            return
        round_trip = (time.monotonic() - asked) * 1000
        line = f"Server → browser → server {round_trip:.0f} ms"
        if touches:
            line = (
                f"Touch → screen {touches['total']} ms: finger → click {touches['click']}, "
                f"click → server {touches['server']}, drawing {touches['draw']} "
                f"(last {touches['count']}) · {line}"
            )
            if touches["split"]:  # the browser can tell what the drawing was
                line += f" · drawing: scripts {touches['scripts']}, style and layout {touches['layout']}"
        self._speed.set_text(line)

    async def _play(self, sound: Sound) -> None:
        problem = await self._backend.play(sound)
        if problem:
            self._report(problem)
