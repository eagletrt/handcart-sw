import datetime
import queue
import threading
import tkinter
from enum import Enum

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

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
        entries.append([tkinter.Entry(root_element) for _ in range(num_columns)])

    for row in range(num_rows):
        for col in range(num_columns):
            entries[row][col].grid(row=row, column=col)
            root_element.grid_columnconfigure(col, weight=1)
            entries[row][col].insert(END, values[row][col])
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
            entries[row][col].delete(0, tkinter.END)
            entries[row][col].insert(END, values[row][col])


class Element(Enum):
    BUTTON_WINDOW_LEFT = 0
    BUTTON_WINDOW_RIGHT = 1


class Tab(Enum):
    TAB_MAIN = 0
    TAB_SETTINGS = 1
    TAB_ERRORS = 2


class Gui(threading.Thread):
    FULL_SCREEN = True

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

    # Settings window
    tab_settings: ttk.Frame

    # Errors window
    tab_errors: ttk.Frame

    # Logic
    selected_element = None
    current_tab = Tab.TAB_MAIN.value

    def calculate_resolution(self):
        if self.FULL_SCREEN:
            self.WINDOW_HEIGHT = self.root.winfo_screenheight()
            self.WINDOW_WIDTH = self.root.winfo_screenwidth()

        self.ROOT_HEADER_HEIGHT = int(self.WINDOW_HEIGHT * 0.05)
        self.ROOT_CENTER_HEIGHT = int(self.WINDOW_HEIGHT * 0.9)
        self.ROOT_BOTTOM_HEIGHT = int(self.WINDOW_WIDTH * 0.05)

        self.MAIN_CENTER_WIDTH = int(self.WINDOW_WIDTH / 3)

    def on_focus_in(self, event: tkinter.Event, s):
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

        self.main_another_center_left = ttk.Frame(self.main_center_left)
        self.main_another_center_left.pack(fill=BOTH)

        self.main_bms_values = [["State", "value"],
                                ["Max cell v", "3.4 V"],
                                ["Min cell v", "2.8 V"],
                                ["avg cell v", "3.2 V"],
                                ["cell delta", "0.4 V"]]

        self.main_table_bms = init_table(self.main_bms_values, self.main_another_center_left)

        self.main_center_center = ttk.Frame(
            self.tab_main,
            width=self.MAIN_CENTER_WIDTH, height=self.ROOT_CENTER_HEIGHT, borderwidth=self.BORDER_WIDTH, relief=GROOVE)
        self.main_center_center.grid(column=1, row=0)
        self.main_center_center.pack_propagate(False)  # prevents the frame to resize automatically

        self.main_center_right = ttk.Frame(
            self.tab_main,
            width=self.MAIN_CENTER_WIDTH, height=self.ROOT_CENTER_HEIGHT, borderwidth=self.BORDER_WIDTH, relief=GROOVE)
        self.main_center_right.grid(column=2, row=0)
        self.main_center_right.pack_propagate(False)  # prevents the frame to resize automatically

        self.main_refresh()

    def main_refresh(self):
        self.main_bms_values[0][1] = str(datetime.datetime.now())
        self.main_bms_values[1][1] = str(datetime.datetime.now())
        self.main_bms_values[2][1] = str(datetime.datetime.now())
        update_table(self.main_bms_values, self.main_table_bms)
        self.tab_main.after(self.REFRESH_RATE, self.main_refresh)

    # SETTINGS WINDOW --------------------------------------------------------------------------------------------------

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
        self.setup_root()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    t = Gui(None, None, None)
    t.run()
