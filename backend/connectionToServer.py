import threading

import grpc

import sys, os

dir = os.getcwd()
curr_dir = "backend"

if curr_dir in dir:
    sys.path.insert(1, "../")
else:
    sys.path.insert(1, "./")

import protos.messages_pb2 as messages_pb2 ## as chat
import protos.messages_pb2_grpc as messages_pb2_grpc ## as rpc

from communication.connectionData import *

class ClientBE:
    def __init__(self):
        """
        The initialization will create a connection with the server, then starts the action and the request's listeners
        """
        # Create a gRPC channel + stub
        channel = grpc.insecure_channel(address + ':' + str(port))
        self.conn = messages_pb2_grpc.BroadcastStub(channel)
        print("Backend connected at port {}".format(port))
        # Create new listening thread for when new message streams come in
        print("\nStarting action listener...")
        threading.Thread(target=self.sub_action, daemon=False).start()
        print("Started!")
        print("\nStarting request listener...")
        threading.Thread(target=self.sub_request, daemon=False).start()
        print("Started!")

    def sub_request(self):
        """
        This method will be ran in a separate thread, because the for-in call is blocking when waiting for new messages
        """
        for note in self.conn.SubRequest(messages_pb2.Empty()):  # This line will wait for new messages from the server!
            # Note is the array with last actions stored on the server
            # The for cycle will get the request name
            for key, value in REQUESTS.items():
                if value == note.type:
                    print("Data received: REQUEST:{}".format(key))

                    # Send the asked data
                    ## EXAMPLE: response to request management
                    datatype = key
                    # Data received from the accumulator
                    mydata = []
                    for i in range(10):
                        mydata.append(i)

                    print("\nSending {} data: {}...".format(datatype, mydata))
                    self.send_response(datatype, mydata)
                    print("Data sent!")

    def send_response(self, res_type, res_data):
        """
        This method is called when the frontend asks for some data and the accumulator has sent them to the backend (this)
        """
        # Managing how to send requests
        response = messages_pb2.Response()
        response.type = REQUESTS.get(res_type)
        response.data.extend(res_data)
        print("Sending a response...")
        self.conn.SendResponse(response)
        print("Response sent!")

    def sub_action(self):
        """
        This method will be ran in a separate thread, because the for-in call is blocking when waiting for new messages
        """
        for note in self.conn.SubAction(messages_pb2.Empty()): # this line will wait for new messages from the server!
            # Note is the array with last actions stored on the server
            # The for cycle will get the request name
            for key, value in ACTIONS.items():
                if value == note.type:
                    print("Data received: ACTION:{} - {}".format(key, note.value))
            # Execute the requested action


if __name__ == '__main__':
    print("Initializing BEClient...")
    c = ClientBE()
    print("\nBEClient initialized!")
