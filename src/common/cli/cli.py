import json
import os
import queue
import threading
import curses
from enum import Enum

import requests

from common.handcart_can import CanListener
from common.settings import STATE


class Tab(Enum):
    MAIN = 0
    ERRORS = 1

class Cli(threading.Thread):
    TTY = "/dev/tty1"
    DEFAULT_WIDTH = 80
    DEFAULT_HEIGHT = 24
    # SERVER_ADDRESS = 'http://127.0.0.1:5000/'
    SERVER_ADDRESS = 'http://192.168.1.51:8080/'
    handcart_connected = False
    brusa_connected = False
    bms_connected = False

    THIRD = int(DEFAULT_WIDTH / 3)
    FIRST_COLUMN_INDEX = 0
    SECOND_COLUMN_INDEX = THIRD
    THIRD_COLUMN_INDEX = THIRD * 2

    scroll = 0
    stdscr = None

    # BMS HV
    bms_status = "offline"
    bms_volt = 0.0
    bms_temp = 0.0
    bms_temp_max = 0.0
    bms_temp_min = 0.0
    bms_cell_max = 0.0
    bms_cell_min = 0.0
    bms_v_req = 0.0
    bms_a_req = 0.0
    bms_err_str = ""

    # BRUSA
    brusa_status = "offline"
    brusa_max_v_set = 0.0
    brusa_max_a_set = 0.0
    brusa_mains_current = 0
    brusa_mains_voltage = 0
    brusa_output_voltage = 0
    brusa_output_current = 0
    brusa_mains_current_limit = 0
    brusa_temp = 0
    brusa_warning = False
    brusa_err_str = ""

    # HANDCART
    handcart_status = "offline"
    cutoff_voltage = 0
    fast_charge = False

    input_cutoff = False
    awaiting_input = False

    # Shared data
    com_queue: queue.Queue
    lock: threading.Lock
    shared_data: CanListener

    def __init__(self,
                 com_queue: queue.Queue,
                 lock: threading.Lock,
                 shared_data: CanListener):

        super().__init__(args=(com_queue,
                               lock,
                               shared_data))
        self.com_queue = com_queue
        self.lock = lock
        self.shared_data = shared_data

        os.environ['TERM'] = 'linux'

        # Used to connect to a tty and expose the CLI
        with open(self.TTY, 'rb') as inf, open(self.TTY, 'wb') as outf:
            os.dup2(inf.fileno(), 0)
            os.dup2(outf.fileno(), 1)
            os.dup2(outf.fileno(), 2)

        self.stdscr = curses.initscr()

        curses.noecho()
        self.stdscr.keypad(True)
        curses.halfdelay(5)

    def intro(self):
        """
        Prints Fenice logo and waits for commands
        """
        begin_x = 0
        begin_y = 0
        height = self.DEFAULT_HEIGHT
        width = self.DEFAULT_WIDTH
        intro = curses.newwin(height, width, begin_y, begin_x)

        intro.addstr(1, int(self.DEFAULT_WIDTH / 2) - 22, "███████╗███████╗███╗   ██╗██╗ ██████╗███████╗")
        intro.addstr(2, int(self.DEFAULT_WIDTH / 2) - 22, "██╔════╝██╔════╝████╗  ██║██║██╔════╝██╔════╝")
        intro.addstr(3, int(self.DEFAULT_WIDTH / 2) - 22, "█████╗  █████╗  ██╔██╗ ██║██║██║     █████╗")
        intro.addstr(4, int(self.DEFAULT_WIDTH / 2) - 22, "██╔══╝  ██╔══╝  ██║╚██╗██║██║██║     ██╔══╝")
        intro.addstr(5, int(self.DEFAULT_WIDTH / 2) - 22, "██║     ███████╗██║ ╚████║██║╚██████╗███████╗")
        intro.addstr(6, int(self.DEFAULT_WIDTH / 2) - 22, "╚═╝     ╚══════╝╚═╝  ╚═══╝╚═╝ ╚═════╝╚══════╝")
        intro.addstr(7, int(self.DEFAULT_WIDTH / 2) - 22, ">>>>>>>>>>>>>>>> HANDCART >>>>>>>>>>>>>>>>>>>")
        intro.addstr(10, int(self.DEFAULT_WIDTH / 2) - 12, "press a key to continue..")

        intro.refresh()

    def header(self):
        begin_x = 0
        begin_y = 0
        height = 3
        width = self.DEFAULT_WIDTH
        header = curses.newwin(height, width, begin_y, begin_x)

        header.addstr(1, int(self.DEFAULT_WIDTH / 2) - 4, "Handcart")
        handcart_status_str = f"STATUS: {self.shared_data.FSM_stat.name}"
        header.addstr(1, 3, handcart_status_str)

        header.border()
        header.refresh()

    def bottom(self):
        bottom = curses.newwin(3, self.DEFAULT_WIDTH, self.DEFAULT_HEIGHT - 3, 0)

        if self.input_cutoff:
            bottom.addstr(1, 2, "set cutoff voltage: ")
            bottom.border()
            curses.echo()
            bottom.refresh()
            cutoff_voltage = int(bottom.getstr(1, 22, 15))

            j = {"com-type": "cutoff", "value": cutoff_voltage}
            self.com_queue.put(j) # TODO: to check if ok

            self.awaiting_input = False
            self.input_cutoff = False
            curses.halfdelay(5)

        bottom_str = ""

        if self.shared_data.FSM_stat == STATE.IDLE:
            bottom_str += "[c] precharge | "
        elif self.shared_data.FSM_stat == STATE.READY:
            bottom_str += "[c] charge | "
        elif self.shared_data.FSM_stat == STATE.CHARGE:
            bottom_str += "[c] stop | "

        bottom_str += "[v] set cutoff | [f] toggle fastcharge | [w] change view"
        bottom.addstr(1, 2, bottom_str)

        bottom.border()
        bottom.refresh()
        # TODO: continue

    def actual_tab(self, tab):
        actual_tab = curses.newpad(100, self.DEFAULT_WIDTH)

        if tab == Tab.MAIN.value:
            actual_tab.addstr(0, int(self.DEFAULT_WIDTH / 2) - 4, "Main view")

            actual_tab.addstr(1, self.FIRST_COLUMN_INDEX, "bms HV")
            actual_tab.addstr(1, self.SECOND_COLUMN_INDEX, "Brusa")
            actual_tab.addstr(1, self.THIRD_COLUMN_INDEX, "Handcart")

            # BMS
            actual_tab.addstr(3, self.FIRST_COLUMN_INDEX, "status:\t\t" + str(self.bms_status))
            actual_tab.addstr(4, self.FIRST_COLUMN_INDEX, "Voltage:\t" + str(self.bms_volt))
            actual_tab.addstr(5, self.FIRST_COLUMN_INDEX, "cell max v:\t" + str(self.bms_cell_max))
            actual_tab.addstr(6, self.FIRST_COLUMN_INDEX, "cell min v:\t" + str(self.bms_cell_min))
            actual_tab.addstr(7, self.FIRST_COLUMN_INDEX, "Temp:\t\t" + str(self.bms_temp))
            actual_tab.addstr(8, self.FIRST_COLUMN_INDEX, "Temp max:\t" + str(self.bms_temp_max))
            actual_tab.addstr(9, self.FIRST_COLUMN_INDEX, "Temp min:\t" + str(self.bms_temp_min))

            # BRUSA
            actual_tab.addstr(3, self.SECOND_COLUMN_INDEX, "status:\t" + str(self.brusa_status))
            actual_tab.addstr(4, self.SECOND_COLUMN_INDEX, "main in V:\t" + str(self.brusa_mains_voltage))
            actual_tab.addstr(5, self.SECOND_COLUMN_INDEX, "main in A:\t" + str(self.brusa_mains_current))
            actual_tab.addstr(6, self.SECOND_COLUMN_INDEX, "out V:\t" + str(self.brusa_output_voltage))
            actual_tab.addstr(7, self.SECOND_COLUMN_INDEX, "out A:\t" + str(self.brusa_output_current))
            actual_tab.addstr(8, self.SECOND_COLUMN_INDEX, "mainIN lim A:\t" + str(self.brusa_mains_current_limit))
            actual_tab.addstr(9, self.SECOND_COLUMN_INDEX, "temperature:\t" + str(self.brusa_temp))
            actual_tab.addstr(10, self.SECOND_COLUMN_INDEX, "Warning:\t" + str(self.brusa_warning))

            # HANDCART
            actual_tab.addstr(3, self.THIRD_COLUMN_INDEX, "Status:\t" + str(self.handcart_status))
            actual_tab.addstr(4, self.THIRD_COLUMN_INDEX, "cutoff v:\t" + str(self.cutoff_voltage))
            actual_tab.addstr(5, self.THIRD_COLUMN_INDEX, "fastcharge:\t" + str(self.fast_charge))

            for y in range(2, self.DEFAULT_HEIGHT - 6):
                if y == 2:
                    actual_tab.addch(y, self.SECOND_COLUMN_INDEX - 1, curses.ACS_PLUS)
                    actual_tab.addch(y, self.THIRD_COLUMN_INDEX - 1, curses.ACS_PLUS)
                    for x in range(0, self.DEFAULT_WIDTH):
                        if x != self.SECOND_COLUMN_INDEX - 1 and x != self.THIRD_COLUMN_INDEX - 1:
                            actual_tab.addch(y, x, curses.ACS_HLINE)
                else:
                    actual_tab.addch(y, self.SECOND_COLUMN_INDEX - 1, curses.ACS_VLINE)
                    actual_tab.addch(y, self.THIRD_COLUMN_INDEX - 1, curses.ACS_VLINE)

            actual_tab.refresh(0, 0, 3, 0, self.DEFAULT_HEIGHT - 4, self.DEFAULT_WIDTH)


        elif tab == Tab.ERRORS.value:
            actual_tab.addstr(0, int(self.DEFAULT_WIDTH / 2) - 5, "Errors view")

            actual_tab.addstr(1, 0, "Brusa:")
            actual_tab.addstr(2, 0, self.brusa_err_str)

            actual_tab.addstr(6, 0, "BMS_HV:\n" + self.bms_err_str)
            actual_tab.refresh(self.scroll, 0, 3, 0, self.DEFAULT_HEIGHT - 4, self.DEFAULT_WIDTH)

    def doRequests(self):
        try:
            if not self.handcart_connected:
                r = requests.get(self.SERVER_ADDRESS)

                if r.status_code == 200:
                    handcart_connected = True

            r = requests.get(self.SERVER_ADDRESS + 'handcart/status')
            if r.status_code == 200:
                self.handcart_status = r.json()['state']

            r = requests.get(self.SERVER_ADDRESS + 'brusa/status')
            if r.status_code == 200:
                self.brusa_connected = True
                self.brusa_status = "online"
                json = r.json()
                # print(json)
                if "Indicates if hardware enabled, i.e. a hi or lo signal is fed to the 'Power On' pin (pin3 of control connector)" in \
                        json['status']:
                    brusa_status = "enabled"
                if "An error has been detected, red LED is ON, no power is output" in json['status']:
                    brusa_status = "error"
            elif r.status_code == 400:
                self.brusa_connected = False
                self.brusa_status = "offline"

            r = requests.get(self.SERVER_ADDRESS + 'bms-hv/status')
            if r.status_code == 200:
                self.bms_connected = True
                self.bms_status = r.json()['status']
            elif r.status_code == 400:
                self.bms_connected = False

            '''
            try:
                r = requests.get(self.SERVER_ADDRESS + 'bms-hv/volt/last')
                if r.status_code == 200:
                    bms_connected = True
                    bms_volt = r.json()['volts']
                elif r.status_code == 400:
                    bms_connected = False
            except requests.exceptions.ConnectionError:
                handcart_connected = False
            '''

            r = requests.get(self.SERVER_ADDRESS + 'bms-hv/errors')
            if r.status_code == 200:
                self.bms_connected = True
                json = r.json()
                bms_err_str = ""
                for err in json['errors']:
                    bms_err_str = bms_err_str + err + "\n"
            elif r.status_code == 400:
                self.bms_connected = False

            r = requests.get(self.SERVER_ADDRESS + "brusa/errors")
            if r.status_code == 200:
                self.brusa_connected = True
                json = r.json()
                brusa_err_str = ""
                for err in json['errors']:
                    brusa_err_str = brusa_err_str + err + "\n"
                if brusa_err_str != "":
                    brusa_status = "error"
            elif r.status_code == 400:
                self.brusa_connected = False

            r = requests.get(self.SERVER_ADDRESS + "bms-hv/volt/last")
            if r.status_code == 200:
                json = r.json()
                bms_volt = json['bus_voltage']
                bms_cell_max = json['max_cell_voltage']
                bms_cell_min = json['min_cell_voltage']
            elif r.status_code == 400:
                bms_connected = False
                bms_volt = 0
                bms_cell_max = 0
                bms_cell_min = 0

            r = requests.get(self.SERVER_ADDRESS + "bms-hv/temp/last")
            if r.status_code == 200:
                json = r.json()
                bms_temp = json['average_temp']
                bms_temp_max = json['max_temp']
                bms_temp_min = json['min_temp']
            elif r.status_code == 400:
                bms_connected = False
                bms_temp = 0
                bms_temp_max = 0
                bms_temp_min = 0

            r = requests.get(self.SERVER_ADDRESS + "brusa/info")
            if r.status_code == 200:
                json = r.json()
                brusa_mains_current = json['NLG5_MC_ACT']
                brusa_mains_voltage = json['NLG5_MV_ACT']
                brusa_output_voltage = json['NLG5_OV_ACT']
                brusa_output_current = json['NLG5_OC_ACT']
                brusa_mains_current_limit = json['NLG5_S_MC_M_CP']
                brusa_temp = json['NLG5_P_TMP']
            elif r.status_code == 400:
                bms_connected = False
                brusa_mains_current = 0
                brusa_mains_voltage = 0
                brusa_output_voltage = 0
                brusa_output_current = 0
                brusa_mains_current_limit = 0
                brusa_temp = 0

        except requests.exceptions.ConnectionError:
            handcart_connected = False

        if not self.brusa_connected:
            brusa_status = "offline"
        if not self.bms_connected:
            bms_status = "offline"
        if not self.handcart_connected:
            handcart_status = "offline"

    def run(self):
        input_cutoff = False
        awaiting_input = False
        key = -1
        selected_tab = Tab.MAIN.value

        while key == -1:
            self.intro()
            key = self.stdscr.getch()

        while (key != ord('q')):
            self.header()
            self.bottom()
            self.actual_tab(selected_tab)

            self.doRequests()

            if not awaiting_input:
                key = self.stdscr.getch()
                if key == ord('w'):
                    if selected_tab == 1:
                        selected_tab = 0
                    else:
                        selected_tab += 1
                elif key == curses.KEY_DOWN:
                    self.scroll += 1
                elif key == curses.KEY_UP:
                    if self.scroll != 0:
                        self.scroll -= 1
                elif key == ord('v'):
                    awaiting_input = True
                    input_cutoff = True
                elif key == ord('f'):
                    self.fast_charge = not self.fast_charge
                    j = {"com-type": "fast-charge", "value": self.fast_charge}
                    requests.post(self.SERVER_ADDRESS + "command/setting", json=json.dumps(j))
                elif key == ord('c'):
                    if self.handcart_status == 'IDLE':
                        j = {"com-type": "precharge", "value": True}
                        requests.post(self.SERVER_ADDRESS + "command/action", json=json.dumps(j))
                    elif self.handcart_status == 'READY':
                        j = {"com-type": "charge", "value": True}
                        requests.post(self.SERVER_ADDRESS + "command/action", json=json.dumps(j))
                    elif self.handcart_status == 'CHARGE':
                        j = {"com-type": "charge", "value": False}
                        requests.post(self.SERVER_ADDRESS + "command/action", json=json.dumps(j))

            else:
                curses.echo()

        curses.endwin()