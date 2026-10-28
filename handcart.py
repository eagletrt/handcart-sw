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
import signal
import struct
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
UV_RUN = ["uv", "run"]
SERVICES = ["handcart-backend.service", "handcart-frontend.service"]  # restarted by update
LAST_UPDATE = ROOT / "var" / "last-update.txt"  # what the last update did, shown on the System page
# what the running update is doing, for the display (it shows "Updating" while the file is there);
# the same paths are in shared/config.py, which this launcher does not import
UPDATE_STEP = ROOT / "var" / "update-step.txt"
# the update installs the changed services and system files itself, but not the boot files: those are
# edited by hand (a broken cmdline.txt stops the Pi from booting), so it says so
BOOT_CHANGED = "boot files changed: copy system/raspberry/ into /boot/firmware by hand, then reboot"

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


def run(cmd: list[str], input: str | None = None, **kwargs) -> int:
    """Run cmd until it ends, feeding it input if given.

    Ctrl+C reaches cmd too, straight from the terminal: wait while it shuts down instead of killing it
    (the backend needs that moment to leave the relays safe).
    """
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    stdin = subprocess.PIPE if input is not None else None
    process = subprocess.Popen(cmd, cwd=ROOT, env=env, stdin=stdin, text=True, **kwargs)
    if process.stdin:
        process.stdin.write(input or "")
        process.stdin.close()
    while True:
        try:
            return process.wait()
        except KeyboardInterrupt:
            pass


