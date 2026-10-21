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
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
UV_RUN = ["uv", "run"]
SERVICES = ["handcart-backend.service", "handcart-frontend.service"]  # restarted by update
LAST_UPDATE = ROOT / "var" / "last-update.txt"  # what the last update did, shown on the System page

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


def install_services() -> int:
    """Set up the Pi to boot straight into the handcart UI.

    Copies the services and the CAN network (filling in user, paths and port), installs the sudo rule
    of the System page and the boot splash, enables the services that start at boot and boots to
    console, so the display service owns the screen.
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
        print(f"{src.relative_to(ROOT)} -> {dest}/{src.name}")
        if rc := run(
            ["sudo", "tee", f"{dest}/{src.name}"], input=fill(src, values), stdout=subprocess.DEVNULL
        ):
            return rc
    if rc := install_sudoers(fill(ROOT / "system/sudoers/handcart", values)):
        return rc
    # handcart-update has no [Install]: it runs only when the System page asks
    units = [src.name for src, _ in files if src.suffix == ".service" and "[Install]" in src.read_text()]
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


def fill(src: Path, values: dict[str, str]) -> str:
    """The file with its {{PLACEHOLDERS}} filled in."""
    text = src.read_text()
    for key, value in values.items():
        text = text.replace(key, value)
    return text


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

    print(f"Updating {old} -> {new}:")
    run(["git", "log", "--oneline", f"HEAD..{upstream}"])
    problem = install(new)
    if problem is None:
        problem = tests()
    if problem is None:
        problem = restart(cfg["health_timeout"])
    if problem is None:
        return finish(0, f"Updated {old} -> {new}")

    print(f"{problem}: going back to {old}")
    back = install(old)
    if back is None:
        back = restart(cfg["health_timeout"])
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


def restart(timeout: float) -> str | None:
    """Restart backend and frontend, then wait for the backend to answer. Returns what failed, or None."""
    if not (Path("/etc/systemd/system") / SERVICES[0]).exists():
        print("Not the handcart: restart the backend and the frontend by hand")
        return None
    if run(["sudo", "-n", "systemctl", "restart", *SERVICES]):
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
