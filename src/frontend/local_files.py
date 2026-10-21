"""What the backend and ./handcart.py update leave in var/ for the display, besides the API.

They run on the same machine as the frontend, and these files are there even while the backend is down
or restarting, when the API cannot answer:
- var/backend-error.txt  why the backend stopped (backend/__main__.py); gone once it starts fine
- var/update-step.txt    the step the update is at (handcart.py); there only while it runs
- var/last-update.txt    how the last update ended (handcart.py)

On a computer running only the frontend they are simply not there: every function returns "".
"""

from pathlib import Path

from shared.config import BACKEND_ERROR_FILE, LAST_UPDATE_FILE, UPDATE_STEP_FILE


def backend_error() -> str:
    return _read(BACKEND_ERROR_FILE)


def update_step() -> str:
    return _read(UPDATE_STEP_FILE)


def last_update() -> str:
    """ "2026-10-21 18:30 Updated abc -> def", or why it failed."""
    return _read(LAST_UPDATE_FILE)


def _read(path: Path) -> str:
    try:
        return path.read_text().strip()
    except OSError:  # not there: nothing to say
        return ""
