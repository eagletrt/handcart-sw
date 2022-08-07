timer = [];
getUrl = window.location;
url = getUrl .protocol + "//" + getUrl.host + "/";
errMsg = "Device not connected!";
hintMsg = "Connect the device and refresh."
OFFLINE_CODE = 450;
NZ = "nozoom";
IS_WARNING = "NLG5_S_WAR";
WARNINGS = {
    "NLG5_S_BPD_I":     "Bypass detection bit 1; 00: no bypass, 01: DC bypass detected, 10:AC bypass in phase, 11: AC bypass not in phase",
    "NLG5_S_BPD_II":    "Bypass detection bit 2; 00: no bypass, 01: DC bypass detected, 10:AC bypass in phase, 11: AC bypass not in phase",
    "NLG5_S_L_OV":      "Output power limited by battery output voltage limit",
    "NLG5_S_L_OC":      "Output power limited by battery output current limit",
    "NLG5_S_L_MC":      "Output power limited by mains current limit",
    "NLG5_S_L_PI":      "Output power limited by analog input 'power indicator' (PI) limit",
    "NLG5_S_L_CP":      "Output power limited by control pilot signal (SAE J1772)",
    "NLG5_S_L_PMAX":    "Output power limited by maximum power capability of NLG5",
    "NLG5_S_L_MC_MAX":  "Output power limited by maximum mains current capability of NLG5",
    "NLG5_S_L_OC_MAX":  "Output power limited by maximum output current capability of NLG5",
    "NLG5_S_L_MO_MAX":  "Output power limited by maximum output voltage capability of NLG5",
    "NLG5_S_L_T_CPRIM": "Output power limited by temperature of primary capacitors",
    "NLG5_S_L_T_POW":   "Output power limited by temperature of power stage",
    "NLG5_S_L_T_DIO":   "Output power limited by temperature of diodes",
    "NLG5_S_L_T_TR":    "Output power limited by temperature of transformer",
    "NLG5_S_L_T_BATT":  "Output power limited by battery temperature"
};
states = {  // a dictionary containing HTML ids and sessionStorage's keys
    "bmsState": "bmsState",
    "hcState": "hcState",
    "brusaState": "brusaState",
    "timeText": "timeText",
    "nWarnings": "warnings",
    "nErrors": "errors",
    "fan": "fanOnOff",
    "fo": "foState",
    "fanSpeed": "mfsValue",
    "temp": "average_temp",
    "volt": "bus_voltage",
    "COvolt": "covValue",
    "amp": "current",
    "charge": "charge"
};