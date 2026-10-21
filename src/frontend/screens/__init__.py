"""The four screens of the touch UI. Each builds its elements once; update() refreshes them from a Status."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from nicegui import ui

from frontend.targets import Reachable
from shared.models import Command, Status


class Screen(Protocol):
    root: ui.element

    def update(self, status: Status) -> None: ...

    def reachable(self) -> list[Reachable]:
        """Its buttons the physical controls can reach now, in reading order."""
        ...


@dataclass
class Actions:
    """What a screen can ask the page for."""

    send: Callable[[Command], Awaitable[None]]  # a command to the backend
    show: Callable[[str], None]  # switch to another screen: "charge", "cells", "charger", "shutdown"
    open_settings: Callable[[], None]
    open_balancing_settings: Callable[[], None]  # the balancing threshold


def number(value: float | None, digits: int = 1) -> str:
    """A reading for the screen; a dash until the device has sent it."""
    return "—" if value is None else f"{value:.{digits}f}"
