"""What covers the screens: the precharge and error takeovers, the settings and info windows, the toast."""

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from nicegui import ui

from frontend.controls import Target
from frontend.readings import details_screen
from frontend.targets import Reachable, button, usable
from shared.config import Config
from shared.models import Settings, State, Status, TsacState

ERROR_ART = {
    kind: (Path(__file__).parent / "static" / "errors" / f"{kind}.svg").read_text()
    for kind in ("cell", "hot", "mushroom", "loop", "bms", "offline", "charger")
}
PRECHARGE_PHASES = [
    (TsacState.AIRN_CHECK, "AIR− closed"),
    (TsacState.PRECHARGE, "Precharge"),
    (TsacState.AIRP_CHECK, "AIR+ closed"),
    (TsacState.TS_ON, "TS on"),
]
TOAST_TIME = 3.0  # s

# what the ⓘ button explains, per state
INFO = {
    State.CHECK: (
        "Connect the accumulator",
        "Plug the HV and LV connectors. The handcart waits until both the "
        "<b>BMS</b> and the <b>charger</b> answer on CAN.",
    ),
    State.IDLE: (
        "Ready to precharge",
        "<b>Precharge</b> closes the AIRs and brings the TS up to pack voltage in "
        "a few seconds. You can also <b>balance cells</b> now, with the TS off.",
    ),
    State.PRECHARGE: (
        "Precharging",
        "The BMS closes AIR−, charges the TS through the precharge resistor, then "
        "closes AIR+. Keep clear of the HV connectors.",
    ),
    State.READY: (
        "TS on",
        "Check <b>target</b> and <b>max current</b>, then <b>start charging</b>. "
        "<b>STOP</b> turns the TS off.",
    ),
    State.CHARGE: (
        "Charging",
        "Constant current until the pack reaches the target, then constant voltage while "
        "the current tapers. <b>Pause</b> keeps the TS on, <b>STOP</b> turns it off.",
    ),
    State.CHARGE_DONE: (
        "Charge complete",
        "The target is reached. Press <b>STOP</b> to turn the TS off before "
        "unplugging, or <b>charge again</b>.",
    ),
    State.BALANCING: (
        "Balancing",
        "The BMS bleeds the highest cells until the delta is under the threshold. Marked cells are bleeding.",
    ),
    State.ERROR: (
        "Error",
        "The handcart cut the charger and opened the shutdown loop. Fix the cause shown, "
        "then <b>reset errors</b>. The <b>Shutdown</b> screen shows where the loop is open.",
    ),
}


class Precharge:
    """The most dangerous moment gets the whole screen: shown while precharging and just after."""

    def __init__(self) -> None:
        with ui.element("div").classes("ovl pre") as self.root:
            ui.label("High voltage").classes("k")
            self._title = ui.label("Precharging").classes("t")
            ui.label("Keep clear of the HV connectors.").classes("d")
            with ui.element("div").classes("pbar"):
                self._bar = ui.element("i").classes("flow")
            self._phases = ui.html("").classes("pphases")
            self._numbers = ui.html("").classes("pnums num")

    def update(self, status: Status) -> None:
        bms = status.bms
        ts, pack = bms.ts_voltage or 0.0, bms.pack_voltage or 0.0
        phases = [phase for phase, _ in PRECHARGE_PHASES]
        if status.state is State.READY:  # done: the takeover lingers a moment to show it
            title, percent, current = "TS is on", 100.0, len(phases)
        else:
            title, percent, current = "Precharging", 0.0, 0
            if pack:
                percent = min(99.0, ts / pack * 100)
            if bms.state in phases:
                current = phases.index(bms.state)
        self._title.set_text(title)
        self._bar.style(f"width:{percent:.1f}%")

        spans = []
        for i, (_, label) in enumerate(PRECHARGE_PHASES):
            if i < current:
                spans.append(f'<span class="done">{label}</span>')
            elif i == current:
                spans.append(f'<span class="now">{label}</span>')
            else:
                spans.append(f"<span>{label}</span>")
        self._phases.set_content("".join(spans))
        self._numbers.set_content(
            f"<span>TS <b>{ts:.0f} V</b> / {pack:.0f} V</span><span><b>{percent:.0f}%</b></span>"
        )


