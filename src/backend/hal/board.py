"""The handcart PCB, through its peripherals. The same class runs on the Pi and in the tests."""

import time
from collections.abc import Callable

from backend.hal.controls import Buttons, Encoder
from backend.hal.drivers import Gpio, Pwm, Spi
from backend.hal.feedback import (
    LAST_CHANNEL,
    configuration_word,
    parse_result,
    scan_word,
    shutdown_loop,
)
from backend.hal.relays import relay_levels
from shared.config import Config
from shared.models import InputEvent, ShutdownLoop

ADC_READ_PERIOD = 0.1  # s between two scans of the feedbacks
READING_MAX_AGE = 1.0  # s: a feedback not read again for this long is unknown, never stuck at its last value


class BoardHal:
    def __init__(
        self,
        cfg: Config,
        gpio: Gpio,
        buzzer: Pwm,
        adc: Spi,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._cfg = cfg
        self._gpio = gpio
        self._buzzer = buzzer
        self._adc = adc
        self._clock = clock
        pins = cfg.gpio
        self._buttons = Buttons(
            {
                pins.button_up: InputEvent.UP,
                pins.button_down: InputEvent.DOWN,
                pins.button_left: InputEvent.LEFT,
                pins.button_right: InputEvent.RIGHT,
                pins.encoder_press: InputEvent.PRESS,
            }
        )
        self._encoder = Encoder()
        self._events: list[InputEvent] = []
        self._readings: dict[int, tuple[float, float]] = {}  # ADC channel -> (volts, when read)
        self._next_adc_read = 0.0
        self._adc.transfer(configuration_word())

    def poll(self, now: float) -> None:
        self._read_controls(now)
        if now >= self._next_adc_read:
            self._read_feedbacks(now)
            self._next_adc_read = now + ADC_READ_PERIOD

    def set_relays(self, sd_relay_closed: bool, charger_power: bool, discharge: bool) -> None:
        for pin, high in relay_levels(self._cfg.gpio, sd_relay_closed, charger_power, discharge).items():
            self._gpio.write(pin, high)

    def shutdown_loop(self) -> ShutdownLoop:
        now = self._clock()
        fresh = {
            ch: volts for ch, (volts, read_at) in self._readings.items() if now - read_at <= READING_MAX_AGE
        }
        return shutdown_loop(fresh)

    def input_events(self) -> list[InputEvent]:
        events, self._events = self._events, []
        return events

    def set_buzzer(self, frequency: float | None) -> None:
        self._buzzer.tone(frequency)

    def _read_controls(self, now: float) -> None:
        levels = {pin: self._gpio.read(pin) for pin in self._buttons.pins}
        self._events += self._buttons.update(now, levels)
        pins = self._cfg.gpio
        self._events += self._encoder.update(self._gpio.read(pins.encoder_a), self._gpio.read(pins.encoder_b))

    def _read_feedbacks(self, now: float) -> None:
        """One scan: ask for all the channels, then read one result per channel, in order, from the FIFO.

        Every result is read: 00 00 is also channel 0 at 0 V (the loop supply gone), not "nothing left".
        A result for another channel than expected (the ADC out of step, or not answering) is left out.
        """
        self._adc.transfer(scan_word())
        self._adc.transfer(b"\x00")
        for expected in range(LAST_CHANNEL + 1):
            channel, volts = parse_result(self._adc.transfer(b"\x00\x00"), self._cfg.adc)
            if channel == expected:
                self._readings[channel] = (volts, now)
