from datetime import datetime

from settings import ERROR_LOG_FILE_PATH
from termcolor import colored


def log_error(error_string: str):
    try:
        f = open(ERROR_LOG_FILE_PATH, "a")
        time_now = datetime.now()
        error_msg = "[ERROR] " + str(time_now) + ": " + error_string
        print(error_msg)
        f.write(error_msg + "\n")
    except:
        pass


class P_TYPE():
    INFO = 0
    WARNING = 1
    ERROR = 2
    DEBUG = 3

def tprint(msg: str, type:int):
    if type == P_TYPE.INFO:
        header = "[INFO] "
        print(header + msg)
        return
    elif type == P_TYPE.WARNING:
        header = "[WARNING] "
        print(colored(header + msg, "yellow"))
        return
    elif type == P_TYPE.ERROR:
        header = "[ERROR] "
        print(colored(header + msg, "red"))
        return
    elif type == P_TYPE.DEBUG:
        header = "[DEBUG] "
        print(header + msg)
        return

    print(msg)
