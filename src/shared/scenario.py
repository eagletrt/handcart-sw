"""What the debug page (/debug) asks of the simulated hardware: open loop, faults, unplugged devices.

Kept in var/sim.json. The debug page writes it; the simulator (BMS and charger) and the backend's FakeHal
(shutdown loop) read it a few times a second. Only with simulated hardware: the real board never reads it.
"""

from pathlib import Path

from pydantic import BaseModel

from shared.config import ROOT

SCENARIO_FILE = ROOT / "var" / "sim.json"


class Scenario(BaseModel):
    shutdown_open_at: str | None = None  # a point of the loop, as in backend.hal.feedback.LOOP_CHANNELS
    bms_unplugged: bool = False  # the BMS sends nothing
    charger_unplugged: bool = False  # the charger sends nothing
    bms_fault: bool = False  # the BMS reports overvoltage in TsacMainboardError
    charger_error: bool = False  # the charger reports the ERROR state
    high_cell: bool = False  # one cell above the 4.20 V limit
    hot_cell: bool = False  # one temperature probe above the limit


def read(path: Path = SCENARIO_FILE) -> Scenario:
    """The scenario in the file; a normal one if there is no file or it cannot be read."""
    try:
        return Scenario.model_validate_json(path.read_text())
    except (FileNotFoundError, ValueError):  # ValueError: half written, or edited by hand wrong
        return Scenario()


def write(scenario: Scenario, path: Path = SCENARIO_FILE) -> None:
    path.parent.mkdir(exist_ok=True)
    draft = path.with_suffix(".new")
    draft.write_text(scenario.model_dump_json(indent=2))
    draft.replace(path)  # in one step: a reader never sees half a file
