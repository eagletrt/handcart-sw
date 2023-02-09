import cantools
from RPi import GPIO

brusa_dbc = cantools.database.load_file('NLG5_BRUSA.dbc')

GPIO.setmode(GPIO.BCM)  # Set Pi to use pin number when referencing GPIO pins.

ENABLE_LED = True

MAX_CHARGE_MAINS_AMPERE = 16
DEFAULT_CHARGE_MAINS_AMPERE = 6
MAX_ACC_CHG_AMPERE = 12  # Maximum charging current of accumulator
DEFAULT_ACC_CHG_AMPERE = 8  # Standard charging current of accumulator

DEFAULT_TARGET_V_ACC = 442  # Default charging voltage of the accumulator
MAX_TARGET_V_ACC = 455 # Maximum voltage to charge the accumulator to

CAN_DEVICE_TIMEOUT = 2000  # Time tolerated between two message of a device
CAN_ID_BMS_HV_CHIMERA = 0xAA
CAN_ID_ECU_CHIMERA = 0x55

actual_fsm_state = 0  # Read only

led_blink = False

CAN_INTERFACE = "can0"
CAN_BMS_PRESENCE_TIMEOUT = 0.5  # in seconds
CAN_BRUSA_PRESENCE_TIMEOUT = 0.5  # in seconds
ERROR_LOG_FILE_PATH = "errors.log"

BMS_PRECHARGE_STATUS_CHANGE_TIMEOUT = 2
RETRANSMIT_INTERVAL = 0.5 # Time to wait before retransmitting a request message

# BMS_HV_BYPASS = False # Use at your own risk