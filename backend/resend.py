import can
from can.listener import Listener

bus = can.interface.Bus(interface='socketcan',
                        channel='can0',
                        receive_own_messages=True)

class Can_rx_listener(Listener):
    def on_message_received(self, msg):
        print(msg)
        if msg.arbitration_id == 0x79:
            m = can.Message(arbitration_id=0x80, data=[1,0,0], is_extended_id=False)

            bus.send(m)
            exit()


l = Can_rx_listener()
notif = can.Notifier(bus, [l])

while(1):
    pass