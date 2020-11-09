import sys, os
from concurrent import futures

import grpc

dir = os.getcwd()
curr_dir = "communication"

if curr_dir in dir:
    sys.path.insert(1, "../")
else:
    sys.path.insert(1, "./")

import protos.messages_pb2 as messages_pb2
import protos.messages_pb2_grpc as messages_pb2_grpc

from communication.connectionData import port as port

class HandcartServer(messages_pb2_grpc.BroadcastServicer):

    def __init__(self):
        self.request = []
        self.response = []
        self.actions = []

    def SubRequest(self, request, context):
        while True:
            lastindex = 0

            while True:
                # Check if there are any new messages
                while len(self.request) > lastindex:
                    # Never pop or remove to have a history (can change this thing)
                    msg = self.request[lastindex]
                    lastindex += 1
                    # This is generator's return, so we will have messages as a list, when we call the function
                    yield msg

    def SendRequest(self, request, context):
        print("Request received!")
        self.request.append(request)

        return messages_pb2.Empty()

    def SubResponse(self, request, context):
        while True:
            lastindex = 0

            while True:
                # Check if there are any new messages
                while len(self.response) > lastindex:
                    # Never pop or remove to have a history (can change this thing)
                    msg = self.response[lastindex]
                    lastindex += 1
                    # This is generator's return, so we will have messages as a list, when we call the function
                    yield msg

    def SendResponse(self, request, context):
        print("Response received!")
        self.response.append(request)

        return messages_pb2.Empty()

    def SubAction(self, request, context):
        while True:
            lastindex = 0

            while True:
                # Check if there are any new messages
                while len(self.actions) > lastindex:
                    # Never pop or remove to have a history (can change this thing)
                    act = self.actions[lastindex]
                    lastindex += 1
                    # This is generator's return, so we will have messages as a list, when we call the function
                    yield act

    def SendAction(self, request, context):
        print("Action received!")
        self.actions.append(request)

        return messages_pb2.Empty()

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    messages_pb2_grpc.add_BroadcastServicer_to_server(HandcartServer(), server)
    server.add_insecure_port('[::]:' + str(port))
    server.start()
    print("Running on port {}...".format(port))
    input("Press Enter to close\n")
    #server.wait_for_termination() ## Better with event handler
    print("Turning off the server...")
    server.stop(grace=True)
    print("Server turned off")


if __name__ == '__main__':
    serve()
