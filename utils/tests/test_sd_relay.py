import time

import RPi.GPIO as GPIO  # Import the GPIO library.

GPIO.setmode(GPIO.BCM)  # Set Pi to use pin number when referencing GPIO pins.
# Can use GPIO.setmode(GPIO.BCM) instead to use
# Broadcom SOC channel names.

GPIO.setup(20, GPIO.OUT)  # Set GPIO pin 12 to output mode.

while 1:
    time.sleep(1)
    # uscita a livello logico alto
    GPIO.output(21, GPIO.HIGH)
    # uscita a livello logico basso
    time.sleep(1)
    GPIO.output(21, GPIO.LOW)