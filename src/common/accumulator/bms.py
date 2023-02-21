import struct
from datetime import datetime

from src.can_eagle.lib.primary.python.network import *
from src.common.settings import *


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

    hv_cells_act = [0 for i in range(18 * 6)]
    hv_temps_act = [0 for i in range(36 * 6)]

    charged_capacity_ah = 0
    charged_capacity_wh = 0
    act_pack_voltage = -1
    act_bus_voltage = -1
    act_current = -1
    act_power = -1
    max_cell_voltage = -1
    min_cell_voltage = -1
    error = False
    errors = 0
    warnings = None
    error_str = ""
    error_list_chimera = []
    status = TsStatus.OFF
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

        converted = message_HV_VOLTAGE.deserialize(msg.data).convert()

        self.act_pack_voltage = round(converted.pack_voltage, 2)
        self.act_bus_voltage = round(converted.bus_voltage, 2)
        self.max_cell_voltage = round(converted.max_cell_voltage, 2)
        self.min_cell_voltage = round(converted.min_cell_voltage, 2)

        self.hv_voltage_history.append({"timestamp": self.lastupdated,
                                        "pack_voltage": self.act_pack_voltage,
                                        "bus_voltage": self.act_bus_voltage,
                                        "max_cell_voltage": self.max_cell_voltage,
                                        "min_cell_voltage": self.max_cell_voltage})

        self.hv_voltage_history_index += 1

    def doHV_CURRENT(self, msg):
        """
        Processes the HV_CURRENT CAN message from BMS_HV
        :param msg: the HV_CURRENT CAN message
        """
        # self.ACC_CONNECTED = ACCUMULATOR.FENICE

        converted = message_HV_CURRENT.deserialize(msg.data).convert()

        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()

        self.act_current = abs(round(converted.current, 2))
        self.act_power = round(converted.power, 2)

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

    def doHV_TEMP(self, msg):
        """
        Processes the HV_TEMP CAN message from BMS_HV
        :param msg: the HV_TEMP CAN message
        """
        # self.ACC_CONNECTED = ACCUMULATOR.FENICE

        converted = message_HV_TEMP.deserialize(msg.data).convert()
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()

        self.act_average_temp = round(converted.average_temp, 2)
        self.min_temp = round(converted.min_temp, 2)
        self.max_temp = round(converted.max_temp, 2)

        self.hv_temp_history.append({"timestamp": self.lastupdated,
                                     "average_temp": self.act_average_temp,
                                     "max_temp": self.max_temp,
                                     "min_temp": self.min_temp})

        self.hv_temp_history_index += 1

    def doHV_ERRORS(self, msg):
        """
        Processes the HV_ERRORS CAN message from BMS_HV
        :param msg: the HV_ERRORS CAN message
        """
        # self.ACC_CONNECTED = ACCUMULATOR.FENICE

        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()

        deserialized = message_HV_ERRORS.deserialize(msg.data)

        self.errors = HvErrors(deserialized.errors)

        self.warnings = deserialized.warnings

        if self.errors != 0:
            self.error = True

    def doHV_STATUS(self, msg):
        """
        Processes the HV_STATUS CAN message from BMS_HV
        :param msg: the HV_STATUS CAN message
        """
        # self.ACC_CONNECTED = ACCUMULATOR.FENICE

        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()
        self.status = message_TS_STATUS.deserialize(msg.data).ts_status

    def doHV_CELLS_VOLTAGE(self, msg):
        """
        Processes the
        :param msg: the CAN message
        """
        # self.ACC_CONNECTED = ACCUMULATOR.FENICE
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()

        converted = message_HV_CELLS_VOLTAGE.deserialize(msg.data).convert()

        self.hv_cells_act[converted.start_index:converted.start_index + 3] = round(converted.voltage_0, 3), \
            round(converted.voltage_1, 3), \
            round(converted.voltage_2, 3)

    def doHV_CELLS_TEMP(self, msg):
        """
        Processes the
        :param msg: the CAN message
        """
        # self.ACC_CONNECTED = ACCUMULATOR.FENICE
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()

        converted = message_HV_CELLS_TEMP.deserialize(msg.data).convert()
        self.hv_temps_act[converted.start_index:converted.start_index + 6] = round(converted.temp_0, 3), \
            round(converted.temp_1, 3), \
            round(converted.temp_2, 3), \
            round(converted.temp_3, 3), \
            round(converted.temp_4, 3), \
            round(converted.temp_5, 3)

    def doHV_BALANCING_STATUS(self, msg):
        """
        Updates the balancing status of the acc
        """
        self.ACC_CONNECTED = ACCUMULATOR.FENICE
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()

        deserialized = message_HV_CELL_BALANCING_STATUS.deserialize(msg.data)
        self.is_balancing = deserialized.balancing_status

    def doHV_FANS_OVERRIDE_STATUS(self, msg):
        """
        Updates the fans override status of the acc
        """
        self.ACC_CONNECTED = ACCUMULATOR.FENICE
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()

        deserialized = message_HV_FANS_OVERRIDE_STATUS.deserialize(msg.data).convert()
        self.fans_override_status = deserialized.fans_override
        self.fans_override_speed = round(deserialized.fans_speed, 2)

    def do_CHIMERA(self, msg):
        """
        Processes a BMS HV message from CHIMERA accumulator
        """
        self.ACC_CONNECTED = ACCUMULATOR.CHIMERA

        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()

        if msg.data[0] == CAN_CHIMERA_MSG_ID.TS_ON.value:
            print("ts on message")
            self.status = TsStatus.ON
        elif msg.data[0] == CAN_CHIMERA_MSG_ID.TS_OFF.value:
            self.status = TsStatus.OFF
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
