from concurrent import futures
import grpc

import messages_pb2
import messages_pb2_grpc

class HandcartServer(messages_pb2_grpc.BroadcastServicer):

    def __init__(self):
        self.messages = []
        self.actions = []

    def SubResponse(self, request, context):
        while True:
            lastindex = 0

            while True:
                # Check if there are any new messages
                while len(self.messages) > lastindex:
                    # Never pop or remove to have a history (can change this thing)
                    msg = self.messages[lastindex]
                    lastindex += 1
                    # This is generator's return, so we will have messages as a list, when we call the function
                    yield msg

    def SendResponse(self, request, context):
        # We only need request, but context could contain something that we'll need
        pair = [request, context]
        self.messages.append(pair)
        return self.messages.Empty()

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
        pair = [request, context]
        self.actions.append(pair)
        return self.messages.Empty()

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    messages_pb2_grpc.add_BroadcastServicer_to_server(HandcartServer(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()