from os.path import dirname, realpath, join

import cantools
from cantools.database import Database

# Import the dbc files -------------------------------------------------------------------------------------------------
brusa_dbc_file = join(dirname(dirname(realpath(__file__))), "NLG5_BRUSA.dbc")
BMS_DBC_PATH = join(dirname(realpath(__file__)), "can_eagle", "dbc", "bms", "bms.dbc")
DBC_PRIMARY_PATH = join(dirname(realpath(__file__)), "can_eagle", "dbc", "primary", "primary.dbc")
dbc_brusa: Database = cantools.database.load_file(brusa_dbc_file)
dbc_bms: Database = cantools.database.load_file(BMS_DBC_PATH)  # load the bms dbc file
dbc_primary: Database = cantools.database.load_file(DBC_PRIMARY_PATH)  # load the bms dbc file
# ----------------------------------------------------------------------------------------------------------------------

MAX_CHARGE_MAINS_AMPERE = 16
DEFAULT_CHARGE_MAINS_AMPERE = 6
MAX_ACC_CHG_AMPERE = 12  # Maximum charging current of accumulator
DEFAULT_ACC_CHG_AMPERE = 8  # Standard charging current of accumulator

DEFAULT_TARGET_V_ACC = 442  # Default charging voltage of the accumulator
MAX_TARGET_V_ACC = 455  # Maximum voltage to charge the accumulator to

CAN_DEVICE_TIMEOUT = 2000  # Time tolerated between two message of a device

CAN_INTERFACE = "vcan0"

CAN_BMS_PRESENCE_TIMEOUT = 0.5  # in seconds
CAN_BRUSA_PRESENCE_TIMEOUT = 0.5  # in seconds
ERROR_LOG_FILE_PATH = "errors.log"

BMS_PRECHARGE_STATUS_CHANGE_TIMEOUT = 2  # Time allowed for the BMS to finish precharge
RETRANSMIT_INTERVAL = 0.5  # Time to wait before retransmitting a request message

ENABLE_FAN_CONTROL = True  # Put false to disable handcart fan control over bms
ENABLE_CLI = True  # Set to true to enable USB cli
ENABLE_WEB = False
ENABLE_LED = True

from common.can_classes import *  # This inits all the enums in the can_classes.py file, not move


class PIN(Enum):
    RED_LED = 12  # 31
    GREEN_LED = 13  # 33
    BLUE_LED = 16  # 36
    SD_RELAY = 20
    PON_CONTROL = 21
    BUT_0 = 22
    BUT_1 = 23
    BUT_2 = 24
    BUT_3 = 26
    BUT_4 = 27
    BUT_5 = 19
    ROT_A = 18
    ROT_B = 17


class STATE(Enum):
    """Enum containing the states of the backend's state-machine
    """
    CHECK = 0
    IDLE = 1
    PRECHARGE = 2
    READY = 3
    CHARGE = 4
    C_DONE = 5
    BALANCING = 6
    ERROR = -1
    EXIT = -2
