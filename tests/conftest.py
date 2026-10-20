"""Shared fixtures: the repo config, the real DBC files, a clock the tests move by hand."""

from collections.abc import Callable
from typing import Any

import pytest
from cantools.database.can import Database

from backend.canbus import Frame, load_dbc
from shared import config
from shared.config import Config


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture(scope="session")
def cfg() -> Config:
    return config.load()


@pytest.fixture(scope="session")
def primary(cfg: Config) -> Database:
    return load_dbc(cfg.can.primary_dbc)


@pytest.fixture(scope="session")
def charger_db(cfg: Config) -> Database:
    return load_dbc(cfg.can.charger_dbc)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


MakeFrame = Callable[..., Frame]


def _frame_maker(db: Database) -> MakeFrame:
    def make(message: str, raw: bool = False, **signals: Any) -> Frame:
        m = db.get_message_by_name(message)
        return Frame(m.frame_id, bytes(m.encode(signals, scaling=not raw)))

    return make


@pytest.fixture(scope="session")
def bms_frame(primary: Database) -> MakeFrame:
    """Build a frame the BMS would send, by message name and signal values."""
    return _frame_maker(primary)


@pytest.fixture(scope="session")
def charger_frame(charger_db: Database) -> MakeFrame:
    """Build a frame the charger would send, by message name and signal values."""
    return _frame_maker(charger_db)
