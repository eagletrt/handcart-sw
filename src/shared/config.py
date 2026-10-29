"""Handcart configuration: config.toml loaded into typed, read-only sections and checked at startup."""

import ipaddress
import tomllib
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATH = ROOT / "config.toml"
LOCAL_PATH = ROOT / "config.local.toml"  # optional, not in git: overrides for this machine
# files in var/ (not in git); the ones the display reads are explained in frontend/local_files.py
BACKEND_ERROR_FILE = ROOT / "var" / "backend-error.txt"  # why the backend stopped; shown by the frontend
SETTINGS_FILE = ROOT / "var" / "settings.json"  # the operator's setpoints, kept across restarts
BUZZER_FILE = ROOT / "var" / "buzzer.json"  # the buzzer's resonance, found by ear in the Debug window
RECORD_FILE = ROOT / "var" / "record.db"  # what happened and how the charges went (backend/recorder.py)
HOTSPOT_FILE = ROOT / "var" / "hotspot.json"  # the hotspot's name and password, once changed on the screen
# written by ./handcart.py update (handcart.py has the same paths): the step it is at, and how it ended
UPDATE_STEP_FILE = ROOT / "var" / "update-step.txt"
LAST_UPDATE_FILE = ROOT / "var" / "last-update.txt"


class _Section(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Network(_Section):
    backend_host: str
    backend_port: int = Field(gt=0, lt=65536)
    frontend_host: str
    frontend_port: int = Field(gt=0, lt=65536)

    @model_validator(mode="after")
    def _only_this_machine(self) -> Self:
        """There is no login yet: anyone reaching the API or the UI could turn the HV on."""
        for name, host in (("backend_host", self.backend_host), ("frontend_host", self.frontend_host)):
            if not _is_this_machine(host):
                raise ValueError(f"{name} must stay 127.0.0.1 until there is a login, not {host}")
        return self


def _is_this_machine(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:  # a name, e.g. pi.local: it can be reached from the network
        return False


class Hotspot(_Section):
    """The hotspot's name and password until they are changed on the screen (then HOTSPOT_FILE)."""

    ssid: str = Field(min_length=1, max_length=32)  # what a Wi-Fi network name can be
    password: str = Field(min_length=8, max_length=63)  # what a WPA password can be


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
    balancing_threshold: float = Field(gt=0)  # the default
    balancing_threshold_min: float = Field(gt=0)
    balancing_threshold_max: float = Field(gt=0)
    cold_temperature: float
    warm_temperature: float
    max_temperature: float

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
        if not self.balancing_threshold_min <= self.balancing_threshold <= self.balancing_threshold_max:
            raise ValueError("balancing_threshold must be between balancing_threshold_min and _max")
        if not self.cold_temperature < self.warm_temperature < self.max_temperature:
            raise ValueError("temperatures must be in order: cold < warm < max")
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
    precharge_timeout: float = Field(gt=0)
    charger_stop_delay: float = Field(gt=0)
    bms_repeat_period: float = Field(gt=0)
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


class Update(_Section):
    remote: str
    branch: str
    health_timeout: float = Field(gt=0)


class Auth(_Section):
    session_timeout: float = Field(gt=0)
    max_pin_failures: int = Field(gt=0)
    lockout: float = Field(gt=0)
    users_file: Path
    audit_log: Path


class Config(_Section):
    network: Network
    hotspot: Hotspot
    can: Can
    accumulator: Accumulator
    charge: Charge
    timing: Timing
    shutdown: Shutdown
    hardware: Hardware
    gpio: GpioPins
    adc: Adc
    update: Update
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


def hardware_is_simulated(cfg: Config) -> bool:
    """True off the Pi, or when the config asks for simulated hardware: fake board, simulator, /debug page."""
    model = Path("/proc/device-tree/model")
    on_raspberry_pi = model.exists() and "Raspberry Pi" in model.read_text()
    return cfg.hardware.simulated or not on_raspberry_pi
