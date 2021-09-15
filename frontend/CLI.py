import curses
import json
from enum import Enum

import requests

DEFAULT_WIDTH = 80
DEFAULT_HEIGHT = 24
SERVER_ADDRESS = 'http://127.0.0.1:5000/'
handcart_connected = False
brusa_connected = False
bms_connected = False

THIRD = int(DEFAULT_WIDTH / 3)
FIRST_COLUMN_INDEX = 0
SECOND_COLUMN_INDEX = THIRD
THIRD_COLUMN_INDEX = THIRD * 2

stdscr = curses.initscr()

curses.noecho()
stdscr.keypad(True)
curses.halfdelay(5)

scroll = 0

# BMS HV
bms_status = "offline"
bms_volt = 0.0
bms_temp = 0.0
bms_cell_max = 0.0
bms_cell_min = 0.0
bms_v_req = 0.0
bms_a_req = 0.0
bms_err_str = ""

# BRUSA
brusa_status = "offline"
brusa_max_v_set = 0.0
brusa_max_a_set = 0.0
brusa_actual_out_v = 0.0
brusa_actual_out_a = 0.0
brusa_warning = False
brusa_err_str = ""

# HANDCART
handcart_status = "offline"
cutoff_voltage = 0
fast_charge = False


class Tab(Enum):
    MAIN = 0
    ERRORS = 1


def intro():
    begin_x = 0
    begin_y = 0
    height = DEFAULT_HEIGHT
    width = DEFAULT_WIDTH
    intro = curses.newwin(height, width, begin_y, begin_x)

    intro.addstr(1, int(DEFAULT_WIDTH / 2) - 22, "███████╗███████╗███╗   ██╗██╗ ██████╗███████╗")
    intro.addstr(2, int(DEFAULT_WIDTH / 2) - 22, "██╔════╝██╔════╝████╗  ██║██║██╔════╝██╔════╝")
    intro.addstr(3, int(DEFAULT_WIDTH / 2) - 22, "█████╗  █████╗  ██╔██╗ ██║██║██║     █████╗")
    intro.addstr(4, int(DEFAULT_WIDTH / 2) - 22, "██╔══╝  ██╔══╝  ██║╚██╗██║██║██║     ██╔══╝")
    intro.addstr(5, int(DEFAULT_WIDTH / 2) - 22, "██║     ███████╗██║ ╚████║██║╚██████╗███████╗")
    intro.addstr(6, int(DEFAULT_WIDTH / 2) - 22, "╚═╝     ╚══════╝╚═╝  ╚═══╝╚═╝ ╚═════╝╚══════╝")
    intro.addstr(7, int(DEFAULT_WIDTH / 2) - 22, ">>>>>>>>>>>>>>>> HANDCART >>>>>>>>>>>>>>>>>>>")
    intro.addstr(10, int(DEFAULT_WIDTH / 2) - 12, "press a key to continue..")

    intro.refresh()


def header():
    begin_x = 0
    begin_y = 0
    height = 3
    width = DEFAULT_WIDTH
    header = curses.newwin(height, width, begin_y, begin_x)

    header.addstr(1, int(DEFAULT_WIDTH / 2) - 4, "Handcart")
    handcart_status_str = "STATUS: check"
    header.addstr(1, 3, handcart_status_str)

    header.border()
    header.refresh()


def bottom():
    global awaiting_input, input_cutoff, cutoff_voltage
    bottom = curses.newwin(3, DEFAULT_WIDTH, DEFAULT_HEIGHT - 3, 0)

    if input_cutoff:
        bottom.addstr(1, 2, "set cutoff voltage: ")
        bottom.border()
        curses.echo()
        bottom.refresh()
        cutoff_voltage = int(bottom.getstr(1, 22, 15))

        j = {"com-type": "cutoff", "value": cutoff_voltage}
        requests.post(SERVER_ADDRESS + "command/setting/", json=json.dumps(j))

        awaiting_input = False
        input_cutoff = False
        curses.halfdelay(5)

    bottom_str = ""

    if handcart_status == 'IDLE':
        bottom_str += "[c] precharge | "
    elif handcart_status == 'READY':
        bottom_str += "[c] charge | "
    elif handcart_status == 'CHARGE':
        bottom_str += "[c] stop | "

    bottom_str += "[v] set cutoff | [f] toggle fastcharge | [w] change view"
    bottom.addstr(1, 2, bottom_str)

    bottom.border()
    bottom.refresh()


