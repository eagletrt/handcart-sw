"""Knowing when a periodic frame is due again."""

import math


class Periodic:
    def __init__(self) -> None:
        self._last_sent: dict[str, float] = {}

    def due(self, name: str, period: float, now: float) -> bool:
        """True once every `period` seconds for each name."""
        if now - self._last_sent.get(name, -math.inf) < period:
            return False
        self._last_sent[name] = now
        return True
