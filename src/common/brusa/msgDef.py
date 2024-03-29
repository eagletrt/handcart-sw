#
#   This file contains string reference for can messages
#

NLG5_ERR_DEF = [
    "battery output overvoltage; error can only be cleared by cycling power ON-OFF-ON",
    "Mains overvoltage 2 detected",
    "Mains overvoltage 1 detected",
    "power stage short circuit condition detected; error can only be cleared by cycling power ON-OFF-ON",
    "plausibility battery output voltage measurement wrong",
    "plausibility mains voltage measurement wrong",
    "output fuse defective",
    "Mains fuse defective",
    "wrong battery polarity; error can only be cleared by cycling power ON-OFF-ON",
    "Temperature sensor for prim capacitor defective",
    "Temperature sensor for prim power stage defective",
    "Temperature sensor for diodes defective",
    "Temperature sensor for transformer defective",
    "Ext. temperature sensor 1 defective (if enabled)",
    "Ext. temperature sensor 2 defective (if enabled)",
    "Ext. temperature sensor 3 defective (if enabled)",
    "Flash memory checksum failure",
    "NVSRAM check sum failure; contains most of the scaling & calibration values, CAN ID's and charging profile etc.",
    "Sys EEPROM checksum failure",
    "Pow EEPROM checksum failure",
    "Internal Watchdog Timeout",
    "Initialization error",
    "CAN timeout, no control message received for >300ms",
    "CAN off, transmit buffer >255",
    "CAN transmit buffer >127",
    "CAN receiver buffer >127",
    "Emergency Shutdown Threshold 'Battery Temperature' is exceeded; see ChargeStar help section 'protective "
    "features'; error can only be cleared by cycling power ON-OFF-ON",
    "Emergency Shutdown Threshold 'Battery Voltage' is exceeded; see ChargeStar help section 'protective features'; "
    "error can only be cleared by cycling power ON-OFF-ON",
    "Emergency Shutdown Threshold 'Amp Hours' is exceeded; see ChargeStar help section 'protective features'; error "
    "can only be cleared by cycling power ON-OFF-ON",
    "Emergency Shutdown Threshold 'Charging Time' is exceeded; see ChargeStar help section 'protective features'; "
    "error can only be cleared by cycling power ON-OFF-ON",
    "",
    "",
    "Output power limited by low mains voltage",
    "Output power limited by low battery voltage",
    "Output power limited by charger internal overtemperature",
    "Commanded value is out of specified range; max or min applicable value is assumed instead",
    "NLG5 Control message not active",
    "LED Output driver defective, LEDs can´t be controlled by NLG5 anymore. Charging is still possible.",
    "Save-Charging-Mode reduces primary current to 3.95 A as long as one of the four internal temperature sensors "
    "indicates -18° C or less."
]

NLG5_ST_DEF = [
    "Indicates if hardware enabled, i.e. a hi or lo signal is fed to the 'Power On' pin (pin3 of control connector)",
    "An error has been detected, red LED is ON, no power is output",
    "Warning condition on, i.e. charging power limited due to any limiting condition; red LED is blinking",
    "Charger cooling fan is active",
    "European mains input detected (230V, 50Hz)",
    "US mains level 1 (120VAC / 60Hz) detected",
    "US mains level 2 (240VAC / 60Hz) detected",
    "Control pilot signal (SAE J1772) detected ",
    "Bypass detection bit 1; 00: no bypass, 01: DC bypass detected, 10:AC bypass in phase, 11: AC bypass not in phase",
    "Bypass detection bit 2; 00: no bypass, 01: DC bypass detected, 10:AC bypass in phase, 11: AC bypass not in phase",
    "Output power limited by battery output voltage limit",
    "Output power limited by battery output current limit",
    "Output power limited by mains current limit",
    "Output power limited by analog input 'power indicator' (PI) limit",
    "Output power limited by control pilot signal (SAE J1772)",
    "Output power limited by maximum power capability of NLG5",
    "Output power limited by maximum mains current capability of NLG5",
    "Output power limited by maximum output current capability of NLG5",
    "Output power limited by maximum output voltage capability of NLG5",
    "Output power limited by temperature of primary capacitors",
    "Output power limited by temperature of power stage",
    "Output power limited by temperature of diodes",
    "Output power limited by temperature of transformer",
    "Output power limited by battery temperature",
    "AUX 12 V Automatic Charging Active"
]
