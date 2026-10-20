#!/usr/bin/env python3
"""Handcart launcher: ./handcart.py <command> [args].

Standard library only. Commands go through uv, which creates the environment
and installs the dependencies the first time.
"""

import getpass
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

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


def usage() -> None:
    print("Usage: ./handcart.py <command> [args]\n")
    for name, (description, _) in COMMANDS.items():
        print(f"  {name:<17} {description}")
    print(f"  {'install-services':<17} Set up the Pi to boot straight into the handcart UI")


def main() -> int:
    name, args = (sys.argv[1], sys.argv[2:]) if len(sys.argv) > 1 else ("help", [])
    if name == "install-services":
        return install_services()
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
