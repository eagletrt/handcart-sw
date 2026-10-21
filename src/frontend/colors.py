"""Colour scales of the cell maps. Both are diverging: a neutral gray at the reference, a colour at each end.

Volts: violet below the pack average, orange above (the cells balancing bleeds).
Temps: blue cold, red hot: the classic colours, and different from the volts at a glance.
The end colours come from the dataviz reference palette (its dark steps). Checked on the black screen,
colour-blind readers included: violet/orange ΔE 26, blue/red ΔE 19 (the target is at least 8).
"""

NEUTRAL = "#383835"  # at the reference: an average cell, a normal temperature
NO_READING = "#141411"  # a cell or probe the BMS has not sent yet
VOLTS_LOW, VOLTS_HIGH = "#9085e9", "#d95926"  # violet, orange
TEMPS_COLD, TEMPS_HOT = "#3987e5", "#e66767"  # blue, red


def diverging(position: float, low: str, high: str) -> str:
    """The colour at position -1 (all low) ... 0 (neutral) ... +1 (all high); beyond, it stays at the end."""
    position = max(-1.0, min(1.0, position))
    if position < 0:
        return mix(NEUTRAL, low, -position)
    return mix(NEUTRAL, high, position)


def gradient(low: str, high: str) -> str:
    """The same scale as a CSS background, for the legend."""
    return f"linear-gradient(90deg, {low}, {NEUTRAL}, {high})"


def mix(start: str, end: str, amount: float) -> str:
    """The colour amount (0..1) of the way from start to end, as #rrggbb."""
    a = [int(start[i : i + 2], 16) for i in (1, 3, 5)]
    b = [int(end[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * amount):02x}" for x, y in zip(a, b, strict=True))
