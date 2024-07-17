import curses
import os
import queue
import sys
import threading
from enum import Enum

import settings
from common.can_classes import Toggle, STATE
from common.handcart_can import CanListener
from common.logging import tprint, P_TYPE
from settings import CLI_DEFAULT_WIDTH, CLI_DEFAULT_HEIGHT, CLI_TTY, CLI_TTY_REDIRECT_ENABLED, \
    ACC_CELLS_VOLTAGES_PER_SEGMENT, ACC_CELLS_TEMPS_PER_SEGMENT, CLI_CELLS_VOLTAGE_RED_THRESHOLD_LOW, \
    CLI_CELLS_VOLTAGE_RED_THRESHOLD_HIGH, CLI_CELLS_TEMPS_RED_THRESHOLD_HIGH, CLI_CELLS_TEMPS_RED_THRESHOLD_LOW


class Tab(Enum):
    MAIN = 0
    ERRORS = 1
    LOG = 2
    CELLS_VOLTAGES = 3
    CELLS_TEMPERATURES = 4
    SETTINGS = 5


class InputType(Enum):
    BMS_FAN_SPEED = 1
    BMS_MAX_CHARGE_CURRENT = 2
    BRUSA_MAX_MAIN_CURRENT = 3
    BMS_TARGET_VOLTAGE = 4


class StdOutWrapper:
    text = ""

    def write(self, txt):
        self.text += txt
        self.text = '\n'.join(self.text.split('\n')[-30:])

    def get_text(self, beg=0):
        return '\n'.join(self.text.split('\n')[beg:])

    def flush(self, *args, **kwargs):
        """No-op for wrapper"""
        pass


