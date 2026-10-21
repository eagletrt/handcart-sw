"""Debug page, only with simulated hardware: http://<frontend>/debug

The UI as on the display (800 x 480), and beside it switches that make the simulated shutdown loop, BMS and
charger misbehave. They write var/sim.json (shared/scenario.py); the simulator and the backend follow it
within a fraction of a second, and the UI reacts as it would on the handcart.
"""

from nicegui import ui

from backend.hal.feedback import LOOP_CHANNELS
from shared import scenario

CLOSED = "closed"
SWITCHES = {  # Scenario field: label
    "bms_unplugged": "BMS unplugged",
    "charger_unplugged": "Charger unplugged",
    "bms_fault": "BMS fault (overvoltage)",
    "charger_error": "Charger in ERROR",
    "high_cell": "A cell above the voltage limit",
    "hot_cell": "A probe above the temperature limit",
}


def build() -> None:
    test = scenario.read()  # this page's copy; every change is written to the file at once

    def change(field: str, value: object) -> None:
        setattr(test, field, value)
        scenario.write(test)

    with ui.row().classes("items-start gap-6 p-4 no-wrap"):
        ui.element("iframe").props('src="/" width="800" height="480"').style("border: 1px solid #555")
        with ui.column().classes("gap-2"):
            ui.label("Simulated hardware").classes("text-h6")
            ui.label("Click the UI first to use the keys: arrows, Enter, Q and E for the knob.").classes(
                "text-caption"
            )
            options = {CLOSED: "closed"} | {point: f"open at {point}" for point in LOOP_CHANNELS.values()}
            loop = ui.select(
                options,
                value=test.shutdown_open_at or CLOSED,
                label="Shutdown loop",
                on_change=lambda e: change("shutdown_open_at", None if e.value == CLOSED else e.value),
            ).classes("w-64")
            switches = []
            for field, label in SWITCHES.items():
                switch = ui.switch(
                    label, value=getattr(test, field), on_change=lambda e, field=field: change(field, e.value)
                )
                switches.append(switch)

            def all_normal() -> None:
                loop.value = CLOSED  # each of these writes the file through its on_change
                for switch in switches:
                    switch.value = False

            ui.button("All normal", on_click=all_normal).props("outline")