class Discharge:
    """After TS off, until the TS is below 60 V: on every screen, because the high voltage is still there."""

    SAFE = 60.0  # V

    def __init__(self) -> None:
        self._start: float | None = None  # V when the discharge began: 0 % on the bar
        self.dismissed = False  # hidden by the operator until the next discharge
        with ui.element("div").classes("ovl pre dis") as self.root:
            ui.label("High voltage").classes("k")
            ui.label("TS discharging").classes("t")
            ui.label("The AIRs are open but the TS is still live. Keep clear of the HV connectors.").classes(
                "d"
            )
            with ui.element("div").classes("pbar"):
                self._bar = ui.element("i").classes("flow")
            self._numbers = ui.html("").classes("pnums num")
            self._hide = ui.button("Hide", on_click=self._on_hide).props("flat no-caps text-color=white")
            self._hide.classes("dhide")

    def reachable(self) -> list[Reachable]:
        return usable(button("hide", self._hide, priority=1))

    def update(self, status: Status) -> None:
        ts = status.bms.ts_voltage or 0.0
        if self._start is None or ts > self._start:
            self._start = ts
        percent = 100.0
        if self._start > self.SAFE:
            percent = max(0.0, min(100.0, (self._start - ts) / (self._start - self.SAFE) * 100))
        self._bar.style(f"width:{percent:.1f}%")
        self._numbers.set_content(f"<span>TS <b>{ts:.0f} V</b></span><span>safe below <b>60 V</b></span>")

    def done(self) -> None:
        """The TS is below 60 V (or on again): the next discharge starts fresh."""
        self._start = None
        self.dismissed = False

    def _on_hide(self) -> None:
        self.dismissed = True
        self.root.set_visibility(False)


class Error:
    """The handcart stopped on a fault: why, what it did, and the way out."""

    def __init__(self, on_reset: Callable[[], Awaitable[None]], on_details: Callable[[], None]) -> None:
        with ui.element("div").classes("ovl err") as self.root:
            with ui.element("div").classes("etext"):
                ui.label("Error").classes("k")
                self._title = ui.label("").classes("t")
                self._reason = ui.label("").classes("d")
                ui.html(
                    '<div class="efx"><span>CHARGER OFF</span><span>TS OFF</span>'
                    "<span>SD RELAY OPEN</span></div>"
                )
            self._art = ui.html("").classes("eart")
            with ui.element("div").classes("eact"):
                self._reset = ui.button("Reset errors", icon="restart_alt", on_click=on_reset)
                self._reset.props("unelevated no-caps").classes("reset")
                self._details = (
                    ui.button("", on_click=on_details).props("flat no-caps text-color=white").classes("det")
                )
        self._kind = ""

    def reachable(self) -> list[Reachable]:
        return usable(button("reset", self._reset, priority=1), button("details", self._details))

    def update(self, status: Status, kind: str, ts_was_on: bool) -> None:
        self._title.set_text("Charging stopped" if ts_was_on else "Handcart stopped")
        self._reason.set_text(status.message)
        if kind == self._kind:
            return  # redrawing the picture would restart its animation
        self._kind = kind
        self._art.set_content(ERROR_ART[kind])
        screen = details_screen(kind, status.message)
        text, icon = {
            "cells": ("View cells", "grid_view"),
            "charger": ("Charger", "ev_station"),
            "shutdown": ("Shutdown loop", "power"),
        }[screen]
        self._details.set_text(text)
        self._details.props(f"icon={icon}")


@dataclass(frozen=True)
class Field:
    """One setting in the window: its limits, its steps, and how it reads."""

    title: str
    low: float
    high: float
    button_step: float  # of − and +, for a finger
    knob_step: float  # of one encoder step: finer
    unit: str
    digits: int  # decimals shown
    note: Callable[[float], str]  # a line under the value
    shown_as: float = 1.0  # the value is shown times this: 1000 shows a value in V as mV


