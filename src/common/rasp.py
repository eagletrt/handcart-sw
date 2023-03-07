from RPi import GPIO

from common.settings import PIN


def GPIO_setup():
    """
    This function is used to set-up the GPIO pins
    """
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(PIN.BUT_0.value, GPIO.OUT)
    GPIO.setup(PIN.BUT_1.value, GPIO.OUT)
    GPIO.setup(PIN.BUT_2.value, GPIO.OUT)
    GPIO.setup(PIN.BUT_3.value, GPIO.OUT)
    GPIO.setup(PIN.BUT_4.value, GPIO.OUT)
    GPIO.setup(PIN.BUT_5.value, GPIO.OUT)
    GPIO.setup(PIN.PON_CONTROL.value, GPIO.OUT)
    GPIO.setup(PIN.ROT_A.value, GPIO.OUT)
    GPIO.setup(PIN.ROT_B.value, GPIO.OUT)
    GPIO.setup(PIN.SD_RELAY.value, GPIO.OUT)
    GPIO.setup(PIN.GREEN_LED.value, GPIO.OUT)
    GPIO.setup(PIN.BLUE_LED.value, GPIO.OUT)
    GPIO.setup(PIN.RED_LED.value, GPIO.OUT)


def resetGPIOs():
    GPIO.output(PIN.PON_CONTROL.value, GPIO.LOW)
    GPIO.output(PIN.SD_RELAY.value, GPIO.HIGH)
    GPIO.output(PIN.GREEN_LED.value, GPIO.LOW)
    GPIO.output(PIN.BLUE_LED.value, GPIO.LOW)
    GPIO.output(PIN.RED_LED.value, GPIO.LOW)
