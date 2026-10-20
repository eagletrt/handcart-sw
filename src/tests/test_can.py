"""
Tests for the primary-CAN handling after the libcan-sw swap.

These exercise the encode/decode paths only, so they run without any CAN hardware
(they build frames straight from the dbc and feed them to the decoders).
"""
import sys
import time
from os.path import dirname, realpath

# Make ``settings`` / ``common`` importable no matter the cwd pytest is invoked from
SRC = dirname(dirname(realpath(__file__)))
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from settings import dbc_primary, ACC_CELLS_VOLTAGES_PER_SEGMENT, ACC_BALANCING_THRESHOLD
from common.accumulator.bms import BMS_HV
from common.can_classes import (
    HvStatus, Toggle,
    primary_ID_BMS_SET, primary_ID_RASPBERRY_BALANCING_SET, primary_ID_ECU_STATUS,
)


class FakeMsg:
    """Minimal stand-in for a python-can Message (what the BMS decoders touch)."""

    def __init__(self, arbitration_id, data, timestamp=None):
        self.arbitration_id = arbitration_id
        self.data = data
        self.timestamp = time.time() if timestamp is None else timestamp


def _frame(name: str, signals: dict) -> FakeMsg:
    m = dbc_primary.get_message_by_name(name)
    return FakeMsg(m.frame_id, m.encode(signals))


def test_primary_has_expected_messages():
    for name in ["TsacStatus", "TsacMainboardVoltageInfo", "TsacMainboardCurrentInfo",
                 "TsacMainboardTemperatureInfo", "TsacMainboardError", "TsacMainboardFeedback",
                 "TsacCellboard1Voltage", "TsacCellboard1Temperature", "TsacCellboard1Balancing",
                 "BmsSet", "RaspberryBalancingSet"]:
        assert dbc_primary.get_message_by_name(name) is not None


def _status_frame(mainboard_status: int) -> FakeMsg:
    return _frame("TsacStatus", {
        "mainboardStatus": mainboard_status,
        "cellboard1Status": 1, "cellboard2Status": 1, "cellboard3Status": 1,
        "cellboard4Status": 1, "cellboard5Status": 1, "cellboard6Status": 1,
    })


def test_tsac_status_decode():
    bms = BMS_HV()

    bms.doTSAC_STATUS(_status_frame(HvStatus.TS_ON.value))
    assert bms.status == HvStatus.TS_ON
    assert bms.is_balancing == Toggle.OFF

    bms.doTSAC_STATUS(_status_frame(HvStatus.BALANCING.value))
    assert bms.status == HvStatus.BALANCING
    assert bms.is_balancing == Toggle.ON


def test_mainboard_voltage_decode():
    bms = BMS_HV()
    bms.doTSAC_MB_VOLTAGE(_frame("TsacMainboardVoltageInfo", {
        "ts": 400, "total": 410, "cellSum": 405, "average": 3.8, "min": 3.5, "max": 4.0,
    }))
    assert bms.act_pack_voltage == 410
    assert bms.act_bus_voltage == 400
    assert abs(bms.min_cell_voltage - 3.5) < 1e-6
    assert abs(bms.max_cell_voltage - 4.0) < 1e-6
    assert abs(bms.act_cell_delta - 0.5) < 1e-6


def test_mainboard_current_decode():
    bms = BMS_HV()
    bms.doTSAC_MB_CURRENT(_frame("TsacMainboardCurrentInfo", {"current": 12.3, "power": 5.0}))
    assert abs(bms.act_current - 12.3) < 0.1  # abs value, 0.1 A resolution
    assert abs(bms.act_power - 5.0) < 0.1


def test_cellboard_voltage_placed_at_right_index():
    bms = BMS_HV()
    # Cellboard 3 (index 2), multiplexer group 0 carries cell1..cell6
    m = dbc_primary.get_message_by_name("TsacCellboard3Voltage")
    data = m.encode({"group": 0, "cell1": 3.1, "cell2": 3.2, "cell3": 3.3,
                     "cell4": 3.4, "cell5": 3.5, "cell6": 3.6})
    bms.doTSAC_CELLBOARD_VOLTAGE(FakeMsg(m.frame_id, data))

    base = 2 * ACC_CELLS_VOLTAGES_PER_SEGMENT
    assert abs(bms.hv_cells_act[base + 0] - 3.1) < 1e-3
    assert abs(bms.hv_cells_act[base + 5] - 3.6) < 1e-3


def test_cellboard_balancing_collects_cells():
    bms = BMS_HV()
    bms.balancing_cells = []
    m = dbc_primary.get_message_by_name("TsacCellboard1Balancing")
    signals = {f"cell{i}": 0 for i in range(1, 25)}
    signals["cell1"] = 1
    signals["cell5"] = 1
    bms.doTSAC_CELLBOARD_BALANCING(FakeMsg(m.frame_id, m.encode(signals)))
    assert 0 in bms.balancing_cells   # cell1 -> index 0
    assert 4 in bms.balancing_cells   # cell5 -> index 4


def test_bms_set_roundtrip():
    m = dbc_primary.get_message_by_frame_id(primary_ID_BMS_SET)
    data = m.encode({"status": Toggle.ON.value})
    assert int(dbc_primary.decode_message(primary_ID_BMS_SET, data)["status"]) == 1


def test_raspberry_balancing_set_roundtrip():
    m = dbc_primary.get_message_by_frame_id(primary_ID_RASPBERRY_BALANCING_SET)
    data = m.encode({"start": Toggle.ON.value, "target": 3.5, "threshold": ACC_BALANCING_THRESHOLD / 1000.0})
    dec = dbc_primary.decode_message(primary_ID_RASPBERRY_BALANCING_SET, data)
    assert int(dec["start"]) == 1
    assert abs(dec["target"] - 3.5) < 0.005
    assert abs(dec["threshold"] - ACC_BALANCING_THRESHOLD / 1000.0) < 0.005


def test_ecu_status_heartbeat_roundtrip():
    # Same payload the FSM heartbeat sends every CAN_ECU_STATUS_INTERVAL: ECU "idle"
    m = dbc_primary.get_message_by_frame_id(primary_ID_ECU_STATUS)
    data = m.encode({"vehicleStatus": 1, "krakenStatus": 2})
    dec = dbc_primary.decode_message(primary_ID_ECU_STATUS, data)
    assert str(dec["vehicleStatus"]) == "IDLE"
    assert str(dec["krakenStatus"]) == "IDLE"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("all tests passed")
