# Script to tune the buzzer frequency

import RPi.GPIO as GPIO
import time

# Pin numbers on Raspberry Pi
CLK_PIN = 17
DT_PIN = 16
counter = 3000
prev_button_state = GPIO.HIGH

# Configure GPIO pins
GPIO.setmode(GPIO.BCM)
GPIO.setup(CLK_PIN, GPIO.IN)
GPIO.setup(DT_PIN, GPIO.IN)
GPIO.setup(1, GPIO.OUT)

# Create a PWM channel
pwm = GPIO.PWM(1, 440)  # 440Hz is a common frequency

# Define a function to play a single note
def play_note(note, duration):
    pwm.start(50)  # 50% duty cycle for a square wave
    pwm.ChangeFrequency(note)
    #time.sleep(duration)
    #pwm.stop()

def callback_both(gpio_pin: int):
    global counter, prev_CLK_state, direction
    CLK_state = GPIO.input(CLK_PIN)
    DT_state = GPIO.input(DT_PIN)

    if CLK_state == GPIO.HIGH and DT_state == GPIO.LOW:
        counter -= 10
        play_note(counter, 1)
        print(f"Freq: {counter} Hz")

    elif CLK_state == GPIO.HIGH and DT_state == GPIO.HIGH:
        counter += 10
        play_note(counter, 1)

        print(f"Freq: {counter} Hz")

GPIO.add_event_detect(CLK_PIN, GPIO.RISING, callback=callback_both, bouncetime=1)

try:
    while True:
        time.sleep(0.01)

except KeyboardInterrupt:
    GPIO.cleanup()