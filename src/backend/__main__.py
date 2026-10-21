"""Run the backend: the handcart loop and the API, in one process. ./handcart.py backend"""

import asyncio
import logging
import os
import signal
import socket
import time

import uvicorn

from backend.api import create_app
from backend.canbus.bus import open_bus
from backend.hal import Hal, Sound
from backend.hal.board import BoardHal
from backend.hal.fake import FakeHal
from backend.handcart import Handcart
from backend.system import System
from shared import config
from shared.config import BACKEND_ERROR_FILE, SETTINGS_FILE, Config, hardware_is_simulated
from shared.scenario import SCENARIO_FILE

TICK = 0.005  # s, faster than the fastest periodic frame (HYC_Ctrl, 10 ms)
WATCHDOG_PING = 1.0  # s between two "still ticking" to systemd (WatchdogSec in handcart-backend.service)

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
    check_port_free(cfg.network.backend_host, cfg.network.backend_port)
    bms_bus = open_bus(cfg.can, cfg.can.bms_channel)
    charger_bus = bms_bus if cfg.can.shared_bus else open_bus(cfg.can, cfg.can.charger_channel)
    hal = make_hal(cfg)
    handcart = Handcart(cfg, hal, bms_bus, charger_bus, settings_file=SETTINGS_FILE)
    hal.play(Sound.STARTUP)

    system = System(cfg.update)
    asyncio.get_running_loop().run_in_executor(None, system.check)  # look for updates at every start

    app = create_app(handcart, system)
    server = uvicorn.Server(uvicorn.Config(app, host=cfg.network.backend_host, port=cfg.network.backend_port))
    failed = False

    async def loop() -> None:
        """Tick for ever. If a tick fails the whole backend stops: an API still answering without the loop
        would look alive while nothing watches the charge. The finally below leaves the hardware safe, and
        systemd starts the backend again. If the ticks stop without failing, systemd's watchdog does it."""
        nonlocal failed
        notify_systemd("READY=1")
        BACKEND_ERROR_FILE.unlink(missing_ok=True)  # started fine: no reason to show any more
        last_ping = 0.0
        try:
            while True:
                handcart.tick()
                if time.monotonic() - last_ping >= WATCHDOG_PING:
                    notify_systemd("WATCHDOG=1")
                    last_ping = time.monotonic()
                await asyncio.sleep(TICK)
        except Exception as error:
            log.exception("The control loop failed: stopping the backend")
            report_failure(error)
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


def check_port_free(host: str, port: int) -> None:
    """Fail with a clear reason if another program listens on the API port: uvicorn would just exit.

    SO_REUSEADDR, as uvicorn: right after a restart the old connections must not count as "in use".
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((host, port))
        except OSError as error:
            raise OSError(f"port {port} is already in use: is another backend running?") from error


def notify_systemd(state: str) -> None:
    """Tell systemd how the service is doing (sd_notify): READY=1 once started, WATCHDOG=1 while ticking.

    Does nothing when systemd did not start the backend (no NOTIFY_SOCKET), e.g. on a computer.
    """
    address = os.environ.get("NOTIFY_SOCKET")
    if not address:
        return
    if address.startswith("@"):
        address = "\0" + address[1:]  # an abstract socket
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
            sock.sendto(state.encode(), address)
    except OSError as error:
        log.warning("cannot notify systemd (%s): %s", state, error)


def report_failure(error: BaseException) -> None:
    """Leave the reason on disk: the frontend shows it while systemd starts the backend again."""
    BACKEND_ERROR_FILE.parent.mkdir(exist_ok=True)
    BACKEND_ERROR_FILE.write_text(f"{type(error).__name__}: {error}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    # systemd stops the service with SIGTERM: make it a Ctrl+C, so the finally above always runs
    # (by default SIGTERM ends the process on the spot, relays as they are)
    signal.signal(signal.SIGTERM, signal.default_int_handler)
    try:
        asyncio.run(run())
    except KeyboardInterrupt:  # the way out, not an error
        pass
    except Exception as error:  # it could not start: no config, no CAN interface, no GPIO...
        log.exception("The backend could not start")
        report_failure(error)
        raise
