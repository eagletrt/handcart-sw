#!/usr/bin/env python3
"""Handcart launcher: ./handcart.py <command> [args].

Standard library only. Commands go through uv, which creates the environment
and installs the dependencies the first time. `status` and `command` talk to the
running backend, so they work over SSH too.
"""

import getpass
import json
import os
import shutil
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
UV_RUN = ["uv", "run"]

# name: (description, commands run in order; extra args go to the last one)
COMMANDS: dict[str, tuple[str, list[list[str]]]] = {
    "setup": (
        "Fetch the submodules and install the dependencies",
        [["git", "submodule", "update", "--init", "--recursive"], ["uv", "sync"]],
    ),
    "backend": ("Run the backend", [[*UV_RUN, "python", "-m", "backend"]]),
    "frontend": ("Run the frontend", [[*UV_RUN, "python", "-m", "frontend"]]),
    "sim": ("Run the simulated BMS and charger", [[*UV_RUN, "python", "-m", "sim"]]),
    "test": ("Run the tests", [[*UV_RUN, "pytest"]]),
    "lint": ("Lint the code", [[*UV_RUN, "ruff", "check", "."]]),
    "format": ("Format the code", [[*UV_RUN, "ruff", "format", "."]]),
    "typecheck": ("Type-check the code", [[*UV_RUN, "mypy"]]),
    "vcan-up": (
        "Create vcan0 for the simulator",
        [
            ["sudo", "modprobe", "vcan"],
            ["sudo", "ip", "link", "add", "dev", "vcan0", "type", "vcan"],
            ["sudo", "ip", "link", "set", "up", "vcan0"],
        ],
    ),
    "update-libcan": (
        "Move libcan to its latest commit and run the tests",
        [["git", "submodule", "update", "--remote", "libs/libcan"], [*UV_RUN, "pytest"]],
    ),
}


def run(cmd: list[str], **kwargs) -> int:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    return subprocess.run(cmd, cwd=ROOT, env=env, **kwargs).returncode


def install_services() -> int:
    """Set up the Pi to boot straight into the handcart UI.

    Copies the services and the CAN network (filling in user, paths and port), installs the boot
    splash, enables everything and boots to console, so the display service owns the screen.
    """
    uv = shutil.which("uv")
    config = tomllib.loads((ROOT / "config.toml").read_text())
    values = {
        "{{USER}}": getpass.getuser(),
        "{{ROOT}}": str(ROOT),
        "{{UV_DIR}}": str(Path(uv).parent) if uv else "/usr/local/bin",
        "{{FRONTEND_PORT}}": str(config["network"]["frontend_port"]),
    }
    files = [(f, "/etc/systemd/system") for f in (ROOT / "system/services").glob("*.service")]
    files += [(f, "/etc/systemd/network") for f in (ROOT / "system/can").glob("*.network")]
    for src, dest in files:
        text = src.read_text()
        for key, value in values.items():
            text = text.replace(key, value)
        print(f"{src.relative_to(ROOT)} -> {dest}/{src.name}")
        if rc := run(["sudo", "tee", f"{dest}/{src.name}"], input=text, text=True, stdout=subprocess.DEVNULL):
            return rc
    units = [src.name for src, _ in files if src.suffix == ".service"]
    splash = [str(f) for f in sorted((ROOT / "system/splash").iterdir())] + [str(ROOT / "assets/eagle.png")]
    for cmd in (
        ["systemctl", "daemon-reload"],
        ["systemctl", "enable", "systemd-networkd", *units],
        ["systemctl", "set-default", "multi-user.target"],
        ["install", "-D", "-m", "644", "-t", "/usr/share/plymouth/themes/handcart", *splash],
        ["plymouth-set-default-theme", "-R", "handcart"],
    ):
        if rc := run(["sudo", *cmd]):
            return rc
    print(
        "Done. Add system/raspberry/boot-config.txt and cmdline.txt to /boot/firmware by hand, then reboot."
    )
    return 0


def api(method: str, path: str, body: dict | None = None) -> Any:
    """Call the backend running on this machine."""
    port = tomllib.loads((ROOT / "config.toml").read_text())["network"]["backend_port"]
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=3) as response:
        return json.loads(response.read() or b"null")


def status(args: list[str]) -> int:
    """Print what the backend sees, in a few lines."""
    s = api("GET", "/api/status")
    bms, charger = s["bms"], s["charger"]
    print(f"state     {s['state']}: {s['message']}")
    print(f"settings  {s['settings']['target_voltage']:g} V, {s['settings']['max_current']:g} A")
    if bms["connected"]:
        cells = [v for v in bms["cells"] if v is not None]
        cell_range = f"{min(cells):.3f}-{max(cells):.3f} V" if cells else "-"
        print(f"BMS       {bms['state']}, pack {bms['pack_voltage']} V, TS {bms['ts_voltage']} V")
        print(f"          cells {cell_range}, max {bms['temp_max']} °C")
        print(f"          errors: {', '.join(bms['errors']) or 'none'}")
    else:
        print("BMS       not responding")
    if charger["connected"]:
        print(f"charger   {charger['state']}, {charger['voltage']} V, {charger['current']} A")
        print(f"          errors: {', '.join(charger['errors']) or 'none'}")
    else:
        print("charger   not responding")
    print("shutdown  " + ", ".join(f"{point} {volts} V" for point, volts in s["shutdown"]))
    return 0


def command(args: list[str]) -> int:
    """Send a command to the state machine, then show what it did."""
    if len(args) != 1:
        print("Usage: ./handcart.py command <PRECHARGE|START_CHARGE|PAUSE_CHARGE|BALANCE|STOP|RESET>")
        return 1
    api("POST", "/api/command", {"command": args[0].upper()})
    time.sleep(0.2)  # the command is handled at the next tick
    s = api("GET", "/api/status")
    print(f"{s['state']}: {s['message']}")
    return 0


# name: (description, function), for the commands that are not just a list of programs to run
FUNCTIONS = {
    "status": ("Show what the backend sees", status),
    "command": ("Send a command, e.g. ./handcart.py command STOP", command),
    "install-services": (
        "Set up the Pi to boot straight into the handcart UI",
        lambda args: install_services(),
    ),
}


def usage() -> None:
    print("Usage: ./handcart.py <command> [args]\n")
    for name, (description, _) in {**COMMANDS, **FUNCTIONS}.items():
        print(f"  {name:<17} {description}")


def main() -> int:
    name, args = (sys.argv[1], sys.argv[2:]) if len(sys.argv) > 1 else ("help", [])
    if name in FUNCTIONS:
        try:
            return FUNCTIONS[name][1](args)
        except urllib.error.HTTPError as error:
            detail = json.loads(error.read()).get("detail")
            if isinstance(detail, list):  # a request the API could not read: keep only the reason
                detail = "; ".join(item["msg"] for item in detail)
            print(f"Refused: {detail}", file=sys.stderr)
            return 1
        except urllib.error.URLError:
            print(
                "The backend is not running on this machine (start it with ./handcart.py backend)",
                file=sys.stderr,
            )
            return 1
    if name not in COMMANDS:
        usage()
        return 0 if name in ("help", "-h", "--help") else 1
    if not shutil.which("uv"):
        print("uv is not installed: curl -LsSf https://astral.sh/uv/install.sh | sh", file=sys.stderr)
        return 1
    *first, last = COMMANDS[name][1]
    for cmd in [*first, [*last, *args]]:
        if rc := run(cmd):
            return rc
    return 0


if __name__ == "__main__":
    sys.exit(main())