def actual_tab(tab):
    actual_tab = curses.newpad(100, DEFAULT_WIDTH)

    if tab == Tab.MAIN.value:
        actual_tab.addstr(0, int(DEFAULT_WIDTH / 2) - 4, "Main view")

        actual_tab.addstr(1, FIRST_COLUMN_INDEX, "bms HV")
        actual_tab.addstr(1, SECOND_COLUMN_INDEX, "Brusa")
        actual_tab.addstr(1, THIRD_COLUMN_INDEX, "Handcart")

        # BMS
        actual_tab.addstr(3, FIRST_COLUMN_INDEX, "status:\t\t" + str(bms_status))
        actual_tab.addstr(4, FIRST_COLUMN_INDEX, "Voltage:\t" + str(bms_volt))
        actual_tab.addstr(5, FIRST_COLUMN_INDEX, "Temp:\t\t" + str(bms_temp))
        actual_tab.addstr(6, FIRST_COLUMN_INDEX, "cell max v:\t" + str(bms_cell_max))
        actual_tab.addstr(7, FIRST_COLUMN_INDEX, "cell min v:\t" + str(bms_cell_min))
        actual_tab.addstr(8, FIRST_COLUMN_INDEX, "req V:\t\t" + str(bms_v_req))
        actual_tab.addstr(9, FIRST_COLUMN_INDEX, "req A:\t\t" + str(bms_a_req))

        # BRUSA
        actual_tab.addstr(3, SECOND_COLUMN_INDEX, "status:\t" + str(brusa_status))
        actual_tab.addstr(4, SECOND_COLUMN_INDEX, "max V:\t" + str(brusa_max_v_set))
        actual_tab.addstr(5, SECOND_COLUMN_INDEX, "max A:\t" + str(brusa_max_a_set))
        actual_tab.addstr(6, SECOND_COLUMN_INDEX, "actual V:\t" + str(brusa_actual_out_v))
        actual_tab.addstr(7, SECOND_COLUMN_INDEX, "actual A:\t" + str(brusa_actual_out_a))
        actual_tab.addstr(8, SECOND_COLUMN_INDEX, "Warning:\t" + str(brusa_warning))

        # HANDCART
        actual_tab.addstr(3, THIRD_COLUMN_INDEX, "Status:\t" + str(handcart_status))
        actual_tab.addstr(4, THIRD_COLUMN_INDEX, "cutoff v:\t" + str(cutoff_voltage))
        actual_tab.addstr(5, THIRD_COLUMN_INDEX, "fastcharge:\t" + str(fast_charge))

        for y in range(2, DEFAULT_HEIGHT - 6):
            if y == 2:
                actual_tab.addch(y, SECOND_COLUMN_INDEX - 1, curses.ACS_PLUS)
                actual_tab.addch(y, THIRD_COLUMN_INDEX - 1, curses.ACS_PLUS)
                for x in range(0, DEFAULT_WIDTH):
                    if x != SECOND_COLUMN_INDEX - 1 and x != THIRD_COLUMN_INDEX - 1:
                        actual_tab.addch(y, x, curses.ACS_HLINE)
            else:
                actual_tab.addch(y, SECOND_COLUMN_INDEX - 1, curses.ACS_VLINE)
                actual_tab.addch(y, THIRD_COLUMN_INDEX - 1, curses.ACS_VLINE)

        actual_tab.refresh(0, 0, 3, 0, DEFAULT_HEIGHT - 4, DEFAULT_WIDTH)


    elif tab == Tab.ERRORS.value:
        actual_tab.addstr(0, int(DEFAULT_WIDTH / 2) - 5, "Errors view")

        actual_tab.addstr(1, 0, "Brusa:")
        actual_tab.addstr(2, 0, brusa_err_str)

        actual_tab.addstr(6, 0, "BMS_HV:\n" + bms_err_str)
        actual_tab.refresh(scroll, 0, 3, 0, DEFAULT_HEIGHT - 4, DEFAULT_WIDTH)


