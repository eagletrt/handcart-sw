import queue
import threading
import time
from enum import Enum

import RPi.GPIO as GPIO

from common.logging import tprint, P_TYPE
from settings import PIN


class BuzzerNote(Enum):
    DO = 2090
    RE_B = 2215
    RE = 2350
    MI_B = 2490
    MI = 2640
    FA = 2790
    SOL_B = 2690
    SOL = 3285  # to fix
    LA_B = 3320
    LA = 3510
    SI_B = 3730
    SI = 3950
    EMPTY = 0


STARTUP_SOUND = [
    (BuzzerNote.DO, 0.05),
    (BuzzerNote.EMPTY, .5),
    (BuzzerNote.DO, 0.05),
    (BuzzerNote.EMPTY, .5),
    (BuzzerNote.DO, 0.05),
    (BuzzerNote.EMPTY, 1),
    (BuzzerNote.DO, 0.15),
    (BuzzerNote.MI_B, 0.15),
    (BuzzerNote.DO, 0.15),
    (BuzzerNote.MI_B, 0.15)
]


class Buzzer(threading.Thread):
    pwm = None
    PWM_DUTY_CYCLE = 50
    melody_queue: queue.Queue

    def setup(self):
        # Set up GPIO pin
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(PIN.BUZZER.value, GPIO.OUT)
        self.pwm = GPIO.PWM(PIN.BUZZER.value, 440)  # 440Hz is a common frequency

    def play_note(self, note: BuzzerNote, duration: float):
        # 50% duty cycle for a square wave
        if note != BuzzerNote.EMPTY:
            self.pwm.start(self.PWM_DUTY_CYCLE)
            self.pwm.ChangeFrequency(note.value)

        time.sleep(duration)

        if note != BuzzerNote.EMPTY:
            self.pwm.stop()

    def play_melody(self, melody: list[tuple[BuzzerNote, float]], repeat: int = 1) -> None:
        """

        Args:
            melody:
            repeat: -1 for infinite. default 1 times

        Returns:

        """

        for n, dur in melody:
            self.play_note(n, dur)
            time.sleep(0.01)

    def __init__(self,
                 melody_queue: queue.Queue):

        super().__init__(args=(
            melody_queue,
        ))

        self.setup()

        self.melody_queue = self._args[0]

    def run(self):
        while True:
            if not self.melody_queue.empty():
                try:
                    com = self.melody_queue.get()
                    self.play_melody(com['melody'], com['repeat'])
                except Exception as e:
                    tprint(str(e), P_TYPE.WARNING)
                    pass
            time.sleep(0.1)
