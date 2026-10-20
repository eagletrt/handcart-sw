"""Simulated LittleSIC charger: follows HYC_Ctrl and HYC_Target and reports like the real one."""

from cantools.database.can import Database

from backend.canbus import Frame, decode, encode
from backend.canbus.periodic import Periodic
from backend.devices.charger import RAW_MESSAGES, STATE_CODES, ChargerCommand
from shared.models import ChargerState

CODE_OF_STATE = {state: code for code, state in STATE_CODES.items()}
CURRENT_RAMP = 3.0  # A/s
CONSTANT_VOLTAGE_GAIN = 2.0  # A per volt below the target, once close to it
GRID_VOLTAGE = 230.0  # V per phase


class SimCharger:
    def __init__(self, db: Database) -> None:
        self._db = db
        self._periodic = Periodic()
        self.state = ChargerState.STANDBY
        self.current = 0.0
        self.output_voltage = 0.0
        self._command = ChargerCommand.STOP
        self._target_voltage = 0.0
        self._target_current = 0.0

    # what the handcart sends

    def on_frame(self, frame: Frame) -> bool:
        try:
            name = self._db.get_message_by_frame_id(frame.id).name
        except KeyError:
            return False
        if name == "HYC_Ctrl":
            self._command = ChargerCommand(int(decode(self._db, frame)["ctrlCmd"]))
        elif name == "HYC_Target":
            signals = decode(self._db, frame)
            self._target_voltage, self._target_current = signals["uTarget"], signals["iTarget"]
        elif name != "HYC_Alive":
            return False
        return True

    # the charger over time

    def tick(self, dt: float, pack_voltage: float) -> float:
        """Advance by dt with the battery at pack_voltage, and return the current it pushes into it."""
        self.output_voltage = pack_voltage
        if self._command is ChargerCommand.CHARGE and pack_voltage > 60:
            # constant current, then constant voltage when close to the target
            room = (self._target_voltage - pack_voltage) * CONSTANT_VOLTAGE_GAIN
            wanted = max(0.0, min(self._target_current, room))
            self.state = ChargerState.RUNNING_VC if room < self._target_current else ChargerState.RUNNING
        else:
            wanted = 0.0
            self.state = ChargerState.STANDBY
        step = CURRENT_RAMP * dt
        self.current += max(-step, min(step, wanted - self.current))
        return self.current

    # what the charger sends

    def frames(self, now: float) -> list[Frame]:
        due = self._periodic.due
        frames = []
        if due("status", 0.1, now):
            frames.append(encode(self._db, "HYC_Status", status=CODE_OF_STATE[self.state]))
            frames.append(encode(self._db, "HYC_Actual", uActual=self.output_voltage, iActual=self.current))
        if due("grid", 0.5, now):
            frames.append(
                encode(self._db, "HYC_Grid_Voltage", u1=GRID_VOLTAGE, u2=GRID_VOLTAGE, u3=GRID_VOLTAGE, f=50)
            )
        if due("health", 1.0, now):
            temperature = 30 + 2 * self.current
            for name in ("HYC_Temperature", "HYC_Maintenance2"):
                signals = {s.name: temperature for s in self._db.get_message_by_name(name).signals}
                frames.append(encode(self._db, name, **signals))
            for name in RAW_MESSAGES:  # no errors or warnings: all flags 0
                message = self._db.get_message_by_name(name)
                frames.append(Frame(message.frame_id, bytes(message.length)))
        return frames
