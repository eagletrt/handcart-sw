from datetime import datetime

from common.logging import tprint, P_TYPE
from settings import *


class ACCUMULATOR(Enum):
    FENICE = 2


class BMS_HV:
    """
    Class that stores and processes all the data of the BMS_HV
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
    fans_override_status = Toggle.OFF
    fans_override_speed = 0
    balancing_cells = []

    fans_set_override_speed = 0
    fans_set_override_status = Toggle.OFF

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

    def doHV_TOTAL_VOLTAGE(self, msg):
        """
        Processes th HV_VOLTAGE CAN message from BMS_HV
        :param msg: the HV_VOLTAGE CAN message
        """

        # self.ACC_CONNECTED = ACCUMULATOR.FENICE
        # someway somehow you have to extract:
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()

        message = dbc_primary.decode_message(msg.arbitration_id, msg.data)

        self.act_pack_voltage = round(message.get("pack"), 2)
        self.act_bus_voltage = round(message.get("bus"), 2)
        self.sum_cell = round(message.get("sum_cell"), 2)

        """
        self.hv_voltage_history.append({"timestamp": self.lastupdated,
                                        "pack_voltage": self.act_pack_voltage,
                                        "bus_voltage": self.act_bus_voltage,
                                        "max_cell_voltage": self.max_cell_voltage,
                                        "min_cell_voltage": self.max_cell_voltage})

        self.hv_voltage_history_index += 1
        """

    def doHV_ENERGY(self, msg):
        """
        Processes the HV_CURRENT CAN message from BMS_HV
        :param msg: the HV_CURRENT CAN message
        """
        # self.ACC_CONNECTED = ACCUMULATOR.FENICE

        message = dbc_primary.decode_message(msg.arbitration_id, msg.data)

        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()
        self.act_current = abs(round(message.get("energy"), 2))

    def doHV_CURRENT(self, msg):
        """
        Processes the HV_CURRENT CAN message from BMS_HV
        :param msg: the HV_CURRENT CAN message
        """
        # self.ACC_CONNECTED = ACCUMULATOR.FENICE

        message = dbc_primary.decode_message(msg.arbitration_id, msg.data)

        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()
        self.act_current = abs(round(message.get("current"), 2))

        """
        self.hv_current_history.append({
            "timestamp": self.lastupdated,
            "current": self.act_current,
            "power": self.act_power
        })
        self.hv_current_history_index += 1
        

        if self.act_current != 0:
            delta = (datetime.fromisoformat(self.lastupdated) - datetime.fromisoformat(
                self.last_hv_current)).seconds * (1 / 3600)
            self.charged_capacity_ah += self.act_current * delta
            self.charged_capacity_wh += self.act_power * delta
        """

    def doHV_CELLS_TEMP_STATS(self, msg):
        """
        Processes the HV_TEMP CAN message from BMS_HV
        :param msg: the HV_TEMP CAN message
        """
        # self.ACC_CONNECTED = ACCUMULATOR.FENICE

        message = dbc_primary.decode_message(msg.arbitration_id, msg.data)
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()

        self.act_average_temp = round(message.get("avg"), 2)
        self.min_temp = round(message.get("min"), 2)
        self.max_temp = round(message.get("max"), 2)

        """
        self.hv_temp_history.append({"timestamp": self.lastupdated,
                                     "average_temp": self.act_average_temp,
                                     "max_temp": self.max_temp,
                                     "min_temp": self.min_temp})

        self.hv_temp_history_index += 1
        """

    def doHV_ERRORS(self, msg):
        """
        Processes the HV_ERRORS CAN message from BMS_HV
        :param msg: the HV_ERRORS CAN message
        """
        # self.ACC_CONNECTED = ACCUMULATOR.FENICE

        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()
        message = dbc_primary.decode_message(msg.arbitration_id, msg.data)

        for i in message.keys():
            try:
                self.errors[i] = message.get(i)
                if self.errors[i] != 0:
                    tprint(f"BMS error {i}", P_TYPE.ERROR)
                    # self.error = True
            except KeyError:
                pass

    def doHV_STATUS(self, msg):
        """
        Processes the HV_STATUS CAN message from BMS_HV
        :param msg: the HV_STATUS CAN message
        """

        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()
        message = dbc_primary.decode_message(msg.arbitration_id, msg.data)
        self.status = HvStatus(int(message.get('status').value))

    def doHV_CELLS_VOLTAGE(self, msg):
        """
        Processes the
        :param msg: the CAN message
        """

        try:
            message = dbc_primary.decode_message(msg.arbitration_id, msg.data)
            self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()
        except ValueError:
            tprint(f"ValueError in doHV_CELLS_VOLTAGE, msg data: {msg.data}", P_TYPE.ERROR)
            return

        if message.get('start_index') > 105:
            tprint(f"cells voltage index out of range: {message.get('start_index')}", P_TYPE.ERROR)
            return

        self.hv_cells_act[message.get("start_index"):message.get("start_index") + 3] = \
            round(message.get("voltage_0"), 3), \
                round(message.get("voltage_1"), 3), \
                round(message.get("voltage_2"), 3)

    def doHV_CELLS_VOLTAGE_STATS(self, msg):
        try:
            message = dbc_primary.decode_message(msg.arbitration_id, msg.data)
            self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()
        except ValueError:
            tprint(f"ValueError in doHV_CELL_VOLTAGE, msg data: {msg.data}", P_TYPE.ERROR)
            return

        self.max_cell_voltage = round(message.get("max"), 2)
        self.min_cell_voltage = round(message.get("min"), 2)
        # AVG and sum missing
        self.act_cell_delta = round(message.get("delta"), 2)

    def doHV_CELLS_TEMP(self, msg):
        """
        Processes the
        :param msg: the CAN message
        """

        try:
            message = dbc_primary.decode_message(msg.arbitration_id, msg.data)
            self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()
        except ValueError:
            tprint(f"ValueError in doHV_CELLS_TEMP, msg data: {msg.data}", P_TYPE.ERROR)
            return

        if message.get('start_index') > 216:
            tprint(f"cells temp index out of range: {message.get('start_index')}", P_TYPE.ERROR)
            return

        self.hv_temps_act[message.get("start_index"):message.get("start_index") + 4] = \
            round(message.get("temp_0"), 3), \
                round(message.get("temp_1"), 3), \
                round(message.get("temp_2"), 3), \
                round(message.get("temp_3"), 3)

    def doHV_BALANCING_STATUS(self, msg):
        """
        Updates the balancing status of the acc
        """

        try:
            message = dbc_primary.decode_message(msg.arbitration_id, msg.data)
            self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()
            # if message.get("cellboard_id") > BMS_CELLBOARD_COUNT - 1: # TODO add
            #    raise ValueError("cellboard_id out of range")
        except ValueError:
            tprint(f"ValueError in CELLS_BALANCING_STATUS, msg data: {msg.data}", P_TYPE.ERROR)
            return

        self.is_balancing = Toggle(int(message.get("balancing_status").value))
        if self.is_balancing == Toggle.ON:
            self.balancing_cells = message.get("balancing_cells")  # TODO: check
            # tprint(f"Balanging status: {message.get('balancing_status')}", P_TYPE.DEBUG)

    def doHV_FANS_STATUS(self, msg):
        """
        Updates the fans override status of the acc
        """
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()

        message = dbc_primary.decode_message(msg.arbitration_id, msg.data)

        # tprint(message, P_TYPE.DEBUG)

        self.fans_override_status = Toggle(int(message.get("fans_override").value))
        self.fans_override_speed = round(message.get("fans_speed"), 2)

    def do_HV_CELLBOARD_VERSION(self, msg):
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()

        message = dbc_primary.decode_message(msg.arbitration_id, msg.data)
        # tprint(f"Cellboard {message.get('cellboard_id')} version:  {message.get('component_build_time')}", P_TYPE.DEBUG)

    def do_HV_MAINBOARD_VERSION(self, msg):
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()

        message = dbc_primary.decode_message(msg.arbitration_id, msg.data)
        # tprint(message.get("component_build_time"), P_TYPE.DEBUG)

    def do_HV_FEEDBACK_STATUS(self, msg):
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()

        message = dbc_primary.decode_message(msg.arbitration_id, msg.data)

        try:
            for k in message.keys():
                self.feedbacks[k] = bms_feedback_status.get(str(message.get(k)))
        except Exception:
            pass
