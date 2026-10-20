"""The handcart PCB, through its peripherals. The same class runs on the Pi and in the tests."""

import time
from collections.abc import Callable

from backend.hal import Sound
from backend.hal.buzzer import Player
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
        self._player = Player()
        self._events: list[InputEvent] = []
        self._volts: dict[int, float] = {}  # last reading of each ADC channel
        self._next_adc_read = 0.0
        self._adc.transfer(configuration_word())

    def poll(self, now: float) -> None:
        self._read_controls(now)
        if now >= self._next_adc_read:
            self._read_feedbacks()
            self._next_adc_read = now + ADC_READ_PERIOD
        self._buzzer.tone(self._player.frequency(now))

    def set_relays(
        self, sd_relay_closed: bool, charger_power: bool, discharge: bool
    ) -> None:
        for pin, high in relay_levels(
            self._cfg.gpio, sd_relay_closed, charger_power, discharge
        ).items():
            self._gpio.write(pin, high)

    def shutdown_loop(self) -> ShutdownLoop:
        return shutdown_loop(self._volts)

    def input_events(self) -> list[InputEvent]:
        events, self._events = self._events, []
        return events

    def play(self, sound: Sound) -> None:
        self._player.play(sound, self._clock())

    def _read_controls(self, now: float) -> None:
        levels = {pin: self._gpio.read(pin) for pin in self._buttons.pins}
        self._events += self._buttons.update(now, levels)
        pins = self._cfg.gpio
        self._events += self._encoder.update(
            self._gpio.read(pins.encoder_a), self._gpio.read(pins.encoder_b)
        )

    def _read_feedbacks(self) -> None:
        """One scan: ask for all the channels, then read a result per channel from the ADC FIFO."""
        self._adc.transfer(scan_word())
        self._adc.transfer(b"\x00")
        for _ in range(LAST_CHANNEL + 1):
            result = self._adc.transfer(b"\x00\x00")
            if result == b"\x00\x00":
                break  # FIFO empty
            channel, volts = parse_result(result, self._cfg.adc)
            self._volts[channel] = volts
