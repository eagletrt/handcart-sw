"""The real peripherals on the Raspberry Pi: GPIO through RPi.GPIO (rpi-lgpio), SPI through spidev.

Only translation to the libraries here, no logic: that lives in the other hal/ modules and is tested.
Not yet tried on the handcart Pi.
"""

import pigpio
import spidev
from RPi import GPIO

from shared.config import Config


class RpiGpio:
    def __init__(self, cfg: Config) -> None:
        pins = cfg.gpio
        GPIO.setmode(GPIO.BCM)
        for pin in (pins.sd_relay, pins.pon, pins.discharge_relay):
            GPIO.setup(pin, GPIO.OUT)
        for pin in (
            pins.button_up,
            pins.button_down,
            pins.button_left,
            pins.button_right,
            pins.encoder_press,
        ):
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        for pin in (pins.encoder_a, pins.encoder_b):
            GPIO.setup(pin, GPIO.IN)

    def write(self, pin: int, high: bool) -> None:
        GPIO.output(pin, GPIO.HIGH if high else GPIO.LOW)

    def read(self, pin: int) -> bool:
        return GPIO.input(pin) == GPIO.HIGH


class PigpioPwm:
    """Square wave timed by DMA through pigpiod: clean on any GPIO, unlike RPi.GPIO's software PWM."""

    def __init__(self, pin: int) -> None:
        self._pi = pigpio.pi()
        if not self._pi.connected:
            raise RuntimeError("pigpiod is not running")
        self._pin = pin
        self._pi.set_mode(pin, pigpio.OUTPUT)
        self._pi.write(pin, 0)
        self._wave: int | None = None
        self._frequency: float | None = None

    def tone(self, frequency: float | None) -> None:
        if frequency == self._frequency:
            return
        self._frequency = frequency
        self._pi.wave_tx_stop()
        if self._wave is not None:
            self._pi.wave_delete(self._wave)
            self._wave = None
        if frequency is None:
            self._pi.write(self._pin, 0)
            return
        half = round(500_000 / frequency)  # µs, half a period
        mask = 1 << self._pin
        self._pi.wave_add_generic(
            [pigpio.pulse(mask, 0, half), pigpio.pulse(0, mask, half)]
        )
        self._wave = self._pi.wave_create()
        self._pi.wave_send_repeat(self._wave)


class RpiSpi:
    def __init__(self, cfg: Config) -> None:
        self._spi = spidev.SpiDev()
        self._spi.open(cfg.adc.spi_bus, cfg.adc.spi_device)
        self._spi.mode = cfg.adc.spi_mode
        self._spi.max_speed_hz = cfg.adc.spi_max_speed_hz

    def transfer(self, data: bytes) -> bytes:
        return bytes(self._spi.xfer2(list(data)))
