"""Charger screen: its state and DC output on the left, the grid phases and temperature on the right."""

from nicegui import ui

from frontend.screens import number
from frontend.targets import Reachable
from shared.models import ChargerState, Status

PHASE_FULL_SCALE = 250  # V, a full phase bar


class ChargerScreen:
    def __init__(self) -> None:
        with ui.element("div").classes("tab mid") as self.root, ui.element("div").classes("chg"):
            with ui.element("div"):
                self._state = ui.label("—").classes("state")
                self._voltage = ui.html("").classes("out num")
                self._current = ui.html("").classes("out2 num")
            with ui.element("div"):
                with ui.element("div").classes("phases"):
                    self._phases = [self._phase(name) for name in ("L1", "L2", "L3")]
                with ui.element("div").classes("kv num"):
                    ui.label("Max temp").classes("k")
                    self._temperature = ui.label("—").classes("v")
                    ui.label("Errors").classes("k")
                    self._errors = ui.label("—").classes("v")

    def reachable(self) -> list[Reachable]:
        return []  # nothing to press: only readings

    def update(self, status: Status) -> None:
        charger = status.charger
        state = charger.state
        if not charger.connected:
            self._state.set_text("Not connected")
        elif state is None:
            self._state.set_text("—")  # no status yet, or a code the DBC does not document
        else:
            self._state.set_text(state.value)

        if state is not None and state.delivering:
            self._state.classes(replace="state run")  # yellow
        elif state in (None, ChargerState.OFF, ChargerState.ERROR):
            self._state.classes(replace="state bad")  # red
        else:
            self._state.classes(replace="state")
        self._voltage.set_content(f"{number(charger.voltage)}<small>V</small>")
        mode = ""
        if state in (ChargerState.RUNNING_VC, ChargerState.RUNNING_VC_DERATING):
            mode = " · CV"
        elif state and state.delivering:
            mode = " · CC"
        self._current.set_content(f"{number(charger.current)} A{mode}")
        for (value, bar), volts in zip(self._phases, charger.grid_voltages, strict=True):
            value.set_text("—" if volts is None else f"{volts:.0f} V")
            bar.style(f"width:{min(100, (volts or 0) / PHASE_FULL_SCALE * 100):.0f}%")
        self._temperature.set_text(f"{number(charger.max_temperature)} °C")
        self._errors.set_text(", ".join(sorted(charger.errors)) or "none")

    def _phase(self, name: str) -> tuple[ui.label, ui.element]:
        with ui.element("div").classes("ph"):
            ui.label(name).classes("lbl")
            value = ui.label("—").classes("v num")
            with ui.element("div").classes("b"):
                bar = ui.element("i")
        return value, bar
