import datetime
import tkinter
import pyautogui

import ttkbootstrap as ttk
from RPi import GPIO
from RPi.GPIO import FALLING
from ttkbootstrap.constants import *

from common.handcart_can import *
from common.can_classes import Toggle
from common.handcart_can import CanListener


def init_table(values: list[list[str]], root_element: ttk.Frame) -> list[list[tkinter.Entry]]:
    """
    Generate a tkinter table given the value matrix.
    Args:
        values: The value matrix by which the table will be built
        root_element: The tkinter element where the table will be placed

    Returns: a matrix of tkinter.Entry elements, that are basically a table
    """
    num_rows = len(values)
    num_columns = len(values[0])

    entries: list[list[tkinter.Entry]] = []

    for row in range(num_rows):
        tmp = []
        for col in range(num_columns):
            en: tkinter.Entry = tkinter.Entry(
                root_element,
                disabledbackground="#000000",
                disabledforeground="#ffffff"
            )
            tmp.append(en)
        entries.append(tmp)

    for row in range(num_rows):
        for col in range(num_columns):
            entries[row][col].grid(row=row, column=col)
            root_element.grid_columnconfigure(col, weight=1)
            entries[row][col].insert(END, values[row][col])
            entries[row][col].configure(state=DISABLED)
    return entries


def update_table(values: list[list[str]], entries: list[list[tkinter.Entry]]) -> None:
    """
    Update a tkinter table withe given values
    Args:
        values: the values matrix to update the given entries tkinter matrix. Note that the values structure should
        match the entries structure
        entries: The tkinter Entry table
    """
    num_rows = len(values)
    num_columns = len(values[0])

    for row in range(num_rows):
        for col in range(num_columns):
            entries[row][col].configure(state=NORMAL)
            entries[row][col].delete(0, tkinter.END)
            entries[row][col].insert(END, values[row][col])
            entries[row][col].configure(state=DISABLED)


class Element(Enum):
    BUTTON_WINDOW_LEFT = 0
    BUTTON_WINDOW_RIGHT = 1


class Tab(Enum):
    TAB_MAIN = 0
    TAB_SETTINGS = 1
    TAB_ERRORS = 2


