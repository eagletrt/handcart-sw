import datetime
import subprocess
import tkinter

import pyautogui
import ttkbootstrap as ttk
from RPi import GPIO
from RPi.GPIO import RISING, FALLING
from ttkbootstrap.constants import *

from common.buzzer import BuzzerNote
from common.feedbacks.feedbacks import FB
from common.handcart_can import *
from common.handcart_can import CanListener
from common.logging import tprint, P_TYPE


def init_table(values: list[list[str]], root_element: ttk.Frame, state=DISABLED) -> list[list[tkinter.Entry]]:
    """
    Generate a tkinter table given the value matrix.
    Args:
        state: state of the element, default disabled
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
            entries[row][col].configure(state=state)
    return entries


def update_table(values: list[list[str]], entries: list[list[tkinter.Entry]], state=DISABLED) -> None:
    """
    Update a tkinter table withe given values
    Args:
        state: state of the entities, default DISABLED
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
            entries[row][col].configure(state=state)


class Element(Enum):
    BUTTON_WINDOW_LEFT = 0
    BUTTON_WINDOW_RIGHT = 1
    SETTING_CUTOFF = 2
    SETTING_MAX_OUT_CURRENT = 3
    SETTING_FAN_OVERRIDE_STATUS = 4
    SETTING_FAN_OVERRIDE_SPEED = 5


# limits for the possible values of the settings in the interface
SETTING_ELEMENT_LIMIT = {
    Element.SETTING_CUTOFF: {"min": 350, "max": 450, "step": 1},
    Element.SETTING_MAX_OUT_CURRENT: {"min": 0, "max": 8, "step": .1},
    Element.SETTING_FAN_OVERRIDE_STATUS: {"min": 0, "max": 1, "step": 1},
    Element.SETTING_FAN_OVERRIDE_SPEED: {"min": 0, "max": 1, "step": .05},
}


def is_settings_element(el: Element) -> bool:
    """
    Tells if the element is a setting element or not
    Args:
        el:

    Returns:

    """
    return el in [
        Element.SETTING_CUTOFF,
        Element.SETTING_MAX_OUT_CURRENT,
        Element.SETTING_FAN_OVERRIDE_STATUS,
        Element.SETTING_FAN_OVERRIDE_SPEED
    ]


class Tab(Enum):
    TAB_MAIN = 0
    TAB_SETTINGS = 1
    TAB_ERRORS = 2


class ScrollableFrame(ttk.Frame):
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        canvas = tkinter.Canvas(self)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")


def update():
    """
    Update the handcart and the submodules and restart the service
    Returns:

    """
    try:
        result = subprocess.run(["git", "pull", "--recurse-submodules"])
        result = subprocess.run(["sudo", "systemctl", "restart", "handcart-backend.service"])
    except Exception:
        tprint("Error during update", P_TYPE.ERROR)


