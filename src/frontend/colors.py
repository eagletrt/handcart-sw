"""Colours of the cell maps.

Volts: a diverging scale around the pack average: violet below, gray at it, orange above (the cells balancing
bleeds). End colours from the dataviz reference palette (dark steps); colour-blind safe on black (ΔE 26).
Temps: a gradient pinned to the team's thresholds, so a cell warming up shows long before it is warm:
blue below cold, gray at cold turning amber at warm, amber turning red at max, blinking red (CSS) above.
The amber is a little brighter than the other colours: any darker it turns brown and, for colour-blind
readers, too close to the red (ΔE 10 as it is). The danger cells also blink, so colour is not alone there.
"""

NEUTRAL = "#383835"  # an average cell, a normal temperature
NO_READING = "#141411"  # a cell or probe the BMS has not sent yet
VOLTS_LOW, VOLTS_HIGH = "#9085e9", "#d95926"  # violet, orange
TEMPS_COLD, TEMPS_WARM, TEMPS_HOT = "#3987e5", "#eda100", "#ff453a"  # blue, amber, red (the UI's red)


def diverging(position: float, low: str, high: str) -> str:
    """The colour at position -1 (all low) ... 0 (neutral) ... +1 (all high); beyond, it stays at the end."""
    position = max(-1.0, min(1.0, position))
    if position < 0:
        return mix(NEUTRAL, low, -position)
    return mix(NEUTRAL, high, position)


def temperature(temp: float, cold: float, warm: float, limit: float) -> str:
    """The colour of a probe below the limit (above it the cell blinks red instead)."""
    if temp < cold:
        return TEMPS_COLD
    if temp <= warm:
        return mix(NEUTRAL, TEMPS_WARM, (temp - cold) / (warm - cold))
    return mix(TEMPS_WARM, TEMPS_HOT, min(1.0, (temp - warm) / (limit - warm)))


def temperature_gradient(cold: float, warm: float, limit: float) -> str:
    """The temperature scale from cold to limit as a CSS background, for the legend."""
    at_warm = (warm - cold) / (limit - cold) * 100
    return f"linear-gradient(90deg, {NEUTRAL}, {TEMPS_WARM} {at_warm:.0f}%, {TEMPS_HOT})"


def gradient(low: str, high: str) -> str:
    """The same scale as a CSS background, for the legend."""
    return f"linear-gradient(90deg, {low}, {NEUTRAL}, {high})"


def mix(start: str, end: str, amount: float) -> str:
    """The colour amount (0..1) of the way from start to end, as #rrggbb."""
    a = [int(start[i : i + 2], 16) for i in (1, 3, 5)]
    b = [int(end[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * amount):02x}" for x, y in zip(a, b, strict=True))
