import json
import os
import queue
import threading
import curses
from enum import Enum

import requests

from common.handcart_can import CanListener
from common.logging import tprint, P_TYPE
from settings import STATE


class Tab(Enum):
    MAIN = 0
    ERRORS = 1

class Cli(threading.Thread):
    TTY = "/dev/tty1"
    DEFAULT_WIDTH = 80
    DEFAULT_HEIGHT = 24

    THIRD = int(DEFAULT_WIDTH / 3)
    FIRST_COLUMN_INDEX = 0
    SECOND_COLUMN_INDEX = THIRD
    THIRD_COLUMN_INDEX = THIRD * 2

    scroll = 0
    stdscr = None

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
        self.com_queue = self._args[0]
        self.lock = self._args[1]
        self.shared_data = self._args[2]
        tprint(f"Shared data on cli: {self.shared_data}", P_TYPE.DEBUG)
        tprint(f"Starting CLI thread", P_TYPE.DEBUG)
        os.environ['TERM'] = 'linux'

        # Used to connect to a tty and expose the CLI
        #with open(self.TTY, 'rb') as inf, open(self.TTY, 'wb') as outf:
        #    os.dup2(inf.fileno(), 0)
        #    tprint(f"Setted 0", P_TYPE.DEBUG)
        #    os.dup2(outf.fileno(), 1)
        #    tprint(f"Setted 1", P_TYPE.DEBUG)
        #    os.dup2(outf.fileno(), 2)
        #    tprint(f"Setted 2", P_TYPE.DEBUG)

        tprint(f"CLI linked to {self.TTY}", P_TYPE.DEBUG)

        self.stdscr = curses.initscr()

        curses.noecho()
        self.stdscr.keypad(True)
        curses.halfdelay(5)

        tprint(f"Curses inited {self.TTY}", P_TYPE.DEBUG)

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
        with self.lock:
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
            self.com_queue.put(j)  # TODO: to check if ok

            self.awaiting_input = False
            self.input_cutoff = False
            curses.halfdelay(5)

        bottom_str = ""

        with self.lock:
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
            with self.lock:
                actual_tab.addstr(
                    3, self.FIRST_COLUMN_INDEX, "status:\t\t" + str(self.shared_data.bms_hv.status.name))
                actual_tab.addstr(
                    4, self.FIRST_COLUMN_INDEX, "Voltage:\t" + str(self.shared_data.bms_hv.act_bus_voltage))
                actual_tab.addstr(
                    5, self.FIRST_COLUMN_INDEX, "cell max v:\t" + str(self.shared_data.bms_hv.max_cell_voltage))
                actual_tab.addstr(
                    6, self.FIRST_COLUMN_INDEX, "cell min v:\t" + str(self.shared_data.bms_hv.min_cell_voltage))
                actual_tab.addstr(
                    7, self.FIRST_COLUMN_INDEX, "Avg Temp:\t" + str(self.shared_data.bms_hv.act_average_temp))
                actual_tab.addstr(
                    8, self.FIRST_COLUMN_INDEX, "Temp max:\t" + str(self.shared_data.bms_hv.max_temp))
                actual_tab.addstr(
                    9, self.FIRST_COLUMN_INDEX, "Temp min:\t" + str(self.shared_data.bms_hv.min_temp))

                # BRUSA
                actual_tab.addstr(
                    3, self.SECOND_COLUMN_INDEX, "status:\t" + str(self.shared_data.brusa.isConnected()))
                actual_tab.addstr(
                    4, self.SECOND_COLUMN_INDEX, "main in V:\t" + str(self.shared_data.brusa.act_NLG5_ACT_I.get("NLG5_MV_ACT")))
                actual_tab.addstr(
                    5, self.SECOND_COLUMN_INDEX, "main in A:\t" + str(self.shared_data.brusa.act_NLG5_ACT_I.get("NLG5_MC_ACT")))
                actual_tab.addstr(
                    6, self.SECOND_COLUMN_INDEX, "out V:\t" + str(self.shared_data.brusa.act_NLG5_ACT_I.get("NLG5_OV_ACT")))
                actual_tab.addstr(
                    7, self.SECOND_COLUMN_INDEX, "out A:\t" + str(self.shared_data.brusa.act_NLG5_ACT_I.get("NLG5_OC_ACT")))
                actual_tab.addstr(
                    8, self.SECOND_COLUMN_INDEX, "mainIN lim A:\t" + str(self.shared_data.brusa.act_NLG5_ACT_I.get("NLG5_S_MC_M_CP")))
                actual_tab.addstr(
                    9, self.SECOND_COLUMN_INDEX, "temperature:\t" + str(self.shared_data.brusa.act_NLG5_ACT_I.get("NLG5_P_TMP")))
                actual_tab.addstr(
                    10, self.SECOND_COLUMN_INDEX, "Warning:\t" + str(False))

                # HANDCART
                actual_tab.addstr(3, self.THIRD_COLUMN_INDEX, "Status:\t" + str(self.shared_data.FSM_stat.name))
                actual_tab.addstr(4, self.THIRD_COLUMN_INDEX, "cutoff v:\t" + str(self.shared_data.target_v))
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
            with self.lock:
                actual_tab.addstr(2, 0, "\n".join(self.shared_data.brusa.act_NLG5_ERR_list))

                bms_errors_on = []
                if self.shared_data.bms_hv.error:
                    for k, v in self.shared_data.bms_hv.errors.items():
                        if v == 1:
                            bms_errors_on.append(f"{k}={v}")
                    actual_tab.addstr(6, 0, "BMS_HV:\n" + "\n".join(bms_errors_on))
                else:
                    actual_tab.addstr(6, 0, "BMS_HV:\nNo errors")

            actual_tab.refresh(self.scroll, 0, 3, 0, self.DEFAULT_HEIGHT - 4, self.DEFAULT_WIDTH)

    def run(self):
        self.input_cutoff = False
        self.awaiting_input = False
        key = -1
        selected_tab = Tab.MAIN.value

        while key == -1:
            self.intro()
            key = self.stdscr.getch()

        while (key != ord('q')):
            self.header()
            self.bottom()
            self.actual_tab(selected_tab)

            if not self.awaiting_input:
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
                    self.awaiting_input = True
                    self.input_cutoff = True
                elif key == ord('f'):
                    self.fast_charge = not self.fast_charge
                    j = {"com-type": "fast-charge", "value": self.fast_charge}
                    requests.post(self.SERVER_ADDRESS + "command/setting", json=json.dumps(j))
                elif key == ord('c'):
                    with self.lock:
                        if self.shared_data.FSM_stat == STATE.IDLE:
                            j = {"com-type": "precharge", "value": True}
                            self.com_queue.put(j)
                        elif self.shared_data.FSM_stat == STATE.READY:
                            j = {"com-type": "charge", "value": True}
                            self.com_queue.put(j)
                        elif self.shared_data.FSM_stat == STATE.CHARGE:
                            j = {"com-type": "charge", "value": False}
                            self.com_queue.put(j)

            else:
                curses.echo()

        curses.endwin()