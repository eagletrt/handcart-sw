import time
from enum import Enum

from RPi import GPIO

from settings import PIN
from settings import STATE


class TSAL_COLOR(Enum):
    OFF = -1
    RED = 0
    GREEN = 1
    ORANGE = 2
    PURPLE = 3
    WHITE = 4
    YELLOW = 5


def setLedColor(color):
    if color == TSAL_COLOR.OFF:
        GPIO.output(PIN.GREEN_LED.value, GPIO.LOW)
        GPIO.output(PIN.BLUE_LED.value, GPIO.LOW)
        GPIO.output(PIN.RED_LED.value, GPIO.LOW)
    if color == TSAL_COLOR.RED:  # TSON
        GPIO.output(PIN.GREEN_LED.value, GPIO.LOW)
        GPIO.output(PIN.BLUE_LED.value, GPIO.LOW)
        GPIO.output(PIN.RED_LED.value, GPIO.HIGH)
    elif color == TSAL_COLOR.ORANGE:  # ERROR
        GPIO.output(PIN.GREEN_LED.value, GPIO.HIGH)
        GPIO.output(PIN.BLUE_LED.value, GPIO.LOW)
        GPIO.output(PIN.RED_LED.value, GPIO.HIGH)
    elif color == TSAL_COLOR.PURPLE:  # TSON and CHARGING
        GPIO.output(PIN.GREEN_LED.value, GPIO.LOW)
        GPIO.output(PIN.BLUE_LED.value, GPIO.HIGH)
        GPIO.output(PIN.RED_LED.value, GPIO.HIGH)
    elif color == TSAL_COLOR.GREEN:  # TS OFF
        GPIO.output(PIN.GREEN_LED.value, GPIO.HIGH)
        GPIO.output(PIN.BLUE_LED.value, GPIO.LOW)
        GPIO.output(PIN.RED_LED.value, GPIO.LOW)
    elif color == TSAL_COLOR.WHITE:
        GPIO.output(PIN.GREEN_LED.value, GPIO.HIGH)
        GPIO.output(PIN.BLUE_LED.value, GPIO.HIGH)
        GPIO.output(PIN.RED_LED.value, GPIO.HIGH)
    elif color == TSAL_COLOR.YELLOW:
        GPIO.output(PIN.GREEN_LED.value, GPIO.HIGH)
        GPIO.output(PIN.BLUE_LED.value, GPIO.LOW)
        GPIO.output(PIN.RED_LED.value, GPIO.HIGH)


def thread_led(shared_data):
    blinking = False
    is_tsal_on = False
    tsal_actual_color = TSAL_COLOR.OFF
    # This thread just access shared_data, doesn't need the use of lock

    while 1:
        time.sleep(.1)
        # if actual_state != shared_data.FSM_stat:

        if shared_data.FSM_stat == STATE.CHECK:
            blinking = False
            setLedColor(TSAL_COLOR.WHITE)
            tsal_actual_color = TSAL_COLOR.WHITE
        elif shared_data.FSM_stat == STATE.IDLE:
            blinking = False
            setLedColor(TSAL_COLOR.GREEN)
            tsal_actual_color = TSAL_COLOR.GREEN
        elif shared_data.FSM_stat == STATE.PRECHARGE or \
                shared_data.FSM_stat == STATE.READY:
            blinking = True
            setLedColor(TSAL_COLOR.RED)
            tsal_actual_color = TSAL_COLOR.RED
        elif shared_data.FSM_stat == STATE.CHARGE:
            blinking = True
            setLedColor(TSAL_COLOR.PURPLE)
            tsal_actual_color = TSAL_COLOR.PURPLE
        elif shared_data.FSM_stat == STATE.CHARGE_DONE:
            blinking = True
            setLedColor(TSAL_COLOR.RED)
            tsal_actual_color = TSAL_COLOR.RED
        elif shared_data.FSM_stat == STATE.ERROR:
            blinking = False
            setLedColor(TSAL_COLOR.ORANGE)
            tsal_actual_color = TSAL_COLOR.ORANGE

        if blinking:
            if is_tsal_on:
                setLedColor(TSAL_COLOR.OFF)
                is_tsal_on = False
            else:
                setLedColor(tsal_actual_color)
                is_tsal_on = True
