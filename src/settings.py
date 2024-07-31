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

# Accumulator (BMS) settings
ACC_MAX_CHG_CURRENT = 8  # (A DC) Maximum charging current of accumulator
ACC_MIN_CHG_CURRENT = 0  # To prevent discharge
ACC_DEFAULT_CHG_CURRENT = 4  # Standard charging current of accumulator
ACC_DEFAULT_TARGET_V = 442  # (V DC) Default charging voltage of the accumulator
ACC_MIN_TARGET_V = 390  # Maximum voltage to charge the accumulator to
ACC_MAX_TARGET_V = 454  # Maximum voltage to charge the accumulator to
ACC_MAX_FAN_SPEED = 100  # 100%
ACC_MIN_FAN_SPEED = 0  # 0%
ACC_MAX_CELL_VOLTAGE = 4.2  # Maximum voltage allowed for a cell. If this voltage is reached, charge is stopped
ACC_CELLS_VOLTAGES_COUNT = 108
ACC_CELLS_TEMPS_COUNT = 216
ACC_SEGMENT_COUNT = 6
ACC_CELLS_VOLTAGES_PER_SEGMENT = ACC_CELLS_VOLTAGES_COUNT / ACC_SEGMENT_COUNT
ACC_CELLS_TEMPS_PER_SEGMENT = ACC_CELLS_TEMPS_COUNT / ACC_SEGMENT_COUNT
ACC_CELLBOARD_COUNT = 6
ACC_PRECHARGE_FINISH_TIMEOUT = 3  # Time allowed for the BMS to finish precharge

# Feedbacks ADC stuff
ADC_BUS = 0
ADC_DEVICE = 1
ADC_SPI_MODE = 3
ADC_SPI_MAX_SPEED = 1 * (10 ** 6) # HZ
ADC_VREF = 3.310  # V
ADC_V_DIVIDER_CORRECTION = 1.3  # Correction value to match real voltage

# Can settings
CAN_INTERFACE = "can0"
MAX_BATCH_CAN_READ = 5  # Maximum number of message read in a single FSM cycle (to avoid starvation)
CAN_RETRANSMIT_INTERVAL_NORMAL = 0.5  # Time to wait before retransmitting a non-critical request message (seconds)
CAN_RETRANSMIT_INTERVAL_CRITICAL = 0.1  # time to wait before retransmitting a critical request message (seconds)
CAN_ACC_PRESENCE_TIMEOUT = 0.5  # in seconds
CAN_CHARGER_PRESENCE_TIMEOUT = 0.4  # in seconds

ERROR_LOG_FILE_PATH = "errors.log"

ENABLE_FAN_CONTROL = True  # Put false to disable handcart fan control over bms
ENABLE_WEB = False  # deprecated for new charger
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
