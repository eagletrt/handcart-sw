"""The handcart PCB logic, with fake peripherals: what BoardHal does with pins, SPI bytes and the buzzer."""

from dataclasses import dataclass

import pytest

from backend.hal.board import BoardHal
from backend.hal.controls import CLOCKWISE, Encoder
from backend.hal.fake import FakeHal
from backend.hal.feedback import configuration_word, parse_result, scan_word
from frontend.readings import first_open
from shared import scenario
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


def click(encoder: Encoder, clockwise: bool, start: tuple[bool, bool] = (True, True)) -> list[InputEvent]:
    """One click of the knob from its rest: A and B once round the cycle, one change at a time."""
    order = CLOCKWISE if clockwise else CLOCKWISE[::-1]
    position = order.index(start)
    events = []
    for step in range(1, len(order) + 1):
        before, after = order[(position + step - 1) % 4], order[(position + step) % 4]
        is_a = before[0] != after[0]
        events += encoder.change(is_a, after[0] if is_a else after[1])
    return events


def test_no_encoder_step_at_start(board):
    board.hal.poll(0.0)  # A and B at rest: not a turn
    assert board.hal.input_events() == []


@pytest.mark.parametrize("clockwise, event", [(True, InputEvent.TURN_CW), (False, InputEvent.TURN_CCW)])
def test_a_click_of_the_knob_is_one_step(clockwise, event):
    encoder = Encoder(True, True)
    assert click(encoder, clockwise) == [event]


def test_a_fast_turn_loses_no_step():
    encoder = Encoder(True, True)
    events = []
    for _ in range(50):
        events += click(encoder, clockwise=True)
    for _ in range(20):
        events += click(encoder, clockwise=False)
    assert events == [InputEvent.TURN_CW] * 50 + [InputEvent.TURN_CCW] * 20


def test_a_bouncing_contact_counts_nothing():
    encoder = Encoder(True, True)
    events = []
    for _ in range(5):  # A leaves the rest and comes back, a few times
        events += encoder.change(True, False)
        events += encoder.change(True, True)
    assert events == []


def test_the_same_level_twice_is_not_a_move():
    encoder = Encoder(True, True)
    assert encoder.change(True, True) == []
    assert click(encoder, clockwise=True) == [InputEvent.TURN_CW]


def test_the_rest_is_where_the_knob_was_at_the_start():
    encoder = Encoder(False, False)  # an encoder that rests with both low
    assert click(encoder, clockwise=True, start=(False, False)) == [InputEvent.TURN_CW]


def test_without_pigpiod_the_board_reads_the_encoder_at_each_tick(board, cfg):
    a, b = cfg.gpio.encoder_a, cfg.gpio.encoder_b
    events = []
    # clockwise from the rest: A goes down, B down, A up, B up (B rising with A high, as before pigpiod)
    for level_a, level_b in [(False, True), (False, False), (True, False), (True, True)]:
        board.gpio.levels[a], board.gpio.levels[b] = level_a, level_b
        board.hal.poll(0.0)
        events += board.hal.input_events()
    assert events == [InputEvent.TURN_CW]


class FakeEncoderPins:
    def __init__(self) -> None:
        self.waiting: list[tuple[bool, bool]] = []

    def levels(self) -> tuple[bool, bool]:
        return True, True

    def changes(self) -> list[tuple[bool, bool]]:
        changes, self.waiting = self.waiting, []
        return changes


def test_the_board_takes_every_change_since_the_last_tick(cfg):
    pins = FakeEncoderPins()
    hal = BoardHal(cfg, FakeGpio(), FakePwm(), FakeAdc(), pins, clock=lambda: 0.0)
    # three clicks clockwise between two ticks, as pigpiod collects them
    pins.waiting = [(True, False), (False, False), (True, True), (False, True)] * 3  # (it is A, high)
    hal.poll(0.0)
    assert hal.input_events() == [InputEvent.TURN_CW] * 3


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
    assert loop["mushroom"] == 0.0
    assert loop["charger"] is None  # no reading yet


def test_the_adc_is_configured_once_at_start(board):
    assert board.adc.sent[0] == configuration_word()


# buzzer


def test_the_buzzer_plays_the_frequency_asked(board):
    board.hal.set_buzzer(440.0)
    board.hal.set_buzzer(None)
    assert board.pwm.tones == [440.0, None]


def test_the_fake_loop_opens_where_the_scenario_says(tmp_path):
    path = tmp_path / "sim.json"
    hal = FakeHal(scenario_file=path)
    hal.set_relays(sd_relay_closed=True, charger_power=True, discharge=False)
    scenario.write(scenario.Scenario(shutdown_open_at="mushroom"), path)
    hal.poll(1.0)
    assert first_open(hal.shutdown_loop(), 2.0) == "mushroom"
    path.unlink()
    hal.poll(2.0)
    assert first_open(hal.shutdown_loop(), 2.0) is None


def test_an_open_tsms_reads_as_tsms(board, cfg):
    # on the handcart channel 4 is after the TSMS and channel 5 after the BMS
    adc = cfg.adc
    twelve_volts = round(12.0 / (adc.divider + adc.divider_correction) / adc.vref * 4096)
    # the ADC answers in channel order; only channel 4 has no voltage
    board.adc.results = [result(channel, 0 if channel == 4 else twelve_volts) for channel in range(6)]
    board.hal.poll(0.0)
    assert first_open(board.hal.shutdown_loop(), cfg.shutdown.open_below) == "TSMS"


def test_a_lost_loop_supply_reads_zero_not_the_last_value(board, cfg):
    adc = cfg.adc
    twelve_volts = round(12.0 / (adc.divider + adc.divider_correction) / adc.vref * 4096)
    board.adc.results = [result(channel, twelve_volts) for channel in range(6)]
    board.hal.poll(0.0)
    board.adc.results = [result(channel, 0) for channel in range(6)]  # 00 00 first: channel 0 at 0 V
    board.hal.poll(0.2)
    assert all(volts == 0.0 for _, volts in board.hal.shutdown_loop())


def test_a_reading_not_refreshed_becomes_unknown(cfg):
    now = 0.0
    gpio, pwm, adc = FakeGpio(), FakePwm(), FakeAdc()
    hal = BoardHal(cfg, gpio, pwm, adc, clock=lambda: now)
    adc.results = [result(0, 1000)]
    hal.poll(now)
    assert dict(hal.shutdown_loop())["supply"] is not None
    now = 2.0  # no scan since: say the SPI reads stopped
    assert dict(hal.shutdown_loop())["supply"] is None  # unknown, not stuck at its last value
