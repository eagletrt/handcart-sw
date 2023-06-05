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

import common.accumulator.fans as fans
from common.cli.cli import Cli
from common.fsm import FSM
from common.handcart_can import CanListener, thread_2_CAN
# from backend.common.methods.logging import log_error
from common.leds import TSAL_COLOR, setLedColor, thread_led
from common.rasp import GPIO_setup, resetGPIOs
from common.server.server import thread_3_WEB
from common.settings import *

import os, getpass
print("[DEBUG] Env thinks the user is [%s]" % (os.getlogin()))
print("[DEBUG] Effective user is [%s]" % (getpass.getuser()))

# IPC (shared between threads)
shared_data: CanListener = CanListener()  # Variable that holds a copy of canread, to get the information from web thread
rx_can_queue = queue.Queue()  # Queue for incoming can messages
tx_can_queue = queue.Queue()  # Queue for outgoing can messages
tele_can_queue = queue.Queue() # Queue used to send can messages to telemetry thread
com_queue = queue.Queue()  # Command queue
lock = threading.Lock()
can_forward_enabled = False  # Enable or disable the charge can messages from BMS_HV to BRUSA
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
        can_forward_enabled,
        lock,
        shared_data,
        forward_lock
    )
    t2 = threading.Thread(target=thread_2_CAN,
                          args=(shared_data,
                                rx_can_queue,
                                tx_can_queue,
                                can_forward_enabled,
                                forward_lock,
                                lock,
                                tele_can_queue))
    t3 = threading.Thread(target=thread_3_WEB, args=(shared_data, lock, com_queue))
    t4 = threading.Thread(target=thread_led, args=(shared_data,))
    t5 = threading.Thread(target=fans.thread_fans, args=(shared_data, tx_can_queue, lock))
    t6 = Cli(
        com_queue,
        lock,
        shared_data
    )

    t1.start()
    t2.start()
    t3.start()
    if ENABLE_LED:
        setLedColor(TSAL_COLOR.OFF)
        t4.start()
    if ENABLE_FAN_CONTROL:
        print("Warning, starting without fan control")
        t5.start()
    if ENABLE_CLI:
        t6.start()
