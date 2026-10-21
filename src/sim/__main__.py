"""Run the simulated BMS and charger on the CAN bus of the config: ./handcart.py sim [--speed N]."""

import argparse
import time

from backend.canbus import load_dbc
from backend.canbus.bus import open_bus, receive, send
from shared import config, scenario
from sim.bms import SimBms
from sim.charger import SimCharger

TICK = 0.01  # s
SCENARIO_PERIOD = 0.2  # s between two reads of the debug page's scenario


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--speed", type=float, default=30.0, help="how much faster than real life to charge")
    args = parser.parse_args()

    cfg = config.load()
    bms = SimBms(load_dbc(cfg.can.primary_dbc), cfg.accumulator, speed=args.speed)
    charger = SimCharger(load_dbc(cfg.can.charger_dbc))
    bms_bus = open_bus(cfg.can, cfg.can.bms_channel)
    charger_bus = bms_bus if cfg.can.shared_bus else open_bus(cfg.can, cfg.can.charger_channel)
    print(f"Simulating BMS and charger on {cfg.can.interface} ({cfg.can.bms_channel}), speed x{args.speed:g}")

    last = time.monotonic()
    next_scenario_read = 0.0
    test = scenario.Scenario()
    try:
        while True:
            now = time.monotonic()
            dt, last = now - last, now

            if now >= next_scenario_read:  # what the debug page asks (shared/scenario.py)
                next_scenario_read = now + SCENARIO_PERIOD
                test = scenario.read()
                bms.faults = {"overvoltage"} if test.bms_fault else set()
                bms.high_cell, bms.hot_cell = test.high_cell, test.hot_cell
                charger.forced_error = test.charger_error

            for frame in receive(bms_bus):
                if not bms.on_frame(frame, now):
                    charger.on_frame(frame)
            if charger_bus is not bms_bus:
                for frame in receive(charger_bus):
                    charger.on_frame(frame)

            current = charger.tick(dt, bms.ts_voltage)
            bms.tick(now, dt, current)

            for frame in bms.frames(now):
                if not test.bms_unplugged:
                    send(bms_bus, frame)
            for frame in charger.frames(now):
                if not test.charger_unplugged:
                    send(charger_bus, frame)
            time.sleep(TICK)
    except KeyboardInterrupt:
        pass
    finally:
        bms_bus.shutdown()
        if charger_bus is not bms_bus:
            charger_bus.shutdown()


if __name__ == "__main__":
    main()