def doRequests():
    global handcart_connected, \
        handcart_status, \
        brusa_connected, \
        brusa_status, \
        bms_connected, \
        bms_status, \
        bms_err_str, \
        brusa_err_str

    try:
        if not handcart_connected:
            r = requests.get(SERVER_ADDRESS)

            if r.status_code == 200:
                handcart_connected = True

        r = requests.get(SERVER_ADDRESS + 'handcart/status/')
        if r.status_code == 200:
            handcart_status = r.json()['state']

        r = requests.get(SERVER_ADDRESS + 'brusa/status/')
        if r.status_code == 200:
            brusa_connected = True
            brusa_status = "online"
            json = r.json()
            # print(json)
            if "Indicates if hardware enabled, i.e. a hi or lo signal is fed to the 'Power On' pin (pin3 of control connector)" in \
                    json['status']:
                brusa_status = "enabled"
            if "An error has been detected, red LED is ON, no power is output" in json['status']:
                brusa_status = "error"
        elif r.status_code == 400:
            brusa_connected = False
            brusa_status = "offline"

        r = requests.get(SERVER_ADDRESS + 'bms-hv/status/')
        if r.status_code == 200:
            bms_connected = True
            bms_status = r.json()['status']
        elif r.status_code == 400:
            bms_connected = False

        '''
        try:
            r = requests.get(SERVER_ADDRESS + 'bms-hv/volt/last/')
            if r.status_code == 200:
                bms_connected = True
                bms_volt = r.json()['volts']
            elif r.status_code == 400:
                bms_connected = False
        except requests.exceptions.ConnectionError:
            handcart_connected = False
        '''

        r = requests.get(SERVER_ADDRESS + 'bms-hv/errors/')
        if r.status_code == 200:
            bms_connected = True
            json = r.json()
            bms_err_str = ""
            for err in json['errors']:
                bms_err_str = bms_err_str + err + "\n"
        elif r.status_code == 400:
            bms_connected = False

        r = requests.get(SERVER_ADDRESS + "brusa/errors/")
        if r.status_code == 200:
            brusa_connected = True
            json = r.json()
            brusa_err_str = ""
            for err in json['errors']:
                brusa_err_str = brusa_err_str + err + "\n"
            if brusa_err_str != "":
                brusa_status = "error"
        elif r.status_code == 400:
            brusa_connected = False

    except requests.exceptions.ConnectionError:
        handcart_connected = False

    if not brusa_connected:
        brusa_status = "offline"
    if not bms_connected:
        bms_status = "offline"
    if not handcart_connected:
        handcart_status = "offline"


input_cutoff = False
awaiting_input = False
key = -1
selected_tab = Tab.MAIN.value

while key == -1:
    intro()
    key = stdscr.getch()

while (key != ord('q')):
    header()
    bottom()
    actual_tab(selected_tab)

    doRequests()

    if not awaiting_input:
        key = stdscr.getch()
        if key == ord('w'):
            if selected_tab == 1:
                selected_tab = 0
            else:
                selected_tab += 1
        elif key == curses.KEY_DOWN:
            scroll += 1
        elif key == curses.KEY_UP:
            if scroll != 0:
                scroll -= 1
        elif key == ord('v'):
            awaiting_input = True
            input_cutoff = True
        elif key == ord('f'):
            fast_charge = not fast_charge
            j = {"com-type": "fast-charge", "value": fast_charge}
            requests.post(SERVER_ADDRESS + "command/setting/", json=json.dumps(j))
        elif key == ord('c'):
            if handcart_status == 'IDLE':
                j = {"com-type": "precharge", "value": True}
                requests.post(SERVER_ADDRESS + "command/action/", json=json.dumps(j))
            elif handcart_status == 'READY':
                j = {"com-type": "charge", "value": True}
                requests.post(SERVER_ADDRESS + "command/action/", json=json.dumps(j))
            elif handcart_status == 'CHARGE':
                j = {"com-type": "charge", "value": False}
                requests.post(SERVER_ADDRESS + "command/action/", json=json.dumps(j))

    else:
        curses.echo()
