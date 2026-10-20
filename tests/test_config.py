"""config.toml loads, and the checks catch values that would be dangerous on the handcart."""

import tomllib

import pytest
from pydantic import ValidationError

from shared import config
from shared.config import Config


@pytest.fixture
def raw() -> dict:
    return tomllib.loads(config.DEFAULT_PATH.read_text())


def test_the_repo_config_loads():
    cfg = config.load()
    assert cfg.accumulator.cells == 144
    assert cfg.can.primary_dbc.is_absolute()
    assert cfg.can.primary_dbc.exists()


def test_config_is_read_only():
    cfg = config.load()
    with pytest.raises(ValidationError):
        cfg.charge.current_max = 99  # type: ignore[misc]


def test_target_above_the_pack_limit_is_refused(raw):
    raw["charge"]["target_voltage_max"] = 700
    with pytest.raises(ValidationError, match="pack limit"):
        Config.model_validate(raw)


def test_default_outside_the_limits_is_refused(raw):
    raw["charge"]["target_voltage_default"] = raw["charge"]["target_voltage_max"] + 1
    with pytest.raises(ValidationError, match="target_voltage_default"):
        Config.model_validate(raw)


def test_a_pin_used_twice_is_refused(raw):
    raw["gpio"]["pon"] = raw["gpio"]["sd_relay"]
    with pytest.raises(ValidationError, match="assigned twice"):
        Config.model_validate(raw)


def test_unknown_keys_are_refused(raw):
    raw["charge"]["curent_max"] = 10
    with pytest.raises(ValidationError):
        Config.model_validate(raw)
