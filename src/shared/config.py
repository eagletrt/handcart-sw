"""Handcart configuration: config.toml loaded into typed, read-only sections and checked at startup."""

import tomllib
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATH = ROOT / "config.toml"
LOCAL_PATH = ROOT / "config.local.toml"  # optional, not in git: overrides for this machine


class _Section(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Network(_Section):
    backend_host: str
    backend_port: int = Field(gt=0, lt=65536)
    frontend_host: str
    frontend_port: int = Field(gt=0, lt=65536)


class Can(_Section):
    interface: str  # python-can interface: socketcan on the Pi, udp_multicast anywhere else
    bms_channel: str
    charger_channel: str
    primary_dbc: Path
    charger_dbc: Path

    @property
    def shared_bus(self) -> bool:
        return self.bms_channel == self.charger_channel


class Accumulator(_Section):
    cellboards: int = Field(gt=0)
    cells_per_cellboard: int = Field(gt=0)
    temps_per_cellboard: int = Field(gt=0)
    max_cell_voltage: float = Field(gt=0)
    min_cell_voltage: float = Field(gt=0)
    balancing_threshold: float = Field(gt=0)

    @property
    def cells(self) -> int:
        return self.cellboards * self.cells_per_cellboard

    @property
    def temps(self) -> int:
        return self.cellboards * self.temps_per_cellboard

    @property
    def max_pack_voltage(self) -> float:
        return self.cells * self.max_cell_voltage

    @model_validator(mode="after")
    def _cell_limits(self) -> Self:
        if self.min_cell_voltage >= self.max_cell_voltage:
            raise ValueError("min_cell_voltage must be below max_cell_voltage")
        return self


class Charge(_Section):
    target_voltage_min: float = Field(gt=0)
    target_voltage_max: float = Field(gt=0)
    target_voltage_default: float = Field(gt=0)
    current_max: float = Field(gt=0)
    current_default: float = Field(gt=0)

    @model_validator(mode="after")
    def _defaults_within_limits(self) -> Self:
        if not self.target_voltage_min <= self.target_voltage_default <= self.target_voltage_max:
            raise ValueError(
                "target_voltage_default must be between target_voltage_min and target_voltage_max"
            )
        if self.current_default > self.current_max:
            raise ValueError("current_default must not exceed current_max")
        return self


class Timing(_Section):
    bms_presence_timeout: float = Field(gt=0)
    charger_presence_timeout: float = Field(gt=0)
    bms_response_timeout: float = Field(gt=0)
    charger_stop_delay: float = Field(gt=0)
    ecu_heartbeat_period: float = Field(gt=0)
    bms_command_period: float = Field(gt=0)
    charger_ctrl_period: float = Field(gt=0)
    charger_alive_period: float = Field(gt=0)
    charger_target_period: float = Field(gt=0)


class Shutdown(_Section):
    closed_above: float = Field(gt=0)
    open_below: float = Field(ge=0)

    @model_validator(mode="after")
    def _thresholds_in_order(self) -> Self:
        if self.open_below >= self.closed_above:
            raise ValueError("open_below must be below closed_above")
        return self


class Hardware(_Section):
    simulated: bool


class GpioPins(_Section):
    buzzer: int
    discharge_relay: int
    pon: int
    sd_relay: int
    button_up: int
    button_down: int
    button_left: int
    button_right: int
    encoder_press: int
    encoder_a: int
    encoder_b: int

    @model_validator(mode="after")
    def _no_shared_pins(self) -> Self:
        pins = list(self.model_dump().values())
        if len(pins) != len(set(pins)):
            raise ValueError(f"a GPIO pin is assigned twice: {sorted(pins)}")
        return self


class Adc(_Section):
    spi_bus: int
    spi_device: int
    spi_mode: int
    spi_max_speed_hz: int = Field(gt=0)
    vref: float = Field(gt=0)
    divider: float = Field(gt=0)
    divider_correction: float


class Auth(_Section):
    session_timeout: float = Field(gt=0)
    max_pin_failures: int = Field(gt=0)
    lockout: float = Field(gt=0)
    users_file: Path
    audit_log: Path


class Config(_Section):
    network: Network
    can: Can
    accumulator: Accumulator
    charge: Charge
    timing: Timing
    shutdown: Shutdown
    hardware: Hardware
    gpio: GpioPins
    adc: Adc
    auth: Auth

    @model_validator(mode="after")
    def _target_fits_the_pack(self) -> Self:
        pack = self.accumulator
        if self.charge.target_voltage_max > pack.max_pack_voltage:
            raise ValueError(
                f"target_voltage_max {self.charge.target_voltage_max} V is above the pack limit "
                f"{pack.max_pack_voltage:.1f} V ({pack.cells} cells x {pack.max_cell_voltage} V)"
            )
        return self


def load(path: Path = DEFAULT_PATH, local: Path = LOCAL_PATH) -> Config:
    """Read and validate a config file, with the keys of the local file, if any, on top.

    Relative paths are relative to the config file.
    """
    data = tomllib.loads(path.read_text())
    if local.exists():
        for section, values in tomllib.loads(local.read_text()).items():
            data.setdefault(section, {}).update(values)
    base = path.resolve().parent
    for section, keys in (("can", ("primary_dbc", "charger_dbc")), ("auth", ("users_file", "audit_log"))):
        for key in keys:
            if key in data.get(section, {}):
                data[section][key] = base / data[section][key]
    return Config.model_validate(data)
