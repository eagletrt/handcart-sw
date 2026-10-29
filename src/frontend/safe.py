"""The combination of the safe in front of the Debug window. Plain logic, no UI (tests/test_safe.py).

As on a real safe: the dial is turned right to the first number, left to the second, right to the third,
then the handle is pulled. Turning the other way sets the number the dial stopped on; only the last three
turns count, so a wrong start is fixed by just going on. Right or wrong, pulling the handle starts over.
"""

NUMBERS = 20  # on the dial, 0 to 19: one for each step of the encoder, so one turn of it is one of the dial
COMBINATION = (5, 10, 15)  # a simple one for now, to try the safe out: right to 5, left to 10, right to 15
RIGHT, LEFT = 1, -1  # right: clockwise, the numbers under the mark go up


class Dial:
    def __init__(self) -> None:
        self.position = 0  # steps turned right since the start, minus those turned left
        self.turns: list[tuple[int, int]] = []  # the last turns, oldest first: (direction, where it stopped)

    @property
    def number(self) -> int:
        """The number under the mark."""
        return self.position % NUMBERS

    def turn(self, steps: int) -> None:
        """Turn the dial: steps to the right if positive, to the left if negative."""
        if steps == 0:
            return
        direction = RIGHT if steps > 0 else LEFT
        self.position += steps
        if self.turns and self.turns[-1][0] == direction:
            self.turns[-1] = (direction, self.number)  # the same turn, further on
        else:
            self.turns.append((direction, self.number))
        del self.turns[: -len(COMBINATION)]

    def pull(self) -> bool:
        """Pull the handle: whether the combination is right. Then the turns start over."""
        right = self.turns == [(RIGHT, COMBINATION[0]), (LEFT, COMBINATION[1]), (RIGHT, COMBINATION[2])]
        self.turns = []
        return right
