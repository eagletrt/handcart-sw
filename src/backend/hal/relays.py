"""Which level each relay pin needs. Polarity as wired on the handcart PCB (from the old repo)."""

from shared.config import GpioPins


def relay_levels(
    pins: GpioPins, sd_relay_closed: bool, charger_power: bool, discharge: bool
) -> dict[int, bool]:
    """Pin -> level (True = high) for the relays."""
    return {
        pins.sd_relay: sd_relay_closed,  # high closes the shutdown relay
        pins.pon: charger_power,  # high powers the charger
        pins.discharge_relay: not discharge,  # low puts the TS discharge resistor in
    }
