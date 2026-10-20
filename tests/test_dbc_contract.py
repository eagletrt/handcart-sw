"""Contract between the handcart and the DBC files in the submodules.

If libcan or the charger DBC rename or drop something the handcart relies on,
these tests fail before the code does.
"""

import pytest

from backend.devices.charger import RAW_MESSAGES
from shared import config

CELLBOARDS = config.load().accumulator.cellboards

PRIMARY_REQUIRED: dict[str, set[str]] = {
    # commands the handcart sends to the accumulator
    "BmsSet": {"status"},
    "EcuFsm": {"vehicleStatus", "krakenStatus"},
    "RaspberryTsacBalancingSet": {"start", "threshold"},
    # accumulator telemetry
    "TsacStatus": {"mainboardStatus"},
    "TsacMainboardVoltageInfo": {"ts", "total", "cellSum", "average", "min", "max"},
    "TsacMainboardCurrentInfo": {"current", "power"},
    "TsacMainboardTemperatureInfo": {"min", "max", "average"},
    "TsacMainboardError": set(),
    "TsacMainboardFeedback": {"tsLessThan60V"},
    "TsacCellboardErrorA": set(),
    "TsacCellboardErrorB": set(),
    "TsacCellboardErrorC": set(),
    **{f"TsacCellboard{i}Voltage": {"group"} for i in range(1, CELLBOARDS + 1)},
    **{f"TsacCellboard{i}Temperature": {"group"} for i in range(1, CELLBOARDS + 1)},
    **{f"TsacCellboard{i}Balancing": set() for i in range(1, CELLBOARDS + 1)},
}

CHARGER_REQUIRED: dict[str, set[str]] = {
    "HYC_Ctrl": {"ctrlCmd"},
    "HYC_Status": {"status"},
    "HYC_Target": {"uTarget", "iTarget"},
    "HYC_Actual": {"uActual", "iActual"},
    "HYC_Alive": {"AliveCnt", "fanMin", "fanMax"},
    "HYC_Grid_Voltage": {"u1", "u2", "u3", "f"},
    "HYC_Temperature": set(),
    "HYC_Maintenance2": set(),
    "HYC_Version": set(),
    "HYC_Error": set(),
    "HYC_Warning": set(),
}

# The BMS states the charge sequence waits for.
TSAC_STATES = {"IDLE", "ERROR", "BALANCING", "AIRN_CHECK", "PRECHARGE", "AIRP_CHECK", "TS_ON"}


def _missing(db, required: dict[str, set[str]]) -> list[str]:
    names = {m.name: m for m in db.messages}
    problems = []
    for message, signals in required.items():
        if message not in names:
            problems.append(message)
            continue
        have = {s.name for s in names[message].signals}
        problems += [f"{message}.{s}" for s in sorted(signals - have)]
    return problems


def test_primary_has_what_the_handcart_uses(primary):
    assert _missing(primary, PRIMARY_REQUIRED) == []


def test_charger_has_what_the_handcart_uses(charger_db):
    assert _missing(charger_db, CHARGER_REQUIRED) == []


def test_tsac_status_states(primary):
    signal = next(s for s in primary.get_message_by_name("TsacStatus").signals if s.name == "mainboardStatus")
    assert {str(v) for v in signal.choices.values()} >= TSAC_STATES


def test_cell_count_matches_the_dbc(primary, cfg):
    cells = {s.name for s in primary.get_message_by_name("TsacCellboard1Voltage").signals} - {"group"}
    assert len(cells) == cfg.accumulator.cells_per_cellboard


def test_no_signal_is_scaled_to_zero(primary, charger_db):
    """A scale of 0 turns every value into 0. LittleSIC's flag messages have it and are decoded raw."""
    zero = [
        f"{m.name}.{s.name}"
        for db in (primary, charger_db)
        for m in db.messages
        if m.name not in RAW_MESSAGES
        for s in m.signals
        if s.scale == 0
    ]
    assert zero == []


@pytest.mark.xfail(
    strict=True,
    reason="HYC_Error (0x1A0) collides with TsacMainboardShutdown: the charger needs new IDs on a shared bus",
)
def test_no_id_collisions_on_a_shared_bus(primary, charger_db, cfg):
    if not cfg.can.shared_bus:
        pytest.skip("charger on its own bus")
    primary_ids = {m.frame_id: m.name for m in primary.messages}
    clashes = [
        f"{m.name} / {primary_ids[m.frame_id]} at {m.frame_id:#x}"
        for m in charger_db.messages
        if m.frame_id in primary_ids
    ]
    assert clashes == []
