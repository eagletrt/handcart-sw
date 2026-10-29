"""The System page: version, updates of the handcart repo, reboot and shut down.

The update itself is ./handcart.py update, run by handcart-update.service: it restarts the backend, so the
backend only starts it and does not wait. Reboot, shut down and starting the update need sudo; the rule
that allows exactly these commands is system/sudoers/handcart.
"""

import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path

from shared.config import ROOT, Update
from shared.models import SystemInfo

log = logging.getLogger(__name__)

FETCH_TIMEOUT = 15  # s: at the track there is often no network
UPDATE_SERVICE = Path("/etc/systemd/system/handcart-update.service")  # there only on the handcart
SUDO_SYSTEMCTL = ["sudo", "-n", "systemctl"]  # -n: fail instead of asking for a password
# never wait for a password prompt; messages in English, to tell a missing branch from no network
GIT_ENV = {**os.environ, "GIT_SSH_COMMAND": "ssh -o BatchMode=yes", "LC_ALL": "C"}


class System:
    def __init__(self, cfg: Update, repo: Path = ROOT) -> None:
        self._cfg = cfg
        self._repo = repo
        self._updates: list[str] = []
        self._checked_at: str | None = None
        self._check_problem: str | None = None

    def info(self) -> SystemInfo:
        return SystemInfo(
            version=self._git("log", "-1", "--format=%h %cd", "--date=short"),
            branch=self._cfg.branch,
            updates=self._updates,
            checked_at=self._checked_at,
            check_problem=self._check_problem,
            last_update=self._last_update(),
            on_handcart=UPDATE_SERVICE.exists(),
        )

    def check(self) -> None:
        """Fetch the branch and list the commits not installed yet. Blocks for a few seconds at most."""
        remote, branch = self._cfg.remote, self._cfg.branch
        self._checked_at = datetime.now().strftime("%H:%M")
        try:
            self._git("fetch", "--quiet", remote, branch, timeout=FETCH_TIMEOUT)
            new = self._git("log", "--format=%h %s", f"HEAD..{remote}/{branch}")
        except subprocess.TimeoutExpired:
            self._check_problem = f"Could not reach {remote}: no network?"
            return
        except subprocess.CalledProcessError as error:
            if "couldn't find remote ref" in error.stderr:
                self._check_problem = f"The branch {branch} is not on {remote}"
            else:
                self._check_problem = f"Could not reach {remote}: no network?"
            log.warning("update check failed: %s", error.stderr.strip())
            return
        self._check_problem = None
        self._updates = new.splitlines()
        if self._updates:
            log.info("%d updates on %s/%s", len(self._updates), remote, branch)

    def start_update(self) -> str | None:
        """Start ./handcart.py update in its own service. Returns why it could not, or None."""
        if not self._updates:
            return "Already up to date"
        return self._systemctl("start", "--no-block", "handcart-update.service")

    def reboot(self) -> str | None:
        return self._systemctl("reboot")

    def shut_down(self) -> str | None:
        return self._systemctl("poweroff")

    def _last_update(self) -> str | None:
        """What ./handcart.py update wrote in var/last-update.txt, if it ever ran."""
        path = self._repo / "var" / "last-update.txt"
        if not path.exists():
            return None
        return path.read_text().strip()

    def _git(self, *args: str, timeout: float | None = None) -> str:
        """Run git in the repo and return what it printed."""
        result = subprocess.run(
            ["git", *args],
            cwd=self._repo,
            env=GIT_ENV,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True,
        )
        return result.stdout.strip()

    def not_installed(self) -> str | None:
        """Why update, reboot and shut down cannot work on this machine, or None."""
        if not UPDATE_SERVICE.exists():
            return "Only on the handcart: run ./handcart.py install-services there"
        return None

    def _systemctl(self, *args: str) -> str | None:
        if problem := self.not_installed():
            return problem
        result = subprocess.run([*SUDO_SYSTEMCTL, *args], capture_output=True, text=True)
        if result.returncode != 0:
            return f"systemctl {' '.join(args)} failed: {result.stderr.strip()}"
        return None
