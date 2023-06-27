from os.path import join, dirname, realpath

import common.handcart_can as handcart_can
import can
import cantools
from cantools.database import Database
from cantools.database.can import message

brusa_dbc_file = join(dirname(dirname(dirname(realpath(__file__)))), "NLG5_BRUSA.dbc")
BMS_DBC_PATH = join(dirname(dirname(realpath(__file__))), "can_eagle", "dbc", "bms", "bms.dbc")
DBC_PRIMARY_PATH = join(dirname(dirname(realpath(__file__))), "can_eagle", "dbc", "primary", "primary.dbc")
dbc_brusa: Database = cantools.database.load_file(brusa_dbc_file)
dbc_bms: Database = cantools.database.load_file(BMS_DBC_PATH)  # load the bms dbc file
dbc_primary: Database = cantools.database.load_file(DBC_PRIMARY_PATH)  # load the bms dbc file


def test_1():
    for i in dbc_primary.messages:
        print(i)
    m: message = dbc_primary.get_message_by_name("HV_VERSION")

    for j in m.signals:
        print(j)

    data = m.encode({"component_version": 12, "canlib_build_time": 123})

    can_message = can.Message(arbitration_id=m.frame_id, data=data)

    recv_data = dbc_primary.decode_message(can_message.arbitration_id, can_message.data)

    print(recv_data)


m: message = dbc_primary.get_message_by_name("TS_STATUS")


def test_2():
    for i in dbc_primary.messages:
        print(i)
    m: message = dbc_primary.get_message_by_name("HANDCART_STATUS")

    print(m)
    print(m.signals)
    for j in m.signals:
        print(f"\"{j.name}\" : None,")
        # d : OrderedDict = j.choices
        # print(d)
        # while len(d)>0:
        #    val, name = d.popitem(last=False)
        #    print(f"{val} {name}")


def test_HANDCART_SET_COMMAND():
    message = dbc_primary.get_message_by_name("HANDCART_SETTINGS_SET")
    data = message.encode({
        "target_voltage": 450,
        "fans_override": 0,
        "fans_speed": 0,
        "acc_charge_current": 4,
        "grid_max_current": 4,
        "status": 0
    })
    can_message = can.Message(arbitration_id=message.frame_id, data=data, is_extended_id=False)
    commands = handcart_can.do_HANDCART_SETTING_SET(can_message)

    assert commands == [{'com-type': 'cutoff', 'value': 449.7725490196078}, {'com-type': 'fan-override-set-status', 'value': False}, {'com-type': 'fan-override-set-speed', 'value': 0.0}, {'com-type': 'max-out-current', 'value': 4.0}, {'com-type': 'max-in-current', 'value': 4.0}]

    data = message.encode({
        "target_voltage": 450,
        "fans_override": 1,
        "fans_speed": 0.59,
        "acc_charge_current": 6,
        "grid_max_current": 6,
        "status": 0
    })
    can_message = can.Message(arbitration_id=message.frame_id, data=data, is_extended_id=False)
    commands = handcart_can.do_HANDCART_SETTING_SET(can_message)

    assert {"com-type":"fan-override-set-status", "value": True } in commands
    for i in commands:
        if i["com-type"] == "fan-override-set-speed":
            assert (58 <= i["value"] <= 59)

        if i["com-type"] == "max-out-current":
            assert i["value"] == 6

        if i["com-type"] == "max-in-current":
            assert i["value"] == 6


    print (commands)