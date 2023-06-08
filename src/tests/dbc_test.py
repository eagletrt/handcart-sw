from collections import OrderedDict
from enum import Enum
from os.path import join, dirname, realpath

import can
import cantools
from cantools.database import Database
from cantools.database.can import message

brusa_dbc_file = join(dirname(dirname(dirname(realpath(__file__)))), "NLG5_BRUSA.dbc")
BMS_DBC_PATH = join(dirname(dirname(realpath(__file__))), "can_eagle", "dbc", "bms", "bms.dbc")
DBC_PRIMARY_PATH = join(dirname(dirname(realpath(__file__))), "can_eagle", "dbc", "primary", "primary.dbc")
dbc_brusa : Database = cantools.database.load_file(dbc_brusa_file)
dbc_bms : Database = cantools.database.load_file(BMS_DBC_PATH) # load the bms dbc file
dbc_primary : Database = cantools.database.load_file(DBC_PRIMARY_PATH) # load the bms dbc file

def test_1():
    for i in dbc_primary.messages:
        print(i)
    m : message = dbc_primary.get_message_by_name("HV_VERSION")

    for j in m.signals:
        print(j)

    data = m.encode({"component_version": 12, "canlib_build_time": 123})

    can_message = can.Message(arbitration_id=m.frame_id, data=data)

    recv_data = dbc_primary.decode_message(can_message.arbitration_id, can_message.data)

    print(recv_data)

m : message = dbc_primary.get_message_by_name("TS_STATUS")


def test_2():
    for i in dbc_primary.messages:
        print(i)
    m : message = dbc_primary.get_message_by_name("HANDCART_STATUS")

    print(m)
    print(m.signals)
    for j in m.signals:
        print(f"\"{j.name}\" : None,")
        #d : OrderedDict = j.choices
        #print(d)
        #while len(d)>0:
        #    val, name = d.popitem(last=False)
        #    print(f"{val} {name}")




test_2()