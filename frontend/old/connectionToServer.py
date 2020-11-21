import threading

import grpc

import sys, os

dir = os.getcwd()
curr_dir = "frontend"

if curr_dir in dir:
    sys.path.insert(1, "../")
else:
    sys.path.insert(1, "./")

import protos.messages_pb2 as messages_pb2 ## as chat
import protos.messages_pb2_grpc as messages_pb2_grpc ## as rpc

from communication.connectionData import *

class ClientFE:
    def __init__(self):
        """
        The initialization will create a connection with the server, then starts the response's listeners
        """
        # the frame to put ui components on
        #self.window = window
        #self.username = u
        # create a gRPC channel + stub
        channel = grpc.insecure_channel(address + ':' + str(port))
        self.conn = messages_pb2_grpc.BroadcastStub(channel)
        print("Frontend connected at port {}".format(port))
        # Create new listening thread for when new message streams come in
        print("\nStarting response listener...")
        threading.Thread(target=self.sub_response, daemon=False).start()
        print("Started!")
        #self.__setup_ui()
        #self.window.mainloop()

    def sub_response(self):
        """
        This method will be ran in a separate thread, because the for-in call is blocking when waiting for new messages
        """
        for note in self.conn.SubResponse(messages_pb2.Empty()): # this line will wait for new messages from the server!
            # Note is the array with last messages stored on the server
            # The for cycle will get the request name
            for key, value in REQUESTS.items():
                if value == note.type:
                    print("Data received: RESPONSE:{} - {}".format(key, note.data))

            # Do what you need to do with data
        """
        # Graphic part
        print("R[{}] {}".format(note.name, note.message))  # debugging statement
        self.chat_list.insert(END, "[{}] {}\n".format(note.name, note.message))  # add the message to the UI
        """

    def send_request(self, req_type):
        """
        This method is called when the user asks for some data so the frontend (this) ask them to the backend
        """
        # Managing how to send requests and actions
        request = messages_pb2.Request()
        request.type = REQUESTS.get(req_type)
        print("Sending a request...")
        self.conn.SendRequest(request)
        print("Request sent!")

    def send_action(self, act_type, act_value=-1):
        """
        This method is called when the user needs to do some action so the frontend (this) ask to the backend to do it
        """
        # Managing how to send requests and actions
        action = messages_pb2.Action()
        action.type = ACTIONS.get(act_type)
        action.value = act_value
        print("Sending an action...")
        self.conn.SendAction(action)
        print("Action sent!")

    """
    def __setup_ui(self):
        self.chat_list = Text()
        self.chat_list.pack(side=TOP)
        self.lbl_username = Label(self.window, text=self.username)
        self.lbl_username.pack(side=LEFT)
        self.entry_message = Entry(self.window, bd=5)
        self.entry_message.bind('<Return>', self.send_message)
        self.entry_message.focus()
        self.entry_message.pack(side=BOTTOM)
    """


if __name__ == '__main__':
    datatype = "VOLTAGE"

    print("Initializing FEClient...")
    c = ClientFE()
    print("\nFEClient initialized!")

    print("\nSending {} request...".format(datatype))
    c.send_request(datatype)
    print("Request sent!")

    """
    root = Tk()  # I just used a very simple Tk window for the chat UI, this can be replaced by anything
    frame = Frame(root, width=300, height=300)
    frame.pack()
    root.withdraw()
    username = None
    while username is None:
        # retrieve a username so we can distinguish all the different clients
        username = simpledialog.askstring("Username", "What's your username?", parent=root)
    root.deiconify()  # don't remember why this was needed anymore...
    c = Client(username, frame)  # this starts a client and thus a thread which keeps connection to server open
    """