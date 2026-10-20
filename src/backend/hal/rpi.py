"""The real peripherals on the Raspberry Pi: GPIO and PWM through RPi.GPIO (rpi-lgpio), SPI through spidev.

Only translation to the libraries here, no logic: that lives in the other hal/ modules and is tested.
Not yet tried on the handcart Pi.
"""

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


class RpiPwm:
    DUTY_CYCLE = 50  # %, a square wave

    def __init__(self, pin: int) -> None:
        GPIO.setup(pin, GPIO.OUT)
        self._pwm = GPIO.PWM(pin, 1000)
        self._frequency: float | None = None

    def tone(self, frequency: float | None) -> None:
        if frequency == self._frequency:
            return
        if frequency is None:
            self._pwm.stop()
        elif self._frequency is None:
            self._pwm.ChangeFrequency(frequency)
            self._pwm.start(self.DUTY_CYCLE)
        else:
            self._pwm.ChangeFrequency(frequency)
        self._frequency = frequency


class RpiSpi:
    def __init__(self, cfg: Config) -> None:
        self._spi = spidev.SpiDev()
        self._spi.open(cfg.adc.spi_bus, cfg.adc.spi_device)
        self._spi.mode = cfg.adc.spi_mode
        self._spi.max_speed_hz = cfg.adc.spi_max_speed_hz

    def transfer(self, data: bytes) -> bytes:
        return bytes(self._spi.xfer2(list(data)))