class SettingsWindow:
    """The operator's settings, changed with − and +, saved together.

    It opens on some of them: target voltage and max current from the charge screen, the balancing
    threshold from the cells screen.
    """

    def __init__(self, cfg: Config, save: Callable[[Settings], Awaitable[bool]]) -> None:
        charge, pack, cells = cfg.charge, cfg.accumulator, cfg.accumulator.cells
        self._fields = {  # keyed as in Settings
            "target_voltage": Field(
                title="Target",
                low=charge.target_voltage_min,
                high=charge.target_voltage_max,
                button_step=2.0,
                knob_step=1.0,
                unit="V",
                digits=0,
                note=lambda volts: f"{volts / cells:.3f} V per cell",
            ),
            "max_current": Field(
                title="Max current",
                low=0.5,
                high=charge.current_max,
                button_step=0.5,
                knob_step=0.1,
                unit="A",
                digits=1,
                note=lambda amps: f"{amps * charge.target_voltage_max / 1000:.1f} kW max",
            ),
            "balancing_threshold": Field(
                title="Threshold",  # the window title already says balancing
                low=pack.balancing_threshold_min,
                high=pack.balancing_threshold_max,
                button_step=0.005,  # the BMS takes it in 5 mV steps
                knob_step=0.005,
                unit="mV",
                digits=0,
                note=lambda volts: f"bleeds cells over lowest + {volts * 1000:.0f} mV",
                shown_as=1000,
            ),
        }
        self._draft: dict[str, float] = {}
        self._labels: dict[str, tuple[ui.label, ui.label]] = {}  # value, note
        self._boxes: dict[str, ui.element] = {}  # the frame of the controls goes on these
        self._save = save

        with (
            ui.element("div").classes("modal") as self.root,
            ui.element("div").classes("sheet set") as self._sheet,
        ):
            self._title = ui.label("").classes("sheet-title")
            with ui.element("div").classes("fields"):
                for key, field in self._fields.items():
                    self._build_field(key, field)
            with ui.element("div").classes("sheet-actions"):
                self._cancel = ui.button("Cancel", on_click=lambda: self.root.set_visibility(False))
                self._cancel.props("flat no-caps text-color=white").classes("cancel")
                self._save_button = ui.button("Save", on_click=self._on_save)
                self._save_button.props("unelevated no-caps text-color=black")
        self.root.set_visibility(False)

    def reachable(self) -> list[Reachable]:
        """The settings themselves (turning changes them, a click saves), then the buttons."""
        save = button("save", self._save_button)
        settings = []
        shown = [(key, box) for key, box in self._boxes.items() if box.visible]
        for i, (key, box) in enumerate(shown):
            priority = 1 if i == 0 else 0  # turning on Charge opens this window on the first setting
            target = Target(key, priority=priority, adjusts=key, presses="save")
            settings.append(Reachable(target, box, press=save.press))
        return [*settings, *usable(button("cancel", self._cancel), save)]

    def knob_step(self, key: str) -> float:
        return self._fields[key].knob_step

    def turn(self, key: str, steps: int) -> None:
        """Encoder steps on a setting (signed), within its limits."""
        self._change(key, steps * self._fields[key].knob_step)

    def open(self, settings: Settings, title: str, keys: tuple[str, ...]) -> None:
        """Show the window with only the settings in keys; Save sends all of them."""
        self._draft = settings.model_dump()
        self._title.set_text(title)
        if len(keys) == 1:
            self._sheet.classes(add="one")  # narrower, one column
        else:
            self._sheet.classes(remove="one")
        for key in self._fields:
            self._boxes[key].set_visibility(key in keys)
            self._draw(key)
        self.root.set_visibility(True)

    def _build_field(self, key: str, field: Field) -> None:
        with ui.element("div").classes("fld") as self._boxes[key]:
            with ui.element("div"):
                ui.label(field.title).classes("lbl")
                self._labels[key] = (ui.label("").classes("v num"), ui.label("").classes("n num"))
            with ui.element("div").classes("steps"):
                minus = ui.button("−", on_click=lambda: self._change(key, -field.button_step))
                plus = ui.button("+", on_click=lambda: self._change(key, +field.button_step))
                for step_button in (minus, plus):
                    step_button.props("flat text-color=white").classes("stp")

    def _change(self, key: str, amount: float) -> None:
        field = self._fields[key]
        value = max(field.low, min(field.high, self._draft[key] + amount))
        self._draft[key] = round(value, 6)  # 0.1 + 0.2 is not 0.3 in floats
        self._draw(key)

    def _draw(self, key: str) -> None:
        field, value = self._fields[key], self._draft[key]
        value_label, note_label = self._labels[key]
        value_label.set_text(f"{value * field.shown_as:.{field.digits}f} {field.unit}")
        note_label.set_text(field.note(value))

    async def _on_save(self) -> None:
        if await self._save(Settings(**self._draft)):
            self.root.set_visibility(False)


