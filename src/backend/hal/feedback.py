"""Shutdown feedbacks: the MAX11335 ADC on SPI measures the loop voltage at several points.

Datasheet: https://www.analog.com/media/en/technical-documentation/data-sheets/max11335-max11340.pdf
Register settings and channel wiring are those of the old repo.
"""

from shared.config import Adc
from shared.models import ShutdownLoop

# ADC channel -> point of the shutdown loop, in loop order (the old FB enum, channels 0-5).
# Each channel measures the loop just after a part, and is named after that part: no voltage there means
# that part is open. On the PCB (handcart-hw): VSD -> SD relay -> SD_TO_MUSHROOM -> mushroom -> SD_TO_CHARGER
# -> charger interlock -> SD_BMS_IN -> BMS -> SD_BMS_OUT -> TSMS key -> SD_END
LOOP_CHANNELS = {0: "supply", 1: "SD relay", 2: "mushroom", 3: "charger", 4: "BMS", 5: "TSMS"}
LAST_CHANNEL = 10  # channels 6-10 are other feedbacks: discharge coil, 12 V, PON, SD relay

FULL_SCALE = 4096  # 12 bits


def _bits(*fields: tuple[int, int]) -> bytes:
    """Pack (value, width) fields, most significant first, into a 16-bit register word."""
    assert sum(width for _, width in fields) == 16, "a register is 16 bits"
    word = 0
    for value, width in fields:
        word = word << width | value
    return word.to_bytes(2, "big")


def configuration_word() -> bytes:
    """ADC configuration register: external single-ended reference, averaging of 32 samples, echo on."""
    return _bits(
        (0b10000, 5),  # register: ADC configuration
        (0, 1),  # REFSEL: external, single-ended
        (1, 1),  # AVGON: averaging on
        (0b11, 2),  # NAVG: 32 conversions
        (0b00, 2),  # NSCAN
        (0b00, 2),  # SPM: normal power
        (1, 1),  # ECHO on
        (0, 2),  # unused
    )


def scan_word() -> bytes:
    """ADC mode control register: scan channels 0..LAST_CHANNEL, channel id in each result."""
    return _bits(
        (0, 1),  # register: ADC mode control
        (0b0100, 4),  # SCAN: standard, external clock
        (LAST_CHANNEL, 4),  # up to this channel
        (0b00, 2),  # RESET: none
        (0b00, 2),  # PM: normal
        (1, 1),  # CHAN_ID: channel number in each result
        (1, 1),  # SWCNV: start with chip select
        (0, 1),  # unused
    )


def parse_result(word: bytes, adc: Adc) -> tuple[int, float]:
    """(channel, volts on the loop) from one 16-bit result: 4 bits of channel, 12 of value."""
    raw = int.from_bytes(word, "big")
    channel, value = raw >> 12, raw & 0xFFF
    volts_at_adc = adc.vref * value / FULL_SCALE
    return channel, round(volts_at_adc * (adc.divider + adc.divider_correction), 2)


def shutdown_loop(volts_by_channel: dict[int, float]) -> ShutdownLoop:
    """The loop points in order, None where no reading has arrived yet."""
    return tuple((name, volts_by_channel.get(channel)) for channel, name in LOOP_CHANNELS.items())
