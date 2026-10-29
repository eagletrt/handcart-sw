"""The handcart: reads the devices, runs the state machine, drives the relays and sends the periodic frames.

tick() does one round of all of it. The backend calls it every few milliseconds.
What happens is kept in the record (backend/recorder.py): commands, transitions, devices, errors, samples.
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
from backend.core import ChargeFsm, Event, Inputs, Outputs, Transition
from backend.core.checks import BMS_HV_STATES, setpoint_problem
from backend.devices.bms import Bms
from backend.devices.charger import LittleSic
from backend.hal import Hal
from backend.recorder import Recorder
from backend.sounds.announcer import Announcer
from backend.sounds.player import Player
from shared.config import Config
from shared.models import (
    Command,
    InputEvent,
    Sample,
    Settings,
    Severity,
    Sound,
    State,
    Status,
    TsacState,
)

log = logging.getLogger(__name__)

CHARGER_FANS = (0, 100)  # % duty range the charger may use for its fans
BMS_REQUEST_REPEATS = 5  # times each TS or balancing request is sent, in case a frame is lost
SAMPLE_PERIOD = 1.0  # s between two samples of the readings, for the graphs
UNSAMPLED_STATES = {State.CHECK, State.IDLE}  # nothing happening: no samples


class Handcart:
    def __init__(
        self,
        cfg: Config,
        hal: Hal,
        bms_bus: can.BusABC,
        charger_bus: can.BusABC,
        clock: Callable[[], float] = time.monotonic,
        settings_file: Path | None = None,
        recorder: Recorder | None = None,
    ) -> None:
        self._cfg = cfg
        self._recorder = recorder  # None: nothing is recorded (tests)
        self._command_id: int | None = (
            None  # the recorded command request() is handling: what its tick causes
        )
        # what the last tick saw, to record only the changes
        self._connected = (False, False)  # BMS, charger
        self._bms_errors: frozenset[str] = frozenset()
        self._charger_errors: frozenset[str] = frozenset()
        self._hal = hal
        self._player = Player()
        self._announcer = Announcer(cfg.accumulator)
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
        self._sounds: deque[tuple[int, Sound]] = deque(maxlen=64)  # (number, sound), for the frontend
        self._sound_count = 0

    # what the operator asks, through the API

    def request(self, command: Command) -> str | None:
        """Handle a command right away, with one extra tick. Returns why it was refused, or None."""
        self._command = command
        sounds_before = self._sound_count
        command_id = self.record("command", Severity.INFO, "api", str(command), {"command": command}, "api")
        self._command_id = command_id
        refusal = self.tick().refusal
        self._command_id = None
        if refusal is not None:
            self.record("refusal", Severity.NOTICE, "fsm", refusal, {"command": command}, cause_id=command_id)
        # A command is always heard: refused (the screen says why), or the sound of the state it led to
        # (PRECHARGE, say), or else the confirm beep
        if refusal is not None:
            self.play(Sound.REFUSED)
        elif self._sound_count == sounds_before:
            self.play(Sound.CONFIRM)
        return refusal

    def hush(self) -> None:
        """The operator touched the screen or changed screen: the tune of a job done stops."""
        self._player.hush()

    def play(self, sound: Sound) -> None:
        """Start a sound on the buzzer; the ticks play it."""
        if self._player.play(sound, self._clock()):
            self._sound_count += 1
            self._sounds.append((self._sound_count, sound))

    def maintenance_problem(self) -> str | None:
        """Why the handcart cannot be updated, rebooted or shut down now (TS on, or running), or None."""
        state = self._fsm.state
        if state not in (State.CHECK, State.IDLE):
            return f"Stop first: the handcart is in {state}"
        return None

    def record(
        self,
        kind: str,
        severity: Severity,
        source: str,
        summary: str,
        data: dict | None = None,
        actor: str | None = None,
        cause_id: int | None = None,
    ) -> int | None:
        """Add an event to the record (see Recorder.record); its id, or None without a record."""
        if self._recorder is None:
            return None
        return self._recorder.record(kind, severity, source, summary, data, actor, cause_id)

    def change_settings(self, settings: Settings) -> str | None:
        """Use new setpoints, from the operator. Returns why they were refused, or None."""
        before = self.settings
        problem = self._use_settings(settings)
        data = {"before": before.model_dump(), "asked": settings.model_dump()}
        if problem is None:
            self.record("settings", Severity.INFO, "api", "Settings changed", data, "api")
        else:
            self.record("refusal", Severity.NOTICE, "api", f"Settings refused: {problem}", data, "api")
        return problem

    def _use_settings(self, settings: Settings) -> str | None:
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
        if problem := self._use_settings(saved):
            log.warning("saved settings not used: %s", problem)

    def inputs_since(self, last: int) -> tuple[int, list[InputEvent]]:
        """The control presses after number `last`, and the number of the newest one."""
        return self._input_count, [event for number, event in self._inputs if number > last]

    def sounds_since(self, last: int) -> tuple[int, list[Sound]]:
        """The sounds the buzzer started after number `last`, and the number of the newest one."""
        return self._sound_count, [sound for number, sound in self._sounds if number > last]

    def status(self) -> Status:
        history = self._fsm.history
        return Status(
            state=self._fsm.state,
            message=self._fsm.message,
            fault=self._fsm.fault,
            balancing_done=bool(history) and history[-1].trigger is Event.BALANCING_DONE,
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
        change_id = self._record_changes(inputs)
        last_transition = self._fsm.history[-1] if self._fsm.history else None
        out = self._fsm.step(inputs)
        self._hal.set_relays(out.sd_relay_closed, out.charger_power, out.discharge)
        transition = self._fsm.history[-1] if self._fsm.history else None
        new_transition = transition if transition is not last_transition else None
        if new_transition is not None:
            # caused by the command of this tick, else by what changed in it (a device lost, an error)
            cause_id = self._command_id
            if cause_id is None:
                cause_id = change_id
            self._record_transition(new_transition, inputs, cause_id)
        if (
            self._recorder is not None
            and out.state not in UNSAMPLED_STATES
            and self._periodic.due("sample", SAMPLE_PERIOD, now)
        ):
            self._recorder.sample(sample(self._recorder.now(), out.state, inputs))
        for sound in self._announcer.sounds(now, inputs, out.state, new_transition, out.message):
            self.play(sound)
        self._collect_inputs()
        self._hal.set_buzzer(self._player.frequency(now))
        self._send(now, out)
        return out

    def _record_changes(self, inputs: Inputs) -> int | None:
        """Record the devices coming and going, and the errors they report. The id of the last, or None."""
        last_id = None
        names = ("BMS", "Charger")
        connected = (inputs.bms.connected, inputs.charger.connected)
        for name, was, now in zip(names, self._connected, connected, strict=True):
            if now and not was:
                last_id = self.record("device", Severity.NOTICE, name.lower(), f"{name} connected")
            elif was and not now:
                last_id = self.record("device", Severity.NOTICE, name.lower(), f"{name} lost")
        self._connected = connected

        seen = (self._bms_errors, self._charger_errors)
        errors = (inputs.bms.errors, inputs.charger.errors)
        for name, before, after in zip(names, seen, errors, strict=True):
            if after == before:
                continue
            data = {"errors": sorted(after), "new": sorted(after - before), "gone": sorted(before - after)}
            summary = f"{name} errors cleared"
            if after:
                summary = f"{name} errors: " + ", ".join(sorted(after))
            last_id = self.record("errors", Severity.NOTICE, name.lower(), summary, data)
        self._bms_errors, self._charger_errors = errors
        return last_id

    def _record_transition(self, transition: Transition, inputs: Inputs, cause_id: int | None) -> None:
        severity = Severity.NOTICE
        if transition.target is State.ERROR:
            severity = Severity.CRITICAL
        data = {
            "from": transition.source,
            "to": transition.target,
            "trigger": str(transition.trigger),
            "reason": transition.reason,
            "fault": transition.fault,
            "readings": readings(inputs),  # what the handcart saw then: to find out why later
        }
        summary = f"{transition.source} → {transition.target}: {transition.reason}"
        self.record("transition", severity, "fsm", summary, data, cause_id=cause_id)

    def _collect_inputs(self) -> None:
        """Keep the control presses, numbered, until the frontend reads them."""
        for event in self._hal.input_events():
            self._input_count += 1
            self._inputs.append((self._input_count, event))
            self.hush()  # a control used: the operator is there
            if event in (InputEvent.TURN_CW, InputEvent.TURN_CCW):
                self.play(Sound.TICK)  # heard without looking at the screen

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
        elif out.balancing and due("balancing", timing.bms_repeat_period, now):
            # the BMS stops balancing if it gets no request for 3 s
            send(self._bms_bus, self.bms.balancing_command(True, self.settings.balancing_threshold))
        elif (
            not out.balancing
            and self.bms.state is TsacState.BALANCING
            and due("balancing off again", timing.bms_repeat_period, now)
        ):
            # stopped here but still balancing there: the stop frames were lost, send it again
            send(self._bms_bus, self.bms.balancing_command(False, self.settings.balancing_threshold))
        if (
            not out.ts_on
            and self.bms.state in BMS_HV_STATES
            and due("ts off again", timing.bms_repeat_period, now)
        ):
            # TS off asked but the AIRs are still closed: the TS off frames were lost, send it again
            send(self._bms_bus, self.bms.ts_command(False))
        if due("charger control", timing.charger_ctrl_period, now):
            send(self._charger_bus, self.charger.control(out.charger))
        if due("charger alive", timing.charger_alive_period, now):
            send(self._charger_bus, self.charger.alive(*CHARGER_FANS))
        if due("charger target", timing.charger_target_period, now):
            target = self.charger.target(self.settings.target_voltage, self.settings.max_current)
            send(self._charger_bus, target)


def readings(inputs: Inputs) -> dict:
    """The readings worth keeping with a transition: the devices and the shutdown loop, not every cell."""
    bms, charger = inputs.bms, inputs.charger
    return {
        "bms": {
            "connected": bms.connected,
            "state": bms.state,
            "ts_voltage": bms.ts_voltage,
            "pack_voltage": bms.pack_voltage,
            "current": bms.current,
            "cell_min": bms.cell_min,
            "cell_max": bms.cell_max,
            "temp_max": bms.temp_max,
            "errors": sorted(bms.errors),
        },
        "charger": {
            "connected": charger.connected,
            "state": charger.state,
            "voltage": charger.voltage,
            "current": charger.current,
            "errors": sorted(charger.errors),
            "warnings": sorted(charger.warnings),
        },
        "shutdown": dict(inputs.shutdown),
        "target_voltage": inputs.target_voltage,
        "max_current": inputs.max_current,
    }


def sample(at: float, state: State, inputs: Inputs) -> Sample:
    """The readings for the graphs, at `at` (s since 1970)."""
    return Sample(
        time=at,
        state=state,
        pack_voltage=inputs.bms.pack_voltage,
        current=inputs.bms.current,
        cell_min=inputs.bms.cell_min,
        cell_max=inputs.bms.cell_max,
        temp_max=inputs.bms.temp_max,
        charger_voltage=inputs.charger.voltage,
        charger_current=inputs.charger.current,
    )
