"""Run the backend: the handcart loop and the API, in one process. ./handcart.py backend"""

import asyncio
import logging

import uvicorn

from backend.api import create_app
from backend.canbus.bus import open_bus
from backend.hal import Sound
from backend.hal.fake import FakeHal
from backend.handcart import Handcart
from shared import config

TICK = 0.005  # s, faster than the fastest periodic frame (HYC_Ctrl, 10 ms)

log = logging.getLogger("backend")


async def run() -> None:
    cfg = config.load()
    bms_bus = open_bus(cfg.can, cfg.can.bms_channel)
    charger_bus = bms_bus if cfg.can.shared_bus else open_bus(cfg.can, cfg.can.charger_channel)
    # TODO: the real HAL on the Pi; until then the relays and the shutdown loop are simulated
    hal = FakeHal()
    handcart = Handcart(cfg, hal, bms_bus, charger_bus)
    hal.play(Sound.STARTUP)
    log.warning("Hardware is simulated: relays and shutdown feedbacks are not real")

    async def loop() -> None:
        while True:
            handcart.tick()
            await asyncio.sleep(TICK)

    app = create_app(handcart)
    server = uvicorn.Server(uvicorn.Config(app, host=cfg.network.backend_host, port=cfg.network.backend_port))
    ticking = asyncio.create_task(loop())
    try:
        await server.serve()
    finally:
        ticking.cancel()
        bms_bus.shutdown()
        if charger_bus is not bms_bus:
            charger_bus.shutdown()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    asyncio.run(run())
