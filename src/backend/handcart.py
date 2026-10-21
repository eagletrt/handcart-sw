"""The handcart: reads the devices, runs the state machine, drives the relays and sends the periodic frames.

tick() does one round of all of it. The backend calls it every few milliseconds.
"""

import logging
import time
from collections import deque
from collections.abc import Callable
from pathlib import Path

import can
from cantools.database.errors import DecodeError

from backend.canbus import load_dbc
from backend.canbus.bus import receive, send
from backend.canbus.periodic import Periodic
from backend.core.fsm import ChargeFsm, Inputs, Outputs, setpoint_problem
from backend.devices.bms import Bms
from backend.devices.charger import LittleSic
from backend.hal import Hal, Sound
from shared.config import Config
from shared.models import Command, InputEvent, Settings, State, Status

log = logging.getLogger(__name__)

CHARGER_FANS = (0, 100)  # % duty range the charger may use for its fans
BMS_REQUEST_REPEATS = 5  # times each TS or balancing request is sent, in case a frame is lost
SOUND_ON_ENTERING = {State.CHARGE_DONE: Sound.CHARGE_DONE, State.ERROR: Sound.ERROR}


class Handcart:
    def __init__(
        self,
        cfg: Config,
        hal: Hal,
        bms_bus: can.BusABC,
        charger_bus: can.BusABC,
        clock: Callable[[], float] = time.monotonic,
        settings_file: Path | None = None,
    ) -> None:
        self._cfg = cfg
        self._hal = hal
        self._bms_bus = bms_bus
        self._charger_bus = charger_bus
        self._clock = clock
        self._periodic = Periodic()
        self._ts_on_sent: bool | None = None  # None: nothing sent yet, so the first tick asks TS off
        self._balancing_sent = False

        timing = cfg.timing
        self.bms = Bms(load_dbc(cfg.can.primary_dbc), cfg.accumulator, timing.bms_presence_timeout, clock)
        self.charger = LittleSic(load_dbc(cfg.can.charger_dbc), timing.charger_presence_timeout, clock)
        self._fsm = ChargeFsm(cfg, now=clock())
        self.settings = Settings(
            target_voltage=cfg.charge.target_voltage_default,
            max_current=cfg.charge.current_default,
            balancing_threshold=cfg.accumulator.balancing_threshold,
        )
        self._settings_file = settings_file  # if given, the settings are kept there across restarts
        self._load_settings()
        self._command: Command | None = None  # for the tick that request() runs
        self._inputs: deque[tuple[int, InputEvent]] = deque(maxlen=64)  # (number, event), for the frontend
        self._input_count = 0

    # what the operator asks, through the API

    def request(self, command: Command) -> str | None:
        """Handle a command right away, with one extra tick. Returns why it was refused, or None."""
        self._command = command
        refusal = self.tick().refusal
        if refusal is None:
            self._hal.play(Sound.CONFIRM)  # a refusal is shown on the screen: no beep for it
        return refusal

    def maintenance_problem(self) -> str | None:
        """Why the handcart cannot be updated, rebooted or shut down now (TS on, or running), or None."""
        state = self._fsm.state
        if state not in (State.CHECK, State.IDLE):
            return f"Stop first: the handcart is in {state}"
        return None

    def change_settings(self, settings: Settings) -> str | None:
        """Use new setpoints. Returns why they were refused, or None."""
        problem = setpoint_problem(self._cfg.charge, settings.target_voltage, settings.max_current)
        pack = self._cfg.accumulator
        low, high = pack.balancing_threshold_min, pack.balancing_threshold_max
        if problem is None and not low <= settings.balancing_threshold <= high:
            problem = f"balancing threshold outside {low * 1000:g}-{high * 1000:g} mV"
        if problem is None:
            self.settings = settings
            if self._settings_file is not None:
                self._settings_file.parent.mkdir(exist_ok=True)
                self._settings_file.write_text(settings.model_dump_json(indent=2))
        return problem

    def _load_settings(self) -> None:
        """The settings saved last time, if still within the limits of the config; else the defaults."""
        if self._settings_file is None or not self._settings_file.exists():
            return
        try:
            saved = Settings.model_validate_json(self._settings_file.read_text())
        except ValueError as error:  # unreadable, or from an older version
            log.warning("saved settings not used: %s", error)
            return
        if problem := self.change_settings(saved):
            log.warning("saved settings not used: %s", problem)

    def inputs_since(self, last: int) -> tuple[int, list[InputEvent]]:
        """The control presses after number `last`, and the number of the newest one."""
        return self._input_count, [event for number, event in self._inputs if number > last]

    def status(self) -> Status:
        return Status(
            state=self._fsm.state,
            message=self._fsm.message,
            fault=self._fsm.fault,
            settings=self.settings,
            bms=self.bms.snapshot(),
            charger=self.charger.snapshot(),
            shutdown=self._hal.shutdown_loop(),
        )

    # one round

    def tick(self) -> Outputs:
        now = self._clock()
        self._hal.poll(now)
        self._receive()
        inputs = Inputs(
            now=now,
            bms=self.bms.snapshot(),
            charger=self.charger.snapshot(),
            shutdown=self._hal.shutdown_loop(),
            target_voltage=self.settings.target_voltage,
            max_current=self.settings.max_current,
            command=self._command,
        )
        self._command = None
        state_before = self._fsm.state
        out = self._fsm.step(inputs)
        self._hal.set_relays(out.sd_relay_closed, out.charger_power, out.discharge)
        self._play_sounds(state_before, out.state)
        self._collect_inputs()
        self._send(now, out)
        return out

    def _play_sounds(self, before: State, after: State) -> None:
        if after is not before and after in SOUND_ON_ENTERING:
            self._hal.play(SOUND_ON_ENTERING[after])

    def _collect_inputs(self) -> None:
        """Keep the control presses, numbered, until the frontend reads them."""
        for event in self._hal.input_events():
            self._input_count += 1
            self._inputs.append((self._input_count, event))
            if event in (InputEvent.TURN_CW, InputEvent.TURN_CCW):
                self._hal.play(Sound.TICK)  # heard without looking at the screen

    def _receive(self) -> None:
        frames = receive(self._bms_bus)
        if self._charger_bus is not self._bms_bus:
            frames += receive(self._charger_bus)
        for frame in frames:
            try:
                if not self.bms.on_frame(frame):
                    self.charger.on_frame(frame)
            except (DecodeError, ValueError, KeyError) as error:
                # a frame we cannot read is dropped: it must never stop the control loop
                log.warning("unreadable frame %#x (%s): %s", frame.id, error, frame.data.hex())

    def _send(self, now: float, out: Outputs) -> None:
        due, timing = self._periodic.due, self._cfg.timing
        # The BMS requests go out only when they change, a few times over: this is what the charge script
        # that worked on the TSAC did. Sending them all the time broke the precharge.
        if out.ts_on != self._ts_on_sent:
            for _ in range(BMS_REQUEST_REPEATS):
                send(self._bms_bus, self.bms.ts_command(out.ts_on))
            self._ts_on_sent = out.ts_on
        if out.balancing != self._balancing_sent:
            for _ in range(BMS_REQUEST_REPEATS):
                send(
                    self._bms_bus,
                    self.bms.balancing_command(out.balancing, self.settings.balancing_threshold),
                )
            self._balancing_sent = out.balancing
        elif out.balancing and due("balancing", timing.balancing_period, now):
            # the BMS stops balancing if it gets no request for 3 s
            send(self._bms_bus, self.bms.balancing_command(True, self.settings.balancing_threshold))
        if due("charger control", timing.charger_ctrl_period, now):
            send(self._charger_bus, self.charger.control(out.charger))
        if due("charger alive", timing.charger_alive_period, now):
            send(self._charger_bus, self.charger.alive(*CHARGER_FANS))
        if due("charger target", timing.charger_target_period, now):
            target = self.charger.target(self.settings.target_voltage, self.settings.max_current)
            send(self._charger_bus, target)
