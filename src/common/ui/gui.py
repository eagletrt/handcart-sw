import queue
import threading
import tkinter
from enum import Enum

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

from common.handcart_can import CanListener


class Element(Enum):
    BUTTON_WINDOW_LEFT = 0
    BUTTON_WINDOW_RIGHT = 1


class Tab(Enum):
    TAB_MAIN = 0
    TAB_SETTINGS = 1
    TAB_ERRORS = 2


class Gui(threading.Thread):
    FULL_SCREEN = False

    WINDOW_WIDTH = 1024
    WINDOW_HEIGHT = 600
    TTKBOOSTRAP_THEME = "cyborg"  # https://ttkbootstrap.readthedocs.io/en/latest/themes/dark/

    HEADER_HEIGHT = int(WINDOW_HEIGHT * 0.05)
    CENTER_HEIGHT = int(WINDOW_HEIGHT * 0.9)
    BOTTOM_HEIGHT = int(WINDOW_WIDTH * 0.05)

    BORDER_WIDTH = 1

    CENTER_SUB_WIDTH = int(WINDOW_WIDTH / 3)

    shared_data: CanListener = None
    lock: threading.Lock
    queue: queue.Queue

    root: ttk.Window
    header: ttk.Frame
    center: ttk.Frame
    bottom: ttk.Frame
    lbl_state: ttk.Label
    button_left: ttk.Button
    button_right: ttk.Button
    tabs: ttk.Notebook

    # Main window
    tab_main: ttk.Frame
    center_left: ttk.Frame
    center_center: ttk.Frame
    center_right: ttk.Frame

    tab_settings: ttk.Frame
    tab_errors: ttk.Frame

    # Logic
    selected_element = None
    current_tab = Tab.TAB_MAIN.value

    def calculate_resolution(self):
        if self.FULL_SCREEN:
            self.WINDOW_HEIGHT = self.root.winfo_screenheight()
            self.WINDOW_WIDTH = self.root.winfo_screenwidth()

        self.HEADER_HEIGHT = int(self.WINDOW_HEIGHT * 0.05)
        self.CENTER_HEIGHT = int(self.WINDOW_HEIGHT * 0.9)
        self.BOTTOM_HEIGHT = int(self.WINDOW_WIDTH * 0.05)

        self.CENTER_SUB_WIDTH = int(self.WINDOW_WIDTH / 3)

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

        self.tabs.select(self.current_tab)

    def refresh_header_footer(self):
        self.lbl_state.config(text=self.shared_data.FSM_stat.name)
        self.header.after(1000, self.refresh_header_footer)

    def setup_header_footer(self):
        self.header = ttk.Frame(self.root, width=self.WINDOW_WIDTH, height=self.HEADER_HEIGHT,
                                borderwidth=self.BORDER_WIDTH, relief=GROOVE)
        self.header.grid(column=0, row=0)
        self.header.pack_propagate(False)  # prevents the frame to resize automatically

        self.lbl_state = ttk.Label(self.header, text="STATE: None")
        self.lbl_state.pack(side=TOP)

        self.bottom = ttk.Frame(self.root, width=self.WINDOW_WIDTH, height=self.BOTTOM_HEIGHT,
                                borderwidth=self.BORDER_WIDTH,
                                relief=GROOVE)
        self.bottom.grid(column=0, row=2)
        self.bottom.pack_propagate(False)  # prevents the frame to resize automatically

        self.button_left = ttk.Button(self.bottom, text="<-", bootstyle=(SECONDARY),
                                      command=lambda fw=False: self.change_tab(fw))
        self.button_left.bind("<FocusIn>",
                              lambda ev, el=Element.BUTTON_WINDOW_LEFT: self.on_focus_in(ev, el))  # select thing
        self.button_left.bind("<FocusOut>", lambda ev: self.on_focus_out(ev))
        self.button_left.pack(side=LEFT, padx=5, pady=10)

        self.button_right = ttk.Button(self.bottom, text="->", bootstyle=(SECONDARY),
                                       command=lambda fw=True: self.change_tab(fw))
        self.button_right.bind("<FocusIn>",
                               lambda ev, el=Element.BUTTON_WINDOW_RIGHT: self.on_focus_in(ev, el))  # select thing
        self.button_right.bind("<FocusOut>", lambda ev: self.on_focus_out(ev))
        self.button_right.pack(side=RIGHT, padx=5, pady=10)

        self.refresh_header_footer()

    def setup_tab_main(self):
        self.center_left = ttk.Frame(self.tab_main, width=self.CENTER_SUB_WIDTH, height=self.CENTER_HEIGHT,
                                     borderwidth=self.BORDER_WIDTH, relief=GROOVE)
        self.center_left.grid(column=0, row=0)
        self.center_left.pack_propagate(False)  # prevents the frame to resize automatically

        self.center_center = ttk.Frame(self.tab_main, width=self.CENTER_SUB_WIDTH, height=self.CENTER_HEIGHT,
                                       borderwidth=self.BORDER_WIDTH, relief=GROOVE)
        self.center_center.grid(column=1, row=0)
        self.center_center.pack_propagate(False)  # prevents the frame to resize automatically

        self.center_right = ttk.Frame(self.tab_main, width=self.CENTER_SUB_WIDTH, height=self.CENTER_HEIGHT,
                                      borderwidth=self.BORDER_WIDTH, relief=GROOVE)
        self.center_right.grid(column=2, row=0)
        self.center_right.pack_propagate(False)  # prevents the frame to resize automatically

    def setup_tab_settings(self):
        pass

    def setup_tab_errors(self):
        pass

    def on_tab_changed(self, event: tkinter.Event):
        self.current_tab = self.tabs.index(self.tabs.select())

    def setup(self):
        self.root = ttk.Window(themename=self.TTKBOOSTRAP_THEME)
        if self.FULL_SCREEN:
            self.root.attributes("-fullscreen", True)
            self.calculate_resolution()
        else:
            self.root.resizable(False, False)

        self.root.geometry(f"{self.WINDOW_WIDTH}x{self.WINDOW_HEIGHT}")

        self.setup_header_footer()
        self.center = ttk.Frame(self.root, width=self.WINDOW_WIDTH, height=self.CENTER_HEIGHT,
                                borderwidth=self.BORDER_WIDTH,
                                relief=GROOVE)
        self.center.grid(column=0, row=1)
        self.center.pack_propagate(False)  # prevents the frame to resize automatically

        self.tabs = ttk.Notebook(self.center)

        self.tab_main = ttk.Frame(self.tabs)
        self.tab_settings = ttk.Frame(self.tabs)
        self.tab_errors = ttk.Frame(self.tabs)

        self.tabs.add(self.tab_main, text="main")  # 0
        self.tabs.add(self.tab_settings, text="settings")  # 1
        self.tabs.add(self.tab_errors, text="errors")  # 2
        self.tabs.bind('<<NotebookTabChanged>>', lambda ev: self.on_tab_changed(ev))
        self.tabs.pack(expand=1, fill=tkinter.BOTH)

        # print(self.tabs.tab(2))

        # tab_names = [self.tabs.tab(i, option="id") for i in self.tabs.tabs()]
        # print(tab_names)

        self.tabs.select(self.tab_main)

        self.setup_tab_main()
        self.setup_tab_settings()
        self.setup_tab_errors()

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
        self.setup()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    t = Gui()
    t.run()
