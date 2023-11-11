import struct
from datetime import datetime

from common.logging import tprint, P_TYPE
from settings import *


class ACCUMULATOR(Enum):
    CHIMERA = 1
    FENICE = 2


class CAN_CHIMERA_MSG_ID(Enum):
    PACK_VOLTS = 0x01
    PACK_TEMPS = 0x0A
    TS_ON = 0x03
    TS_OFF = 0x04
    CURRENT = 0x05
    AVG_TEMP = 0x06
    MAX_TEMP = 0x07
    ERROR = 0x08
    WARNING = 0x09


CAN_ID_BMS_HV_CHIMERA = 0xAA
CAN_ID_ECU_CHIMERA = 0x55


class CAN_REQ_CHIMERA(Enum):
    REQ_TS_ON = 0x0A  # Remember to ask charge state with byte 1 set to 0x01
    REQ_TS_OFF = 0x0B


class BMS_HV:
    """
    Class that stores and processes all the data of the BMS_HV
    """

    ACC_CONNECTED = ACCUMULATOR.FENICE  # Default fenice, if msgs from chimera received will be changed

    lastupdated = 0

    hv_voltage_history = []
    hv_voltage_history_index = 0
    hv_current_history = []
    hv_current_history_index = 0
    hv_temp_history = []
    hv_temp_history_index = 0

    hv_cells_act = [0 for i in range(BMS_CELLS_VOLTAGES_COUNT)]
    hv_temps_act = [0 for j in range(BMS_CELLS_TEMPS_COUNT)]

    charged_capacity_ah = 0
    charged_capacity_wh = 0
    act_pack_voltage = -1
    act_bus_voltage = -1
    act_current = -1
    act_power = -1
    max_cell_voltage = -1
    min_cell_voltage = -1
    error = False
    errors = HvErrors.copy()
    warnings = HvWarnings.copy()
    error_str = ""
    error_list_chimera = []
    status = TsStatus.INIT
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

    fans_set_override_speed = 0
    fans_set_override_status = Toggle.OFF

    def isConnected(self):
        """
        Check if BMS_HV is connected
        :return: True if BMS_HV is connected
        """
        if self.lastupdated == 0:
            return False
        else:
            return (datetime.now() - datetime.fromisoformat(str(self.lastupdated))).seconds \
                < CAN_BMS_PRESENCE_TIMEOUT

    def doHV_VOLTAGE(self, msg):
        """
        Processes th HV_VOLTAGE CAN message from BMS_HV
        :param msg: the HV_VOLTAGE CAN message
        """

        # self.ACC_CONNECTED = ACCUMULATOR.FENICE
        # someway somehow you have to extract:
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()

        message = dbc_primary.decode_message(msg.arbitration_id, msg.data)

        self.act_pack_voltage = round(message.get("pack_voltage"), 2)
        self.act_bus_voltage = round(message.get("bus_voltage"), 2)
        self.max_cell_voltage = round(message.get("max_cell_voltage"), 2)
        self.min_cell_voltage = round(message.get("min_cell_voltage"), 2)
        self.act_cell_delta = round(message.get("max_cell_voltage") - message.get("min_cell_voltage"), 2)

        """
        self.hv_voltage_history.append({"timestamp": self.lastupdated,
                                        "pack_voltage": self.act_pack_voltage,
                                        "bus_voltage": self.act_bus_voltage,
                                        "max_cell_voltage": self.max_cell_voltage,
                                        "min_cell_voltage": self.max_cell_voltage})

        self.hv_voltage_history_index += 1
        """

    def doHV_CURRENT(self, msg):
        """
        Processes the HV_CURRENT CAN message from BMS_HV
        :param msg: the HV_CURRENT CAN message
        """
        # self.ACC_CONNECTED = ACCUMULATOR.FENICE

        message = dbc_primary.decode_message(msg.arbitration_id, msg.data)

        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()
        self.act_current = abs(round(message.get("current"), 2))
        self.act_power = round(message.get("power"), 2)

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

    def doHV_TEMP(self, msg):
        """
        Processes the HV_TEMP CAN message from BMS_HV
        :param msg: the HV_TEMP CAN message
        """
        # self.ACC_CONNECTED = ACCUMULATOR.FENICE

        message = dbc_primary.decode_message(msg.arbitration_id, msg.data)
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()

        self.act_average_temp = round(message.get("average_temp"), 2)
        self.min_temp = round(message.get("min_temp"), 2)
        self.max_temp = round(message.get("max_temp"), 2)

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
                self.errors[i] = message[i]
                if message[i] != 0:
                    tprint("BMS error", P_TYPE.ERROR)
                    # self.error = True
            except KeyError:
                # Could be that it is not an error but a warning
                self.warnings[i] = message[i]
                # if it is not both of these, raises key error

    def doHV_STATUS(self, msg):
        """
        Processes the HV_STATUS CAN message from BMS_HV
        :param msg: the HV_STATUS CAN message
        """

        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()
        message = dbc_primary.decode_message(msg.arbitration_id, msg.data)
        self.status = TsStatus(int(message.get('ts_status').value))

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

    def doHV_CELL_BALANCING_STATUS(self, msg):
        """
        Updates the balancing status of the acc
        """
        self.ACC_CONNECTED = ACCUMULATOR.FENICE

        try:
            message = dbc_primary.decode_message(msg.arbitration_id, msg.data)
            self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()
            # if message.get("cellboard_id") > BMS_CELLBOARD_COUNT - 1: # TODO add
            #    raise ValueError("cellboard_id out of range")
        except ValueError:
            tprint(f"ValueError in CELLS_BALANCING_STATUS, msg data: {msg.data}", P_TYPE.ERROR)
            return

        self.is_balancing = Toggle(int(message.get("balancing_status").value))  # TODO: reinsert when BMS is fixed
        if self.is_balancing == Toggle.ON:
            tprint(f"Balanging status: {message.get('balancing_status')}", P_TYPE.DEBUG)

    def doHV_FANS_OVERRIDE_STATUS(self, msg):
        """
        Updates the fans override status of the acc
        """
        self.ACC_CONNECTED = ACCUMULATOR.FENICE
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()

        message = dbc_primary.decode_message(msg.arbitration_id, msg.data)

        # tprint(message, P_TYPE.DEBUG)

        self.fans_override_status = message.get("fans_override")
        self.fans_override_speed = round(message.get("fans_speed"), 2)

    def do_CHIMERA(self, msg):
        """
        Processes a BMS HV message from CHIMERA accumulator
        """
        self.ACC_CONNECTED = ACCUMULATOR.CHIMERA
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()

        if msg.data[0] == CAN_CHIMERA_MSG_ID.TS_ON.value:
            print("ts on message")
            self.status = TsStatus.TS_ON
        elif msg.data[0] == CAN_CHIMERA_MSG_ID.TS_OFF.value:
            self.status = TsStatus.IDLE
        elif msg.data[0] == CAN_CHIMERA_MSG_ID.ERROR.value:
            self.error = True
            if msg.data[1] == 0:  # ERROR_LTC6804_PEC_ERROR
                self.error_list_chimera.append("ERROR_LTC6804_PEC_ERROR")
            if msg.data[2] == 1:  # ERROR_CELL_UNDER_VOLTAGE
                self.error_list_chimera.append("ERROR_CELL_UNDER_VOLTAGE")
            if msg.data[3] == 2:  # ERROR_CELL_OVER_VOLTAGE
                self.error_list_chimera.append("ERROR_CELL_OVER_VOLTAGE")
            if msg.data[4] == 3:  # ERROR_CELL_OVER_TEMPERATURE
                self.error_list_chimera.append("ERROR_CELL_OVER_TEMPERATURE")
            if msg.data[5] == 4:  # ERROR_OVER_CURRENT
                self.error_list_chimera.append("ERROR_OVER_CURRENT")

        elif msg.data[0] == CAN_CHIMERA_MSG_ID.PACK_VOLTS.value:
            self.act_bus_voltage = round((msg.data[1] << 16 | msg.data[2] << 8 | msg.data[3]) / 10000, 1)
            self.max_cell_voltage = round((msg.data[4] << 8 | msg.data[5]) / 10000, 2)
            self.min_cell_voltage = round((msg.data[6] << 8 | msg.data[7]) / 10000, 2)
            self.hv_voltage_history.append({"timestamp": self.lastupdated,
                                            "bus_voltage": self.act_bus_voltage,
                                            "max_cell_voltage": self.max_cell_voltage,
                                            "min_cell_voltage": self.max_cell_voltage})

            self.hv_voltage_history_index += 1

        elif msg.data[0] == CAN_CHIMERA_MSG_ID.PACK_TEMPS.value:
            a = ">chhh"
            _, self.act_average_temp, self.max_temp, self.min_temp = struct.unpack(a, msg.data)
            self.act_average_temp /= 100
            self.max_temp /= 100
            self.min_temp /= 100
            self.hv_temp_history.append({"timestamp": self.lastupdated,
                                         "average_temp": self.act_average_temp,
                                         "max_temp": self.max_temp,
                                         "min_temp": self.min_temp})
            # print(self.act_average_temp, self.max_temp, self.min_temp)
            self.hv_temp_history_index += 1

        elif msg.data[0] == CAN_CHIMERA_MSG_ID.CURRENT.value:
            self.act_current = (msg.data[1] << 8 | msg.data[2]) / 10
            self.act_power = (msg.data[3] << 8 | msg.data[4])
            self.hv_current_history.append({"timestamp": self.lastupdated,
                                            "current": self.act_current,
                                            "power": self.act_power})

            self.hv_current_history_index += 1
