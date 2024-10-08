"""@package Handcart backend
For more info read the ../../doc section, or contact matteo.bitussi@studenti.unitn.it
For test purposes, launch start-can.sh before launching this file

Notes:
    
    
    
    
    
    BMS (or BMS HV) - Stands for Battery Manage System (also the accumulator)
"""

import atexit
import queue
import threading

from RPi import GPIO

import common.accumulator.fans as fans
from common.buzzer import Buzzer, STARTUP_SOUND
from common.feedbacks.feedbacks import Feedbacks
from common.fsm import FSM
from common.handcart_can import CanListener, thread_2_CAN
# from backend.common.methods.logging import log_error
from common.leds import TSAL_COLOR, setLedColor, thread_led
from common.logging import tprint, P_TYPE
from common.rasp import GPIO_setup, resetGPIOs
from common.ui.gui import Gui
from settings import *

GPIO.setmode(GPIO.BCM)  # Set Pi to use pin number when referencing GPIO pins.

# IPC (shared between threads)
shared_data: CanListener = CanListener()  # Variable that holds a copy of canread, to get the information from web
# thread
rx_can_queue = queue.Queue()  # Queue for incoming can messages
tx_can_queue = queue.Queue()  # Queue for outgoing can messages
tele_can_queue = queue.Queue()  # Queue used to send can messages to telemetry thread
com_queue = queue.Queue()  # Command queue
melody_queue = queue.Queue()  # Queue to send melodies to the buzzer
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

    if ENABLE_LED:
        tprint("Leds are enabled", P_TYPE.DEBUG)
        setLedColor(TSAL_COLOR.OFF)
        t4 = threading.Thread(target=thread_led, args=(shared_data,))
        t4.start()

    if ENABLE_FAN_CONTROL:
        t5 = threading.Thread(target=fans.thread_fans, args=(shared_data, tx_can_queue, lock))
        t5.start()
    else:
        tprint("starting without fan control", P_TYPE.WARNING)

    if ENABLE_BUZZER:
        tprint("Buzzer enabled, starting buzzer thread", P_TYPE.DEBUG)
        b = Buzzer(
            melody_queue
        )
        b.start()

        melody_queue.put({"melody": STARTUP_SOUND, "repeat": 1})

    if ENABLE_FEEDBACKS:
        tprint("Feedbacks reading enabled, starting feedbacks thread", P_TYPE.DEBUG)
        f = Feedbacks(lock, shared_data)
        f.start()

    if ENABLE_GUI:
        tprint("GUI is enabled, starting gui..", P_TYPE.DEBUG)
        g = Gui(
            com_queue,
            lock,
            shared_data,
            melody_queue
        )
        g.run()  # WARNING, not a thread
