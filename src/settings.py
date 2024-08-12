from os.path import dirname, realpath, join

import cantools
from cantools.database import Database

# Import the dbc files -------------------------------------------------------------------------------------------------
brusa_dbc_file = join(dirname(dirname(realpath(__file__))), "NLG5_BRUSA.dbc")
DBC_PRIMARY_PATH = join(dirname(realpath(__file__)), "can_eagle", "dbc", "primary", "primary.dbc")
dbc_brusa: Database = cantools.database.load_file(brusa_dbc_file)
dbc_primary: Database = cantools.database.load_file(DBC_PRIMARY_PATH)  # load the bms dbc file
# ----------------------------------------------------------------------------------------------------------------------

# If you want to check that the dbc of the canlib has the same names of the messages that are used in the code, enable
CAN_MESSAGE_CHECK_ENABLED = True

DEFAULT_CHARGE_MAINS_AMPERE = 16
MAX_ACC_CHG_AMPERE = 9  # Maximum charging current of accumulator
DEFAULT_ACC_CHG_AMPERE = 6  # Standard charging current of accumulator

DEFAULT_TARGET_V_ACC = 442  # Default charging voltage of the accumulator
MIN_TARGET_V_ACC = 370  # Maximum voltage to charge the accumulator to
MAX_TARGET_V_ACC = 454  # Maximum voltage to charge the accumulator to
MAX_BMS_FAN_SPEED = 100  # 100%
MIN_BMS_FAN_SPEED = 0  # 0%
MAX_BMS_CHARGE_CURRENT = 8  # Maximum bms charging current
MIN_BMS_CHARGE_CURRENT = 0
MIN_CHARGER_GRID_CURRENT = 0
MAX_CHARGER_GRID_CURRENT = 16  # maximum current to be taken from grid by charger

MAX_ACC_CELL_VOLTAGE = 4.2

CAN_DEVICE_TIMEOUT = 2000  # Time tolerated between two message of a device

CAN_INTERFACE = "can0"
MAX_BATCH_CAN_READ = 5  # Maximum number of message read in a single FSM cycle (to avoid starvation)

CAN_BMS_PRESENCE_TIMEOUT = 0.5  # in seconds
CAN_BRUSA_PRESENCE_TIMEOUT = 0.5  # in seconds
ERROR_LOG_FILE_PATH = "errors.log"
BMS_CELLS_VOLTAGES_COUNT = 108
BMS_CELLS_TEMPS_COUNT = 216
BMS_SEGMENT_COUNT = 6
BMS_CELLS_VOLTAGES_PER_SEGMENT = BMS_CELLS_VOLTAGES_COUNT // BMS_SEGMENT_COUNT
BMS_CELLS_TEMPS_PER_SEGMENT = BMS_CELLS_TEMPS_COUNT // BMS_SEGMENT_COUNT
BMS_CELLBOARD_COUNT = 6

# CLI config
CLI_TTY = "/dev/serial0"
CLI_TTY_REDIRECT_ENABLED = False
CLI_DEFAULT_WIDTH = 80
CLI_DEFAULT_HEIGHT = 24
CLI_CELLS_VOLTAGE_RED_THRESHOLD_LOW = 3.6
CLI_CELLS_VOLTAGE_RED_THRESHOLD_HIGH = 4.15
CLI_CELLS_TEMPS_RED_THRESHOLD_LOW = 5
CLI_CELLS_TEMPS_RED_THRESHOLD_HIGH = 50

ADC_BUS = 0
ADC_DEVICE = 1
ADC_SPI_MODE = 3
ADC_SPI_MAX_SPEED = 1 * (10 ** 6) # HZ
ADC_VREF = 3.310  # V
ADC_V_DIVIDER_CORRECTION = 1.3  # Correction value to match real voltage

BMS_PRECHARGE_STATUS_CHANGE_TIMEOUT = 3  # Time allowed for the BMS to finish precharge
RETRANSMIT_INTERVAL_NORMAL = 0.5  # Time to wait before retransmitting a non-critical request message (seconds)
RETRANSMIT_INTERVAL_CRITICAL = 0.1  # time to wait before retransmitting a critical request message (seconds)

ENABLE_TELEMETRY_SETTINGS = False  # Set to true to enable receiving commands from telemetry

ENABLE_FAN_CONTROL = True  # Put false to disable handcart fan control over bms
ENABLE_CLI = False  # Set to true to enable CLI over tty
ENABLE_WEB = False
ENABLE_LED = False
ENABLE_GUI = True
ENABLE_BUZZER = True
ENABLE_FEEDBACKS = True

from common.can_classes import *  # This inits all the enums in the can_classes.py file, not move


class PIN(Enum):
    BUZZER = 1
    RED_LED = 12  # (GPIO12) # TODO remove
    GREEN_LED = 13  # GPIO13 # TODO remove
    BLUE_LED = 18  # GPIO16 # TODO remove
    DISCHARGE = 19
    SD_RELAY = 21
    PON_CONTROL = 20
    BUT_0 = 22  # Confirm rotative
    BUT_1 = 23  # left
    BUT_2 = 24  # UP
    BUT_3 = 26  # right
    BUT_4 = 27  # Down
    ROT_A = 16
    ROT_B = 17  # B
    LED_STRIP_CTRL = 18