class Gui():
    FULL_SCREEN = True
    USE_MOCKED_VALUES = False

    TTKBOOSTRAP_THEME = "cyborg"  # https://ttkbootstrap.readthedocs.io/en/latest/themes/dark/

    REFRESH_RATE = 100  # ms at which the interface refreshes itself

    WINDOW_WIDTH = 1024
    WINDOW_HEIGHT = 600
    BORDER_WIDTH = 1

    BOUNCETIME = 200  # ms

    ROOT_HEADER_HEIGHT: int  # calculated later
    ROOT_CENTER_HEIGHT: int  # calculated later
    ROOT_BOTTOM_HEIGHT: int  # calculated later

    ELEMENT_INDEX_OFFSET = 2  # offset of the element int value of the enum wrt 0

    shared_data: CanListener = None
    lock: threading.Lock
    com_queue: queue.Queue
    melody_queue: queue.Queue

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
    button_start_precharge: ttk.Button
    button_start_charge: ttk.Button
    button_stop_charge: ttk.Button
    button_start_balance: ttk.Button
    button_stop_balance: ttk.Button
    button_go_idle: ttk.Button

    last_fsm_state: STATE = STATE.CHECK

    # Main window
    tab_main: ttk.Frame
    main_center_left: ttk.Frame
    main_another_center_left: ttk.Frame
    main_center_center: ttk.Frame
    main_center_right: ttk.Frame
    MAIN_CENTER_WIDTH: int
    main_bms_values: list[list[str]]
    main_table_bms: list[list[tkinter.Entry]]
    main_charger_values: list[list[str]]
    main_table_brusa: list[list[tkinter.Entry]]
    main_handcart_values: list[list[str]]
    main_table_handcart: list[list[tkinter.Entry]]

    # Settings window
    settings_name_value: list[list[str]]
    settings_name_table: list[list[tkinter.Entry]]
    tab_settings: ttk.Frame
    settings_actual_value: list[list[float | int]] = [[-1], [-1], [-1], [-1], [-1]]
    settings_set_value: list[list[float | int]] = [[-1], [-1], [-1], [-1], [-1]]
    settings_set_value_table: list[list[tkinter.Entry]]

    # Errors window
    tab_errors: ttk.Frame

    # Logic
    selected_element: Element = None
    current_tab = Tab.TAB_MAIN.value
    confirmed: bool = False

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

        # save old value of element selected
        if 10 >= self.selected_element.value >= 2:
            self.confirmed = False  # tell if the new element new value haas been confirmed

        tprint(f"focus on: {s}", P_TYPE.DEBUG)

    def on_focus_out(self, event: tkinter.Event, s: Element):
        """
        Reset the element focused
        """

        # restore old value if not confirmed
        if is_settings_element(s) and not self.confirmed:
            self.settings_set_value[self.get_element_index(s)][0] \
                = self.settings_actual_value[self.get_element_index(s)][0]
        self.selected_element = None
        self.confirmed = False

        tprint("reset focus", P_TYPE.DEBUG)

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
        tprint(f"Pressed button: {PIN(ch)}", P_TYPE.DEBUG)
        self.change_tab(True)

    def callback_but_3(self, ch: int):
        """
        Callback for button left. Called whether the button is pressed
        """
        tprint(f"Pressed button: {PIN(ch)}", P_TYPE.DEBUG)
        self.change_tab(False)

    def callback_but_2(self, ch: int):
        """
        Callback for button UP. Called whether the button is pressed
        """
        tprint(f"Pressed button: {PIN(ch)}", P_TYPE.DEBUG)
        with pyautogui.hold('shift'):
            pyautogui.press('\t')

    def callback_but_4(self, ch: int):
        """
        Callback for button DOWN. Called whether the button is pressed
        """
        tprint(f"Pressed button: {PIN(ch)}", P_TYPE.DEBUG)
        pyautogui.press('\t')

    def callback_update_button(self):
        tprint(f"Pressed update button", P_TYPE.DEBUG)
        if self.shared_data.FSM_stat not in [STATE.IDLE, STATE.CHECK]:
            return
        else:
            update()

    def get_element_index(self, elem: Element):
        if is_settings_element(elem):
            index = elem.value - self.ELEMENT_INDEX_OFFSET
            return index

    def get_selected_settings_element_index(self) -> int | None:
        """
        Get selected element only if it is a setting element
        Returns:

        """
        if self.selected_element is not None:
            return self.get_element_index(self.selected_element)

        return None

    def encoder_callback(self, gpio_pin: int):
        CLK_state = GPIO.input(PIN.ROT_B.value)
        DT_state = GPIO.input(PIN.ROT_A.value)

        delta = 0

        if not is_settings_element(self.selected_element):
            return

        selected_settings_element_index = self.get_selected_settings_element_index()

        if selected_settings_element_index is None:
            return

        selected_element_limit = SETTING_ELEMENT_LIMIT[self.selected_element]
        multiplier = selected_element_limit['step']

        if CLK_state == GPIO.HIGH and DT_state == GPIO.LOW:
            # tprint(f"Rotary Encoder direction: {'CLOCKWISE' if False else 'ANTICLOCKWISE'}", P_TYPE.DEBUG)
            delta = -1 * multiplier

        elif CLK_state == GPIO.HIGH and DT_state == GPIO.HIGH:
            # tprint(f"Rotary Encoder direction: {'CLOCKWISE' if True else 'ANTICLOCKWISE'}", P_TYPE.DEBUG)
            delta = 1 * multiplier

        # float values
        if self.selected_element in [Element.SETTING_MAX_OUT_CURRENT,
                                     Element.SETTING_FAN_OVERRIDE_SPEED]:
            val = float(self.settings_set_value[selected_settings_element_index][0])
            new_val = round(val + delta, 2)
            if new_val > selected_element_limit["max"] or new_val < selected_element_limit["min"]:
                return

            self.settings_set_value[selected_settings_element_index][0] = str(new_val)

        # int values
        if self.selected_element in [Element.SETTING_CUTOFF,
                                     Element.SETTING_FAN_OVERRIDE_STATUS]:
            val = int(self.settings_set_value[selected_settings_element_index][0])
            new_val = int(val + delta)
            if new_val > selected_element_limit["max"] or new_val < selected_element_limit["min"]:
                return

            self.settings_set_value[selected_settings_element_index][0] = str(new_val)

    def button_encoder_callback(self, gpio_pin: int):
        tprint("Pressed confirm button", P_TYPE.DEBUG)
        self.confirmed = True
        # TODO: based on selected item send command to update its value
        # On deselect, you will restore the saved value.
        tprint(f"Confirm element: {self.selected_element}", P_TYPE.DEBUG)
        if not is_settings_element(self.selected_element):
            return

        setting_index = self.get_selected_settings_element_index()
        tprint(f"Confirm element indx: {setting_index}", P_TYPE.DEBUG)

        if setting_index is None:
            return

        tprint(f"Confirm element: {self.selected_element}", P_TYPE.DEBUG)

        command_mapping = {
            Element.SETTING_CUTOFF: lambda: {
                "com-type": "cutoff",
                "value": int(self.settings_set_value[self.get_element_index(Element.SETTING_CUTOFF)][0])
            },
            Element.SETTING_MAX_OUT_CURRENT: lambda: {
                "com-type": "max-out-current",
                "value": float(self.settings_set_value[self.get_element_index(Element.SETTING_MAX_OUT_CURRENT)][0])
            },
            Element.SETTING_FAN_OVERRIDE_STATUS: lambda: {
                "com-type": "fan-override-set-status",
                "value": True if self.settings_set_value[self.get_element_index(Element.SETTING_FAN_OVERRIDE_STATUS)][
                                     0] == "1" else False
            },
            Element.SETTING_FAN_OVERRIDE_SPEED: lambda: {
                "com-type": "fan-override-set-speed",
                "value": int(float(self.settings_set_value[self.get_element_index(Element.SETTING_FAN_OVERRIDE_SPEED)][0])*100)
            }
        }

        self.melody_queue.put({"melody": [(BuzzerNote.DO, 0.1)], "repeat": 1})

        self.com_queue.put(command_mapping[self.selected_element]())

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
        self.setup_settings_window()
        self.setup_errors_window()

        self.root_center_tabs.add(self.tab_main, text="main")  # 0
        self.root_center_tabs.add(self.tab_settings, text="settings")  # 1
        self.root_center_tabs.add(self.tab_errors, text="errors")  # 2
        self.root_center_tabs.bind('<<NotebookTabChanged>>', lambda ev: self.on_tab_changed(ev))
        self.root_center_tabs.pack(expand=1, fill=tkinter.BOTH)

        # Register callbacks for buttons
        GPIO.add_event_detect(PIN.BUT_2.value, FALLING, callback=self.callback_but_4, bouncetime=self.BOUNCETIME)
        GPIO.add_event_detect(PIN.BUT_4.value, FALLING, callback=self.callback_but_2, bouncetime=self.BOUNCETIME)
        GPIO.add_event_detect(PIN.ROT_B.value, RISING, callback=self.encoder_callback, bouncetime=2)  # encoder
        GPIO.add_event_detect(PIN.BUT_0.value, FALLING, callback=self.button_encoder_callback,
                              bouncetime=self.BOUNCETIME)

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
        if not self.USE_MOCKED_VALUES:
            self.lbl_state.configure(text=f"STATE: {self.shared_data.FSM_stat.name}")
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
        self.button_left.bind(
            "<FocusOut>", lambda ev, el=Element.BUTTON_WINDOW_LEFT: self.on_focus_out(ev, el))
        self.button_left.pack(side=LEFT)
        # self.button_left.grid(column=0, row=0)

        self.button_right = ttk.Button(
            self.root_bottom, text="->", bootstyle=(SECONDARY), command=lambda fw=True: self.change_tab(fw))
        self.button_right.bind("<FocusIn>",
                               lambda ev, el=Element.BUTTON_WINDOW_RIGHT: self.on_focus_in(ev, el))  # select thing
        self.button_right.bind(
            "<FocusOut>", lambda ev, el=Element.BUTTON_WINDOW_RIGHT: self.on_focus_out(ev, el))
        self.button_right.pack(side=RIGHT)
        # self.button_right.grid(column=2, row=0)

        self.root_bottom_center_button_container = ttk.Frame(
            self.root_bottom,
            width=self.WINDOW_WIDTH / 2,
            height=self.ROOT_BOTTOM_HEIGHT,
            borderwidth=self.BORDER_WIDTH,
            relief=GROOVE
        )
        self.root_bottom_center_button_container.pack_propagate(True)
        self.root_bottom_center_button_container.pack(side=TOP)
        # self.root_bottom_center_button_container.grid(column=1, row=0)

        self.button_start_charge = ttk.Button(
            self.root_bottom_center_button_container,
            text="Charge",
            bootstyle=(SECONDARY),
            command=lambda: self.com_queue.put({"com-type": "charge", "value": True})
        )
        self.button_stop_charge = ttk.Button(
            self.root_bottom_center_button_container,
            text="Stop charge",
            bootstyle=(SECONDARY),
            command=lambda: self.com_queue.put({"com-type": "charge", "value": False})
        )
        self.button_start_precharge = ttk.Button(
            self.root_bottom_center_button_container,
            text="Precharge",
            bootstyle=(SECONDARY),
            command=lambda: self.com_queue.put({"com-type": "precharge", "value": True})
        )
        self.button_start_balance = ttk.Button(
            self.root_bottom_center_button_container,
            text="Balance",
            bootstyle=(SECONDARY),
            command=lambda: self.com_queue.put({"com-type": "balancing", "value": True})
        )
        self.button_stop_balance = ttk.Button(
            self.root_bottom_center_button_container,
            text="Stop balance",
            bootstyle=(SECONDARY),
            command=lambda: self.com_queue.put({"com-type": "balancing", "value": False})
        )
        self.button_go_idle = ttk.Button(
            self.root_bottom_center_button_container,
            text="Idle",
            bootstyle=(SECONDARY),
            command=lambda: self.com_queue.put({"com-type": "shutdown", "value": True})
        )

        # Setup callbacks for buttons
        GPIO.add_event_detect(PIN.BUT_1.value, FALLING, callback=self.callback_but_1, bouncetime=self.BOUNCETIME)
        GPIO.add_event_detect(PIN.BUT_3.value, FALLING, callback=self.callback_but_3, bouncetime=self.BOUNCETIME)

        self.root_bottom_refresh()

    def root_bottom_button_reset(self):
        self.button_start_charge.grid_forget()
        self.button_stop_charge.grid_forget()
        self.button_start_precharge.grid_forget()
        self.button_start_balance.grid_forget()
        self.button_stop_balance.grid_forget()
        self.button_go_idle.grid_forget()

    def root_bottom_refresh(self):
        if self.last_fsm_state != self.shared_data.FSM_stat:
            self.root_bottom_button_reset()  # remove all buttons

            if self.shared_data.FSM_stat == STATE.IDLE:
                self.button_start_precharge.grid(column=0, row=0)
                self.button_start_balance.grid(column=1, row=0)

            if self.shared_data.FSM_stat == STATE.PRECHARGE:
                self.button_go_idle.grid(column=0, row=0)

            if self.shared_data.FSM_stat == STATE.READY:
                self.button_start_charge.grid(column=0, row=0)
                self.button_go_idle.grid(column=1, row=0)

            if self.shared_data.FSM_stat == STATE.CHARGE:
                self.button_go_idle.grid(column=1, row=0)
                self.button_stop_charge.grid(column=0, row=0)

            if self.shared_data.FSM_stat == STATE.CHARGE_DONE:
                self.button_go_idle.grid(column=0, row=0)

            if self.shared_data.FSM_stat == STATE.BALANCING:
                self.button_stop_balance.grid(column=0, row=0)

            self.last_fsm_state = self.shared_data.FSM_stat

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
            ["Pack V", "-"],
            ["BUS V", "-"],
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

        self.main_center_center_lbl_top = ttk.Label(self.main_center_center, text="Charger")
        self.main_center_center_lbl_top.pack(side=TOP)

        self.main_another_center_center = ttk.Frame(self.main_center_center)
        self.main_another_center_center.pack(fill=BOTH)

        self.main_charger_values = [
            ["status", "-"],
            ["Actual V out", "-"],
            ["Actual A out", "-"],
            ["Temp max", "-"],
            ["swVersion", "-"],
            ["Warnings", "-"],
            ["Errors", "-"]
        ]

        self.main_table_brusa = init_table(self.main_charger_values, self.main_another_center_center)

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
            ["fan override speed", "-"],
            [FB.VSD_FB, "-"],
            [FB.SD_TO_MUSHROOM_FB, "-"],
            [FB.SD_TO_CHARGER_FB, "-"],
            [FB.SD_BMS_IN_FB, "-"],
            [FB.SD_BMS_OUT_FB, "-"],
            [FB.SD_END_FB, "-"],
            [FB.COIL_DISCHARGE_FB, "-"],
            [FB.FB_12_V, "-"],
            [FB.PON_FB, "-"],
            [FB.RELAY_SD_FB, "-"]
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
                ["Pack V", self.shared_data.bms_hv.act_pack_voltage],
                ["BUS V", self.shared_data.bms_hv.act_bus_voltage],
                ["Max cell V", self.shared_data.bms_hv.max_cell_voltage],
                ["Min cell V", self.shared_data.bms_hv.min_cell_voltage],
                ["Cell delta V", self.shared_data.bms_hv.act_cell_delta],
                ["Max temp °C", self.shared_data.bms_hv.max_temp],
                ["Min temp °C", self.shared_data.bms_hv.min_temp],
                ["Avg temp °C", self.shared_data.bms_hv.act_average_temp],
            ]

            """
            for i in self.shared_data.bms_hv.errors.keys():
                if self.shared_data.bms_hv.errors[i] == 1:
                    self.main_bms_values.append([i, self.shared_data.bms_hv.errors[i]])

            for i in self.shared_data.bms_hv.feedbacks.keys():
                if self.shared_data.bms_hv.feedbacks[i] == 1:
                    self.main_bms_values.append([i, self.shared_data.bms_hv.feedbacks[i]])
            """

            self.main_charger_values = [
                ["status", self.shared_data.charger.status.name],
                ["Actual V out", self.shared_data.charger.act_voltage],
                ["Actual A out", self.shared_data.charger.act_current],
                ["Temp max", self.shared_data.charger.max_temp],
                ["swVersion", self.shared_data.charger.sw_version],
                ["Warnings", str(self.shared_data.charger.warning)],
                ["Errors", str(self.shared_data.charger.error)]
            ]

            self.main_handcart_values = [
                ["Status", self.shared_data.FSM_stat.name],
                ["target V", self.shared_data.target_v],
                ["Max current out", self.shared_data.act_set_out_current],
                ["Max current in", 0],
                ["Fan override",
                 str("enabled" if self.shared_data.bms_hv.fans_set_override_status.value == Toggle.ON else "disabled")],
                ["fan override speed", str(self.shared_data.bms_hv.fans_set_override_speed)],
                [FB.VSD_FB, self.shared_data.feedbacks[FB.VSD_FB.value]],
                [FB.SD_TO_MUSHROOM_FB,  self.shared_data.feedbacks[FB.SD_TO_MUSHROOM_FB.value]],
                [FB.SD_TO_CHARGER_FB,  self.shared_data.feedbacks[FB.SD_TO_CHARGER_FB.value]],
                [FB.SD_BMS_IN_FB,  self.shared_data.feedbacks[FB.SD_BMS_IN_FB.value]],
                [FB.SD_BMS_OUT_FB,  self.shared_data.feedbacks[FB.SD_BMS_OUT_FB.value]],
                [FB.SD_END_FB,  self.shared_data.feedbacks[FB.SD_END_FB.value]],
                [FB.COIL_DISCHARGE_FB,  self.shared_data.feedbacks[FB.COIL_DISCHARGE_FB.value]],
                [FB.FB_12_V,  self.shared_data.feedbacks[FB.FB_12_V.value]],
                [FB.PON_FB,  self.shared_data.feedbacks[FB.PON_FB.value]],
                [FB.RELAY_SD_FB,  self.shared_data.feedbacks[FB.RELAY_SD_FB.value]]
            ]

        update_table(self.main_bms_values, self.main_table_bms)
        update_table(self.main_charger_values, self.main_table_brusa)
        update_table(self.main_handcart_values, self.main_table_handcart)
        self.tab_main.after(self.REFRESH_RATE, self.main_refresh)

    # SETTINGS WINDOW --------------------------------------------------------------------------------------------------

    def setup_settings_window(self):
        self.tab_settings = ttk.Frame(self.root_center_tabs)

        self.tab_settings_up = ttk.Frame(self.tab_settings)
        self.tab_settings_up.grid(column=0, row=0)
        self.tab_settings_down = ttk.Frame(self.tab_settings)
        self.tab_settings_down.grid(column=0, row=1)

        self.settings_button_update = ttk.Button(self.tab_settings_down,
            text="Update and restart",
            bootstyle=(SECONDARY),
            command=update)

        self.settings_button_update.pack()

        # CENTER LEFT
        self.settings_center_left = ttk.Frame(
            self.tab_settings_up,
            width=self.MAIN_CENTER_WIDTH, height=self.ROOT_CENTER_HEIGHT*0.8, borderwidth=self.BORDER_WIDTH, relief=GROOVE)
        self.settings_center_left.grid(column=0, row=0)
        self.settings_center_left.pack_propagate(False)  # prevents the frame to resize automatically

        self.settings_center_left_lbl_top = ttk.Label(self.settings_center_left, text="Setting name")
        self.settings_center_left_lbl_top.pack(side=TOP)

        self.settings_another_center_left = ttk.Frame(self.settings_center_left)
        self.settings_another_center_left.pack(fill=BOTH)

        self.settings_name_value = [
            ["BMS target voltage (V)"],
            ["BMS max input current (A)"],
            ["BMS fan override status"],
            ["BMS fan override speed"],
            ["CHARGER max grid current"]
        ]

        self.settings_name_table = init_table(self.settings_name_value, self.settings_another_center_left)

        # CENTER CENTER
        self.settings_center_center = ttk.Frame(
            self.tab_settings_up,
            width=self.MAIN_CENTER_WIDTH, height=self.ROOT_CENTER_HEIGHT*0.8, borderwidth=self.BORDER_WIDTH, relief=GROOVE)
        self.settings_center_center.grid(column=1, row=0)
        self.settings_center_center.pack_propagate(False)  # prevents the frame to resize automatically

        self.settings_center_center_lbl_top = ttk.Label(self.settings_center_center, text="Value read")
        self.settings_center_center_lbl_top.pack(side=TOP)

        self.settings_another_center_center = ttk.Frame(self.settings_center_center)
        self.settings_another_center_center.pack(fill=BOTH)

        self.settings_actual_value_table = init_table(self.settings_actual_value, self.settings_another_center_center)

        # CENTER RIGHT

        self.settings_center_center_right = ttk.Frame(
            self.tab_settings_up,
            width=self.MAIN_CENTER_WIDTH, height=self.ROOT_CENTER_HEIGHT*0.8, borderwidth=self.BORDER_WIDTH, relief=GROOVE)
        self.settings_center_center_right.grid(column=2, row=0)
        self.settings_center_center_right.pack_propagate(False)  # prevents the frame to resize automatically

        self.settings_center_center_right_lbl_top = ttk.Label(self.settings_center_center_right, text="Value set")
        self.settings_center_center_right_lbl_top.pack(side=TOP)

        self.settings_another_center_center_right = ttk.Frame(self.settings_center_center_right)
        self.settings_another_center_center_right.pack(fill=BOTH)

        self.settings_set_value_table = init_table(
            self.settings_set_value, self.settings_another_center_center_right, state=NORMAL)

        for i, j in enumerate(self.settings_set_value_table):
            tprint(f"{i}, {j}", P_TYPE.DEBUG)

        # Set callbacks to focus in and out in order to update the selected element global var
        self.settings_set_value_table[self.get_element_index(Element.SETTING_CUTOFF)][0].bind(
            "<FocusIn>", lambda ev, el=Element.SETTING_CUTOFF: self.on_focus_in(ev, el))  # select thing
        self.settings_set_value_table[self.get_element_index(Element.SETTING_CUTOFF)][0].bind(
            "<FocusOut>", lambda ev, el=Element.SETTING_CUTOFF: self.on_focus_out(ev, el))

        self.settings_set_value_table[self.get_element_index(Element.SETTING_MAX_OUT_CURRENT)][0].bind(
            "<FocusIn>", lambda ev, el=Element.SETTING_MAX_OUT_CURRENT: self.on_focus_in(ev, el))  # select thing
        self.settings_set_value_table[self.get_element_index(Element.SETTING_MAX_OUT_CURRENT)][0].bind(
            "<FocusOut>", lambda ev, el=Element.SETTING_MAX_OUT_CURRENT: self.on_focus_out(ev, el))

        self.settings_set_value_table[self.get_element_index(Element.SETTING_FAN_OVERRIDE_STATUS)][0].bind(
            "<FocusIn>", lambda ev, el=Element.SETTING_FAN_OVERRIDE_STATUS: self.on_focus_in(ev, el))  # select thing
        self.settings_set_value_table[self.get_element_index(Element.SETTING_FAN_OVERRIDE_STATUS)][0].bind(
            "<FocusOut>", lambda ev, el=Element.SETTING_FAN_OVERRIDE_STATUS: self.on_focus_out(ev, el))

        self.settings_set_value_table[self.get_element_index(Element.SETTING_FAN_OVERRIDE_SPEED)][0].bind(
            "<FocusIn>", lambda ev, el=Element.SETTING_FAN_OVERRIDE_SPEED: self.on_focus_in(ev, el))  # select thing
        self.settings_set_value_table[self.get_element_index(Element.SETTING_FAN_OVERRIDE_SPEED)][0].bind(
            "<FocusOut>", lambda ev, el=Element.SETTING_FAN_OVERRIDE_SPEED: self.on_focus_out(ev, el))

        self.settings_refresh()

    def settings_refresh(self):
        self.settings_actual_value = [
            [self.shared_data.target_v],
            [self.shared_data.act_set_out_current],
            [1 if self.shared_data.bms_hv.fans_override_status == Toggle.ON else 0],
            [self.shared_data.bms_hv.fans_override_speed],
            [round(self.shared_data.brusa.act_NLG5_ACT_II.get('NLG5_S_MC_M_CP'), 2)]
        ]
        update_table(self.settings_actual_value, self.settings_actual_value_table)

        if self.selected_element != Element.SETTING_CUTOFF:
            self.settings_set_value[self.get_element_index(Element.SETTING_CUTOFF)][0] \
                = self.shared_data.target_v
        if self.selected_element != Element.SETTING_MAX_OUT_CURRENT:
            self.settings_set_value[self.get_element_index(Element.SETTING_MAX_OUT_CURRENT)][0] \
                = self.shared_data.act_set_out_current
        if self.selected_element != Element.SETTING_FAN_OVERRIDE_STATUS:
            self.settings_set_value[self.get_element_index(Element.SETTING_FAN_OVERRIDE_STATUS)][0] \
                = 1 if self.shared_data.bms_hv.fans_set_override_status == Toggle.ON else 0
        if self.selected_element != Element.SETTING_FAN_OVERRIDE_SPEED:
            self.settings_set_value[self.get_element_index(Element.SETTING_FAN_OVERRIDE_SPEED)][0] \
                = self.shared_data.bms_hv.fans_set_override_speed

        update_table(self.settings_set_value, self.settings_set_value_table, state=NORMAL)

        self.tab_settings.after(self.REFRESH_RATE, self.settings_refresh)

    # ERRORS WINDOW ----------------------------------------------------------------------------------------------------
    def setup_errors_window(self):
        self.tab_errors = ttk.Frame(self.root_center_tabs)
        self.errors_scroll = ScrollableFrame(self.tab_errors)
        self.errors_scroll.pack(side=BOTTOM)

        self.errors_text = tkinter.Text(self.errors_scroll.scrollable_frame, wrap="char")
        self.errors_text.pack(fill=X)

        for i in range(50):
            self.errors_text.insert(END, "asddd\n")

        self.errors_refresh()

    def errors_refresh(self):
        # Do refresh
        self.tab_errors.after(self.REFRESH_RATE, self.errors_refresh)

    def __init__(self,
                 com_queue: queue.Queue,
                 lock: threading.Lock,
                 shared_data: CanListener,
                 melody_queue: queue.Queue):
        self.com_queue = com_queue
        self.lock = lock
        self.shared_data = shared_data
        self.setup_root()
        self.melody_queue = melody_queue

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    t = Gui(None, None, None)
    t.run()
