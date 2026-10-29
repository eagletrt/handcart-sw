"""The combination of the safe in front of the Debug window (frontend/safe.py), without any UI."""

from frontend.safe import COMBINATION, LEFT, NUMBERS, RIGHT, Dial

FIRST, SECOND, THIRD = COMBINATION


def to(dial: Dial, number: int, direction: int) -> None:
    """Turn the dial in that direction until the number is under the mark, at least one step."""
    dial.turn(direction)
    while dial.number != number:
        dial.turn(direction)


def test_right_left_right_then_the_handle_opens_it():
    dial = Dial()
    to(dial, FIRST, RIGHT)
    to(dial, SECOND, LEFT)
    to(dial, THIRD, RIGHT)
    assert dial.pull()


def test_the_wrong_directions_do_not_open_it():
    dial = Dial()
    to(dial, FIRST, LEFT)
    to(dial, SECOND, RIGHT)
    to(dial, THIRD, LEFT)
    assert not dial.pull()


def test_a_wrong_number_does_not_open_it():
    dial = Dial()
    to(dial, FIRST, RIGHT)
    to(dial, (SECOND + 1) % NUMBERS, LEFT)
    to(dial, THIRD, RIGHT)
    assert not dial.pull()


def test_only_the_last_three_turns_count():
    dial = Dial()
    to(dial, 5, RIGHT)
    to(dial, 7, LEFT)  # a wrong start
    to(dial, FIRST, RIGHT)
    to(dial, SECOND, LEFT)
    to(dial, THIRD, RIGHT)
    assert dial.pull()


def test_after_the_handle_it_starts_over():
    dial = Dial()
    to(dial, FIRST, RIGHT)
    to(dial, SECOND, LEFT)
    to(dial, THIRD, RIGHT)
    assert dial.pull()
    assert dial.turns == []
    assert not dial.pull()


def test_the_numbers_go_round():
    dial = Dial()
    dial.turn(-1)
    assert dial.number == NUMBERS - 1
    dial.turn(NUMBERS + 1)
    assert dial.number == 0
    assert dial.position == NUMBERS  # the dial keeps turning the same way on screen, past 0
