"""The rules of the physical controls (frontend/controls.py), without any UI."""

from frontend.controls import IDLE_TIME, Adjust, Context, Controls, Press, SwitchScreen, Target
from shared.models import InputEvent

PRESS, CW, CCW = InputEvent.PRESS, InputEvent.TURN_CW, InputEvent.TURN_CCW
LEFT, RIGHT, UP, DOWN = InputEvent.LEFT, InputEvent.RIGHT, InputEvent.UP, InputEvent.DOWN

BUTTONS = [Target("info"), Target("main", priority=1), Target("alt"), Target("charge"), Target("cells")]
CHARGE = Context(targets=BUTTONS)
RUNNING = Context(targets=[*BUTTONS, Target("stop", priority=2)])
VOLTS = Context(
    targets=[Target("volts", opens_map=True), Target("temps", opens_map=True)],
    map_name="volts",
    map_size=(2, 4),
    map_start=5,
)
TEMPS = Context(
    targets=[Target("volts", opens_map=True), Target("temps", opens_map=True)],
    map_name="temps",
    map_size=(2, 8),
    map_start=0,
)
SETTINGS = Context(
    targets=[
        Target("target_voltage", priority=1, adjusts="target_voltage", presses="save"),
        Target("max_current", adjusts="max_current", presses="save"),
        Target("cancel"),
        Target("save"),
    ],
    window_open=True,
)


def gestures(controls, context, *events, start=0.0):
    """Several gestures one second apart; the effect of the last one."""
    effect = None
    for i, event in enumerate(events):
        effect = controls.handle(event, context, now=start + i)
    return effect


# screens


def test_the_first_click_only_shows_the_frame_on_the_main_action():
    controls = Controls()
    assert controls.handle(PRESS, CHARGE, now=0) is None  # nothing pressed
    assert controls.framed == "main"
    assert controls.handle(PRESS, CHARGE, now=1) == Press("main")


def test_stop_comes_first_while_something_runs():
    controls = Controls()
    gestures(controls, RUNNING, PRESS)
    assert controls.framed == "stop"


def test_up_and_down_move_the_frame_and_wrap_around():
    controls = Controls()
    gestures(controls, CHARGE, PRESS, DOWN)
    assert controls.framed == "alt"
    gestures(controls, CHARGE, UP, UP, UP, start=2)
    assert controls.framed == "cells"  # before the first, the last


def test_left_and_right_change_screen_at_once():
    controls = Controls()
    assert controls.handle(RIGHT, CHARGE, now=0) == SwitchScreen(1)
    assert controls.handle(LEFT, CHARGE, now=1) == SwitchScreen(-1)


def test_after_a_pause_the_next_click_only_shows_the_frame_again():
    controls = Controls()
    gestures(controls, CHARGE, PRESS)
    assert controls.handle(PRESS, CHARGE, now=IDLE_TIME + 1) is None
    assert controls.framed == "main"


# Charge


def test_turning_on_charge_moves_the_frame_like_the_arrows():
    controls = Controls()
    gestures(controls, CHARGE, CW)  # the first gesture shows the frame on the main action
    assert controls.handle(CW, CHARGE, now=1) is None
    assert controls.framed == "alt"
    controls.handle(CCW, CHARGE, now=2)
    assert controls.framed == "main"


# Cells: the map


def test_turning_on_cells_moves_the_frame_over_volts_and_temps():
    controls = Controls()
    controls.handle(CW, VOLTS, now=0)  # shows the frame
    controls.handle(CW, VOLTS, now=1)
    assert controls.framed == "temps"


def test_pressing_temps_with_the_controls_then_puts_the_cursor_on_the_map():
    controls = Controls()
    gestures(controls, VOLTS, CW, CW)  # on temps
    assert controls.handle(PRESS, VOLTS, now=2) == Press("temps", opens_map=True)


def test_a_click_puts_the_cursor_on_the_map_at_its_start():
    controls = Controls()
    gestures(controls, VOLTS, PRESS)
    assert controls.cursor == 5  # row 1, column 1


def test_the_arrows_move_the_cursor_across_the_grid_and_stop_at_the_edges():
    controls = Controls()
    gestures(controls, VOLTS, PRESS, RIGHT)
    assert controls.cursor == 6
    gestures(controls, VOLTS, RIGHT, RIGHT, start=2)
    assert controls.cursor == 7  # the end of the row
    gestures(controls, VOLTS, UP, UP, start=4)
    assert controls.cursor == 3  # the first row, same column
    gestures(controls, VOLTS, LEFT, LEFT, LEFT, LEFT, start=6)
    assert controls.cursor == 0


def test_turning_moves_the_cursor_cell_after_cell_across_the_rows():
    controls = Controls()
    controls.touch_map(3, VOLTS)
    controls.handle(CW, VOLTS, now=0)
    assert controls.cursor == 4  # the first of the next row


def test_a_touch_always_moves_the_cursor_to_the_touched_cell():
    controls = Controls()
    controls.touch_map(2, VOLTS)
    controls.touch_map(6, VOLTS)
    assert controls.cursor == 6
    controls.handle(LEFT, VOLTS, now=0)  # and it can be corrected at once
    assert controls.cursor == 5


def test_a_click_takes_the_cursor_away_and_the_arrows_change_screen_again():
    controls = Controls()
    gestures(controls, VOLTS, PRESS, PRESS)
    assert controls.cursor is None
    assert controls.handle(RIGHT, VOLTS, now=2) == SwitchScreen(1)


def test_the_cursor_stays_after_a_pause_and_a_touch_elsewhere():
    controls = Controls()
    controls.touch_map(6, VOLTS)
    controls.clear()  # a touch outside the map
    controls.follow(VOLTS, now=IDLE_TIME * 3)
    assert controls.cursor == 6


def test_the_cursor_goes_when_volts_switch_to_temps_or_the_screen_changes():
    controls = Controls()
    controls.touch_map(6, VOLTS)
    controls.follow(TEMPS, now=0)
    assert controls.cursor is None
    controls.touch_map(6, VOLTS)
    controls.follow(CHARGE, now=1)
    assert controls.cursor is None


# windows


def test_turning_changes_the_framed_setting_one_step_at_a_time():
    controls = Controls()
    gestures(controls, SETTINGS, PRESS)  # the frame starts on the target voltage
    assert controls.handle(CW, SETTINGS, now=1) == Adjust("target_voltage", 1)
    assert controls.handle(CW, SETTINGS, now=1.01) == Adjust("target_voltage", 1)  # fast: still one step


def test_in_a_window_the_arrows_and_turns_move_the_frame_one_button_at_a_time():
    controls = Controls()
    gestures(controls, SETTINGS, PRESS, DOWN)
    assert controls.framed == "max_current"
    controls.handle(RIGHT, SETTINGS, now=2)
    assert controls.framed == "cancel"
    controls.handle(CW, SETTINGS, now=3)
    controls.handle(CCW, SETTINGS, now=3.01)  # fast, but still one button
    assert controls.framed == "cancel"


def test_a_click_on_a_setting_saves():
    controls = Controls()
    gestures(controls, SETTINGS, PRESS, DOWN)
    assert controls.handle(PRESS, SETTINGS, now=2) == Press("save")


def test_when_the_framed_button_goes_the_frame_goes():
    controls = Controls()
    gestures(controls, CHARGE, PRESS)  # on main
    controls.follow(SETTINGS, now=1)  # a window opened over it
    assert controls.framed is None


def test_nothing_reachable_nothing_framed():
    controls = Controls()
    assert controls.handle(PRESS, Context(), now=0) is None
    assert controls.framed is None
