"""Charge state machine of the handcart: from what the devices report and the operator asks, decides what
to do.

No CAN or GPIO in here: ChargeFsm.step() takes the Inputs and returns the Outputs, so every rule can be
tested off the Pi. Each step goes through:

    Inputs -> events.py -> rules.TRANSITIONS / rules.GUARDS -> new state -> rules.MODES -> Outputs

    model.py    data types: Inputs, Outputs, Event, Transition
    checks.py   pure checks on the inputs (faults, setpoints, charge complete)
    events.py   what is happening this step
    rules.py    where each event or command leads, when a command is refused, what each state outputs
    machine.py  ChargeFsm: applies the rules and records every transition in `history`
"""

from .machine import ChargeFsm
from .model import Event, Inputs, Outputs, Transition

__all__ = ["ChargeFsm", "Event", "Inputs", "Outputs", "Transition"]
