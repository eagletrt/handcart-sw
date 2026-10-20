"""A CAN frame as the rest of the backend sees it, independent of python-can."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Frame:
    id: int
    data: bytes
