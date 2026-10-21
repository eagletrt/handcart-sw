"""Shutdown screen: the voltage at each point of the shutdown loop, and where it is open."""

from nicegui import ui

from frontend.readings import first_open
from shared.config import Config
from shared.models import Status


class ShutdownScreen:
    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg.shutdown
        with ui.element("div").classes("tab mid") as self.root:
            self._loop = ui.html("")
            self._verdict = ui.html("")

    def update(self, status: Status) -> None:
        opened_at = first_open(status.shutdown, self._cfg.open_below)
        nodes = []
        for point, volts in status.shutdown:
            if point == opened_at:
                classes, reading = "open", "open"
            elif volts is None:
                classes, reading = "", "—"
            elif volts > self._cfg.closed_above:
                classes, reading = "ok", f"{volts:.1f} V"
            else:
                classes, reading = "", f"{volts:.1f} V"  # between the two thresholds: neither open nor closed
            nodes.append(
                f'<div class="node {classes}"><div class="pin"></div><div class="name">{point}</div>'
                f'<div class="v num">{reading}</div></div>'
            )
        self._loop.set_content(f'<div class="loop">{"".join(nodes)}</div>')
        if all(volts is None for _, volts in status.shutdown):
            self._verdict.set_content('<div class="verdict"><b>No reading yet</b></div>')
        elif opened_at is None:
            self._verdict.set_content('<div class="verdict"><b>Loop closed</b></div>')
        else:
            self._verdict.set_content(f'<div class="verdict bad"><b>Open at {opened_at}</b></div>')
