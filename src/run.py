"""@package Handcart backend
For more info read the ../../doc section, or contact matteo.bitussi@studenti.unitn.it
For test purposes, launch start-can.sh before launching this file

Notes:
    NLG5 - Stands for the BRUSA (also the charger)
    BMS (or BMS HV) - Stands for Battery Manage System (also the accumulator)
"""

import atexit
import queue
import threading

from RPi import GPIO

import common.accumulator.fans as fans
from common.cli.cli import Cli
from common.fsm import FSM
from common.handcart_can import CanListener, thread_2_CAN
# from backend.common.methods.logging import log_error
from common.leds import TSAL_COLOR, setLedColor, thread_led
from common.logging import tprint, P_TYPE
from common.rasp import GPIO_setup, resetGPIOs
from common.server.server import thread_3_WEB
from settings import *

# tprint("Env thinks the user is [%s]" % (os.getlogin()), P_TYPE.DEBUG)
# tprint("Effective user is [%s]" % (getpass.getuser()), P_TYPE.DEBUG)

GPIO.setmode(GPIO.BCM)  # Set Pi to use pin number when referencing GPIO pins.

# IPC (shared between threads)
shared_data: CanListener = CanListener()  # Variable that holds a copy of canread, to get the information from web
# thread
rx_can_queue = queue.Queue()  # Queue for incoming can messages
tx_can_queue = queue.Queue()  # Queue for outgoing can messages
tele_can_queue = queue.Queue()  # Queue used to send can messages to telemetry thread
com_queue = queue.Queue()  # Command queue
lock = threading.Lock()
forward_lock = threading.Lock()  # Lock to manage the access to the can_forward_enabled variable


def exit_handler():
    print("Quitting..")
    setLedColor(TSAL_COLOR.OFF)
    resetGPIOs()
    GPIO.cleanup()


if __name__ == "__main__":
    GPIO_setup()
    resetGPIOs()

    atexit.register(exit_handler)  # On exit of the program, execute the function

    t1 = FSM(
        tx_can_queue,
        rx_can_queue,
        com_queue,
        lock,
        shared_data,
        forward_lock
    )
    t2 = threading.Thread(target=thread_2_CAN,
                          args=(shared_data,
                                rx_can_queue,
                                tx_can_queue,
                                forward_lock,
                                lock,
                                com_queue))

    t1.start()
    t2.start()

    if ENABLE_WEB:
        t3 = threading.Thread(target=thread_3_WEB, args=(shared_data, lock, com_queue))
        t3.start()

    if ENABLE_LED:
        setLedColor(TSAL_COLOR.OFF)
        t4 = threading.Thread(target=thread_led, args=(shared_data,))
        t4.start()

    if ENABLE_FAN_CONTROL:
        t5 = threading.Thread(target=fans.thread_fans, args=(shared_data, tx_can_queue, lock))
        t5.start()
    else:
        tprint("starting without fan control", P_TYPE.WARNING)

    if ENABLE_CLI:
        t6 = Cli(
            com_queue,
            lock,
            shared_data
        )
        t6.start()
