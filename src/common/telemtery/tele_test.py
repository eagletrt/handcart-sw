import datetime
import json
import time

import paho.mqtt.client as mqtt
from proto.primary.python import primary_pb2

topic = "update_data"

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    #topic = "telemetry_get_config"
    client.subscribe(topic)

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    print(msg.topic+" "+str(msg.payload))


def on_publish(client,userdata,result):
    print("data published \n")
    pass

# pack https://github.com/eagletrt/can/blob/build/proto/.proto/primary.proto
# primary.proto Pack to send over mqtt

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect("167.99.136.159", 1883, 60)

client.on_publish = on_publish


while 1:
    time.sleep(1)
    t = datetime.datetime.now().timestamp()
    t = int(t*1000000)

    a = primary_pb2.Pack()
    hv_temp = primary_pb2.HV_TEMP()
    #hv_temp.average_temp = 50.1
    hv_temp.max_temp = 50.1
    #hv_temp.min_temp = 10.1
    hv_temp._inner_timestamp = t
    a.HV_TEMP.append(hv_temp)
    ser = a.SerializeToString()#.decode("latin1") #.decode("utf-8", errors='strict')

    test = bytearray(ser)
    res = ""
    for i in test:
        res += "\\x" + hex(i).split("0x")[1]

    print(bytes("\t", "utf-8"))

    res = '\\x82\\x01\\t \\xde\\xca\\xa6\\x92\\xc3\\xed\\xfd\\x02'

    #TODO: Fare un nuovo topic solo per l'handcart, formato così:
    # timestamp (in byte) separator(in byte) contenuto di protobuf in byte

    print(a)
    ser = str(ser)
    ser = ser.replace("b'", "")
    ser = ser.replace("'", "")

    print(ser)

    car_data = {
        "timestamp": t,
        "primary": res,
        "secondary": "",
        "gps": "",
        "inverters": "",
        "can_frequencies": ""
    }
    print(car_data.__repr__())
    ret = client.publish(topic, json.dumps(car_data))

# Blocking call that processes network traffic, dispatches callbacks and
# handles reconnecting.
# Other loop*() functions are available that give a threaded interface and a
# manual interface.
client.loop_forever()