class Cli(threading.Thread):
    THIRD = int(CLI_DEFAULT_WIDTH / 3)
    FIRST_COLUMN_INDEX = 0
    SECOND_COLUMN_INDEX = THIRD
    THIRD_COLUMN_INDEX = THIRD * 2

    scroll = 0
    stdscr = None

    cutoff_voltage = 0
    fast_charge = False

    is_input_section_enabled = False
    awaiting_input = False

    ask_idle = False

    actual_input_type = -1  # select the type of value you are trying to insert

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

        if CLI_TTY_REDIRECT_ENABLED:
            os.environ['TERM'] = 'linux'
            # Used to connect to a tty and expose the CLI
            with open(CLI_TTY, 'rb') as inf, open(CLI_TTY, 'wb') as outf:
                os.dup2(inf.fileno(), 0)
                tprint(f"Setted 0", P_TYPE.DEBUG)
                os.dup2(outf.fileno(), 1)
                tprint(f"Setted 1", P_TYPE.DEBUG)
                os.dup2(outf.fileno(), 2)
                tprint(f"Setted 2", P_TYPE.DEBUG)

            tprint(f"CLI linked to {CLI_TTY}", P_TYPE.DEBUG)

        # This wrapper holds the stdout things while the cli is displayed, then it prints back them at the end
        self.stdout_buffer = StdOutWrapper()
        sys.stdout = self.stdout_buffer
        sys.stderr = self.stdout_buffer

        self.stdscr = curses.initscr()

        if curses.has_colors():
            tprint("terminal has colors :)", P_TYPE.DEBUG)
            curses.start_color()

            # Define colors
            curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
            curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)

        curses.noecho()
        self.stdscr.keypad(True)
        curses.halfdelay(5)

        tprint(f"Curses inited {CLI_TTY}", P_TYPE.DEBUG)

    def intro(self):
        """
        Prints Fenice logo and waits for commands
        """
        begin_x = 0
        begin_y = 0
        height = CLI_DEFAULT_HEIGHT
        width = CLI_DEFAULT_WIDTH
        intro = curses.newwin(height, width, begin_y, begin_x)

        intro.addstr(1, int(CLI_DEFAULT_WIDTH / 2) - 22, "███████╗███████╗███╗   ██╗██╗ ██████╗███████╗")
        intro.addstr(2, int(CLI_DEFAULT_WIDTH / 2) - 22, "██╔════╝██╔════╝████╗  ██║██║██╔════╝██╔════╝")
        intro.addstr(3, int(CLI_DEFAULT_WIDTH / 2) - 22, "█████╗  █████╗  ██╔██╗ ██║██║██║     █████╗")
        intro.addstr(4, int(CLI_DEFAULT_WIDTH / 2) - 22, "██╔══╝  ██╔══╝  ██║╚██╗██║██║██║     ██╔══╝")
        intro.addstr(5, int(CLI_DEFAULT_WIDTH / 2) - 22, "██║     ███████╗██║ ╚████║██║╚██████╗███████╗")
        intro.addstr(6, int(CLI_DEFAULT_WIDTH / 2) - 22, "╚═╝     ╚══════╝╚═╝  ╚═══╝╚═╝ ╚═════╝╚══════╝")
        intro.addstr(7, int(CLI_DEFAULT_WIDTH / 2) - 22, "         ███████╗██╗   ██╗ ██████╗")
        intro.addstr(8, int(CLI_DEFAULT_WIDTH / 2) - 22, "         ██╔════╝██║   ██║██╔═══██╗")
        intro.addstr(9, int(CLI_DEFAULT_WIDTH / 2) - 22, "         █████╗  ██║   ██║██║   ██║")
        intro.addstr(10, int(CLI_DEFAULT_WIDTH / 2) - 22, "         ██╔══╝  ╚██╗ ██╔╝██║   ██║")
        intro.addstr(11, int(CLI_DEFAULT_WIDTH / 2) - 22, "         ███████╗ ╚████╔╝ ╚██████╔╝")
        intro.addstr(12, int(CLI_DEFAULT_WIDTH / 2) - 22, "         ╚══════╝  ╚═══╝   ╚═════╝")
        intro.addstr(14, int(CLI_DEFAULT_WIDTH / 2) - 22, ">>>>>>>>>>>>>>>> HANDCART >>>>>>>>>>>>>>>>>>>")

        intro.addstr(16, int(CLI_DEFAULT_WIDTH / 2) - 12, "Is telemetry dead? ;)")
        intro.addstr(18, int(CLI_DEFAULT_WIDTH / 2) - 12, "press a key to continue..")

        intro.refresh()

    def header(self):
        begin_x = 0
        begin_y = 0
        height = 3
        width = CLI_DEFAULT_WIDTH
        header = curses.newwin(height, width, begin_y, begin_x)

        header.addstr(1, int(CLI_DEFAULT_WIDTH / 2) - 4, "Handcart")
        with self.lock:
            handcart_status_str = f"STATUS: {self.shared_data.FSM_stat.name}"
        header.addstr(1, 3, handcart_status_str)

        header.border()
        header.refresh()

    def refresh_bottom(self, bottom):
        bottom.border()
        curses.echo()
        bottom.refresh()

    def bottom(self):
        bottom = curses.newwin(3, CLI_DEFAULT_WIDTH, CLI_DEFAULT_HEIGHT - 3, 0)

        if self.is_input_section_enabled:
            if self.actual_input_type == InputType.BMS_TARGET_VOLTAGE:
                txt = "Set cutoff: "
                bottom.addstr(1, 2, txt)

                self.refresh_bottom(bottom)

                cutoff_voltage = int(bottom.getstr(1, len(txt) + 1, 5))
                if 300 < cutoff_voltage < 460:
                    j = {"com-type": "cutoff", "value": cutoff_voltage}
                    self.com_queue.put(j)
            elif self.actual_input_type == InputType.BMS_MAX_CHARGE_CURRENT:
                txt = "Set BMS max charge current: "
                bottom.addstr(1, 2, txt)

                self.refresh_bottom(bottom)

                acc_charge_current = int(bottom.getstr(1, len(txt) + 1, 5))
                if 0 < acc_charge_current <= 8:
                    j = {"com-type": "max-out-current", "value": acc_charge_current}
                    self.com_queue.put(j)
            elif self.actual_input_type == InputType.BRUSA_MAX_MAIN_CURRENT:
                txt = "Set BRUSA max mains current: "
                bottom.addstr(1, 2, txt)

                self.refresh_bottom(bottom)

                brusa_max_mains = int(bottom.getstr(1, len(txt) + 1, 5))
                if 0 < brusa_max_mains <= 16:
                    j = {"com-type": "max-in-current", "value": brusa_max_mains}
                    self.com_queue.put(j)
            elif self.actual_input_type == InputType.BMS_FAN_SPEED:
                txt = "Set BMS fan speed (%): "
                bottom.addstr(1, 2, txt)

                self.refresh_bottom(bottom)

                bms_fan_speed = int(bottom.getstr(1, len(txt) + 1, 5))
                if 0 <= bms_fan_speed <= 100:
                    j = {"com-type": "fan-override-set-speed", "value": bms_fan_speed}
                    self.com_queue.put(j)

            self.awaiting_input = False
            self.is_input_section_enabled = False
            curses.halfdelay(5)

        bottom_str = ""

        with self.lock:
            if self.shared_data.FSM_stat == STATE.IDLE:
                bottom_str += "[c] precharge | [b] bal | "
            elif self.shared_data.FSM_stat == STATE.READY:
                bottom_str += "[c] charge | "
            elif self.shared_data.FSM_stat == STATE.CHARGE:
                bottom_str += "[c] stop | "
            elif self.shared_data.FSM_stat == STATE.BALANCING:
                bottom_str += "[b] bal stop | "

            if self.shared_data.FSM_stat != STATE.IDLE and self.shared_data.FSM_stat != STATE.CHECK:
                bottom_str += "[i] idle | "

        bottom_str += "[v] cutoff | [f] fastchg | [w] view"
        bottom.addstr(1, 2, bottom_str)

        bottom.border()
        bottom.refresh()

    def actual_tab(self, tab):
        actual_tab = curses.newpad(100, CLI_DEFAULT_WIDTH)

        if tab == Tab.MAIN.value:
            actual_tab.addstr(0, int(CLI_DEFAULT_WIDTH / 2) - 4, "Main view")

            actual_tab.addstr(1, self.FIRST_COLUMN_INDEX, "bms HV")
            actual_tab.addstr(1, self.SECOND_COLUMN_INDEX, "Brusa")
            actual_tab.addstr(1, self.THIRD_COLUMN_INDEX, "Handcart")

            # BMS
            with self.lock:
                actual_tab.addstr(
                    3, self.FIRST_COLUMN_INDEX, "status:\t\t" + str(self.shared_data.bms_hv.status.name))
                actual_tab.addstr(
                    4, self.FIRST_COLUMN_INDEX, "pack voltage:\t" + str(self.shared_data.bms_hv.act_pack_voltage))
                actual_tab.addstr(
                    5, self.FIRST_COLUMN_INDEX, "bus voltage:\t" + str(self.shared_data.bms_hv.act_bus_voltage))
                actual_tab.addstr(
                    6, self.FIRST_COLUMN_INDEX, "cell max v:\t" + str(self.shared_data.bms_hv.max_cell_voltage))
                actual_tab.addstr(
                    7, self.FIRST_COLUMN_INDEX, "cell min v:\t" + str(self.shared_data.bms_hv.min_cell_voltage))
                actual_tab.addstr(
                    8, self.FIRST_COLUMN_INDEX, "cell delta v:\t" + str(self.shared_data.bms_hv.act_cell_delta))
                actual_tab.addstr(
                    9, self.FIRST_COLUMN_INDEX, "Avg Temp:\t" + str(self.shared_data.bms_hv.act_average_temp))
                actual_tab.addstr(
                    10, self.FIRST_COLUMN_INDEX, "Temp max:\t" + str(self.shared_data.bms_hv.max_temp))
                actual_tab.addstr(
                    11, self.FIRST_COLUMN_INDEX, "Temp min:\t" + str(self.shared_data.bms_hv.min_temp))
                actual_tab.addstr(
                    12, self.FIRST_COLUMN_INDEX, "Current:\t" + str(self.shared_data.bms_hv.act_current))
                actual_tab.addstr(
                    13, self.FIRST_COLUMN_INDEX, "Balancing:\t" + str(self.shared_data.bms_hv.is_balancing.name))

                # BRUSA
                actual_tab.addstr(
                    3, self.SECOND_COLUMN_INDEX, "status:\t" + str(self.shared_data.brusa.isConnected()))
                actual_tab.addstr(
                    4, self.SECOND_COLUMN_INDEX,
                    "main in V:\t" + str(round(self.shared_data.brusa.act_NLG5_ACT_I.get("NLG5_MV_ACT"), 2)))
                actual_tab.addstr(
                    5, self.SECOND_COLUMN_INDEX,
                    "main in A:\t" + str(round(self.shared_data.brusa.act_NLG5_ACT_I.get("NLG5_MC_ACT"), 2)))
                actual_tab.addstr(
                    6, self.SECOND_COLUMN_INDEX,
                    "out V:\t" + str(round(self.shared_data.brusa.act_NLG5_ACT_I.get("NLG5_OV_ACT"), 2)))
                actual_tab.addstr(
                    7, self.SECOND_COLUMN_INDEX,
                    "out A:\t" + str(round(self.shared_data.brusa.act_NLG5_ACT_I.get("NLG5_OC_ACT"), 2)))
                actual_tab.addstr(
                    8, self.SECOND_COLUMN_INDEX,
                    "mainIN lim A:\t" + str(round(self.shared_data.brusa.act_NLG5_ACT_II.get("NLG5_S_MC_M_CP"), 2)))
                actual_tab.addstr(
                    9, self.SECOND_COLUMN_INDEX,
                    "temperature:\t" + str(round(self.shared_data.brusa.act_NLG5_TEMP.get("NLG5_P_TMP"), 2)))
                actual_tab.addstr(
                    10, self.SECOND_COLUMN_INDEX, "Warning:\t" + str(False))
                actual_tab.addstr(
                    11, self.SECOND_COLUMN_INDEX,
                    "Error:\t" + str(self.shared_data.brusa.error))

                # HANDCART
                actual_tab.addstr(
                    3, self.THIRD_COLUMN_INDEX, "Status:\t\t" + str(self.shared_data.FSM_stat.name))
                actual_tab.addstr(
                    4, self.THIRD_COLUMN_INDEX, "cutoff v:\t\t" + str(self.shared_data.target_v))
                actual_tab.addstr(
                    5, self.THIRD_COLUMN_INDEX, "fastcharge:\t\t" + str(self.fast_charge))
                actual_tab.addstr(
                    6, self.THIRD_COLUMN_INDEX, "max-cur-out:\t" + str(self.shared_data.act_set_out_current))
                actual_tab.addstr(
                    7, self.THIRD_COLUMN_INDEX, "max-in-curr:\t" + str(-1))
                actual_tab.addstr(
                    8,
                    self.THIRD_COLUMN_INDEX, "fan_override:\t" +
                                             str("enabled" if self.shared_data.bms_hv.fans_set_override_status.value
                                                              == Toggle.ON else "disabled"))
                actual_tab.addstr(
                    9,
                    self.THIRD_COLUMN_INDEX, "fan_override_speed:\t" +
                                             str(self.shared_data.bms_hv.fans_set_override_speed))

            for y in range(2, CLI_DEFAULT_HEIGHT - 6):
                if y == 2:
                    actual_tab.addch(y, self.SECOND_COLUMN_INDEX - 1, curses.ACS_PLUS)
                    actual_tab.addch(y, self.THIRD_COLUMN_INDEX - 1, curses.ACS_PLUS)
                    for x in range(0, CLI_DEFAULT_WIDTH):
                        if x != self.SECOND_COLUMN_INDEX - 1 and x != self.THIRD_COLUMN_INDEX - 1:
                            actual_tab.addch(y, x, curses.ACS_HLINE)
                else:
                    actual_tab.addch(y, self.SECOND_COLUMN_INDEX - 1, curses.ACS_VLINE)
                    actual_tab.addch(y, self.THIRD_COLUMN_INDEX - 1, curses.ACS_VLINE)

            actual_tab.refresh(0, 0, 3, 0, CLI_DEFAULT_HEIGHT - 4, CLI_DEFAULT_WIDTH)

        elif tab == Tab.ERRORS.value:
            actual_tab.addstr(0, int(CLI_DEFAULT_WIDTH / 2) - 5, "Errors view")

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

            actual_tab.refresh(self.scroll, 0, 3, 0, CLI_DEFAULT_HEIGHT - 4, CLI_DEFAULT_WIDTH)

        elif tab == Tab.LOG.value:
            actual_tab.addstr(0, int(CLI_DEFAULT_WIDTH / 2) - 5, "Log view")
            actual_tab.addstr(1, 0, self.stdout_buffer.get_text())
            actual_tab.refresh(self.scroll, 0, 3, 0, CLI_DEFAULT_HEIGHT - 4, CLI_DEFAULT_WIDTH)

        elif tab == Tab.CELLS_VOLTAGES.value:
            actual_tab.addstr(0, int(CLI_DEFAULT_WIDTH / 2) - 5, "Cells voltages")
            with self.lock:
                try:
                    row_offset = 1
                    col = 0

                    for index, voltage in enumerate(self.shared_data.bms_hv.hv_cells_act):
                        act_row = int(row_offset + (index % ACC_CELLS_VOLTAGES_PER_SEGMENT))

                        if voltage < CLI_CELLS_VOLTAGE_RED_THRESHOLD_LOW \
                                or voltage > CLI_CELLS_VOLTAGE_RED_THRESHOLD_HIGH:
                            actual_tab.addstr(act_row, col, f" {voltage:.2f} |", curses.color_pair(1))
                        else:
                            actual_tab.addstr(act_row, col, f" {voltage:.2f} |")

                        if (index + 1) % ACC_CELLS_VOLTAGES_PER_SEGMENT == 0 and index != 0:
                            col += 7

                except IndexError:
                    actual_tab.addstr(0, 0, f"Error: cells voltages not available")

            actual_tab.refresh(self.scroll, 0, 3, 0, CLI_DEFAULT_HEIGHT - 4, CLI_DEFAULT_WIDTH)

        elif tab == Tab.CELLS_TEMPERATURES.value:
            actual_tab.addstr(0, int(CLI_DEFAULT_WIDTH / 2) - 5, "Cells temperatures")

            with self.lock:
                try:
                    row_offset = 1
                    col = 0

                    actual_tab.addstr(row_offset, col, f"| ")

                    for index, temp in enumerate(self.shared_data.bms_hv.hv_temps_act):
                        act_row = int(row_offset + (index % ACC_CELLS_TEMPS_PER_SEGMENT))

                        if temp > CLI_CELLS_TEMPS_RED_THRESHOLD_HIGH:
                            actual_tab.addstr(act_row, col, f" {temp:.2f} |", curses.color_pair(1))
                        elif temp < CLI_CELLS_TEMPS_RED_THRESHOLD_LOW:
                            actual_tab.addstr(act_row, col, f" {temp:.2f} |", curses.color_pair(2))
                        else:
                            actual_tab.addstr(act_row, col, f" {temp:.2f} |")

                        if (index + 1) % ACC_CELLS_TEMPS_PER_SEGMENT == 0 and index != 0:
                            col += 9

                except IndexError:
                    actual_tab.addstr(0, 0, f"Error: cells voltages not available")

            actual_tab.refresh(self.scroll, 0, 3, 0, CLI_DEFAULT_HEIGHT - 4, CLI_DEFAULT_WIDTH)

        elif tab == Tab.SETTINGS.value:
            # TODO: add settings such as fan speed and current
            act_row = 0
            actual_tab.addstr(act_row, int(CLI_DEFAULT_WIDTH / 2) - 5, "Settings")

            with self.lock:
                act_row += 2
                actual_tab.addstr(act_row, 0, "Setting name\t\t\t| Value set\t\t| Actual value")
                act_row += 2
                try:
                    actual_tab.addstr(
                        act_row, 0,
                        f"[o] BMS fan override:\t\t "
                        f"{'enabled' if self.shared_data.bms_hv.fans_set_override_status == Toggle.ON else 'disabled'}\t\t"
                        f"{'enabled' if self.shared_data.bms_hv.fans_override_status == Toggle.ON else 'disabled'}",
                        curses.color_pair(0))
                    act_row += 1
                    actual_tab.addstr(
                        act_row, 0,
                        f"[s] BMS fan speed:\t\t "
                        f"{round(self.shared_data.bms_hv.fans_set_override_speed * 100, 2)} %\t\t\t"
                        f"{round(self.shared_data.bms_hv.fans_override_speed, 2)} %",
                        curses.color_pair(0))
                    act_row += 1
                    actual_tab.addstr(
                        act_row, 0,
                        f"[l] BMS max charge current\t "
                        f"{round(self.shared_data.act_set_out_current, 2)} A\t\t\t"
                        f"{round(self.shared_data.brusa.act_NLG5_ACT_I.get('NLG5_OC_ACT'), 2)} A",
                        curses.color_pair(0))
                    act_row += 1
                    actual_tab.addstr(
                        act_row, 0,
                        f"[u] Brusa max main current:\t "
                        f"{round(self.shared_data.act_set_in_current, 2)} A\t\t\t"
                        f"{round(self.shared_data.brusa.act_NLG5_ACT_II.get('NLG5_S_MC_M_CP'), 2)} A",
                        curses.color_pair(0))
                    act_row += 1
                    actual_tab.addstr(
                        act_row, 0,
                        f"[v] BMS target voltage:\t\t "
                        f"{self.shared_data.target_v} V",
                        curses.color_pair(0))
                except Exception:
                    actual_tab.addstr(0, 0, f"Error: settings tab not available")
            actual_tab.refresh(self.scroll, 0, 3, 0, CLI_DEFAULT_HEIGHT - 4, CLI_DEFAULT_WIDTH)

    def run(self):
        self.is_input_section_enabled = False
        self.awaiting_input = False
        key = -1
        selected_tab = Tab.MAIN.value

        while key == -1:
            self.intro()
            key = self.stdscr.getch()

        while key != ord('q'):
            self.header()
            self.bottom()
            self.actual_tab(selected_tab)

            if not self.awaiting_input:
                key = self.stdscr.getch()
                if key == ord('w'):
                    if selected_tab == 5:
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
                    self.is_input_section_enabled = True
                    self.actual_input_type = InputType.BMS_TARGET_VOLTAGE
                elif key == ord('f'):
                    self.fast_charge = not self.fast_charge
                    j = {
                        "com-type": "max-in-current",
                        "value": settings.MAX_CHARGER_GRID_CURRENT if self.fast_charge else settings.DEFAULT_CHARGE_MAINS_AMPERE
                    }
                    self.com_queue.put(j)
                    j = {"com-type": "max-out-current",
                         "value": settings.ACC_MAX_CHG_CURRENT if self.fast_charge else settings.ACC_DEFAULT_CHG_CURRENT}
                    self.com_queue.put(j)
                elif key == ord('i'):
                    j = {"com-type": "shutdown", "value": True}
                    self.com_queue.put(j)
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
                elif key == ord('b'):
                    with self.lock:
                        if self.shared_data.FSM_stat == STATE.IDLE:
                            j = {"com-type": "balancing", "value": True}
                        if self.shared_data.FSM_stat == STATE.BALANCING:
                            j = {"com-type": "balancing", "value": False}
                        self.com_queue.put(j)
                elif key == ord('s'):
                    self.awaiting_input = True
                    self.is_input_section_enabled = True
                    self.actual_input_type = InputType.BMS_FAN_SPEED
                elif key == ord('l'):
                    self.awaiting_input = True
                    self.is_input_section_enabled = True
                    self.actual_input_type = InputType.BMS_MAX_CHARGE_CURRENT
                elif key == ord('u'):
                    self.awaiting_input = True
                    self.is_input_section_enabled = True
                    self.actual_input_type = InputType.BRUSA_MAX_MAIN_CURRENT
                elif key == ord('o'):
                    j = {"com-type": "fan-override-set-status",
                         "value": True if self.shared_data.bms_hv.fans_set_override_status == Toggle.OFF else False}
                    self.com_queue.put(j)

            else:
                curses.echo()

        curses.endwin()
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        sys.stdout.write(self.stdout_buffer.get_text())
