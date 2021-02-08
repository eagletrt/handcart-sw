from enum import Enum

from ctypes import c_uint8

# Gives the position of things in "NLG5_ST_POS" can message's data segment
# See BRUSA's can messages sheet for reference
# Maschera per fare l'and bit a bit


NLG5_ST_MASK = {
    0b10000000: "NLG5_S_HE",
    "NLG5_S_ERR": 0b01000000,
    "NLG5_S_WAR": 0b00100000,
    "NLG5_S_FAN": 0b00010000,
    "NLG5_S_EUM": 0b00001000,
    "NLG5_S_UM_I": 0b00000100,
    "NLG5_S_UM_II": 0b00000010,
    "NLG5_S_CP_DT": 0b00000001,
    "NLG5_S_BPD_I": 0b10000000,
    "NLG5_S_BPD_II": 0b01000000,
    "NLG5_S_L_OV": 0b00100000,
    "NLG5_S_L_OC": 0b00010000,
    "NLG5_S_L_MC": 0b00001000,
    "NLG5_S_L_PI": 0b0000100,
    "NLG5_S_L_CP": 0b00000010,
    "NLG5_S_L_PMAX": 0b00000001,
    "NLG5_S_L_MC_MAX": 0b10000000,
    "NLG5_S_L_OC_MAX": 0b01000000,
    "NLG5_S_L_MO_MAX": 0b00100000,
    "NLG5_S_L_T_CPRIM": 0b00010000,
    "NLG5_S_L_T_POW": 0b00001000,
    "NLG5_S_L_T_DIO": 0b00000100,
    "NLG5_S_L_T_TR": 0b00000010,
    "NLG5_S_L_T_BATT": 0b00000001,
    "NLG5_S_AAC": 0b10000000
}

data = [0b00000010, 0b00000000]

print(NLG5_ST_MASK.get(0b10000000))

asd = bytes(data)

print(10 & 0b0000100)

if data[0] & 0b0000100: NLG5_S_HE = True