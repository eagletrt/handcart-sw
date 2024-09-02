# datasheet https://www.analog.com/media/en/technical-documentation/data-sheets/max11335-max11340.pdf

from bitstring import BitArray


class ADC_MAX11335:
    # Table 1
    REGISTER_ADC_MODE_CONTROL = BitArray(bin='0')
    REGISTER_ADC_CONFIGURATION = BitArray(bin='10000')
    REGISTER_UNIPOLAR = BitArray(bin='10001')
    REGISTER_BIPOLAR = BitArray(bin='10010')
    REGISTER_RANGE = BitArray(bin='10011')
    REGISTER_CUSTOM_SCAN0 = BitArray(bin='10100')
    REGISTER_CUSTOM_SCAN1 = BitArray(bin='10101')
    REGISTER_SAMPLESET = BitArray(bin='10110')

    # Table 2 ADC scan control
    SCAN_CONTROL_MODE_NULL = BitArray(bin='0000')
    SCAN_CONTROL_MODE_MANUAL = BitArray(bin='0001')
    SCAN_CONTROL_MODE_REPEAT = BitArray(bin='0010')
    SCAN_CONTROL_MODE_STANDARD_INT = BitArray(bin='0011')
    SCAN_CONTROL_MODE_STANDARD_EXT = BitArray(bin='0100')
    SCAN_CONTROL_MODE_UPPER_INT = BitArray(bin='0101')
    SCAN_CONTROL_MODE_UPPER_EXT = BitArray(bin='0110')
    SCAN_CONTROL_MODE_CUSTOM_INT = BitArray(bin='0111')
    SCAN_CONTROL_MODE_CUSTOM_EXT = BitArray(bin='1000')
    SCAN_CONTROL_MODE_SAMPLESET = BitArray(bin='1001')

    # Reset (table2)
    RESET_NO = BitArray(bin='00')
    RESET_FIFO_ONLY = BitArray(bin='01')
    RESET_ALL_REGISTERS = BitArray(bin='10')
    RESET_UNUSED = BitArray(bin='00')

    # Power management mode
    POWER_NORMAL = BitArray(bin='00')  # All circuitry is fully powered up at all times
    POWER_AUTO_SHUTDOWN = BitArray(bin='01')  # The device enters full shutdown mode at the end of each conversion
    POWER_AUTO_STANDBY = BitArray(
        bin='10')  # The device powers down all circuitry except for the internal bias generator.

    # Chan_id
    CHAN_ID_EXTERNAL_CLOCK = BitArray(bin='0')
    CHAN_ID_IDK = BitArray(bin='1')

    SWCNV_CNVST = BitArray(bin='0')
    SWCNV_CS = BitArray(bin='1')

    # Analog input channel select (table 4)
    AIN0 = BitArray(bin='0000')
    AIN1 = BitArray(bin='0001')
    AIN2 = BitArray(bin='0010')
    AIN3 = BitArray(bin='0011')
    AIN4 = BitArray(bin='0100')
    AIN5 = BitArray(bin='0101')
    AIN6 = BitArray(bin='0110')
    AIN7 = BitArray(bin='0111')
    AIN8 = BitArray(bin='1000')
    AIN9 = BitArray(bin='1001')
    AIN10 = BitArray(bin='1010')
    AIN11 = BitArray(bin='1011')
    AIN12 = BitArray(bin='1100')
    AIN13 = BitArray(bin='1101')
    AIN14 = BitArray(bin='1110')
    AIN15 = BitArray(bin='1111')

    # ADC configuration register (Table 6)
    REFSEL_EXTERNAL_SINGLE_ENDED = BitArray(bin='0')
    REFSEL_EXTERNAL_DIFFERENTIAL = BitArray(bin='1')
    AVGON_OFF = BitArray(bin='0')
    AVGON_ON = BitArray(bin='1')
    NAVG_4_CONV = BitArray(bin='00')
    NAVG_32_CONV = BitArray(bin='11')
    NAVG_16_CONV = BitArray(bin='10')
    # TODO missing
    NSCAN_4_RESULTS = BitArray(bin='00')
    # TODO missing
    SPM_NORMAL = BitArray(bin='00')
    # TODO missing
    ECHO_ON = BitArray(bin='1')
    ECHO_OFF = BitArray(bin='0')
    UNUSED = BitArray(bin='0')

    def get_default_adc_mode_control(self):
        out = self.REGISTER_ADC_MODE_CONTROL + \
              self.SCAN_CONTROL_MODE_STANDARD_EXT + \
              self.AIN10 + \
              self.RESET_NO + \
              self.POWER_NORMAL + \
              self.CHAN_ID_IDK + \
              self.SWCNV_CS + \
              self.UNUSED

        return out

    def get_default_adc_config(self):
        out = self.REGISTER_ADC_CONFIGURATION + \
              self.REFSEL_EXTERNAL_SINGLE_ENDED + \
              self.AVGON_ON + \
              self.NAVG_32_CONV + \
              self.NSCAN_4_RESULTS + \
              self.SPM_NORMAL + \
              self.ECHO_ON + \
              self.UNUSED

        return out
