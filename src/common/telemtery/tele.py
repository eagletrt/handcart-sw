import queue
import threading
import time
from datetime import datetime

import can
import paho.mqtt.client as mqtt

from common.handcart_can import CanListener
from lib.primary.python.ids import *
from proto.primary.python import primary_pb2

TELE_MQTT_TOPIC = "handcart"
# "handcart/commands" i comandi
# hasndcart/commands/set

# "handcart/update_data
# "handcart/status status

# https://github.com/eagletrt/telemetry-json-loader
# Aggiungere un file json per ogni comando da mandare all'handcart

TELE_MQTT_SERVER_ADDR = 
TELE_MQTT_SERVER_PORT = 1883
TELE_MAX_LOCKED_QUEUE_GET = 10


class Tele(threading.Thread):
    """
    Thread that manages the communication with the telemetry system of E-Agle.
    It won't need the lock to access shared_data as it only reads it.
    It has access to the command queue to add them.
    It uses a dedicated queue to get the messages from the can and to process/send them to the tele
    """

    mqtt_client: mqtt.Client = None
    shared_data: CanListener
    com_queue: queue.Queue
    tele_can_queue: queue.Queue

    def __init__(self,
                 shared_data: CanListener,
                 com_queue: queue.Queue,
                 tele_can_queue: queue.Queue):
        super().__init__(args=(shared_data,
                               com_queue))

        self.shared_data = self._args[0]
        self.com_queue = self._args[1]
        self.tele_can_queue = self._args[2]

        self.init_mqtt()

    def on_connect(self, userdata, flags, rc):
        print("Connected to mqtt with result code " + str(rc))
        self.client.subscribe(TELE_MQTT_TOPIC)

    def on_message(self, client, userdata, msg):
        """
        Called whether a message is received by the server. (should receive commands)
        """
        print(msg.topic + " " + str(msg.payload))

        # TODO: test and validate before enabling this
        command: dict[str, str] = msg.payload

        # self.com_queue.put(command)

    def on_publish(self, client, userdata, result):
        print("data published \n")
        # pack https://github.com/eagletrt/can/blob/build/proto/.proto/primary.proto
        # primary.proto Pack to send over mqtt
        pass

    def init_mqtt(self):
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(TELE_MQTT_SERVER_ADDR, 1883, 60)
        self.client.on_publish = self.on_publish


    def process_can_queue(self):
        gets = 0
        while not self.tele_can_queue.empty() and gets <= TELE_MAX_LOCKED_QUEUE_GET:
            msg: can.Message = self.tele_can_queue.get()
            gets += 1

    def run(self) -> None:
        """
        Runs the thread
        """

        while 1:
            time.sleep(1)
            # TODO: call process_can_queue directly?

            t = datetime.now().timestamp()
            # Convert timestamp to microsecond resolution
            t = int(t * 1000000)

            pack = primary_pb2.Pack()

            # TEST
            hv_temp = primary_pb2.HV_TEMP()
            # hv_temp.average_temp = 50.1
            hv_temp.max_temp = 50.1
            # hv_temp.min_temp = 10.1
            hv_temp._inner_timestamp = t
            pack.HV_TEMP.append(hv_temp)

            serialized = pack.SerializeToString()
            ret = self.client.publish(TELE_MQTT_TOPIC, serialized)
