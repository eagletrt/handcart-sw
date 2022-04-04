# Can send test
# Before use, pls run the script "start-can.sh"

import can
import serial

bus = can.interface.Bus(interface='socketcan',
                        channel='can1',
                        receive_own_messages=True)
ser = serial.Serial('/dev/ttyACM0', 115200)

ID_INV_RX = 0x201


def send_ask_msg():
    REGISTERS = [
        0x49, # Motor Temperature
        0xA8, # Motor speed RPMs
        0x20 # I actual motor
    ]

    for reg in REGISTERS:
        act_msg = can.Message(arbitration_id=ID_INV_RX, data=[0x3D, reg, 0x32], is_extended_id=False)

        try:
            bus.send(act_msg)
            print("Message sent on {}".format(bus.channel_info))
        except can.CanError:
            print("Message NOT sent")

send_ask_msg()

print("Reading and forwarding serial temps")

while ser.is_open:
    raw = str(ser.readline())
    temp = raw.split(']')[1].split('\\r')[0]
    t = temp.split('.')
    temp_l = t[0]
    temp_r = t[1]
    print(temp)

    temp_l = int(temp_l)
    temp_r = int(temp_r)

    act_msg = can.Message(arbitration_id=0x07, data=[temp_l, temp_r], is_extended_id=False)
    try:
        bus.send(act_msg)
    except can.CanError:
        print("Message NOT sent")
