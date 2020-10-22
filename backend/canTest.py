import can

bus = can.interface.Bus(interface='socketcan',
              channel='can0',
              receive_own_messages=True)

msg = bus.recv()

print(msg)