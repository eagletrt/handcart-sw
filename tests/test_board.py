"""The handcart PCB logic, with fake peripherals: what BoardHal does with pins, SPI bytes and the buzzer."""

from dataclasses import dataclass

import pytest

from backend.hal import Sound
from backend.hal.board import BoardHal
from backend.hal.buzzer import RE7, Player
from backend.hal.feedback import configuration_word, parse_result, scan_word
from shared.models import InputEvent


class FakeGpio:
    def __init__(self) -> None:
        self.levels: dict[int, bool] = {}  # inputs, high unless set (pull-ups)
        self.written: dict[int, bool] = {}

    def write(self, pin: int, high: bool) -> None:
        self.written[pin] = high

    def read(self, pin: int) -> bool:
        return self.levels.get(pin, True)


class FakePwm:
    def __init__(self) -> None:
        self.tones: list[float | None] = []

    def tone(self, frequency: float | None) -> None:
        self.tones.append(frequency)


class FakeAdc:
    """Answers every scan with the given results, as the MAX11335 FIFO would."""

    def __init__(self) -> None:
        self.results: list[bytes] = []
        self.sent: list[bytes] = []
        self._fifo: list[bytes] = []

    def transfer(self, data: bytes) -> bytes:
        self.sent.append(data)
        if data == scan_word():
            self._fifo = list(self.results)
        if data == b"\x00\x00":
            return self._fifo.pop(0) if self._fifo else b"\x00\x00"
        return bytes(len(data))


def result(channel: int, value: int) -> bytes:
    return (channel << 12 | value).to_bytes(2, "big")


@dataclass
class Board:
    """A BoardHal on fake peripherals, and the peripherals, to check what it did with them."""

    hal: BoardHal
    gpio: FakeGpio
    pwm: FakePwm
    adc: FakeAdc


@pytest.fixture
def board(cfg) -> Board:
    gpio, pwm, adc = FakeGpio(), FakePwm(), FakeAdc()
    return Board(BoardHal(cfg, gpio, pwm, adc, clock=lambda: 0.0), gpio, pwm, adc)


def press(board, pin: int, seconds: float, start: float = 0.0) -> list[InputEvent]:
    """Hold a button down for a while, polling every 5 ms; return the events."""
    board.gpio.levels[pin] = False
    now = start
    while now < start + seconds:
        now += 0.005
        board.hal.poll(now)
    board.gpio.levels[pin] = True
    board.hal.poll(now + 0.03)
    board.hal.poll(now + 0.06)
    return board.hal.input_events()


# relays


def test_relay_polarity(board, cfg):
    board.hal.set_relays(sd_relay_closed=True, charger_power=True, discharge=False)
    assert board.gpio.written == {cfg.gpio.sd_relay: True, cfg.gpio.pon: True, cfg.gpio.discharge_relay: True}
    board.hal.set_relays(sd_relay_closed=False, charger_power=False, discharge=True)
    assert board.gpio.written == {
        cfg.gpio.sd_relay: False,
        cfg.gpio.pon: False,
        cfg.gpio.discharge_relay: False,
    }


# buttons and encoder


def test_a_held_button_gives_one_event(board, cfg):
    assert press(board, cfg.gpio.button_up, 0.2) == [InputEvent.UP]


def test_a_bounce_shorter_than_the_debounce_is_ignored(board, cfg):
    assert press(board, cfg.gpio.encoder_press, 0.01) == []


def test_two_presses_give_two_events(board, cfg):
    first = press(board, cfg.gpio.button_left, 0.1)
    second = press(board, cfg.gpio.button_left, 0.1, start=1.0)
    assert first + second == [InputEvent.LEFT, InputEvent.LEFT]


def test_no_encoder_step_at_start(board):
    board.hal.poll(0.0)  # B already high: not a turn
    assert board.hal.input_events() == []


@pytest.mark.parametrize("a, event", [(True, InputEvent.TURN_CW), (False, InputEvent.TURN_CCW)])
def test_encoder_direction(board, cfg, a, event):
    board.gpio.levels[cfg.gpio.encoder_a] = a
    board.gpio.levels[cfg.gpio.encoder_b] = False
    board.hal.poll(0.0)
    board.gpio.levels[cfg.gpio.encoder_b] = True  # rising edge of B
    board.hal.poll(0.005)
    assert board.hal.input_events() == [event]


# shutdown feedbacks


def test_adc_registers_match_the_old_repo():
    # what the old max11335.py sent: it built 15 bits for the configuration, and bitstring padded a final 0
    assert configuration_word() == int("100000111000010" + "0", 2).to_bytes(2, "big")
    assert scan_word() == int("0010010100000110", 2).to_bytes(2, "big")


def test_a_result_holds_channel_and_value(cfg):
    channel, volts = parse_result(result(3, 4095), cfg.adc)
    assert channel == 3
    assert volts == pytest.approx(
        cfg.adc.vref * 4095 / 4096 * (cfg.adc.divider + cfg.adc.divider_correction), abs=0.01
    )


def test_board_reports_the_loop_in_order(board, cfg):
    adc = cfg.adc
    twelve_volts = round(12.0 / (adc.divider + adc.divider_correction) / adc.vref * 4096)  # raw ADC value
    board.adc.results = [result(0, twelve_volts), result(1, twelve_volts), result(2, 0)]
    board.hal.poll(0.0)
    loop = dict(board.hal.shutdown_loop())
    assert loop["supply"] == pytest.approx(12.0, abs=0.3)
    assert loop["charger"] == 0.0
    assert loop["BMS in"] is None  # no reading yet


def test_the_adc_is_configured_once_at_start(board):
    assert board.adc.sent[0] == configuration_word()


# buzzer


def test_a_melody_plays_over_time():
    player = Player()
    player.play(Sound.CONFIRM, now=10.0)
    assert player.frequency(10.01) == RE7
    assert player.frequency(10.07) is None  # the rest between the two beeps
    assert player.frequency(10.12) == RE7
    assert player.frequency(11.0) is None  # finished


def test_a_tick_never_cuts_a_melody():
    player = Player()
    player.play(Sound.ERROR, now=10.0)
    player.play(Sound.TICK, now=10.1)
    assert player.frequency(10.25) is not None  # the alarm goes on
    player.play(Sound.TICK, now=20.0)
    assert player.frequency(20.001) == RE7  # alone, it ticks


def test_board_drives_the_buzzer_while_polling(board):
    board.hal.play(Sound.CONFIRM)
    board.hal.poll(0.01)
    board.hal.poll(1.0)
    assert board.pwm.tones[-2:] == [RE7, None]
