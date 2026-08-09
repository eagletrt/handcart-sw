from datetime import datetime

from common.logging import tprint, P_TYPE
from settings import *


class ACCUMULATOR(Enum):
    FENICE = 2


def _as_int(v):
    """Return the integer value of a cantools signal, whether it is a plain int or a NamedSignalValue."""
    return int(v.value) if hasattr(v, "value") else int(v)


def _cellboard_index(msg) -> int:
    """
    0-based cellboard index parsed from the message name (``TsacCellboard{N}...`` -> N-1).
    """
    name = dbc_primary.get_message_by_frame_id(msg.arbitration_id).name
    digits = "".join(c for c in name if c.isdigit())
    return int(digits) - 1


class BMS_HV:
    """
    Class that stores and processes all the data of the accumulator (TSAC).
    """

    ACC_CONNECTED = ACCUMULATOR.FENICE  # Default Fenice, keep for other future BMS

    lastupdated = 0

    hv_voltage_history = []
    hv_voltage_history_index = 0
    hv_current_history = []
    hv_current_history_index = 0
    hv_temp_history = []
    hv_temp_history_index = 0

    hv_cells_act = [0 for i in range(ACC_CELLS_VOLTAGES_COUNT)]
    hv_temps_act = [0 for j in range(ACC_CELLS_TEMPS_COUNT)]

    charged_capacity_ah = 0
    charged_capacity_wh = 0
    act_pack_voltage = -1
    act_bus_voltage = -1
    act_current = -1
    act_power = -1
    max_cell_voltage = -1
    min_cell_voltage = -1
    avg_cell_voltage = -1
    error = False
    errors = bms_errors
    feedbacks = bms_feedbacks
    error_str = ""
    status = HvStatus.INIT
    act_cell_delta = 0
    chg_status = -1
    req_chg_current = 0
    req_chg_voltage = 0
    act_average_temp = -1
    min_temp = -1
    max_temp = -1
    last_hv_current = datetime.now().isoformat()
    is_balancing = Toggle.OFF
    balancing_cells = []

    sum_cell = 0

    cellboard_versions = {}  # id: {"version": "", "build":""}

    def isConnected(self):
        """
        Check if BMS_HV is connected
        :return: True if BMS_HV is connected
        """
        if self.lastupdated == 0:
            return False
        else:
            return (datetime.now() - datetime.fromisoformat(str(self.lastupdated))).seconds \
                < CAN_ACC_PRESENCE_TIMEOUT

    def doTSAC_STATUS(self, msg):
        """
        Processes the TsacStatus CAN message (mainboard FSM state).
        The mainboard reports BALANCING as one of its states, so we derive the
        balancing flag from it.
        """
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()
        message = dbc_primary.decode_message(msg.arbitration_id, msg.data)

        self.status = HvStatus(_as_int(message.get("mainboardStatus")))
        self.is_balancing = Toggle.ON if self.status == HvStatus.BALANCING else Toggle.OFF

    def doTSAC_MB_VOLTAGE(self, msg):
        """
        Processes TsacMainboardVoltageInfo: pack/bus/cell-sum voltages plus the
        min/max/avg cell voltages (which used to live in HV_CELLS_VOLTAGE_STATS).
        """
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()
        message = dbc_primary.decode_message(msg.arbitration_id, msg.data)

        self.act_pack_voltage = round(message.get("total"), 2)
        self.act_bus_voltage = round(message.get("ts"), 2)
        self.sum_cell = round(message.get("cellSum"), 2)
        self.max_cell_voltage = round(message.get("max"), 3)
        self.min_cell_voltage = round(message.get("min"), 3)
        self.avg_cell_voltage = round(message.get("average"), 3)
        self.act_cell_delta = round(self.max_cell_voltage - self.min_cell_voltage, 3)

    def doTSAC_MB_CURRENT(self, msg):
        """
        Processes TsacMainboardCurrentInfo (pack current and power).
        """
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()
        message = dbc_primary.decode_message(msg.arbitration_id, msg.data)

        self.act_current = abs(round(message.get("current"), 2))
        self.act_power = round(message.get("power"), 2)

    def doTSAC_MB_TEMP(self, msg):
        """
        Processes TsacMainboardTemperatureInfo (cell temperature stats).
        """
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()
        message = dbc_primary.decode_message(msg.arbitration_id, msg.data)

        self.act_average_temp = round(message.get("average"), 2)
        self.min_temp = round(message.get("min"), 2)
        self.max_temp = round(message.get("max"), 2)

    def doTSAC_MB_ERROR(self, msg):
        """
        Processes TsacMainboardError, storing the raised errors.
        """
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()
        message = dbc_primary.decode_message(msg.arbitration_id, msg.data)

        for name, value in message.items():
            try:
                self.errors[name] = _as_int(value)
                if self.errors[name] != 0:
                    tprint(f"TSAC error {name}", P_TYPE.ERROR)
            except (KeyError, TypeError):
                pass

    def doTSAC_MB_FEEDBACK(self, msg):
        """
        Processes TsacMainboardFeedback, storing the raw feedback values.
        """
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()
        message = dbc_primary.decode_message(msg.arbitration_id, msg.data)

        for name, value in message.items():
            try:
                self.feedbacks[name] = value
            except Exception:
                pass

    def doTSAC_CELLBOARD_VOLTAGE(self, msg):
        """
        Processes a TsacCellboard{N}Voltage frame (multiplexed by ``group``) and
        writes the decoded cells into the flat hv_cells_act array.
        """
        try:
            message = dbc_primary.decode_message(msg.arbitration_id, msg.data)
            self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()
        except ValueError:
            tprint(f"ValueError in doTSAC_CELLBOARD_VOLTAGE, msg data: {msg.data}", P_TYPE.ERROR)
            return

        base = _cellboard_index(msg) * ACC_CELLS_VOLTAGES_PER_SEGMENT
        for name, value in message.items():
            if not name.startswith("cell"):
                continue
            idx = base + int(name[4:]) - 1
            if 0 <= idx < ACC_CELLS_VOLTAGES_COUNT:
                self.hv_cells_act[idx] = round(value, 3)

    def doTSAC_CELLBOARD_TEMP(self, msg):
        """
        Processes a TsacCellboard{N}Temperature frame (multiplexed by ``group``) and
        writes the decoded temperatures into the flat hv_temps_act array.
        """
        try:
            message = dbc_primary.decode_message(msg.arbitration_id, msg.data)
            self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()
        except ValueError:
            tprint(f"ValueError in doTSAC_CELLBOARD_TEMP, msg data: {msg.data}", P_TYPE.ERROR)
            return

        base = _cellboard_index(msg) * ACC_CELLS_TEMPS_PER_SEGMENT
        for name, value in message.items():
            if not name.startswith("cell"):
                continue
            idx = base + int(name[4:]) - 1
            if 0 <= idx < ACC_CELLS_TEMPS_COUNT:
                self.hv_temps_act[idx] = round(value, 3)

    def doTSAC_CELLBOARD_BALANCING(self, msg):
        """
        Processes a TsacCellboard{N}Balancing frame, updating the list of cells that
        are currently being discharged (global cell indexes).
        """
        try:
            message = dbc_primary.decode_message(msg.arbitration_id, msg.data)
            self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()
        except ValueError:
            tprint(f"ValueError in doTSAC_CELLBOARD_BALANCING, msg data: {msg.data}", P_TYPE.ERROR)
            return

        base = _cellboard_index(msg) * ACC_CELLS_VOLTAGES_PER_SEGMENT
        # drop the previous state of this cellboard, then append the cells being balanced
        self.balancing_cells = [c for c in self.balancing_cells
                                if not (base <= c < base + ACC_CELLS_VOLTAGES_PER_SEGMENT)]
        for name, value in message.items():
            if name.startswith("cell") and _as_int(value) != 0:
                self.balancing_cells.append(base + int(name[4:]) - 1)

    def doTSAC_CELLBOARD_VERSION(self, msg):
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()
        message = dbc_primary.decode_message(msg.arbitration_id, msg.data)
        self.cellboard_versions[_cellboard_index(msg)] = {
            "version": f"{message.get('major')}.{message.get('minor')}.{message.get('patch')}"
        }

    def doTSAC_MB_VERSION(self, msg):
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()
        dbc_primary.decode_message(msg.arbitration_id, msg.data)
