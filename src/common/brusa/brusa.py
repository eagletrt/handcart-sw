from datetime import datetime
from enum import Enum

from settings import dbc_brusa


class CAN_BRUSA_MSG_ID(Enum):
    """Enum containing the IDs of BRUSA's can messages"""
    NLG5_ERR = 0x614
    NLG5_TEMP = 0x613
    NLG5_ACT_I = 0x611
    NLG5_ACT_II = 0x612
    NLG5_ST = 0x610
    NLG5_CTL = 0x618


class BRUSA:
    """Class to store and process all the Brusa data
    """
    lastupdated = 1  # bypass the check of brusa presence if set to 1
    last_act_I = datetime.now().isoformat()

    charged_capacity_ah = 0
    charged_capacity_wh = 0

    act_NLG5_ST_values = {}
    act_NLG5_ACT_I = {'NLG5_OV_ACT': 0,
                      'NLG5_OC_ACT': 0,
                      'NLG5_MV_ACT': 0,
                      'NLG5_MC_ACT': 0,
                      'NLG5_S_MC_M_CP': 0,
                      'NLG5_P_TMP': 0}
    act_NLG5_ACT_II = {'NLG5_S_MC_M_CP': 0,
                       'NLG5_AHC_EXT': 0}
    act_NLG5_TEMP = {'NLG5_P_TMP': 0}
    act_NLG5_ERR = {}

    error = False
    act_NLG5_ERR_list = []
    act_NLG5_ST_srt = []

    def isConnected(self):
        """Checks if Brusa is connected
        :return: True if Brusa is connected
        """
        if self.lastupdated == 0:
            return False
        else:
            return True
        # elif self.lastupdated != 1:
        #    return (datetime.now() - datetime.fromisoformat(str(self.lastupdated))).seconds \
        #           < CAN_BRUSA_PRESENCE_TIMEOUT

    def doNLG5_ST(self, msg):
        """
        Processes a CAN Status message from Brusa
        :param msg: the Can message
        """
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()

        self.act_NLG5_ST_values = dbc_brusa.decode_message(msg.arbitration_id, msg.data)
        for key in self.act_NLG5_ST_values:
            value = self.act_NLG5_ST_values[key]
            if (value == 1):
                signals = dbc_brusa.get_message_by_name('NLG5_ST').signals
                for s in signals:
                    if s.name == key:
                        self.act_NLG5_ST_srt.append(s.comment)
                        break

        if self.act_NLG5_ST_values['NLG5_S_ERR'] == 1:
            self.error = True

    def doNLG5_ACT_I(self, msg):
        """
        Process a CAN ACT_I message from Brusa
        :param msg: the ACT_I can message
        """
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()
        self.act_NLG5_ACT_I = dbc_brusa.decode_message(msg.arbitration_id, msg.data)

        if self.act_NLG5_ACT_I["NLG5_OC_ACT"] != 0:
            delta = (datetime.fromisoformat(self.lastupdated) - datetime.fromisoformat(self.last_act_I)).microseconds \
                    * (1 / (3600 * 1000000))
            self.charged_capacity_ah += self.act_NLG5_ACT_I["NLG5_OC_ACT"] * delta
            self.charged_capacity_wh += (self.act_NLG5_ACT_I["NLG5_OC_ACT"]
                                         * self.act_NLG5_ACT_I["NLG5_OV_ACT"]) * delta
        self.last_act_I = self.lastupdated

    def doNLG5_ACT_II(self, msg):
        """
        Process a CAN ACT_II message from Brusa
        :param msg: the ACT_II can message
        """
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()
        self.act_NLG5_ACT_II = dbc_brusa.decode_message(msg.arbitration_id, msg.data)

    def doNLG5_TEMP(self, msg):
        """
        Process a CAN TEMP message from Brusa
        :param msg: the TEMP can message
        """
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()
        self.act_NLG5_TEMP = dbc_brusa.decode_message(msg.arbitration_id, msg.data)

    def doNLG5_ERR(self, msg):
        """
        Process a CAN ERR message from Brusa
        :param msg: the ERR can message
        """
        self.lastupdated = datetime.fromtimestamp(msg.timestamp).isoformat()
        self.act_NLG5_ERR = dbc_brusa.decode_message(msg.arbitration_id, msg.data)
        self.act_NLG5_ERR_list = []

        for key in self.act_NLG5_ERR:
            value = self.act_NLG5_ERR[key]
            if value == 1:
                self.error = True
                signals = dbc_brusa.get_message_by_name('NLG5_ERR').signals
                for s in signals:
                    if s.name == key:
                        self.act_NLG5_ERR_list.append(s.comment)
                        break
