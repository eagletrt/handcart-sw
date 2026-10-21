"""Opening a CAN bus with python-can, and moving Frames over it."""

import logging
import time

import can

from backend.canbus.frame import Frame
from shared.config import Can

log = logging.getLogger(__name__)

WARNING_PERIOD = 5.0  # s between two warnings about frames not sent
_last_warning = -WARNING_PERIOD  # so the first failure is always logged


def open_bus(config: Can, channel: str) -> can.BusABC:
    """A bus on the configured interface: socketcan on the Pi, udp_multicast anywhere else."""
    if config.interface == "udp_multicast":
        # every process on the machine joins the same multicast group, one per channel name
        return can.Bus(interface="udp_multicast", channel=_multicast_group(channel))
    return can.Bus(interface=config.interface, channel=channel)


def send(bus: can.BusABC, frame: Frame) -> None:
    """Send a frame; if the bus refuses it, log and go on.

    With the BMS or the charger unplugged no one acks the frames, the kernel queue fills up and every
    send fails. That is not a reason to stop the backend: the devices are just missing, and the state
    machine already sees that from the frames that stop arriving.
    """
    global _last_warning
    try:
        bus.send(can.Message(arbitration_id=frame.id, data=frame.data, is_extended_id=False))
    except can.CanOperationError as error:
        now = time.monotonic()
        if now - _last_warning > WARNING_PERIOD:  # one line every few seconds, not one per frame
            log.warning("CAN %s: frame %#x not sent: %s", bus.channel_info, frame.id, error)
            _last_warning = now


def receive(bus: can.BusABC) -> list[Frame]:
    """All the frames waiting on the bus, without blocking."""
    frames = []
    while (message := bus.recv(timeout=0)) is not None:
        frames.append(Frame(message.arbitration_id, bytes(message.data)))
    return frames


def _multicast_group(channel: str) -> str:
    """can0 -> 239.74.163.0, can1 -> 239.74.163.1: one group per channel, like separate buses."""
    number = "".join(c for c in channel if c.isdigit()) or "0"
    return f"239.74.163.{int(number) % 256}"
