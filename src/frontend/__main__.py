"""Run the frontend: the touch UI, served to the kiosk browser on the display. ./handcart.py frontend"""

import asyncio
import contextlib
import logging
from pathlib import Path

from nicegui import app, ui

from frontend import debug
from frontend.backend import Backend
from frontend.page import Page
from shared import config
from shared.config import ROOT, hardware_is_simulated

STATIC = Path(__file__).parent / "static"


def main() -> None:
    cfg = config.load()
    backend = Backend(f"{cfg.network.backend_host}:{cfg.network.backend_port}")
    app.on_startup(lambda: asyncio.create_task(backend.run()))
    app.on_startup(lambda: asyncio.create_task(backend.follow_system()))
    app.add_static_files("/static", STATIC)
    app.add_static_files("/assets", ROOT / "assets")

    @ui.page("/")
    def index() -> None:
        ui.add_head_html(
            '<link rel="stylesheet" href="/static/handcart.css"><script src="/static/handcart.js"></script>'
        )
        ui.colors(primary="#F3FF14", negative="#FF453A", dark="#141411")  # brand yellow and red
        # the boot splash's eagle, in the first HTML: on screen while the page loads (handcart.js removes it)
        ui.add_body_html('<div id="boot"><img src="/assets/eagle.png" alt=""></div>')
        Page(cfg, backend)

    if hardware_is_simulated(cfg):

        @ui.page("/debug")
        def debug_page() -> None:
            debug.build()

    ui.run(
        host=cfg.network.frontend_host,
        port=cfg.network.frontend_port,
        title="Handcart",
        favicon=ROOT / "assets" / "eagle.png",
        dark=True,
        reload=False,
        show=False,
    )


if __name__ in {"__main__", "__mp_main__"}:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    with contextlib.suppress(KeyboardInterrupt):  # Ctrl+C: nothing to clean up, the UI holds no state
        main()