def install_services(splash: bool = True) -> int:
    """Set up the Pi to boot straight into the handcart UI.

    Copies the services, the CAN network and the Wi-Fi permission (filling in user, paths and port),
    installs the sudo rule of the System page and the boot splash, enables the services that start at
    boot and boots to console, so the display service owns the screen. splash=False skips the splash:
    rebuilding it takes minutes, and the update does it only when the splash changed.
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
    files += [(f, "/etc/polkit-1/rules.d") for f in (ROOT / "system/polkit").glob("*.rules")]
    for src, dest in files:
        print(f"{src.relative_to(ROOT)} -> {dest}/{src.name}")
        if rc := run(
            ["sudo", "tee", f"{dest}/{src.name}"], input=fill(src, values), stdout=subprocess.DEVNULL
        ):
            return rc
    if rc := install_sudoers(fill(ROOT / "system/sudoers/handcart", values)):
        return rc
    if rc := install_hidden_cursor():
        return rc
    # handcart-update has no [Install]: it runs only when the System page asks
    units = [src.name for src, _ in files if src.suffix == ".service" and "[Install]" in src.read_text()]
    commands = [
        ["systemctl", "daemon-reload"],
        ["systemctl", "enable", "systemd-networkd", *units],
        ["systemctl", "set-default", "multi-user.target"],
    ]
    if splash:
        theme = [str(f) for f in sorted((ROOT / "system/splash").iterdir())]
        theme.append(str(ROOT / "assets/eagle.png"))
        commands.append(["install", "-D", "-m", "644", "-t", "/usr/share/plymouth/themes/handcart", *theme])
        commands.append(["plymouth-set-default-theme", "-R", "handcart"])
    for cmd in commands:
        if rc := run(["sudo", *cmd]):
            return rc
    print(
        "Done. Add system/raspberry/boot-config.txt and cmdline.txt to /boot/firmware by hand, then reboot."
    )
    return 0


def fill(src: Path, values: dict[str, str]) -> str:
    """The file with its {{PLACEHOLDERS}} filled in."""
    text = src.read_text()
    for key, value in values.items():
        text = text.replace(key, value)
    return text


# The display is a touch screen: cage and Chromium still draw a mouse pointer, so the display service
# looks for cursors only in this folder (XCURSOR_PATH), where the "default" theme, the one cage loads, has
# every cursor as a single transparent pixel.
HIDDEN_CURSOR_PATH = "/usr/share/handcart-cursors"
CURSOR_NAMES = [
    "default", "left_ptr", "arrow", "top_left_arrow", "pointer", "hand1", "hand2", "text", "xterm",
    "wait", "watch", "progress", "left_ptr_watch", "crosshair", "help", "not-allowed", "grab", "grabbing",
    "move", "all-scroll", "col-resize", "row-resize", "context-menu",
]  # fmt: skip


def transparent_xcursor(size: int = 24) -> bytes:
    """An Xcursor file holding one 1x1 fully transparent image (format: man 3 Xcursor)."""
    image_type = 0xFFFD0002
    header = struct.pack("<4sIII", b"Xcur", 16, 0x10000, 1)  # magic, header size, version, entries
    toc = struct.pack("<III", image_type, size, 16 + 12)  # the image starts right after this entry
    image = struct.pack("<IIIIIIIII", 36, image_type, size, 1, 1, 1, 0, 0, 0)  # 1x1, hotspot 0,0
    return header + toc + image + struct.pack("<I", 0)  # one ARGB pixel, alpha 0


def install_hidden_cursor() -> int:
    """Install the transparent cursor theme for the display."""
    dest = f"{HIDDEN_CURSOR_PATH}/default"
    print(f"transparent cursor theme -> {dest}")
    draft = ROOT / "var" / "transparent.xcursor"
    draft.parent.mkdir(exist_ok=True)
    draft.write_bytes(transparent_xcursor())
    for name in CURSOR_NAMES:  # install -D also creates the theme's folders
        if rc := run(["sudo", "install", "-D", "-m", "644", str(draft), f"{dest}/cursors/{name}"]):
            return rc
    theme = "[Icon Theme]\nName=default\nComment=No visible pointer, for the touch display\n"
    return run(["sudo", "tee", f"{dest}/index.theme"], input=theme, stdout=subprocess.DEVNULL)


def install_sudoers(text: str) -> int:
    """Install the sudo rule only once visudo says it is valid: a broken sudoers file would lock sudo out."""
    print("system/sudoers/handcart -> /etc/sudoers.d/handcart")
    draft = "/etc/sudoers.d/handcart.new"  # sudo skips files with a dot in the name while this is checked
    if rc := run(["sudo", "tee", draft], input=text, stdout=subprocess.DEVNULL):
        return rc
    for cmd in (
        ["sudo", "visudo", "--check", "--quiet", "--file", draft],
        ["sudo", "chmod", "440", draft],
        ["sudo", "mv", draft, "/etc/sudoers.d/handcart"],
    ):
        if rc := run(cmd):
            run(["sudo", "rm", "-f", draft])
            return rc
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
    api("POST", "/api/command", {"command": args[0].upper()})  # a refusal raises, and main prints it
    s = api("GET", "/api/status")
    print(f"{s['state']}: {s['message']}")
    return 0


def update(args: list[str]) -> int:
    """Run the update, telling the display each step; the step file goes away however it ends."""
    # systemd stops it with SIGTERM (a reboot, a shutdown): by default that ends Python on the spot, the
    # finally does not run and the display stays on "Updating" for good. Not a Ctrl+C: run() waits on
    # those, and the update would go on to the next step while the Pi switches off.
    signal.signal(signal.SIGTERM, update_stopped)
    try:
        return update_steps()
    finally:
        UPDATE_STEP.unlink(missing_ok=True)


def update_stopped(signum: int, frame: Any) -> None:
    raise SystemExit(finish(1, "Update stopped before the end (switched off?): check the version by SSH"))


def step(text: str) -> None:
    """Say what the update is doing now: on the terminal, and on the display through UPDATE_STEP."""
    print(text)
    UPDATE_STEP.parent.mkdir(exist_ok=True)
    UPDATE_STEP.write_text(text)


def update_steps() -> int:
    """Bring the handcart to the latest commit of its branch; go back if the new version does not work.

    Steps: fetch, move to the new commit, submodules, uv sync, tests, restart, wait for the backend.
    If a step after the move fails, the same steps bring back the commit it started from.
    Never while the TS is on or something runs: the restart would cut it (the System page checks the same).
    """
    cfg = tomllib.loads((ROOT / "config.toml").read_text())["update"]
    remote, branch = cfg["remote"], cfg["branch"]
    upstream = f"{remote}/{branch}"

    state = backend_state()
    if state not in (None, "CHECK", "IDLE"):
        return finish(1, f"Not updated: the handcart is in {state}, stop it first")
    if output(["git", "status", "--porcelain", "--untracked-files=no"]):
        return finish(1, "Not updated: this copy has local changes (commit or discard them first)")
    step("Looking for the new version")
    if run(["git", "fetch", "--quiet", remote, branch]):
        return finish(1, f"Not updated: could not fetch {upstream}")
    old, new = (
        output(["git", "rev-parse", "--short", "HEAD"]),
        output(["git", "rev-parse", "--short", upstream]),
    )
    if old == new:
        print(f"Up to date with {upstream} ({old})")
        return 0
    if run(["git", "merge-base", "--is-ancestor", "HEAD", upstream]):
        return finish(1, f"Not updated: this copy has commits that are not on {upstream}")
    changed = output(["git", "diff", "--name-only", old, new]).splitlines()
    boot_changed = any(f.startswith("system/raspberry/") for f in changed)  # by hand: never installed here
    services_changed = any(f.startswith("system/") and not f.startswith("system/raspberry/") for f in changed)
    splash_changed = any(f.startswith("system/splash/") or f == "assets/eagle.png" for f in changed)

    print(f"Updating {old} -> {new}:")
    run(["git", "log", "--oneline", f"HEAD..{upstream}"])
    step(f"Installing {new}")
    problem = install(new)
    if problem is None:
        step("Checking the new version")
        problem = tests()
    if problem is None and services_changed:
        step("Installing the services" + (" and the splash (a few minutes)" if splash_changed else ""))
        if install_services(splash=splash_changed):
            problem = "the services did not install"
    if problem is None:
        step("Restarting")
        problem = restart(cfg["health_timeout"], display=services_changed)
    if problem is None:
        if boot_changed:
            return finish(0, f"Updated {old} -> {new} · {BOOT_CHANGED}")
        return finish(0, f"Updated {old} -> {new}")

    print(f"{problem}: going back to {old}")
    step(f"Something went wrong: going back to {old}")
    back = install(old)
    if back is None and services_changed:  # the services of the old version, too
        step("Installing the services")
        if install_services(splash=splash_changed):
            back = "the services did not install"
    if back is None:
        step("Restarting")
        back = restart(cfg["health_timeout"], display=services_changed)
    if back is not None:
        return finish(
            1, f"Update to {new} failed ({problem}) and going back failed too ({back}): fix it by SSH"
        )
    return finish(1, f"Update to {new} failed ({problem}), back to {old}")


def backend_state() -> str | None:
    """The state of the backend running on this machine, or None if it is not running."""
    try:
        return api("GET", "/api/status")["state"]
    except OSError:  # not listening: nothing is running, nothing to cut
        return None


def install(commit: str) -> str | None:
    """Move to commit with its submodules and dependencies. Returns what failed, or None."""
    if run(["git", "reset", "--quiet", "--hard", commit]):
        return f"git could not move to {commit}"
    if run(["git", "submodule", "update", "--init", "--recursive"]):
        return "the submodules did not update"
    if run(["uv", "sync"]):
        return "uv sync failed"
    return None


def tests() -> str | None:
    if run([*UV_RUN, "pytest", "--quiet"]):
        return "the tests failed"
    return None


def restart(timeout: float, display: bool = False) -> str | None:
    """Restart backend and frontend (and the display, if asked), then wait for the backend to answer.

    Returns what failed, or None.
    """
    if not (Path("/etc/systemd/system") / SERVICES[0]).exists():
        print("Not the handcart: restart the backend and the frontend by hand")
        return None
    services = [*SERVICES, "handcart-display.service"] if display else SERVICES
    if run(["sudo", "-n", "systemctl", "restart", *services]):
        return "the services did not restart"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            api("GET", "/api/status")
            return None
        except OSError:  # not listening yet, or restarting
            time.sleep(1)
    return f"the backend did not answer within {timeout:g} s"


def finish(code: int, message: str) -> int:
    """Print what the update did and keep it for the System page."""
    print(message, file=sys.stderr if code else sys.stdout)
    LAST_UPDATE.parent.mkdir(exist_ok=True)
    LAST_UPDATE.write_text(f"{datetime.now():%Y-%m-%d %H:%M} {message}\n")
    return code


def output(cmd: list[str]) -> str:
    """What cmd prints, for the short git queries of update."""
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


# name: (description, function), for the commands that are not just a list of programs to run
FUNCTIONS = {
    "status": ("Show what the backend sees", status),
    "command": ("Send a command, e.g. ./handcart.py command STOP", command),
    "update": ("Update to the latest commit of the branch in config.toml, then restart", update),
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
