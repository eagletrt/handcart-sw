from datetime import datetime

from src.common.settings import ERROR_LOG_FILE_PATH


def log_error(error_string: str):
    try:
        f = open(ERROR_LOG_FILE_PATH, "a")
        time_now = datetime.now()
        error_msg = "[ERROR] " + str(time_now) + ": " + error_string
        print(error_msg)
        f.write(error_msg + "\n")
    except:
        pass
