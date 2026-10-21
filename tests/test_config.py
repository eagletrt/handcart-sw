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


def test_a_local_file_overrides_single_keys(tmp_path):
    local = tmp_path / "config.local.toml"
    local.write_text('[can]\ninterface = "udp_multicast"\n')
    cfg = config.load(local=local)
    assert cfg.can.interface == "udp_multicast"
    assert cfg.can.bms_channel == "can0"  # untouched keys keep the repo value


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.4.1", "pi.local"])
def test_the_api_and_the_ui_stay_on_this_machine_until_there_is_a_login(raw, host):
    raw["network"]["backend_host"] = host
    with pytest.raises(ValidationError, match="until there is a login"):
        Config.model_validate(raw)
    raw["network"]["backend_host"] = "127.0.0.1"
    raw["network"]["frontend_host"] = host
    with pytest.raises(ValidationError, match="until there is a login"):
        Config.model_validate(raw)
