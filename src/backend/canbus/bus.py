"""Opening a CAN bus with python-can, and moving Frames over it."""

import can

from backend.canbus.frame import Frame
from shared.config import Can


def open_bus(config: Can, channel: str) -> can.BusABC:
    """A bus on the configured interface: socketcan on the Pi, udp_multicast anywhere else."""
    if config.interface == "udp_multicast":
        # every process on the machine joins the same multicast group, one per channel name
        return can.Bus(interface="udp_multicast", channel=_multicast_group(channel))
    return can.Bus(interface=config.interface, channel=channel)


def send(bus: can.BusABC, frame: Frame) -> None:
    bus.send(can.Message(arbitration_id=frame.id, data=frame.data, is_extended_id=False))


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
