import os
import select
import sys
import termios
import time
import tty

import requests

SERVER_ADDRESS = 'http://127.0.0.1:5000/'
server_connected = False
brusa_connected = False
bms_connected = False
handcart_state = ""


def printcolor(color, text):
    if color == "green":
        print("\033[;32m" + text + "\033[0m")
    if color == "red":
        print("\033[;31m" + text + "\033[0m")


def printbrusaerrors():
    r = requests.get(SERVER_ADDRESS + "brusa/errors/")
    try:
        if r.status_code == 200:
            for i in r.json()['errors']:
                printcolor("red", "[Brusa] " + i['desc'])
    except:
        global server_connected
        server_connected = False


def printcommands():
    pass


def main():
    printcolor("green", "▂▃▅▇█▓▒░۩۞۩    Handcart    ۩۞۩░▒▓█▇▅▃▂")
    print("")
    print("[Info]")
    global server_connected, brusa_connected, bms_connected, handcart_state
    if server_connected:
        print("Server:\tconnected")
    else:
        print("Server:\tNot connected")
    if brusa_connected:
        print("Brusa:\tconnected")
    else:
        print("Brusa:\tnot connected")
    if bms_connected:
        print("BMS:\tconnected")
    else:
        print("BMS:\tnot connected")

    if not server_connected:
        try:
            r = requests.get(SERVER_ADDRESS)

            if r.status_code == 200:
                server_connected = True
        except requests.exceptions.ConnectionError:
            pass

    try:
        r = requests.get(SERVER_ADDRESS + 'handcart/status/')
        if r.status_code == 200:
            print("")
            handcart_state = r.json()
            handcart_state = handcart_state['state']
            print("Handcart state: " + handcart_state)

    except requests.exceptions.ConnectionError:
        server_connected = False

    try:
        r = requests.get(SERVER_ADDRESS + 'brusa/status/')
        if r.status_code == 200:
            brusa_connected = True
        elif r.status_code == 400:
            brusa_connected = False
    except requests.exceptions.ConnectionError:
        server_connected = False

    try:
        r = requests.get(SERVER_ADDRESS + 'bms-hv/status/')
        if r.status_code == 200:
            bms_connected = True
        elif r.status_code == 400:
            bms_connected = False
    except requests.exceptions.ConnectionError:
        server_connected = False

    if handcart_state == "STATE.ERROR":
        print("")
        printcolor("red", "[ Errors ] (╥﹏╥)")
        printbrusaerrors()


def isData():
    return select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], [])


old_settings = termios.tcgetattr(sys.stdin)
try:
    tty.setcbreak(sys.stdin.fileno())
    buff = ""
    refresh = True
    while 1:

        # time = time.time()
        # Main loop
        os.system("clear")
        main()
        print()
        print("Avaiable commands:")
        print("")
        print("\t[c] Start charge\t[b] Stop charge")
        print("\t[f] Enable fast charge\t[t] Set cutoff voltage")
        print("")

        print("Command: " + buff)

        if isData():
            c = sys.stdin.read(1)

            if c == "c":
                print("sdasd")
            elif c == "b":
                pass
            elif c == "f":
                pass
            elif c == "t":
                desired_cutoff = input("Cutoff voltage: ")

            if c == '\x1b':  # x1b is ESC
                break

        time.sleep(0.5)

finally:
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

exit()

while (r.json()['state'] != 'STATE.READY'):
    time.sleep(1)
    r = requests.get(SERVER_ADDRESS + 'handcart/status/')
    print("Handcart STATE is: " + r.json()['state'])

if r.json(['state']) == 'STATE.READY':
    comm = input('Ready to charge, press y to start charging: ')
    if comm == 'y':
        # Sends request to backend
        pass