class Gui():
    FULL_SCREEN = True
    USE_MOCKED_VALUES = True

    TTKBOOSTRAP_THEME = "cyborg"  # https://ttkbootstrap.readthedocs.io/en/latest/themes/dark/

    REFRESH_RATE = 100  # ms at which the interface refreshes itself

    WINDOW_WIDTH = 1024
    WINDOW_HEIGHT = 600
    BORDER_WIDTH = 1

    ROOT_HEADER_HEIGHT: int  # calculated later
    ROOT_CENTER_HEIGHT: int  # calculated later
    ROOT_BOTTOM_HEIGHT: int  # calculated later

    shared_data: CanListener = None
    lock: threading.Lock
    com_queue: queue.Queue

    # Root window
    root: ttk.Window

    # Root center
    root_center: ttk.Frame
    root_center_tabs: ttk.Notebook

    # Root header
    root_header: ttk.Frame
    lbl_state: ttk.Label

    # Root bottom
    root_bottom: ttk.Frame
    button_left: ttk.Button
    button_right: ttk.Button

    # Main window
    tab_main: ttk.Frame
    main_center_left: ttk.Frame
    main_another_center_left: ttk.Frame
    main_center_center: ttk.Frame
    main_center_right: ttk.Frame
    MAIN_CENTER_WIDTH: int
    main_bms_values: list[list[str]]
    main_table_bms: list[list[tkinter.Entry]]
    main_brusa_values: list[list[str]]
    main_table_brusa: list[list[tkinter.Entry]]
    main_handcart_values: list[list[str]]
    main_table_handcart: list[list[tkinter.Entry]]

    # Settings window
    tab_settings: ttk.Frame

    # Errors window
    tab_errors: ttk.Frame

    # Logic
    selected_element: Element = None
    current_tab = Tab.TAB_MAIN.value

    def calculate_resolution(self):
        if self.FULL_SCREEN:
            self.WINDOW_HEIGHT = self.root.winfo_screenheight()
            self.WINDOW_WIDTH = self.root.winfo_screenwidth()

        self.ROOT_HEADER_HEIGHT = int(self.WINDOW_HEIGHT * 0.05)
        self.ROOT_CENTER_HEIGHT = int(self.WINDOW_HEIGHT * 0.9)
        self.ROOT_BOTTOM_HEIGHT = int(self.WINDOW_WIDTH * 0.05)

        self.MAIN_CENTER_WIDTH = int(self.WINDOW_WIDTH / 3)

    def on_focus_in(self, event: tkinter.Event, s: Element):
        """
        Called wheter an element is selected from the keyboard or buttons
        """
        self.selected_element = s
        print(f"focus on: {s}")
        print(self)

    def on_focus_out(self, event: tkinter.Event):
        """
        Reset the element focused
        """
        self.selected_element = None
        print("reset focus")

    def change_tab(self, forward: bool):
        if forward:
            if self.current_tab == Tab.TAB_ERRORS.value:
                self.current_tab = Tab.TAB_MAIN.value
            else:
                self.current_tab += 1
        elif not forward:
            if self.current_tab == Tab.TAB_MAIN.value:
                self.current_tab = Tab.TAB_ERRORS.value
            else:
                self.current_tab -= 1

        self.root_center_tabs.select(self.current_tab)

    def callback_but_1(self, ch: int) -> None:
        """
        Callback for button right. Called whether the button is pressed
        """
        print(PIN(ch))
        self.change_tab(True)

    def callback_but_3(self, ch: int):
        """
        Callback for button left. Called whether the button is pressed
        """
        print(PIN(ch))
        self.change_tab(False)

    def callback_but_2(self, ch: int):
        """
        Callback for button UP. Called whether the button is pressed
        """
        print(PIN(ch))
        with pyautogui.hold('shift'):
            pyautogui.press('\t')

    def callback_but_4(self, ch: int):
        """
        Callback for button DOWN. Called whether the button is pressed
        """
        print(PIN(ch))
        pyautogui.press('\t')

    def on_tab_changed(self, event: tkinter.Event):
        self.current_tab = self.root_center_tabs.index(self.root_center_tabs.select())

    def setup_root(self):
        self.root = ttk.Window(themename=self.TTKBOOSTRAP_THEME)

        if self.FULL_SCREEN:
            self.root.attributes("-fullscreen", True)
        else:
            self.root.resizable(False, False)
            self.root.geometry(f"{self.WINDOW_WIDTH}x{self.WINDOW_HEIGHT}")

        self.calculate_resolution()  # Recalculate resolution with previous changed values

        self.root_header_setup()
        self.root_center_setup()
        self.root_bottom_setup()

        self.setup_main_window()

        self.tab_settings = ttk.Frame(self.root_center_tabs)
        self.tab_errors = ttk.Frame(self.root_center_tabs)

        self.root_center_tabs.add(self.tab_main, text="main")  # 0
        self.root_center_tabs.add(self.tab_settings, text="settings")  # 1
        self.root_center_tabs.add(self.tab_errors, text="errors")  # 2
        self.root_center_tabs.bind('<<NotebookTabChanged>>', lambda ev: self.on_tab_changed(ev))
        self.root_center_tabs.pack(expand=1, fill=tkinter.BOTH)

        # Register callbacks for buttons
        GPIO.add_event_detect(PIN.BUT_2.value, FALLING, callback=self.callback_but_2, bouncetime=200)
        GPIO.add_event_detect(PIN.BUT_4.value, FALLING, callback=self.callback_but_4, bouncetime=200)

        self.root_center_tabs.select(self.tab_main)

    # ROOT HEADER ------------------------------------------------------------------------------------------------------

    def root_header_setup(self):
        self.root_header = ttk.Frame(
            self.root, width=self.WINDOW_WIDTH, height=self.ROOT_HEADER_HEIGHT, borderwidth=self.BORDER_WIDTH,
            relief=GROOVE)
        self.root_header.grid(column=0, row=0)
        self.root_header.pack_propagate(False)  # prevents the frame to resize automatically

        self.lbl_state = ttk.Label(self.root_header, text="STATE: None")
        self.lbl_state.pack(side=TOP)

        self.root_header_refresh()

    def root_header_refresh(self):
        self.root_header.after(self.REFRESH_RATE, self.root_header_refresh)

    # ROOT BOTTOM ------------------------------------------------------------------------------------------------------

    def root_bottom_setup(self):
        self.root_bottom = ttk.Frame(
            self.root, width=self.WINDOW_WIDTH, height=self.ROOT_BOTTOM_HEIGHT, borderwidth=self.BORDER_WIDTH,
            relief=GROOVE)

        self.root_bottom.grid(column=0, row=2)
        self.root_bottom.pack_propagate(False)  # prevents the frame to resize automatically

        self.button_left = ttk.Button(
            self.root_bottom, text="<-", bootstyle=(SECONDARY), command=lambda fw=False: self.change_tab(fw))
        self.button_left.bind(
            "<FocusIn>", lambda ev, el=Element.BUTTON_WINDOW_LEFT: self.on_focus_in(ev, el))  # select thing
        self.button_left.bind("<FocusOut>", lambda ev: self.on_focus_out(ev))
        self.button_left.pack(side=LEFT, padx=5, pady=10)

        self.button_right = ttk.Button(
            self.root_bottom, text="->", bootstyle=(SECONDARY), command=lambda fw=True: self.change_tab(fw))
        self.button_right.bind("<FocusIn>",
                               lambda ev, el=Element.BUTTON_WINDOW_RIGHT: self.on_focus_in(ev, el))  # select thing
        self.button_right.bind("<FocusOut>", lambda ev: self.on_focus_out(ev))
        self.button_right.pack(side=RIGHT, padx=5, pady=10)

        # Setup callbacks for buttons
        GPIO.add_event_detect(PIN.BUT_1.value, FALLING, callback=self.callback_but_1, bouncetime=200)
        GPIO.add_event_detect(PIN.BUT_3.value, FALLING, callback=self.callback_but_3, bouncetime=200)

        self.root_bottom_refresh()

    def root_bottom_refresh(self):
        self.root_bottom.after(self.REFRESH_RATE, self.root_bottom_refresh)

    # ROOT CENTER ------------------------------------------------------------------------------------------------------

    def root_center_setup(self):
        self.root_center = ttk.Frame(
            self.root, width=self.WINDOW_WIDTH, height=self.ROOT_CENTER_HEIGHT, borderwidth=self.BORDER_WIDTH,
            relief=GROOVE)
        self.root_center.grid(column=0, row=1)
        self.root_center.pack_propagate(False)  # prevents the frame to resize automatically

        self.root_center_tabs = ttk.Notebook(self.root_center)

    # MAIN WINDOW ------------------------------------------------------------------------------------------------------

    def setup_main_window(self):
        self.tab_main = ttk.Frame(
            self.root_center_tabs
        )

        self.main_center_left = ttk.Frame(
            self.tab_main,
            width=self.MAIN_CENTER_WIDTH, height=self.ROOT_CENTER_HEIGHT, borderwidth=self.BORDER_WIDTH, relief=GROOVE)
        self.main_center_left.grid(column=0, row=0)
        self.main_center_left.pack_propagate(False)  # prevents the frame to resize automatically

        self.main_center_left_lbl_top = ttk.Label(self.main_center_left, text="BMS")
        self.main_center_left_lbl_top.pack(side=TOP)

        self.main_another_center_left = ttk.Frame(self.main_center_left)
        self.main_another_center_left.pack(fill=BOTH)

        self.main_bms_values = [
            ["State", "-"],
            ["Max cell V", "-"],
            ["Min cell V", "-"],
            ["Cell delta V", "-"],
            ["Max temp °C", "-"],
            ["Min temp °C", "-"],
            ["Avg temp °C", "-"]
        ]

        self.main_table_bms = init_table(self.main_bms_values, self.main_another_center_left)

        self.main_center_center = ttk.Frame(
            self.tab_main,
            width=self.MAIN_CENTER_WIDTH, height=self.ROOT_CENTER_HEIGHT, borderwidth=self.BORDER_WIDTH, relief=GROOVE)
        self.main_center_center.grid(column=1, row=0)
        self.main_center_center.pack_propagate(False)  # prevents the frame to resize automatically

        self.main_center_center_lbl_top = ttk.Label(self.main_center_center, text="BRUSA")
        self.main_center_center_lbl_top.pack(side=TOP)

        self.main_another_center_center = ttk.Frame(self.main_center_center)
        self.main_another_center_center.pack(fill=BOTH)

        self.main_brusa_values = [
            ["status", "-"],
            ["Mains in VAC", "-"],
            ["Mains in A", "-"],
            ["Mains max in A", "-"],
            ["Out VDC", "-"],
            ["Out A", "-"],
            ["Temperature °C", "-"],
            ["Errors", "-"]
        ]

        self.main_table_brusa = init_table(self.main_brusa_values, self.main_another_center_center)

        self.main_center_right = ttk.Frame(
            self.tab_main,
            width=self.MAIN_CENTER_WIDTH, height=self.ROOT_CENTER_HEIGHT, borderwidth=self.BORDER_WIDTH, relief=GROOVE)
        self.main_center_right.grid(column=2, row=0)
        self.main_center_right.pack_propagate(False)  # prevents the frame to resize automatically

        self.main_center_right_lbl_top = ttk.Label(self.main_center_right, text="HANDCART")
        self.main_center_right_lbl_top.pack(side=TOP)

        self.main_another_center_right = ttk.Frame(self.main_center_right)
        self.main_another_center_right.pack(fill=BOTH)

        self.main_handcart_values = [
            ["Status", "-"],
            ["target V", "-"],
            ["Max current out", "-"],
            ["Max current in", "-"],
            ["Fan override", "-"],
            ["fan override speed", "-"]
        ]

        self.main_table_handcart = init_table(self.main_handcart_values, self.main_another_center_right)

        self.main_refresh()

    def main_refresh(self):
        if self.USE_MOCKED_VALUES:
            self.main_bms_values[0][1] = str(datetime.now())
            self.main_bms_values[1][1] = str(datetime.now())
            self.main_bms_values[2][1] = str(datetime.now())
        else:
            self.main_bms_values = [
                ["State", self.shared_data.bms_hv.status.name],
                ["Max cell V", self.shared_data.bms_hv.max_cell_voltage],
                ["Min cell V", self.shared_data.bms_hv.min_cell_voltage],
                ["Cell delta V", self.shared_data.bms_hv.act_cell_delta],
                ["Max temp °C", self.shared_data.bms_hv.max_temp],
                ["Min temp °C", self.shared_data.bms_hv.min_temp],
                ["Avg temp °C", self.shared_data.bms_hv.act_average_temp]
            ]

            self.main_brusa_values = [
                ["status", self.shared_data.brusa.isConnected()],
                ["Mains in VAC", str(round(self.shared_data.brusa.act_NLG5_ACT_I.get("NLG5_MV_ACT"), 2))],
                ["Mains in A", str(round(self.shared_data.brusa.act_NLG5_ACT_I.get("NLG5_MC_ACT"), 2))],
                ["Mains max in A", str(round(self.shared_data.brusa.act_NLG5_ACT_II.get("NLG5_S_MC_M_CP"), 2))],
                ["Out VDC", str(round(self.shared_data.brusa.act_NLG5_ACT_I.get("NLG5_OV_ACT"), 2))],
                ["Out A", str(round(self.shared_data.brusa.act_NLG5_ACT_I.get("NLG5_OC_ACT"), 2))],
                ["Temperature °C", str(round(self.shared_data.brusa.act_NLG5_TEMP.get("NLG5_P_TMP"), 2))],
                ["Errors", str(self.shared_data.brusa.error)]
            ]

            self.main_handcart_values = [
                ["Status", self.shared_data.FSM_stat.name],
                ["target V", self.shared_data.target_v],
                ["Max current out", self.shared_data.act_set_out_current],
                ["Max current in", self.shared_data.act_set_in_current],
                ["Fan override",
                 str("enabled" if self.shared_data.bms_hv.fans_set_override_status.value == Toggle.ON else "disabled")],
                ["fan override speed", str(self.shared_data.bms_hv.fans_set_override_speed)]
            ]

        update_table(self.main_bms_values, self.main_table_bms)
        self.tab_main.after(self.REFRESH_RATE, self.main_refresh)

    # SETTINGS WINDOW --------------------------------------------------------------------------------------------------

    def __init__(self,
                 com_queue: queue.Queue,
                 lock: threading.Lock,
                 shared_data: CanListener):
        self.com_queue = com_queue
        self.lock = lock
        self.shared_data = shared_data
        self.setup_root()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    t = Gui(None, None, None)
    t.run()
