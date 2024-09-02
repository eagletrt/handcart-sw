import threading
import time
from enum import Enum

import spidev
from spidev import SpiDev

from common.feedbacks.max11335 import ADC_MAX11335
from common.handcart_can import CanListener
from common.logging import tprint, P_TYPE
from settings import ADC_DEVICE, ADC_BUS, ADC_SPI_MODE, ADC_SPI_MAX_SPEED, ADC_VREF, ADC_V_DIVIDER_CORRECTION


class FB(Enum):
    VSD_FB = 0
    SD_TO_MUSHROOM_FB = 1
    SD_TO_CHARGER_FB = 2
    SD_BMS_IN_FB = 3
    SD_BMS_OUT_FB = 4
    SD_END_FB = 5
    COIL_DISCHARGE_FB = 6
    NC = 7
    FB_12_V = 8
    PON_FB = 9
    RELAY_SD_FB = 10


class Feedbacks(threading.Thread):
    shared_data: CanListener
    lock: threading.Lock
    adc: ADC_MAX11335
    spi: SpiDev

    def __init__(self,
                 lock: threading.Lock,
                 shared_data: CanListener):

        super().__init__(args=(lock,
                               shared_data))
        self.lock = self._args[0]
        self.shared_data = self._args[1]
        self.adc = ADC_MAX11335()
        self.spi = spidev.SpiDev()
        self.spi.open(ADC_BUS, ADC_DEVICE)
        self.spi.mode = ADC_SPI_MODE
        self.spi.max_speed_hz = ADC_SPI_MAX_SPEED

    def run(self):
        print(f"sent: {self.adc.get_default_adc_config().tobytes()}")
        data = self.spi.xfer(self.adc.get_default_adc_config().tobytes())
        data = bytes(data)

        if data != self.adc.get_default_adc_config().tobytes():
            tprint(f"Received config is not the same as sent: {data}", P_TYPE.ERROR)

        while 1:
            data = self.spi.xfer(self.adc.get_default_adc_mode_control().tobytes())
            self.spi.xfer([0x00])  # pull down CS to start reading

            # retrieve readings from max fifo
            done = False
            while not done:
                data = self.spi.readbytes(2)
                if data == [0, 0]:
                    done = True  # nothing more to read
                b: bytes = bytes(data)
                val = int.from_bytes(b, byteorder="big")

                id = val >> 12  # the 4 most significant bits are the id of the channel

                mask = 4095
                value = val & mask  # the remaining 12 bits it the value

                v_adc = (ADC_VREF / 4096) * value  # see max datasheet, convert to value read by adc

                # multiply value with the voltage divider constant, + a correction value
                v = round(v_adc * (9.18 + ADC_V_DIVIDER_CORRECTION), 2)

                with self.lock:
                    self.shared_data.feedbacks[id] = v

                time.sleep(.05)

            with self.lock:
                print(self.shared_data.feedbacks)

        time.sleep(.2)
