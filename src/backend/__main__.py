"""Run the backend: the handcart loop and the API, in one process. ./handcart.py backend"""

import asyncio
import contextlib
import logging
import signal

import uvicorn

from backend.api import create_app
from backend.canbus.bus import open_bus
from backend.hal import Hal, Sound
from backend.hal.board import BoardHal
from backend.hal.fake import FakeHal
from backend.handcart import Handcart
from backend.system import System
from shared import config
from shared.config import Config, hardware_is_simulated
from shared.scenario import SCENARIO_FILE

TICK = 0.005  # s, faster than the fastest periodic frame (HYC_Ctrl, 10 ms)

log = logging.getLogger("backend")


def make_hal(cfg: Config) -> Hal:
    """The real board on the Pi, unless the config asks for simulated hardware; a fake one elsewhere."""
    if hardware_is_simulated(cfg):
        log.warning("Hardware is simulated: relays, controls and shutdown feedbacks are not real")
        return FakeHal(scenario_file=SCENARIO_FILE)
    from backend.hal import rpi  # needs RPi.GPIO and spidev, which exist only on the Pi

    return BoardHal(cfg, rpi.RpiGpio(cfg), rpi.RpiPwm(cfg.gpio.buzzer), rpi.RpiSpi(cfg))


async def run() -> None:
    cfg = config.load()
    bms_bus = open_bus(cfg.can, cfg.can.bms_channel)
    charger_bus = bms_bus if cfg.can.shared_bus else open_bus(cfg.can, cfg.can.charger_channel)
    hal = make_hal(cfg)
    handcart = Handcart(cfg, hal, bms_bus, charger_bus)
    hal.play(Sound.STARTUP)

    system = System(cfg.update)
    asyncio.get_running_loop().run_in_executor(None, system.check)  # look for updates at every start

    app = create_app(handcart, system)
    server = uvicorn.Server(uvicorn.Config(app, host=cfg.network.backend_host, port=cfg.network.backend_port))
    failed = False

    async def loop() -> None:
        """Tick for ever. If a tick fails the whole backend stops: an API still answering without the loop
        would look alive while nothing watches the charge. The finally below leaves the hardware safe, and
        systemd starts the backend again."""
        nonlocal failed
        try:
            while True:
                handcart.tick()
                await asyncio.sleep(TICK)
        except Exception:
            log.exception("The control loop failed: stopping the backend")
            failed = True
            server.should_exit = True

    ticking = asyncio.create_task(loop())
    try:
        await server.serve()
    finally:
        ticking.cancel()
        # leave the hardware safe: charger unpowered, shutdown open, TS discharge resistor in
        hal.set_relays(sd_relay_closed=False, charger_power=False, discharge=True)
        log.info("Stopped: charger unpowered, shutdown loop open, TS discharging")
        bms_bus.shutdown()
        if charger_bus is not bms_bus:
            charger_bus.shutdown()
    if failed:
        raise SystemExit(1)  # systemd sees a failure, not a clean stop


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    # systemd stops the service with SIGTERM: make it a Ctrl+C, so the finally above always runs
    # (by default SIGTERM ends the process on the spot, relays as they are)
    signal.signal(signal.SIGTERM, signal.default_int_handler)
    with contextlib.suppress(KeyboardInterrupt):  # the way out, not an error
        asyncio.run(run())
