"""The buttons the physical controls can reach, as each screen and window lists them (rules: controls.py)."""

from collections.abc import Callable
from dataclasses import dataclass

from nicegui import ui
from nicegui.elements.mixins.disableable_element import DisableableElement

from frontend.controls import Target


@dataclass(frozen=True)
class Reachable:
    target: Target
    element: ui.element  # the one that gets the frame
    press: Callable[[], None]


def button(key: str, element: ui.button, priority: int = 0, opens_map: bool = False) -> Reachable:
    """A ui.button: pressing it clicks it in the browser, so it runs its usual handler."""

    def press() -> None:
        element.run_method("click")

    return Reachable(Target(key, priority, opens_map=opens_map), element, press)


def usable(*items: Reachable) -> list[Reachable]:
    """The items shown and enabled, in the given order. A tab (a plain element) cannot be disabled."""
    result = []
    for item in items:
        disabled = isinstance(item.element, DisableableElement) and not item.element.enabled
        if item.element.visible and not disabled:
            result.append(item)
    return result
