"""The engine: applies the rules to the inputs of each step and keeps the state."""

import logging
from collections import deque
from collections.abc import Callable

from shared.config import Config
from shared.models import Command, Fault, State, TsacState

from .events import detect_events, detect_fault, status_message
from .model import Event, Inputs, Outputs, Transition, Trigger
from .rules import (
    ALLOWED_COMMANDS,
    GUARDS,
    OVERRIDE_EVENTS,
    TRANSITIONS,
    command_reason,
    outputs,
)

log = logging.getLogger(__name__)

HISTORY_LENGTH = 200


class ChargeFsm:
    def __init__(self, config: Config, now: float) -> None:
        self.state = State.CHECK
        self.message = "Waiting for the BMS and the charger"
        self.fault: Fault | None = None  # why the machine is in ERROR
        self.history: deque[Transition] = deque(maxlen=HISTORY_LENGTH)
        self._cfg = config
        self._entered_at = now
        self._refusal: str | None = None
        self._balancing_seen = False  # the BMS has reported BALANCING since balancing was asked
        self._listeners: list[Callable[[Transition], None]] = []

    def on_transition(self, listener: Callable[[Transition], None]) -> None:
        """Call `listener` after every transition. For logs and the UI: the hardware follows the Outputs."""
        self._listeners.append(listener)

    def step(self, inputs: Inputs) -> Outputs:
        """Advance by one step. Priority: fault, overriding events, operator command, other events."""
        state_before = self.state
        command = inputs.command
        self._refusal = None
        if command is not None and command not in ALLOWED_COMMANDS[self.state]:
            self._refusal = f"{command} is not possible in {self.state}"
            command = None

        if self.state is State.BALANCING and inputs.bms.state is TsacState.BALANCING:
            self._balancing_seen = True

        fault = None if self.state is State.ERROR else detect_fault(self._cfg, self.state, inputs)
        if fault:
            kind, reason = fault
            self._enter(State.ERROR, Event.FAULT, inputs.now, reason, kind)
        else:
            self._handle(inputs, command)

        if self._refusal and self.state is state_before:
            self.message = self._refusal  # the operator must see why the command did nothing
        return outputs(self._cfg, self.state, self._entered_at, inputs, self.message, self._refusal)

    def _handle(self, inputs: Inputs, command: Command | None) -> None:
        elapsed = inputs.now - self._entered_at
        events = detect_events(self._cfg, self.state, inputs, elapsed, self._balancing_seen)

        for event, reason in events:
            if event in OVERRIDE_EVENTS and self._fire(event, inputs.now, reason):
                return

        if command is not None:
            guard = GUARDS.get((self.state, command))
            if guard and (refusal := guard(self._cfg, inputs)):
                self._refusal = refusal
            else:
                self._fire(command, inputs.now, command_reason(command, inputs))
            return

        for event, reason in events:
            if self._fire(event, inputs.now, reason):
                return

        if (message := status_message(self.state, inputs, elapsed, self.message)) is not None:
            self.message = message

    def _fire(self, trigger: Trigger, now: float, reason: str) -> bool:
        """Take the transition for `trigger` from the current state, if there is one."""
        target = TRANSITIONS.get((self.state, trigger))
        if target is None:
            return False
        self._enter(target, trigger, now, reason)
        return True

    def _enter(
        self,
        target: State,
        trigger: Trigger,
        now: float,
        reason: str,
        fault: Fault | None = None,
    ) -> None:
        transition = Transition(now, self.state, trigger, target, reason, fault)
        self.state = target
        self.message = reason
        self.fault = fault
        self._entered_at = now
        if target is State.BALANCING:
            self._balancing_seen = False
        self.history.append(transition)
        log.info("%s", transition)
        for listener in self._listeners:
            try:
                listener(transition)
            except Exception:  # a broken listener must not stop the machine
                log.exception("Transition listener failed on %s", transition)
