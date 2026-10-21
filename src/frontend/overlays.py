"""What covers the screens: the precharge and error takeovers, the settings and info windows, the toast."""

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from nicegui import ui

from shared.config import Config
from shared.models import Settings, State, Status, TsacState

ERROR_ART = {
    kind: (Path(__file__).parent / "static" / "errors" / f"{kind}.svg").read_text()
    for kind in ("cell", "mushroom", "loop")
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


class Error:
    """Charging stopped: why, what the handcart did, and the way out."""

    def __init__(self, on_reset: Callable[[], Awaitable[None]], on_details: Callable[[], None]) -> None:
        with ui.element("div").classes("ovl err") as self.root:
            with ui.element("div").classes("etext"):
                ui.label("Error").classes("k")
                ui.label("Charging stopped").classes("t")
                self._reason = ui.label("").classes("d")
                ui.html(
                    '<div class="efx"><span>CHARGER OFF</span><span>TS OFF</span>'
                    "<span>SD RELAY OPEN</span></div>"
                )
            self._art = ui.html("").classes("eart")
            with ui.element("div").classes("eact"):
                ui.button("Reset errors", icon="restart_alt", on_click=on_reset).props(
                    "unelevated no-caps"
                ).classes("reset")
                self._details = (
                    ui.button("", on_click=on_details).props("flat no-caps text-color=white").classes("det")
                )
        self._kind = ""

    def update(self, status: Status, kind: str) -> None:
        self._reason.set_text(status.message)
        if kind == self._kind:
            return  # redrawing the picture would restart its animation
        self._kind = kind
        self._art.set_content(ERROR_ART[kind])
        if kind == "cell":
            self._details.set_text("View cells")
            self._details.props("icon=grid_view")
        else:
            self._details.set_text("Shutdown loop")
            self._details.props("icon=power")


@dataclass(frozen=True)
class Field:
    """One setting in the window: its limits, the step of − and +, and how it reads."""

    title: str
    low: float
    high: float
    step: float
    unit: str
    digits: int  # decimals shown
    note: Callable[[float], str]  # a line under the value


class SettingsWindow:
    """Target voltage and max current, changed with − and +, saved together."""

    def __init__(self, cfg: Config, save: Callable[[Settings], Awaitable[bool]]) -> None:
        charge, cells = cfg.charge, cfg.accumulator.cells
        self._fields = {  # keyed as in Settings
            "target_voltage": Field(
                title="Target",
                low=charge.target_voltage_min,
                high=charge.target_voltage_max,
                step=2.0,
                unit="V",
                digits=0,
                note=lambda volts: f"{volts / cells:.3f} V per cell",
            ),
            "max_current": Field(
                title="Max current",
                low=0.5,
                high=charge.current_max,
                step=0.5,
                unit="A",
                digits=1,
                note=lambda amps: f"{amps * charge.target_voltage_max / 1000:.1f} kW max",
            ),
        }
        self._draft: dict[str, float] = {}
        self._labels: dict[str, tuple[ui.label, ui.label]] = {}  # value, note
        self._save = save

        with ui.element("div").classes("modal") as self.root, ui.element("div").classes("sheet set"):
            ui.label("Charge settings").classes("sheet-title")
            with ui.element("div").classes("fields"):
                for key, field in self._fields.items():
                    self._build_field(key, field)
            with ui.element("div").classes("sheet-actions"):
                ui.button("Cancel", on_click=lambda: self.root.set_visibility(False)).props(
                    "flat no-caps text-color=white"
                ).classes("cancel")
                ui.button("Save", on_click=self._on_save).props("unelevated no-caps text-color=black")
        self.root.set_visibility(False)

    def open(self, settings: Settings) -> None:
        self._draft = settings.model_dump()
        for key in self._fields:
            self._draw(key)
        self.root.set_visibility(True)

    def _build_field(self, key: str, field: Field) -> None:
        with ui.element("div").classes("fld"):
            with ui.element("div"):
                ui.label(field.title).classes("lbl")
                self._labels[key] = (ui.label("").classes("v num"), ui.label("").classes("n num"))
            with ui.element("div").classes("steps"):
                ui.button("−", on_click=lambda: self._change(key, -field.step)).props(
                    "flat text-color=white"
                ).classes("stp")
                ui.button("+", on_click=lambda: self._change(key, +field.step)).props(
                    "flat text-color=white"
                ).classes("stp")

    def _change(self, key: str, amount: float) -> None:
        field = self._fields[key]
        self._draft[key] = max(field.low, min(field.high, self._draft[key] + amount))
        self._draw(key)

    def _draw(self, key: str) -> None:
        field, value = self._fields[key], self._draft[key]
        value_label, note_label = self._labels[key]
        value_label.set_text(f"{value:.{field.digits}f} {field.unit}")
        note_label.set_text(field.note(value))

    async def _on_save(self) -> None:
        if await self._save(Settings(**self._draft)):
            self.root.set_visibility(False)


class InfoWindow:
    def __init__(self) -> None:
        with ui.element("div").classes("modal") as self.root, ui.element("div").classes("sheet inf"):
            self._title = ui.label("").classes("sheet-title")
            self._text = ui.html("")
            ui.button("Got it", on_click=lambda: self.root.set_visibility(False)).props(
                "unelevated no-caps text-color=black"
            ).classes("ok")
        self.root.set_visibility(False)

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

    def show(self, text: str, ok: bool) -> None:
        self.root.set_text(text)
        if ok:
            self.root.classes(replace="toast")  # yellow
        else:
            self.root.classes(replace="toast bad")  # red
        self.root.set_visibility(True)
        self._until = time.monotonic() + TOAST_TIME

    def update(self) -> None:
        if self.root.visible and time.monotonic() > self._until:
            self.root.set_visibility(False)
