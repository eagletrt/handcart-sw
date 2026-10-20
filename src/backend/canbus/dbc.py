"""DBC files: loading them, and turning frames into signal values and back."""

from pathlib import Path
from typing import Any

import cantools
from cantools.database.can import Database

from backend.canbus.frame import Frame

Signals = dict[str, Any]


def load_dbc(path: Path) -> Database:
    if not path.exists():
        raise FileNotFoundError(f"{path} not found: run ./handcart.py setup to fetch the submodules")
    db = cantools.database.load_file(path)
    if not isinstance(db, Database):
        raise TypeError(f"{path} is not a CAN database")
    return db


def decode(db: Database, frame: Frame, scaling: bool = True) -> Signals:
    """Signal values of a frame. Raises cantools.DecodeError if the frame is malformed."""
    signals = db.decode_message(frame.id, frame.data, scaling=scaling)
    if not isinstance(signals, dict):  # container messages decode to a list; the handcart uses none
        raise TypeError(f"frame {frame.id:#x} is a container message")
    return signals


def encode(db: Database, message: str, **signals: Any) -> Frame:
    m = db.get_message_by_name(message)
    return Frame(m.frame_id, bytes(m.encode(signals)))


def as_float(value: Any) -> float:
    """A decoded signal as a number, also when the DBC gives it named choices."""
    return float(getattr(value, "value", value))
