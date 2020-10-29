import can

bus = can.interface.Bus(interface='socketcan',
              channel='can0',
              receive_own_messages=True)

msg = can.Message(arbitration_id=0x611,
                    data=[0, 25, 0, 1, 3, 1, 4, 1])

try:
    bus.send(msg)
    print("Message sent on {}".format(bus.channel_info))
except can.CanError:
    print("Message NOT sent")