class ConfirmWindow:
    """Asks before something that cannot be undone from the screen: update, reboot, shut down."""

    def __init__(self) -> None:
        self._action: Callable[[], Awaitable[None]] | None = None
        # "confirm": above the window that asks for it
        with ui.element("div").classes("modal confirm") as self.root, ui.element("div").classes("sheet inf"):
            self._title = ui.label("").classes("sheet-title")
            self._text = ui.html("")
            with ui.element("div").classes("sheet-actions"):
                self._cancel = ui.button("Cancel", on_click=lambda: self.root.set_visibility(False))
                self._cancel.props("flat no-caps text-color=white").classes("cancel")
                self._confirm = ui.button("", on_click=self._on_confirm)
                self._confirm.props("unelevated no-caps color=negative")
        self.root.set_visibility(False)

    def reachable(self) -> list[Reachable]:
        # the controls start on the safe choice
        return usable(button("cancel", self._cancel, priority=1), button("confirm", self._confirm))

    def ask(self, title: str, text: str, confirm_text: str, action: Callable[[], Awaitable[None]]) -> None:
        self._title.set_text(title)
        self._text.set_content(f"<p>{text}</p>")
        self._confirm.set_text(confirm_text)
        self._action = action
        self.root.set_visibility(True)

    async def _on_confirm(self) -> None:
        self.root.set_visibility(False)
        if self._action is not None:
            await self._action()


class InfoWindow:
    def __init__(self) -> None:
        with ui.element("div").classes("modal") as self.root, ui.element("div").classes("sheet inf"):
            self._title = ui.label("").classes("sheet-title")
            self._text = ui.html("")
            self._ok = ui.button("Got it", on_click=lambda: self.root.set_visibility(False))
            self._ok.props("unelevated no-caps text-color=black").classes("ok")
        self.root.set_visibility(False)

    def reachable(self) -> list[Reachable]:
        return usable(button("ok", self._ok, priority=1))

    def open(self, state: State) -> None:
        title, text = INFO[state]
        self._title.set_text(title)
        self._text.set_content(
            f"<p>{text}</p><p><b>STOP</b> appears at the bottom whenever something is running.</p>"
        )
        self.root.set_visibility(True)


class Toast:
    def __init__(self) -> None:
        self.root = ui.label("").classes("toast")
        self.root.set_visibility(False)
        self._until = 0.0

    def show(self, text: str, ok: bool, seconds: float = TOAST_TIME) -> None:
        self.root.set_text(text)
        if ok:
            self.root.classes(replace="toast")  # yellow
        else:
            self.root.classes(replace="toast bad")  # red
        self.root.set_visibility(True)
        self._until = time.monotonic() + seconds

    def update(self) -> None:
        if self.root.visible and time.monotonic() > self._until:
            self.root.set_visibility(False)

    def hide(self) -> None:
        self.root.set_visibility(False)
